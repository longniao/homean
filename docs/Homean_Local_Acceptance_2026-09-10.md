# Local pilot acceptance evidence — September 10, 2026

Base commit: `d53e5a1`. Results cover that commit plus the dependency fixes in this
working tree. This is local engineering evidence, not staging or production approval.
The staging acceptance checklist remains pending until its owners record evidence.

## Changes

- Marketing Next.js and matching ESLint configuration: `15.5.22` → `15.5.24`.
- Both web applications override all copies of Sharp to `0.35.4`, including the
  copy used by Miniflare. The old override covered only Next.js.
- Refreshed affected transitive dependencies: `js-yaml` to `4.3.2` in both apps;
  dashboard `fast-uri` to `3.1.7`, `hono` to `4.13.7`, and `qs` to `6.16.0`.
- Updated both npm lockfiles; no application behavior or database schema changes.

The patched versions address findings from npm audit, including the upstream
[Sharp advisory](https://github.com/advisories/GHSA-rgj7-g3m4-5g8c),
[Next.js advisory](https://github.com/advisories/GHSA-2xp9-vwfh-vxw4), and
[js-yaml advisory](https://github.com/advisories/GHSA-2883-xcg3-v3hh).

## Verification

| Check | Result |
| --- | --- |
| Backend pytest, using local PostgreSQL and fake external providers | PASS — 199 tests |
| Backend Ruff | PASS |
| Dashboard tests / TypeScript / ESLint | PASS — 62 tests |
| Playwright signup/upload/confirm/share and property-optional capture workflows | PASS — 2 tests after dependency updates |
| Mobile tests / TypeScript / ESLint | PASS — 79 tests |
| Marketing tests / TypeScript / ESLint | PASS — 12 tests |
| Dashboard OpenNext Cloudflare build and Wrangler deployment dry run | PASS |
| Marketing static export and Wrangler deployment dry run | PASS |
| Dashboard and marketing `npm audit --audit-level=high` | PASS — zero high or critical findings |
| Alembic graph | PASS — one expected head, `20260814_0022` |
| Release preflight: Render structure, Compose, API/worker/dashboard Docker images | PASS |

Backend tests initially could not reach PostgreSQL. Starting the repository's
PostgreSQL and Redis services resolved this; the subsequent full backend run passed.
Tests create isolated temporary databases and do not call paid AI providers.

Two moderate findings remain in each web dependency tree, for Vitest and its mocker
dependency ([advisory](https://github.com/advisories/GHSA-82fw-gwwq-j7x9)). Updating
the test runner across a major version is follow-up work. The configured high-severity
release threshold passes; this is not a claim of zero dependency vulnerabilities.

## Remaining acceptance work

- Record the actual staging release and CI results in
  [the pilot checklist](Homean_Pilot_Acceptance_Checklist.md).
- Complete counsel review: `real_estate.yaml` still has
  `consent.counsel_review_status: pending`.
- Verify staging health, private storage CORS, backup restoration, fresh sessions,
  real English transcription/report generation, Stripe test mode, and SMTP/PDF delivery.
- Run the physical-device airplane-mode capture/recovery check.
- Run the two-week pilot with 3–5 agents and record actual report delivery, repeat use,
  and willingness to continue/pay.

No deployment, customer communication, or trial-user capture was performed.
