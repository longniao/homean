from pathlib import Path

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Vertical
from app.verticals import VerticalConfigService, seed_verticals

EXPECTED_ZONES = [
    "kitchen",
    "living_room",
    "dining_room",
    "primary_bedroom",
    "bedroom",
    "bathroom",
    "basement",
    "garage",
    "backyard",
    "front_exterior",
    "balcony",
    "laundry",
    "office",
    "hallway",
    "other",
]

EXPECTED_OBSERVATIONS = [
    "pro",
    "con",
    "concern",
    "follow_up",
    "noise",
    "light",
    "smell",
    "layout",
    "condition",
    "general",
]


async def test_vertical_config_endpoint_returns_english_labels(
    client: AsyncClient,
) -> None:
    signup = await client.post(
        "/auth/signup",
        json={
            "email": "vertical-endpoint@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    response = await client.get("/vertical-config", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["zone_taxonomy"] == EXPECTED_ZONES
    assert response.json()["observation_schema"] == EXPECTED_OBSERVATIONS
    assert response.json()["display_labels"]["zones"]["living_room"] == ("Living room")
    assert response.json()["display_labels"]["observations"]["follow_up"] == (
        "Follow-up"
    )
    assert (await client.get("/vertical-config")).status_code == 401


async def test_real_estate_vertical_pack_loads_and_seeds_idempotently(
    session: AsyncSession,
) -> None:
    service = VerticalConfigService()
    config = service.get()

    assert config.zone_taxonomy == EXPECTED_ZONES
    assert config.observation_schema == EXPECTED_OBSERVATIONS
    assert config.prompt_version == "re_v1"
    assert config.report_template_id == "real_estate_v1"
    assert set(config.display_labels.zones) == set(EXPECTED_ZONES)
    assert set(config.display_labels.observations) == set(EXPECTED_OBSERVATIONS)

    async with session.begin():
        await seed_verticals(session, service)
        await seed_verticals(session, service)
    count = await session.scalar(
        select(func.count()).select_from(Vertical).where(Vertical.slug == "real_estate")
    )
    assert count == 1


def test_vertical_pack_rejects_incomplete_labels(tmp_path: Path) -> None:
    invalid_config = tmp_path / "invalid.yaml"
    source = Path(__file__).parents[1] / "app" / "verticals" / "real_estate.yaml"
    invalid_config.write_text(
        source.read_text(encoding="utf-8").replace("    kitchen: Kitchen\n", ""),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="zone labels"):
        VerticalConfigService(invalid_config)
