from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Vertical


class DisplayLabels(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zones: dict[str, str]
    observations: dict[str, str]


class PromptTemplates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zone_detection: str
    observation_extraction: str
    report_generation: str


class ReportTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sections: list[str]
    labels: dict[str, str]


class ConsentPolicy(BaseModel):
    """The attestation wording a capture client must show, and its version.

    Versioning exists for evidence: a visit records which wording was agreed
    to, so the exact text can still be resolved long after it changes.
    """

    model_config = ConfigDict(extra="forbid")

    version: str = Field(min_length=1)
    text: str = Field(min_length=1)
    counsel_review_status: Literal["pending", "reviewed"]


class VerticalPack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    slug: Literal["real_estate"]
    display_name: str
    zone_taxonomy: list[str]
    observation_schema: list[str]
    prompt_version: str
    report_template_id: str
    display_labels: DisplayLabels
    # Phrases an agent may speak to name a room on camera. Photos are placed by
    # matching these near the shutter, so the wording is vertical config rather
    # than anything the matcher knows on its own.
    zone_speech_aliases: dict[str, list[str]] = Field(default_factory=dict)
    prompt_templates: PromptTemplates
    report_template: ReportTemplate
    consent: ConsentPolicy

    @model_validator(mode="after")
    def validate_pack_completeness(self) -> "VerticalPack":
        if set(self.display_labels.zones) != set(self.zone_taxonomy):
            raise ValueError("zone labels must exactly match the zone taxonomy")
        if not set(self.zone_speech_aliases) <= set(self.zone_taxonomy):
            raise ValueError("zone speech aliases must reference known zones")
        if set(self.display_labels.observations) != set(self.observation_schema):
            raise ValueError(
                "observation labels must exactly match the observation schema"
            )
        for name, template in self.prompt_templates.model_dump().items():
            if not template.endswith(".j2"):
                raise ValueError(f"{name} must reference a Jinja2 template")
        if not set(self.report_template.sections) <= set(self.report_template.labels):
            raise ValueError("every report section must have a configured label")
        # The scope limit is unconditional, so a pack without it would ship
        # reports that read as inspection findings with nothing saying they
        # are not.
        for required in ("scope_disclosure", "recording_disclosure"):
            if not self.report_template.labels.get(required, "").strip():
                raise ValueError(f"{required} must be configured")
        return self


class VerticalConfigService:
    def __init__(self, config_path: Path | None = None) -> None:
        self._root_path = Path(__file__).parent
        self._config_path = config_path or Path(__file__).with_name("real_estate.yaml")
        self._packs = {"real_estate": self._load_pack(self._config_path)}

    def _load_pack(self, path: Path) -> VerticalPack:
        with path.open(encoding="utf-8") as config_file:
            raw_config = yaml.safe_load(config_file)
        pack = VerticalPack.model_validate(raw_config)
        for name, relative_path in pack.prompt_templates.model_dump().items():
            prompt_path = self._root_path / relative_path
            if not prompt_path.is_file():
                raise ValueError(f"prompt template does not exist: {name}")
            if "output_language" not in prompt_path.read_text(encoding="utf-8"):
                raise ValueError(f"{name} must use output_language")
        return pack

    @property
    def prompt_root(self) -> Path:
        return self._root_path

    def get(self, slug: str = "real_estate") -> VerticalPack:
        try:
            return self._packs[slug]
        except KeyError as exc:
            raise LookupError(f"Unknown vertical pack: {slug}") from exc

    async def seed(self, session: AsyncSession) -> None:
        for pack in self._packs.values():
            values = {
                "slug": pack.slug,
                "version": pack.version,
                "display_name": pack.display_name,
                "zone_taxonomy": pack.zone_taxonomy,
                "observation_schema": pack.observation_schema,
                "zone_labels": pack.display_labels.zones,
                "observation_labels": pack.display_labels.observations,
                "prompt_templates": pack.prompt_templates.model_dump(),
                "prompt_version": pack.prompt_version,
                "report_template_id": pack.report_template_id,
                "report_labels": pack.report_template.labels,
            }
            statement = insert(Vertical).values(**values)
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[Vertical.slug],
                    set_={**values, "updated_at": func.now()},
                )
            )


@lru_cache
def get_vertical_config_service() -> VerticalConfigService:
    return VerticalConfigService()


async def seed_verticals(
    session: AsyncSession, service: VerticalConfigService | None = None
) -> None:
    await (service or get_vertical_config_service()).seed(session)
