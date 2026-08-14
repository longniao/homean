"""Summarize recorded Anthropic usage and estimated cost per visit.

Rates are intentionally environment-configured because Anthropic pricing changes.
The report contains IDs and usage only; it never prints transcript or contact data.
Run from backend/: ``uv run python scripts/ai_cost_report.py``.
"""

import argparse
import asyncio
import json
import sys
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core.config import get_settings
from app.core.database_url import create_async_engine_for_url
from app.models import PipelineRun, Visit


@dataclass(frozen=True)
class VisitCost:
    visit_id: uuid.UUID
    workspace_id: uuid.UUID
    tokens_in: int
    tokens_out: int
    #: None when no rates are configured. Reporting 0.0 in that case reads as
    #: "these tours were free" rather than "we have not priced them", which is
    #: the more expensive mistake to leave sitting in a dashboard.
    estimated_cost_usd: float | None


def estimate_cost(
    tokens_in: int,
    tokens_out: int,
    input_rate_per_million: float,
    output_rate_per_million: float,
) -> float:
    return (tokens_in / 1_000_000 * input_rate_per_million) + (
        tokens_out / 1_000_000 * output_rate_per_million
    )


def rates_configured(
    input_rate_per_million: float, output_rate_per_million: float
) -> bool:
    return input_rate_per_million > 0 or output_rate_per_million > 0


async def collect(visit_id: uuid.UUID | None = None) -> list[VisitCost]:
    settings = get_settings()
    engine = _create_cost_report_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            statement = (
                select(
                    PipelineRun.visit_id,
                    Visit.workspace_id,
                    func.coalesce(func.sum(PipelineRun.tokens_in), 0),
                    func.coalesce(func.sum(PipelineRun.tokens_out), 0),
                )
                .join(Visit, Visit.id == PipelineRun.visit_id)
                .group_by(PipelineRun.visit_id, Visit.workspace_id)
                .order_by(PipelineRun.visit_id)
            )
            if visit_id is not None:
                statement = statement.where(PipelineRun.visit_id == visit_id)
            rows = await session.execute(statement)
            priced = rates_configured(
                settings.anthropic_input_cost_per_million,
                settings.anthropic_output_cost_per_million,
            )
            return [
                VisitCost(
                    visit_id=visit,
                    workspace_id=workspace,
                    tokens_in=int(tokens_in),
                    tokens_out=int(tokens_out),
                    estimated_cost_usd=(
                        round(
                            estimate_cost(
                                int(tokens_in),
                                int(tokens_out),
                                settings.anthropic_input_cost_per_million,
                                settings.anthropic_output_cost_per_million,
                            ),
                            6,
                        )
                        if priced
                        else None
                    ),
                )
                for visit, workspace, tokens_in, tokens_out in rows.tuples()
            ]
    finally:
        await engine.dispose()


def _create_cost_report_engine(database_url: str) -> AsyncEngine:
    return create_async_engine_for_url(database_url, pool_pre_ping=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--visit-id", type=uuid.UUID)
    args = parser.parse_args()
    result = asyncio.run(collect(args.visit_id))
    if any(item.estimated_cost_usd is None for item in result):
        print(
            "warning: ANTHROPIC_INPUT_COST_PER_MILLION and "
            "ANTHROPIC_OUTPUT_COST_PER_MILLION are unset, so cost is reported as "
            "null rather than zero. Token counts below are still accurate.",
            file=sys.stderr,
        )
    payload = [
        {
            "visit_id": str(item.visit_id),
            "workspace_id": str(item.workspace_id),
            "tokens_in": item.tokens_in,
            "tokens_out": item.tokens_out,
            "estimated_cost_usd": item.estimated_cost_usd,
        }
        for item in result
    ]
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
