You are building Homean, an AI showing-report tool for real-estate buyer's agents.
Read docs/Homean_Product_Document_v1.1.md, docs/Homean_Technical_Architecture_v1.1.md,
and docs/Homean_Full_Feature_Roadmap_v1.2.md before writing code.

Non-negotiable architecture rules (from the docs):
1. Database uses GENERIC names: Subject (not Property), Zone (not Room), Contact (not
   Client), Observation, Visit, Vertical, User/Workspace/Membership/ProfessionalProfile.
   The service layer uses real-estate names (RealEstateShowingService etc.).
2. JSONB boundary: industry-specific/volatile fields (Subject.attributes, zone_type and
   observation category value sets) live in JSONB/config. Frequently queried fields
   (workspace_id, contact_id, created_by, visit.status, observation.review_status) are
   real columns with indexes. No enums in the DB for vertical-configurable values.
3. Evidence chain: every Observation links to its TranscriptSegment, RawMedia, timestamps,
   ai_model, prompt_version, confidence, review_status, reviewed_by/reviewed_at.
4. Vertical pack: zone taxonomy, observation schema, prompt templates, and report template
   for real_estate live in a versioned YAML config file loaded at startup — never hardcoded
   in prompts or components. Only real_estate exists; no admin UI, no second vertical.
5. Visit state machine: draft -> confirmed -> sent_to_client. AI output is never sendable
   without explicit agent confirmation.
6. English-only v1, but i18n-ready: UI strings externalized (key-based), Workspace.language
   column fixed to 'en', prompt templates take output_language as a parameter, report label
   text comes from config. UTF-8 everywhere.
7. Multi-tenancy: every query is scoped by workspace_id. Each new user gets one auto-created
   default Workspace + Membership + ProfessionalProfile(role=buyers_agent). No team UI.

Engineering conventions:
- backend/: Python 3.12, uv for deps, ruff for lint/format, pytest (+ pytest-asyncio),
  FastAPI, async SQLAlchemy 2.0, Alembic migrations, Pydantic v2 schemas.
  Layering: api/routers -> services -> repositories/models. No business logic in routers.
- dashboard/: Next.js 15 App Router, TypeScript strict, Tailwind + shadcn/ui,
  TanStack Query for server state. API client generated or hand-written in one module.
- Tests accompany every feature; target meaningful coverage of services and API routes,
  not line-count. All external services (S3, Deepgram, Anthropic, Stripe) are behind
  interfaces with fake implementations for tests. Never call paid APIs from tests.
- Secrets only via environment variables; provide .env.example. Never commit secrets.
- Conventional commits. Keep PR-sized changes coherent per milestone.
