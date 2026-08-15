# Homean — Build Plan v1 (for Codex)

> Companion to: `Homean_Product_Document_v1.1.md`, `Homean_Technical_Architecture_v1.1.md`,
> `Homean_Full_Feature_Roadmap_v1.2.md`.
> Scope = **Phase 1 MVP only**, per Roadmap v1.2: English-only, mobile app for capture,
> web dashboard for editing/management, generic data model with `real_estate` vertical pack.
>
> How to use this document: work through milestones M0 → M7 in order. Each milestone has a
> **Codex prompt** you can paste directly. Paste the **Global Context Prompt** (below) at the
> start of every new Codex session, or rely on `AGENTS.md` (created in M0) which contains the
> same content. Review and test each milestone before starting the next — later prompts assume
> earlier ones landed.

------------------------------------------------------------------------

## Stack decisions (locked for MVP)

| Layer | Choice | Notes |
|---|---|---|
| Backend | **FastAPI** (Python 3.12, `uv`, `ruff`, `pytest`) | Async SQLAlchemy 2.0 + Alembic |
| Database | PostgreSQL 16 | Generic schema per architecture doc; JSONB boundary rules |
| Object storage | S3-compatible (MinIO in dev, S3/R2 in prod) | Presigned uploads for media |
| Background jobs | Celery + Redis | AI pipeline runs as chained tasks |
| Speech-to-text | Pluggable `TranscriptionProvider`; default **Deepgram** (word timestamps needed for the evidence chain); alternative impl slot for OpenAI Whisper | English-only in v1 |
| LLM | **Anthropic Claude** via official `anthropic` Python SDK. Default model `claude-opus-4-8`, set per-pipeline-step in config (downgradable to `claude-sonnet-4-6` / `claude-haiku-4-5` later if cost requires — a config change, not a code change) | Adaptive thinking (`thinking={"type": "adaptive"}`); structured outputs via `client.messages.parse()` with Pydantic; never pass `temperature`/`top_p` |
| PDF rendering | WeasyPrint from server-rendered report HTML | Same JSON content drives web view and PDF |
| Dashboard | **Next.js 15** (App Router, TypeScript, Tailwind, shadcn/ui, TanStack Query) | i18n via `next-intl` with `en` only |
| Mobile | Expo (React Native, TypeScript) | `expo-audio` recording, `expo-sqlite` offline queue — M6, after the web loop works end-to-end |
| Auth | Email/password → JWT access + refresh tokens | httpOnly cookies on dashboard |
| Billing | Stripe subscriptions | M7, last |
| Repo | Single monorepo: `backend/`, `dashboard/`, `mobile/`, `docs/`, `infra/` | One `docker-compose.yml` for local dev |

**Build order rationale**: backend core → AI pipeline → dashboard → mobile. The dashboard plus
manual file upload lets you validate the whole AI loop (upload recording → pipeline → edit →
send report) before any mobile work, which de-risks the two unvalidated hypotheses (H1/H2)
earliest.

------------------------------------------------------------------------

## Global Context Prompt (paste into every Codex session; also lives in AGENTS.md)

```
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
```

------------------------------------------------------------------------

## M0 — Monorepo scaffold & local dev environment

**Deliverables**: repo layout, `docker-compose.yml` (Postgres 16, Redis, MinIO), backend and
dashboard skeletons that boot, CI (lint + tests), `AGENTS.md`, `.env.example`, README.

**Acceptance**: `docker compose up` starts infra; `uvicorn` serves `/health`; `next dev`
renders a placeholder; CI green.

**Codex prompt:**

```
[Global Context Prompt]

Task: Scaffold the Homean monorepo. Do not implement product features yet.

1. Create the layout:
   backend/   - FastAPI app skeleton: app/main.py with /health, app/core/config.py
                (pydantic-settings reading env vars), app/api/, app/services/, app/models/,
                app/schemas/, tests/. pyproject.toml managed by uv; ruff + pytest configured.
   dashboard/ - Next.js 15 App Router + TypeScript strict + Tailwind + shadcn/ui init +
                next-intl configured with a single 'en' locale and messages/en.json.
                One placeholder page reading a string from the i18n catalog.
   infra/     - docker-compose.yml: postgres:16, redis:7, minio (with console), and a
                minio bucket-init job creating bucket "homean-media".
   docs/      - already exists; leave untouched.
2. Create AGENTS.md at repo root containing the project context and engineering conventions
   verbatim from this prompt's preamble, so future sessions pick them up automatically.
3. .env.example listing: DATABASE_URL, REDIS_URL, S3_ENDPOINT_URL, S3_ACCESS_KEY,
   S3_SECRET_KEY, S3_BUCKET, JWT_SECRET, ANTHROPIC_API_KEY, DEEPGRAM_API_KEY,
   TRANSCRIPTION_PROVIDER=deepgram, APP_ENV=dev.
4. GitHub Actions CI: job 1 backend (uv sync, ruff check, pytest), job 2 dashboard
   (npm ci, tsc --noEmit, next lint, next build). Cache deps.
5. Root README.md: prerequisites, `docker compose up -d`, backend run command,
   dashboard run command.

Acceptance: everything above boots locally; one trivial backend test and the CI pass.
```

------------------------------------------------------------------------

## M1 — Data model, migrations, auth, vertical pack config

**Deliverables**: full generic schema + Alembic migrations; signup/login with auto-created
Workspace; `real_estate.yaml` vertical pack loaded at startup; workspace-scoped dependency
injection.

**Acceptance**: migrations apply cleanly from empty DB; signup returns tokens; authed
requests resolve the caller's workspace; vertical config accessible via a typed service.

**Codex prompt:**

```
[Global Context Prompt]

Task: Implement the Homean data layer, auth, and vertical pack config in backend/.

1. SQLAlchemy models + Alembic migrations for (columns per the architecture doc §数据模型):
   users, workspaces (with language TEXT NOT NULL DEFAULT 'en'), memberships,
   professional_profiles, verticals, contacts, subjects (attributes JSONB), visits
   (contact_id nullable, status TEXT with CHECK in draft/confirmed/sent_to_client),
   zones, observations (full evidence-chain fields incl. source_transcript_segment_id,
   source_media_id, timestamp_start/end, ai_model, prompt_version, confidence,
   source_type, review_status, reviewed_by, reviewed_at), raw_media, transcript_segments,
   reports (content JSONB, rendered_html, status). All tables: id UUID pk, created_at,
   updated_at. Indexes on every workspace_id FK, visits(subject_id), visits(contact_id),
   observations(visit_id), transcript_segments(visit_id).
2. Vertical pack: backend/app/verticals/real_estate.yaml containing:
   - zone_taxonomy: kitchen, living_room, dining_room, primary_bedroom, bedroom, bathroom,
     basement, garage, backyard, front_exterior, balcony, laundry, office, hallway, other
   - observation_schema: pro, con, concern, follow_up, noise, light, smell, layout,
     condition, general
   - prompt_version: "re_v1"
   - report_template_id: "real_estate_v1"
   - display labels (English) for every zone type and category
   Loader: typed pydantic model, loaded at startup, seeded into the verticals table by a
   idempotent seed function, exposed via VerticalConfigService.
3. Auth: POST /auth/signup (email+password, argon2/bcrypt), POST /auth/login,
   POST /auth/refresh. JWT access (15 min) + refresh (30 days). On signup, in one
   transaction: User + default Workspace + Membership + ProfessionalProfile
   (vertical=real_estate, role=buyers_agent).
   FastAPI dependency get_current_context() returning (user, workspace, membership);
   every subsequent endpoint uses it and scopes queries by workspace_id.
4. GET /me returning user + workspace + profile.
5. Tests: migration up from empty DB, signup creates the 4-object graph, login/refresh
   round-trip, cross-workspace access is denied (404, not 403, to avoid leaking existence),
   vertical config loads and validates.
```

------------------------------------------------------------------------

## M2 — Visits, media capture API, contacts & subjects

**Deliverables**: CRUD for contacts/subjects; visit lifecycle endpoints; presigned media
upload flow with time-offset metadata; search/list endpoints backing the dashboard.

**Acceptance**: full capture flow works via HTTP: create visit → presign → upload audio/photo
to MinIO → attach → finish visit; listings filter and paginate.

**Codex prompt:**

```
[Global Context Prompt]

Task: Implement capture and workspace-management APIs in backend/. Service layer classes
use real-estate naming (RealEstateShowingService) over the generic models.

1. Contacts: CRUD under /contacts (name, email, phone, notes). Subjects: CRUD under
   /properties (route naming is real-estate; table is subjects) with display_name,
   address/location, attributes JSONB (beds, baths, sqft, listing_price, mls_id - all
   optional, validated by a RealEstateSubjectAttributes pydantic model).
2. Visits under /showings:
   - POST /showings: create draft Visit (subject required or created inline from an
     address string; contact optional).
   - POST /showings/{id}/media/presign: body {type: audio|photo|video, content_type,
     timestamp_offset_ms}; creates RawMedia row (status=pending) and returns a presigned
     PUT URL for S3 key workspace_id/visit_id/media_id.ext. Enforce content-type allowlist
     and max sizes (audio 500MB, photo 25MB, video 1GB).
   - POST /showings/{id}/media/{media_id}/complete: verify object exists in S3 (HEAD),
     mark uploaded.
   - POST /showings/{id}/finish: set ended_at; if at least one completed audio media
     exists, enqueue the AI pipeline (stub the Celery task for now - implemented in M3);
     set processing_status=queued.
   - GET /showings/{id}: visit detail with media, zones, observations, transcript, report.
   - GET /showings: list with filters contact_id, subject_id, status, date range,
     free-text q (ILIKE over subject display_name/address + contact name); cursor
     pagination; sorted newest first.
   - Media download: GET returns short-lived presigned GET URLs, never public URLs.
3. Storage: S3Client wrapper (aioboto3 or boto3 in threadpool) behind a StorageProvider
   interface; FakeStorageProvider for tests.
4. State machine guard: reject media attach/finish on confirmed/sent visits (409).
5. Tests: full happy-path capture flow against FakeStorageProvider; guards; pagination;
   workspace isolation on every route.
```

------------------------------------------------------------------------

## M3 — AI pipeline (transcribe → zones → observations → draft report)

**Deliverables**: Celery pipeline; Deepgram provider behind an interface; Claude-based zone
detection, structured extraction with evidence chain, sensitive-content flagging, and draft
report generation; processing status surfaced on the visit.

**Acceptance**: uploading a real recording and finishing a visit yields, without human input:
transcript segments with timestamps, zones, categorized observations each traceable to a
transcript segment, flagged risky statements, and a draft report in `pending_review` status.

**Codex prompt:**

```
[Global Context Prompt]

Task: Implement the AI processing pipeline in backend/ as Celery tasks on Redis.

Pipeline (chained tasks, one Celery chain per visit, each step idempotent and resumable;
visit.processing_status transitions queued -> transcribing -> structuring -> generating ->
ready, or failed with error stored):

1. TRANSCRIBE. TranscriptionProvider interface:
   transcribe(audio_url, language) -> list[{text, start_ms, end_ms, confidence}].
   Implement DeepgramProvider (nova-3 or latest, language="en", word timestamps on,
   punctuation on, utterance segmentation). Persist TranscriptSegment rows keyed to the
   RawMedia. Also implement FakeTranscriptionProvider returning fixture data for tests.
   Provider chosen by TRANSCRIPTION_PROVIDER env var.

2. ZONE DETECTION (Claude). Input: ordered transcript segments (ids + text + timestamps)
   plus the vertical's zone_taxonomy. Output: contiguous segment ranges labeled with a
   zone_type from the taxonomy (or "other"). Create Zone rows; a visit-level "no zone"
   is allowed. Use the anthropic SDK:
     client.messages.parse(model=cfg.model, thinking={"type": "adaptive"},
                           max_tokens=16000, output_format=ZoneDetectionResult)
   where ZoneDetectionResult is a Pydantic model. Model id comes from pipeline config
   (default "claude-opus-4-8"). Do NOT pass temperature/top_p (removed on this model).
   The prompt is rendered from a Jinja2 template stored under
   backend/app/verticals/prompts/re_v1/zone_detection.j2 with parameters:
   zone_taxonomy, output_language (fixed "en" for now), transcript. Never inline prompt
   text in Python.

3. OBSERVATION EXTRACTION (Claude). Per zone (batched into as few calls as context
   allows), extract observations categorized by the vertical's observation_schema.
   Each extracted observation MUST reference the source transcript segment id and
   timestamps; drop any model output that references a nonexistent segment id.
   Persist Observation rows with the full evidence chain: source_type=ai_generated,
   ai_model, prompt_version (from vertical config), confidence, review_status=pending,
   source_transcript_segment_id, timestamps. Prompt template observation_extraction.j2.
   Additionally run a SENSITIVE-CONTENT pass in the same structured output: flag
   subjective/defamatory/legal-risk statements (e.g. "seller is hiding something") with
   a suggested objective rewrite; store as observation.flags JSONB
   {sensitive: true, reason, suggested_rewrite}.

4. DRAFT REPORT (Claude). Generate Report.content JSONB conforming to a
   RealEstateReportSchema pydantic model with sections: executive_summary,
   room_by_room (ordered, keyed by zone), highlights (pros), concerns (cons + buyer
   concerns), follow_ups. Every bullet carries the observation ids it derives from.
   Report.status=pending_review. Visit stays in status=draft. Prompt template
   report_generation.j2 taking the confirmed vertical labels and output_language.

Infra requirements:
- LLMClient thin wrapper over the anthropic SDK: retries/backoff on RateLimitError and
  5xx (the SDK retries; set max_retries=4), per-call logging of model, input/output
  tokens, latency, prompt_version into a pipeline_runs table (visit_id, step, model,
  tokens_in, tokens_out, duration_ms, status, error).
- FakeLLMClient returning schema-valid fixtures; all pipeline tests run against fakes.
- Config: backend/app/core/pipeline_config.py mapping step -> model id, read from env
  with defaults (all "claude-opus-4-8" initially).
- Failure of any step marks processing_status=failed with a retriable POST
  /showings/{id}/reprocess endpoint (idempotent: wipes ai_generated artifacts for the
  failed step forward, keeps professional_edited ones, re-runs).
- Celery worker service added to docker-compose; README updated with worker run command.

Tests: end-to-end pipeline over fakes producing a full evidence-chained result; idempotent
re-run; invalid segment-id output from the fake LLM is dropped; failure marks status and
reprocess recovers.
```

------------------------------------------------------------------------

## M3.5 — Pipeline quality/integrity pass (post-M3 review findings)

**Why**: a review of the M3 prompt templates + `RealEstateReportSchema` surfaced three issues
that affect report quality (H2) and evidence-chain integrity, all fixable without touching the
schema contract M4/M5 depend on. Run after a real-recording smoke test confirms them; skip any
that the smoke test shows aren't actually problems.

**Deliverables**:
1. Server-side validation that report bullet `observation_ids` reference real observations
   (drop dangling refs, drop empty bullets) — mirrors the extraction step's segment-ref guard.
2. Report generation promotes *salient* descriptive observations (noise/light/smell/layout/
   condition) into highlights/concerns by judgment, not just pro/con/concern — so those
   sections aren't thin while room-by-room is rich.
3. A visit-level "no-zone" extraction batch so segments outside any detected zone
   (entry/exit/exterior/transition comments) still produce observations (`zone_id = null`).

**Acceptance**: fake-LLM fixtures prove dangling report refs are stripped, salient descriptive
observations surface in highlights/concerns with real citations, and no-zone segments reach the
report. Full suite green; schema and dashboard untouched. (Full Codex prompt kept alongside this
plan — issued after the M3 smoke test.)

------------------------------------------------------------------------

## M4 — Review, report finalization, delivery (share link + PDF + email)

**Deliverables**: editing APIs for observations/transcript/report; confirm flow; branded HTML
report + share link + PDF; send tracking.

**Acceptance**: an agent can edit the draft, confirm, and deliver a branded report via a
tokenized public link and PDF; open events are recorded; unconfirmed reports cannot be sent.

**Codex prompt:**

```
[Global Context Prompt]

Task: Implement review and delivery in backend/.

1. Editing APIs (all reject if visit.status == sent_to_client):
   - PATCH /observations/{id}: edit content/category/zone; sets
     source_type=professional_edited, review_status=edited, reviewed_by/reviewed_at.
   - POST /observations/{id}/confirm and /dismiss (dismiss = soft-delete, kept for the
     AI-improvement feedback loop described in the roadmap).
   - POST /observations (manual add, source_type=professional_edited).
   - PATCH /transcript-segments/{id}: correct text; keep original in original_text
     column (add via migration) for future model-improvement analysis.
   - PATCH /reports/{id}: replace content JSONB (validated against
     RealEstateReportSchema).
2. Confirmation: POST /showings/{id}/confirm -> visit.status=confirmed,
   report.status=confirmed. Guard: at least one observation reviewed. Sensitive-flagged
   observations that are still review_status=pending must be explicitly confirmed or
   edited first (422 listing offending ids otherwise).
3. Branding: workspace_branding table (logo S3 key, display_name, phone, email,
   license_no, accent_color) + GET/PUT /branding + presigned logo upload.
4. Rendering: ReportRenderer service turning Report.content + branding + vertical display
   labels into standalone HTML (Jinja2 template real_estate_v1.html, inline CSS,
   mobile-friendly, print-friendly). PDF via WeasyPrint from the same HTML. Snapshot the
   rendered HTML into report.rendered_html at confirm time.
5. Delivery:
   - POST /showings/{id}/share-links -> report_share_links row with 128-bit url-safe
     token, optional expiry, revocable. Public (unauthenticated) GET
     /r/{token} serves the HTML; GET /r/{token}/pdf serves the PDF. Record open events
     (report_share_views: timestamp, user_agent hash) - this is the North Star metric
     instrumentation (Client Reports Delivered + opens).
   - POST /showings/{id}/send: body {channel: email|link_only, to_email?}. Email via an
     EmailProvider interface (implement SMTP + console/dev provider) containing the share
     link and PDF attachment. Sets visit.status=sent_to_client, records report_sends row.
     Reject if not confirmed (409).
6. Tests: edit/confirm guards incl. the sensitive-flag gate; share link auth-free access +
   revocation + expiry; send transitions; renderer snapshot test with fixture content.
```

------------------------------------------------------------------------

## M5 — Web Dashboard (Next.js)

**Deliverables**: the agent-facing workspace per Roadmap v1.2 §1C. This is the biggest
milestone — feed it to Codex as one prompt, but expect to iterate screen by screen.

**Acceptance**: with the backend running, an agent can sign up, upload a recording to a new
showing (manual upload stands in for the mobile app), watch processing, edit everything,
confirm, brand, and send — entirely from the browser.

**Codex prompt:**

```
[Global Context Prompt]

Task: Build the Homean web dashboard in dashboard/ against the backend API
(base URL from NEXT_PUBLIC_API_URL). TypeScript strict, App Router, Tailwind + shadcn/ui,
TanStack Query. ALL user-facing strings go through next-intl keys in messages/en.json.
Auth: store JWTs in httpOnly cookies via a Next.js route handler proxying /auth/*;
middleware redirects unauthenticated users to /login.

Screens:
1. /login, /signup.
2. / (workspace home): showings list with two view toggles (by client / by property),
   filters (status, date range, client, free-text search), status badges
   (processing/draft/confirmed/sent), empty states.
3. /showings/new: create a showing - pick/create property (address autocomplete against
   our own subjects), optional client, and a file-upload dropzone that drives the
   presign -> PUT -> complete -> finish flow with progress. (This stands in for the
   mobile app until M6.)
4. /showings/[id] (the core screen), three tabs:
   a. Report: draft report editor - editable executive summary, per-room sections,
      drag-to-reorder bullets, add/remove bullets, per-bullet link back to its
      observation. Sensitive-flagged items rendered with a warning style, one-click
      "apply suggested rewrite". Confirm button (disabled until backend guards pass,
      surfacing the 422 reasons).
   b. Observations: grouped by zone, inline edit, category picker (labels from vertical
      config endpoint), confirm/dismiss, manual add.
   c. Transcript: segment list with per-segment audio playback (seek the visit audio via
      presigned URL + timestamp offsets), inline text correction. Clicking an observation
      anywhere deep-links to its source segment and starts playback there (the evidence
      chain, made visible).
   Plus: photo strip with timestamps, processing-status banner with reprocess action,
   and after confirm - a Send panel (email form / copy share link, send history, open
   counts).
5. /clients: CRUD + client detail listing their showings + "Compare" action when >=2
   showings: /clients/[id]/compare renders a side-by-side structured comparison table
   (rows = zones + highlight/concern counts + key observations) with print stylesheet.
6. /properties: CRUD + per-property visit history (independent versions listed).
7. /settings: profile, branding editor (logo upload with preview, colors, contact info)
   with live report preview using the backend renderer.

Conventions: one typed API client module (fetch wrappers + zod parsing of responses),
error toasts, optimistic updates only where trivially safe (observation confirm/dismiss).
Component tests for the report editor's guard states and the compare table with mocked
API; Playwright smoke test for signup -> create showing -> (mock pipeline) -> confirm ->
share link flow, with the backend running its fake providers.
```

------------------------------------------------------------------------

## M5.5 — Dashboard backend endpoint backfill (post-M5 findings)

**Why**: building M5 surfaced read/update endpoints the earlier backend milestones never
exposed; the dashboard stubbed them with fallbacks. Backfilled without schema changes.

**Deliverables**:
1. `GET /vertical-config` — zone taxonomy, observation schema, English display labels from
   `VerticalConfigService` (powers category/zone label pickers; drops the raw-enum fallback).
2. `GET /showings/{id}/delivery` — share links + sends + real `open_count` from
   `report_share_views`. **This is the North Star instrumentation surface** — without it the
   agent can't see Client Reports Delivered / opens.
3. `PATCH /me` — editable profile name.
4. `GET /branding/preview` — real `ReportRenderer` HTML for the settings preview iframe.
Plus dashboard rewiring to consume all four.

**Acceptance**: workspace-isolated endpoints with tests; delivery panel shows real open
counts; category pickers show labels; Playwright still green. Done (5 vitest + suite green).

------------------------------------------------------------------------

## M6 — Mobile capture app (Expo)

**Deliverables**: iOS/Android capture app per Roadmap v1.2 — capture-first, offline-first,
deliberately minimal.

**Acceptance**: record a full showing with photos and voice tags on airplane mode; everything
syncs automatically when connectivity returns; the showing then appears in the dashboard.

**Codex prompt:**

```
[Global Context Prompt]

Task: Build the Homean mobile capture app in mobile/ with Expo (managed workflow,
TypeScript). Scope is CAPTURE ONLY per Roadmap v1.2 - editing lives in the dashboard.

1. Auth: login (same JWT endpoints), secure token storage (expo-secure-store), refresh.
2. Home: giant "Start Showing" button + list of recent showings with sync/processing
   status. On start: optional quick-pick of client and property (searchable, both
   skippable, property creatable from a typed address).
3. Recording screen (the core): continuous audio recording (expo-audio, background-capable,
   interruption-safe - persist and resume on app kill), elapsed timer, prominent
   camera button (photos attach with current timestamp_offset_ms), "Voice Tag" button
   that just drops a timestamp marker (the backend treats "note: ..." speech naturally;
   the marker is stored as RawMedia metadata for future use), End button with confirm.
4. Offline-first sync engine: everything (visit draft, media files, offsets) is written
   to local storage first (expo-sqlite + filesystem). A sync queue uploads via
   presign/PUT/complete with retry + exponential backoff, survives restarts, resumes
   partial uploads, and only calls /finish after all media are complete. Airplane-mode
   test is the acceptance bar. Show per-showing sync state (local / syncing / synced /
   processing / ready).
5. Read-only report view: once ready, show the draft report (webview of the authed HTML
   render or a simple native rendering of report content), quick-confirm + send actions
   ONLY if the backend guards pass (no sensitive-flag pending, etc.) - otherwise a
   "Review on desktop" nudge with the dashboard URL. Minimal emergency edit: fix a typo
   in a report bullet, delete an observation.
6. All strings through a key-based i18n catalog (i18next), English only.
7. Tests: sync-queue unit tests (offline enqueue, retry, resume, ordering); component
   tests for the recording state machine. Document the manual airplane-mode test script
   in mobile/README.md.
```

------------------------------------------------------------------------

## M6.5 — Property optional to capture, required to send (post-M6 finding)

**Why**: M6 let agents skip the property, but `visits.subject_id` was `NOT NULL`, so
property-free captures couldn't sync — trapping recordings on-device (breaks the offline-first
"never lose data" promise) and reintroducing capture friction. Fix: capture/sync/process
freely without a property; require one before confirm/send.

**Deliverables**:
1. Migration making `visits.subject_id` nullable (real schema change).
2. `POST /showings` accepts no subject; new `PATCH /showings/{id}` attaches a subject later.
3. Confirm guard requires `subject_id` (422 "attach a property first"), alongside the
   existing observation-reviewed and sensitive-flag gates.
4. Mobile syncs subject-less showings through the normal flow (drops the local-only trap);
   read-only report view surfaces the attach guard via the "review on desktop" nudge.
5. Dashboard: "Unassigned" filter/badge + "Attach property" action; Confirm surfaces the 422.

**Acceptance**: no-subject visit creates→syncs→processes→blocked-at-confirm→attach→confirm;
workspace-isolated; all suites green. (Full Codex prompt issued alongside this plan.)

------------------------------------------------------------------------

## Deferred backlog (do, but not blocking Phase-1 validation)

Small items found during the build, parked deliberately. Revisit during M7 hardening or the
first post-validation iteration — none block putting the product in front of trial agents.

- ~~**Voice-tag marker sync** (from M6)~~ — **done.** Markers persist through the visit
  marker API and sync idempotently from the mobile queue. They are no longer a redundant
  signal: each tag resolves to the transcript segment it bookmarks, the review UI offers
  those as jump points, and extraction receives the marked segment as agent-emphasized
  evidence. An observation drawn from one is flagged `voice_tagged` in `Observation.flags`
  — not a new category, not auto-promoted into the report, and still subject to the normal
  review gate.
- **Migration formatting nit** in `20260804_0004_review_delivery.py` (flagged M3.5) — cosmetic,
  sweep up in hardening.
- **`og.png` social-card copy** is Codex-invented English marketing text; align with the real
  positioning before any public use (and it'll need i18n coverage later).

------------------------------------------------------------------------

## M7 — Billing, hardening, deployment

**Deliverables**: Stripe subscription with trial; production infra; security/ops pass.

**Codex prompt:**

```
[Global Context Prompt]

Task: Production-readiness for Homean.

1. Billing (Stripe): workspace-level subscription. Plans: trial (14 days, full features,
   default on signup), solo monthly. Stripe Checkout for subscribe, customer portal for
   management, webhook handler (checkout.session.completed, customer.subscription.updated/
   deleted) updating a workspace_subscriptions table. Gate: when trial expired and not
   subscribed, block creating new showings and sending reports (reads stay open); backend
   enforces, dashboard shows an upgrade wall. Per-workspace monthly report-generation
   counter recorded now (for future usage tiers), not yet enforced.
2. Security pass: rate limiting on auth + public share routes (slowapi/redis);
   audit that every query is workspace-scoped (add a test helper that walks all routes);
   share-link tokens compared timing-safe; presigned URL TTLs <= 15 min; CORS locked to
   the dashboard origin; security headers on the public report pages; PII-free logs.
3. Recording-consent groundwork (product doc risk #3): consent_ack flag captured at
   showing start from mobile (agent attests they have consent), stored on the visit;
   a short disclosure line rendered in the report footer. No legal text authored - use
   a placeholder string with a TODO for counsel review.
4. Ops: structured JSON logging with request ids; Sentry hooks (env-gated); /health and
   /ready endpoints checking DB/Redis/S3; Dockerfiles for api + worker + dashboard;
   deploy configs for a simple single-region setup (Fly.io or Render - pick one and
   document); daily Postgres backup note in infra/README. Alembic migration run as a
   release step.
5. Cost telemetry: dashboard-facing nothing; internal: pipeline_runs already records
   tokens - add a small admin script summarizing per-visit AI cost using current
   Anthropic pricing from env-configured rates.
```

------------------------------------------------------------------------

## Working with Codex — practical notes

- **One milestone per session/PR.** Paste the global context (or rely on `AGENTS.md` after
  M0), then the milestone prompt. Review the diff before moving on; later milestones assume
  earlier acceptance criteria genuinely pass.
- **Iterate inside a milestone** with follow-ups like "the acceptance criterion X fails
  because Y — fix it" rather than re-pasting the whole prompt.
- **Keys you must provision** before M3: `ANTHROPIC_API_KEY`, `DEEPGRAM_API_KEY`; before
  M7: Stripe keys. Everything else runs on docker-compose locally.
- **Model/cost control** lives in `pipeline_config.py` env overrides — switching a pipeline
  step to `claude-sonnet-4-6` or `claude-haiku-4-5` later is a config change. Watch the
  `pipeline_runs` table during the trial to see real per-visit cost before deciding.
- **Milestone review checkpoints** worth doing manually: after M3, run one real ~10-minute
  showing recording through the pipeline and read the output critically (this is H2 in
  miniature); after M5, do the full loop yourself before recruiting trial agents; after M6,
  the airplane-mode test on a real device.

## Deliberately out of scope (do not let Codex build these)

Teams/RBAC UI, CRM/calendar/MLS integrations, buyer portal accounts, any non-English
content, public sharing, GPS/proof-of-visit, repair-cost estimates, a second vertical,
configurable pipeline steps, a visual report designer. If a prompt result includes any of
these, cut it.
