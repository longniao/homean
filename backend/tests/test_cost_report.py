from scripts.ai_cost_report import estimate_cost


def test_estimate_cost_uses_configured_per_million_rates() -> None:
    assert estimate_cost(1_000_000, 500_000, 3.0, 15.0) == 10.5
    assert estimate_cost(0, 0, 3.0, 15.0) == 0


def test_unconfigured_rates_are_not_the_same_as_free() -> None:
    from scripts.ai_cost_report import rates_configured

    # A report showing $0.00 per tour reads as "these were free", which is a
    # more expensive belief to hold than "we have not priced them yet".
    assert rates_configured(0.0, 0.0) is False
    assert rates_configured(3.0, 0.0) is True
    assert rates_configured(0.0, 15.0) is True
