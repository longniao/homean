import asyncio
import base64
import re
from dataclasses import dataclass

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from app.models import WorkspaceBranding
from app.pipeline.schemas import RealEstateReportSchema
from app.storage import StorageProvider
from app.verticals import VerticalConfigService


@dataclass(frozen=True)
class BrandingRenderData:
    display_name: str | None
    phone: str | None
    email: str | None
    license_no: str | None
    accent_color: str
    logo_data_uri: str | None


class ReportRenderer:
    def __init__(
        self, storage: StorageProvider, verticals: VerticalConfigService
    ) -> None:
        self._storage = storage
        self._verticals = verticals
        self._environment = Environment(
            loader=FileSystemLoader(verticals.prompt_root),
            undefined=StrictUndefined,
            autoescape=select_autoescape(["html", "xml"], default_for_string=True),
        )

    async def render_html(
        self,
        content: RealEstateReportSchema | dict[str, object],
        branding: WorkspaceBranding | None,
    ) -> str:
        report = RealEstateReportSchema.model_validate(content)
        pack = self._verticals.get()
        logo_data_uri = await self._logo_data_uri(branding)
        branding_data = BrandingRenderData(
            display_name=branding.display_name if branding else None,
            phone=branding.phone if branding else None,
            email=branding.email if branding else None,
            license_no=branding.license_no if branding else None,
            accent_color=self._accent_color(branding),
            logo_data_uri=logo_data_uri,
        )
        report_data = report.model_dump(mode="json")
        for room in report_data["room_by_room"]:
            zone_type = room.get("zone_type")
            room["zone_label"] = (
                pack.display_labels.zones.get(zone_type, zone_type)
                if zone_type
                else pack.display_labels.zones["other"]
            )
        template = self._environment.get_template(
            f"report_templates/{pack.report_template_id}.html"
        )
        return template.render(
            report=report_data,
            branding=branding_data,
            labels=pack.report_template.labels,
        )

    async def render_pdf(self, html: str) -> bytes:
        return await asyncio.to_thread(self._render_pdf_sync, html)

    @staticmethod
    def _render_pdf_sync(html: str) -> bytes:
        # Keep the native WeasyPrint stack out of API processes that only render HTML.
        from weasyprint import HTML

        return HTML(string=html).write_pdf()

    async def _logo_data_uri(self, branding: WorkspaceBranding | None) -> str | None:
        if branding is None or not branding.logo_key:
            return None
        stored = await self._storage.get_object_bytes(branding.logo_key)
        if stored is None or not stored.data:
            return None
        content_type = stored.content_type or branding.logo_content_type or "image/png"
        encoded = base64.b64encode(stored.data).decode("ascii")
        return f"data:{content_type};base64,{encoded}"

    @staticmethod
    def _accent_color(branding: WorkspaceBranding | None) -> str:
        value = branding.accent_color if branding else "#1F6F5B"
        return value if re.fullmatch(r"#[0-9A-Fa-f]{6}", value) else "#1F6F5B"
