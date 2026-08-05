from typing import Any, Literal

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from app.verticals import VerticalConfigService, VerticalPack

PromptStep = Literal["zone_detection", "observation_extraction", "report_generation"]


class PromptRenderer:
    def __init__(self, verticals: VerticalConfigService) -> None:
        self._environment = Environment(
            loader=FileSystemLoader(verticals.prompt_root),
            undefined=StrictUndefined,
            autoescape=select_autoescape(default=False),
        )

    def render(self, pack: VerticalPack, step: PromptStep, **parameters: Any) -> str:
        template_name = getattr(pack.prompt_templates, step)
        return self._environment.get_template(template_name).render(**parameters)
