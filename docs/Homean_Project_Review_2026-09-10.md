# Homean project review — September 10, 2026

Reviewed commit: `3913398`. Assessment: **not ready for real pilot use yet**.
The deployed pages load and the automated suites pass, but deployed authentication
is broken and there are uncovered session and mobile account-isolation defects.
This review made no application changes or deployments.

## Remediation follow-up

Subsequent local changes address findings 2–7: account-specific mobile databases and
session-bound sync, owner identity persisted with credentials, body-safe dashboard
retries, refresh-cookie navigation, transient-error session preservation, a real API
integration scenario, and capture dates in mobile history.

Validation: 74 dashboard tests, 85 mobile tests, and all three browser scenarios pass;
dashboard/mobile type checks and lint pass. The integrated browser scenario verifies
the real pipeline service with fake providers, persisted evidence, a save after access
cookie expiry, explicit confirmation, private delivery, public report content and
revocation. The original findings below remain as the historical review record.

Finding 1 remains operationally blocked: no hosted API origin or Render access was
available in this session. Deployment now requires `HOMEAN_API_URL` and checks the API's
database/Redis/S3 readiness before uploading. An unavailable backend yields a retryable
503 instead of an unhandled error. These guards do not make the current live backend
functional. A real API origin is still required.

Legacy mobile captures are preserved but quarantined because their original schema
contains no trustworthy account owner. See the mobile README before upgrading a device
with unsent legacy recordings. No legacy captures were deleted or assigned automatically.

## Findings, in priority order

### 1. P1 — Deployed dashboard has no functional backend origin

`dashboard/wrangler.jsonc:13` sets `HOMEAN_API_URL` to
`https://homean-api-unconfigured.invalid`. The live Worker version inspected during
deployment uses the same binding. A request to the deployed `/api/auth/login` with
deliberately invalid test credentials returned HTTP 500, rather than an authentication
rejection from a working API. Loading the login HTML successfully does not establish
that signup, authentication, or any authenticated workflow works.

Provision/verify the API and worker, configure the actual API origin, and run a live
signup/login plus staging capture-to-delivery check before inviting agents.

### 2. P1 — Mobile captures are not isolated by account/workspace

`mobile/src/storage/database.ts:18` creates one shared capture database without
workspace/user ownership. `listShowings()` and `pendingShowings()` at lines 122–126
select all captures. Logout clears credentials and `cache_entries`, but not the
capture tables. On the next login, `mobile/App.tsx:95` calls `refresh()`, which runs
the same sync engine with the newly signed-in API credentials.

Consequently, account B can see account A's local showing titles/history on a shared
device. A never-synced capture with no contact/property association can also be created
and uploaded into B's workspace: `mobile/src/sync/engine.ts:71–84` has no owner check.
Backend workspace filters cannot detect that those bytes originally belonged to A.
This finding follows directly from the persistence/login/sync code paths; it was not
tested using a physical device or real recordings.

Persist immutable ownership for captures, media, recovery sessions and caches; scope
all reads/sync to the authenticated owner and stop in-flight work on account changes.
Preserve unsent captures for their original owner rather than deleting them on logout.
Add an A → logout → B regression test with an unsynced capture.

### 3. P1 — A write request fails when it triggers token refresh

`dashboard/app/api/backend/[...path]/route.ts:29` consumes the request body on its
first forward. Following an upstream 401 and successful refresh, line 65 forwards the
same request again and tries to read that consumed body. The exception is swallowed
by the refresh catch, and the original 401 response is returned.

Reproduced by executing the actual transpiled route with a standard Request and mocked
upstream responses: PATCH → 401, refresh → 200, no second PATCH sent, response → 401.
New token cookies were set, but the edit was never retried. Report saves and other
POST/PATCH operations at token expiry are affected.

Buffer the body once and reuse the bytes (or clone before consuming), and cover write
retries in route-level tests.

### 4. P2 — Valid refresh sessions cannot restore normal page navigation

`dashboard/middleware.ts:6–15` only checks access cookies. Access cookies expire after
15 minutes, so opening a protected page after that point redirects to login even if
the 30-day refresh session is still valid. The API proxy's refresh flow never gets an
opportunity to run on that navigation.

Reproduced by invoking the middleware with a refresh cookie but no access cookie:
`/showings/1` redirected to `/login?next=%2Fshowings%2F1`.
Implement session restoration for this case while retaining API-side authentication.

### 5. P2 — Transient refresh failures discard valid dashboard sessions

`dashboard/app/api/backend/[...path]/route.ts:66–68` marks every refresh error as
terminal; lines 95–103 delete both authentication cookies. Reproduced with a refresh
HTTP 503: the response remained 401 and all session cookies were deleted. A brief
backend outage or rate limit unnecessarily signs the agent out.

Only an explicit authentication rejection should discard the session. Preserve it
for network errors, 429s and 5xx responses, as the mobile client already does.

### 6. P2 — Browser smoke tests bypass the review/delivery integration

`dashboard/e2e/showing-flow.spec.ts:27–64` intercepts report loading, edits, confirmation,
sending and revocation, returning synthetic results. The second scenario also stubs
these operations. These are useful UI smoke tests, but their passing result does not
prove browser → proxy → real review/delivery API interoperability or real pipeline
completion. In particular, they cannot catch finding 3 on those intercepted routes.

Add a full integration scenario using fake provider implementations behind the real
API, with actual review, confirmation and delivery persistence and token-expiry coverage.
The earlier local acceptance result of two passing browser tests should be read with
this limitation; it is not a fully integrated capture-to-delivery result.

### 7. P2 — Remote-only mobile history still displays sync time as tour time

`mobile/src/api/client.ts` parses only `created_at` for showing summaries, discarding
the API's `started_at`. `mobile/App.tsx:87` assigns that creation time to `startedAt`
for remote-only entries. A Monday offline tour synced Wednesday appears under
Wednesday after reinstalling the app or viewing it on another device, even though
the backend and dashboard now use the actual tour date.

Carry `started_at` through the mobile schema/types/cache and use it with a legacy
`created_at` fallback when constructing history entries.

## Verification and scope

- Fresh backend suite: **199 passed** against isolated local PostgreSQL databases.
- Fresh dashboard: **62 passed**, TypeScript and ESLint passed.
- Fresh mobile: **79 passed**, TypeScript and ESLint passed.
- Fresh marketing: **12 passed**, TypeScript and ESLint passed.
- Total freshly rerun tests: **352**. The two Playwright scenarios passed in the
  immediately preceding acceptance run; their limitations are described above.
- Three targeted dashboard session reproductions were run against the source modules
  using mocked Next.js boundaries/upstream responses.
- Live marketing returned HTTP 200; live login API returned HTTP 500.
- The preceding acceptance/deployment run verified release image builds, Cloudflare
  packaging, dry runs and deployment. Those results do not substitute for functional
  backend integration checks.

Review covered representative paths in backend auth, capture, pipeline, review,
delivery, billing and retention; dashboard auth/proxy/navigation and browser tests;
mobile persistence, account transitions and synchronization; and deployment readiness.
This is not an exhaustive proof of every path or a physical-device certification.

The backend evidence chain, confirmation restrictions, workspace API isolation,
retention retries and billing logic have meaningful existing test coverage. No new
failure was observed in those backend tests. Real Deepgram/Anthropic quality, SMTP,
Stripe test mode, storage CORS, backup restoration and physical-device offline capture
remain unverified here. Counsel review remains `pending` in the vertical pack, and
the staging pilot checklist still has no completed acceptance record.

## Recommended order

1. Fix mobile account isolation and the three dashboard session defects.
2. Add the missing integration/account-transition regressions.
3. Connect the deployed dashboard to a verified backend and worker.
4. Complete staging, physical-device and counsel gates, then run the controlled pilot.

## Remediation follow-up

Findings 2–7 are fixed: mobile capture databases are scoped to the authenticated
workspace and user, stale session operations are rejected, actual tour dates are
preserved, dashboard retries replay buffered request bodies, refresh-only sessions
can recover, and transient upstream errors retain credentials. Legacy unowned mobile
recordings remain preserved in the old database pending owner-verified migration.

Validation after these fixes: backend 199, dashboard 74, mobile 85, and Playwright 3
passed (361 checks). TypeScript, ESLint, Ruff, Cloudflare build and deployment dry run
passed. The new integrated browser flow exercises real backend persistence, pipeline
orchestration with fake AI providers, review, confirmation, sharing and revocation;
only object upload transport and external providers are faked.

Finding 1 deployment is in progress on the Mac mini. Homean has a separate checkout,
API and Celery processes, PostgreSQL, Redis and private MinIO storage. All 22 migrations
applied. API liveness, database, Redis and local storage checks pass. Public storage
readiness and dashboard deployment await the Homean DNS connection. Deepgram and
Anthropic credentials were absent in the earlier Kawu deployment and are not configured
in Homean. SMTP, Stripe, backup restoration and physical-device acceptance remain open.
