# Homean Project Review

**Review date:** August 14, 2026

## Overall Assessment

Homean is a technically solid and nearly complete Phase 1 MVP. Its core workflow is largely end-to-end:

`Mobile capture -> offline sync -> transcription/AI structuring -> agent review -> confirmation -> PDF/private link/email delivery`

It is suitable for a controlled pilot with 3–5 buyer's agents after the launch blockers are resolved. It is not yet ready for a full production launch, and there is no evidence yet to justify moving into Phase 2.

## Current Status

| Area | Assessment |
|---|---|
| Generic data model | Complete and aligned with Subject/Zone/Observation/Visit naming |
| Vertical pack | Complete; taxonomy, labels, prompts, and report template are configurable |
| AI pipeline | Complete; supports retries, reprocessing, evidence links, and cost tracking |
| Review/state machine | Complete; reports cannot be delivered before explicit confirmation |
| Dashboard | Substantially complete |
| Mobile app | Substantially complete, including offline capture and durable sync |
| Billing/delivery | Stripe, email, PDF, private links, and view tracking are implemented |
| Operations | Docker, Render, health checks, logging, Sentry, migrations, and release checks exist |
| Real-world validation | Not started, or at least not recorded |
| Production readiness | Not complete |

## What Is Strong

- The implementation follows the architecture rules closely. Database entities remain generic while APIs and services use real-estate terminology.
- The evidence chain is functional, not merely modeled: AI observations reference transcript segments, source media, timestamps, model information, prompt version, and review state.
- Mobile synchronization handles offline creation, retries, expired presigned URLs, interrupted recording recovery, idempotency, and concurrent local changes.
- Report edits retain immutable revisions. Delivery and editing use consistent locking, and email delivery handles uncertain SMTP outcomes carefully.
- Workspace isolation is applied throughout repositories and covered by cross-workspace tests.
- The codebase has avoided prematurely implementing Phase 2–4 features.

## Verification Results

No existing files were modified during the review.

- Backend: 163 tests passed; Ruff passed.
- Dashboard: 55 tests passed; TypeScript, ESLint, and production build passed.
- Mobile: 74 tests passed; TypeScript, ESLint, and all 21 Expo Doctor checks passed.
- Total: 292 automated tests passed.
- Alembic: 20 migrations with a single head, `20260814_0020`.
- Render Blueprint: local structural validation passed.
- Playwright: the two scenarios did not reach browser assertions because the local Chromium binary was missing. CI installs Chromium explicitly, but E2E cannot be counted as verified in this review.
- The local `.venv/bin/pytest` shebang still points to the old `kawu` project. Running the suite through Python 3.12 works; the virtual environment should be rebuilt.

## Priority Findings

### 1. Legal language is still a launch blocker

The recording-consent text and report disclosures are explicitly marked as pending counsel review in `backend/app/verticals/real_estate.yaml`. Trial capture should not be enabled until this is approved.

### 2. The core product hypotheses remain unvalidated

A complete codebase does not mean the product has been validated. There is no Customer Discovery Log or Experiment Log in the repository, even though the product document requires them.

The next milestone should be repeated real-world use and actual report delivery—not Phase 2 development.

### 3. Offline showing dates are handled incorrectly in history views

Mobile sends the real `started_at`, but backend filtering, sorting, and pagination use `Visit.created_at` in `backend/app/repositories/showings.py`. The dashboard also displays `created_at`.

A showing recorded offline on Monday and synchronized on Wednesday will appear as a Wednesday showing. This affects history, filters, client/property views, and future metrics.

### 4. Media retention can report deletion before deletion succeeds

The purge script commits `purged_at` before deleting the object from storage in `backend/scripts/purge_expired_media.py`.

If storage deletion fails, future runs skip the row, leaving the media behind while the database claims it was purged. The purge process needs a retryable state.

### 5. Voice Tags are stored but not used

The roadmap describes Voice Tags as part of the capture workflow. Markers are now persisted and synchronized, but the AI pipeline does not consume them or convert them into independent notes or navigation points.

The infrastructure exists, but the user-facing behavior is incomplete.

### 6. Rejected media can be silently omitted

The mobile sync engine permits a showing to finish when a photo or video receives a permanent rejection, then clears the showing-level error in `mobile/src/sync/engine.ts`.

Allowing one bad file not to block the entire showing is reasonable, but the agent should see that media was omitted and be given a recovery, replacement, or export option.

### 7. Refresh tokens cannot be revoked server-side

Refresh tokens are stateless JWTs, and refresh only checks whether the user and workspace still exist in `backend/app/services/auth.py`.

Logging out only removes the client-side token. A stolen refresh token may remain valid for up to 30 days. Production should consider server-side sessions, rotation, and revocation.

## Documentation and Scope Risk

The untracked `docs/Buyer_Self_Tour_Mode.md` proposes a direct-to-buyer product and recommends making `Tour` the core domain object.

That conflicts with the frozen baseline:

- The current target user is the buyer's agent.
- The generic database core uses `Visit`.
- Buyer-facing products are outside Phase 1.
- Later phases require evidence from earlier validation gates.

This concept can remain as a separate RFC or experiment hypothesis, but it should not become an implementation instruction yet. The existing `Visit` model should not be renamed to `Tour` at this stage.

There are also minor documentation and branding remnants: the mobile login screen still displays the old `K` mark, and the build plan still lists marker synchronization as deferred even though it has been implemented.

## Recommended Next Steps

1. Keep Phase 1 frozen and treat Buyer Self-Tour as an unapproved RFC.
2. Fix showing-date semantics, retention retries, rejected-media visibility, the old brand mark, and the intended Voice Tag behavior.
3. Complete legal review, a real Deepgram/Anthropic recording test, the physical-device airplane-mode test, Stripe/SMTP staging verification, and a backup restore drill.
4. Create Discovery and Experiment Logs, then run a two-week pilot with 3–5 buyer's agents.
5. Measure repeat use and actual Client Reports Delivered—not signups or generated drafts.
6. Begin Phase 2 planning only after the G1 validation gate passes.

## Conclusion

The engineering MVP is close to pilot-ready. The biggest risk is expanding into new product directions before proving that agents repeatedly use and deliver the current report workflow.
