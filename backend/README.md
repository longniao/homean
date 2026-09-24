# Homean backend

FastAPI service for Homean. See the repository root README for setup instructions.

The optional [Jev evidence experiment](../docs/Homean_Jev_Evidence_Experiment.md)
validates synthetic fixtures and compares a citation-only control with semantic
checks. It is separate from the production pipeline and defaults to offline
validation: `uv run python -m app.evaluation.evidence`.
