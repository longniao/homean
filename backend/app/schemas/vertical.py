from pydantic import BaseModel


class VerticalDisplayLabelsResponse(BaseModel):
    zones: dict[str, str]
    observations: dict[str, str]


class VerticalConsentResponse(BaseModel):
    """The wording a capture client must display, and the version to send back."""

    version: str
    text: str


class VerticalConfigResponse(BaseModel):
    zone_taxonomy: list[str]
    observation_schema: list[str]
    display_labels: VerticalDisplayLabelsResponse
    consent: VerticalConsentResponse
