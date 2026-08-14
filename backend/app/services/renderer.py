import asyncio
import base64
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from app.models import RawMedia, Subject, WorkspaceBranding
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


#: Photos are embedded as data URIs because the rendered HTML is stored and
#: replayed for the life of a share link — a presigned URL would rot in it.
#: Caps keep that stored document to a sane size.
PHOTO_MAX_EDGE_PX = 720
PHOTO_JPEG_QUALITY = 78
PHOTOS_PER_ZONE = 2
PHOTOS_PER_REPORT = 8


@dataclass(frozen=True)
class SubjectRenderData:
    """Identifies which property the report is about, and when it was toured.

    A report that names neither is materially less useful to a buyer holding
    several of them, so the template leads with this rather than the brokerage.
    """

    display_name: str | None
    location: str | None
    toured_on: str | None


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
        *,
        consent_ack: bool = False,
        subject: Subject | None = None,
        toured_on: datetime | None = None,
        timezone: str | None = None,
        photos: Sequence[RawMedia] | None = None,
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
        zone_photos = await self._zone_photos(photos)
        for room in report_data["room_by_room"]:
            zone_type = room.get("zone_type")
            room["zone_label"] = (
                pack.display_labels.zones.get(zone_type, zone_type)
                if zone_type
                else pack.display_labels.zones["other"]
            )
            room["photos"] = zone_photos.get(str(room.get("zone_id")), [])
        template = self._environment.get_template(
            f"report_templates/{pack.report_template_id}.html"
        )
        return template.render(
            report=report_data,
            branding=branding_data,
            subject=self._subject_data(subject, toured_on, timezone),
            labels=pack.report_template.labels,
            consent_ack=consent_ack,
        )

    @classmethod
    def _subject_data(
        cls,
        subject: Subject | None,
        toured_on: datetime | None,
        timezone: str | None,
    ) -> SubjectRenderData | None:
        if subject is None and toured_on is None:
            return None
        return SubjectRenderData(
            display_name=subject.display_name if subject else None,
            location=subject.location if subject else None,
            toured_on=cls._local_date(toured_on, timezone),
        )

    @staticmethod
    def _local_date(moment: datetime | None, timezone: str | None) -> str | None:
        """Render the calendar date as it was where the tour happened.

        An evening showing west of Greenwich falls on the next UTC day, so a
        UTC-formatted date is simply wrong on the artifact. Visits captured
        before the zone was recorded fall back to UTC.
        """

        if moment is None:
            return None
        zone = UTC
        if timezone:
            try:
                zone = ZoneInfo(timezone)
            except (ZoneInfoNotFoundError, ValueError):
                # A zone the platform cannot resolve must not break delivery.
                zone = UTC
        local = moment.astimezone(zone)
        return f"{local.day} {local.strftime('%B %Y')}"

    async def _zone_photos(
        self, photos: Sequence[RawMedia] | None
    ) -> dict[str, list[str]]:
        """Group placed photos by zone, downscaled and inlined."""

        if not photos:
            return {}
        grouped: dict[str, list[str]] = {}
        embedded = 0
        for photo in photos:
            if photo.zone_id is None or embedded >= PHOTOS_PER_REPORT:
                continue
            zone_key = str(photo.zone_id)
            if len(grouped.get(zone_key, ())) >= PHOTOS_PER_ZONE:
                continue
            data_uri = await self._photo_data_uri(photo)
            if data_uri is None:
                continue
            grouped.setdefault(zone_key, []).append(data_uri)
            embedded += 1
        return grouped

    async def _photo_data_uri(self, photo: RawMedia) -> str | None:
        stored = await self._storage.get_object_bytes(photo.object_key)
        if stored is None or not stored.data:
            return None
        try:
            encoded = await asyncio.to_thread(self._downscale_jpeg, stored.data)
        except Exception:
            # An unreadable or corrupt capture must not fail the whole report.
            return None
        return f"data:image/jpeg;base64,{base64.b64encode(encoded).decode('ascii')}"

    @staticmethod
    def _downscale_jpeg(data: bytes) -> bytes:
        from PIL import Image, ImageOps

        with Image.open(BytesIO(data)) as image:
            # Phone captures carry orientation in EXIF; without this the photo
            # can appear sideways in the report.
            upright = ImageOps.exif_transpose(image) or image
            upright.thumbnail((PHOTO_MAX_EDGE_PX, PHOTO_MAX_EDGE_PX))
            buffer = BytesIO()
            upright.convert("RGB").save(
                buffer, format="JPEG", quality=PHOTO_JPEG_QUALITY, optimize=True
            )
        return buffer.getvalue()

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
        return (
            value
            if isinstance(value, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", value)
            else "#1F6F5B"
        )
