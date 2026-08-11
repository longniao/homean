from scripts.ai_cost_report import estimate_cost


def test_estimate_cost_uses_configured_per_million_rates() -> None:
    assert estimate_cost(1_000_000, 500_000, 3.0, 15.0) == 10.5
    assert estimate_cost(0, 0, 3.0, 15.0) == 0
