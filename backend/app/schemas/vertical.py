from pydantic import BaseModel


class VerticalDisplayLabelsResponse(BaseModel):
    zones: dict[str, str]
    observations: dict[str, str]


class VerticalConfigResponse(BaseModel):
    zone_taxonomy: list[str]
    observation_schema: list[str]
    display_labels: VerticalDisplayLabelsResponse
