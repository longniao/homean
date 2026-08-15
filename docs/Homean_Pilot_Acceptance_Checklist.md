# Homean Staging Pilot Acceptance Checklist

## Purpose and scope

This checklist is the go/no-go record for a controlled Homean pilot. It covers one
staging release, then a two-week pilot with 3–5 buyer's agents using English
showings. It is not production approval, a general design document, or permission
to use real customer data before the required legal, backup, and restore gates pass.

Every gate starts as `PENDING`. The release owner must record `PASS` or `FAIL`,
an evidence location, owner, date, and notes. A required gate that is `PENDING`
or `FAIL` is a `NO-GO`. Do not enable trial-user capture until counsel approval,
backup/restore readiness, and the fresh-sign-in gate are complete.

## Run metadata

| Field | Record |
| --- | --- |
| Environment / staging URL |  |
| Release commit |  |
| Checklist run date (UTC) |  |
| Tester(s) |  |
| Release owner |  |
| QA / acceptance lead |  |
| Pilot coordinator |  |
| Evidence root or release record |  |
| Rollback owner and contact |  |
| Incident lead and contact |  |
| Decision | `PENDING` — `GO` / `NO-GO` |

## Acceptance gates

For each gate, replace `PENDING` only after the named owner has attached the
evidence. Do not record secrets, access tokens, refresh tokens, or customer media
in this document.

### 1. Release identity and credential-free checks

- [ ] **Result:** `PENDING`
- **Owner:**
- **Date (UTC):**
- **Evidence location:**
- **Checks:**
  - [ ] Release commit is recorded above and matches the staging deployment.
  - [ ] CI is green for backend, dashboard, mobile, dependency audit, and Playwright.
  - [ ] Alembic has exactly one expected head.
  - [ ] Render Blueprint validation, Compose validation, and release image builds pass.
  - [ ] No production credentials or paid-provider calls were used for repository checks.
- **Notes:**

### 2. Staging environment and health

- [ ] **Result:** `PENDING`
- **Owner:**
- **Date (UTC):**
- **Evidence location:**
- **Checks:**
  - [ ] Staging secrets are provisioned outside the repository.
  - [ ] `GET /health` returns HTTP 200 with `{"status":"ok"}`.
  - [ ] `GET /ready` returns HTTP 200 with database, Redis, and S3 all `ok`.
  - [ ] API, worker, dashboard, Postgres, Redis, and private object storage are reachable through the documented deployment boundary.
- **Notes:**

### 3. Counsel approval and retention policy

- [ ] **Result:** `PENDING`
- **Owner:**
- **Date (UTC):**
- **Evidence location:**
- **Checks:**
  - [ ] Counsel approved the recording-consent wording and scope of consent.
  - [ ] Counsel approved the report scope disclosure and recording disclosure.
  - [ ] Counsel/product owner approved the media-retention period and deletion wording.
  - [ ] Approved wording and version are recorded in the release evidence.
  - [ ] The vertical pack no longer has an unreviewed placeholder status before trial capture is enabled.
- **Notes:**

### 4. Backups and restore drill

- [ ] **Result:** `PENDING`
- **Owner:**
- **Date (UTC):**
- **Evidence location:**
- **Checks:**
  - [ ] Render daily backup / point-in-time recovery is enabled for the staging or pilot database as applicable.
  - [ ] Backup retention is recorded.
  - [ ] A named restore owner and escalation contact are recorded above.
  - [ ] A restore drill completed successfully into an isolated target.
  - [ ] The drill restored representative workspace, visit, evidence-chain, report, and delivery-state data.
  - [ ] The restored application passed `/ready` and a read-only verification.
- **Notes:**

### 5. Fresh sign-in after auth-session migration

- [ ] **Result:** `PENDING`
- **Owner:**
- **Date (UTC):**
- **Evidence location:**
- **Checks:**
  - [ ] Every pilot device performed a fresh sign-in after the auth-session migration; do not reuse pre-migration local credentials.
  - [ ] Access tokens expire after 15 minutes and refresh does not extend the absolute 30-day session expiry.
  - [ ] Using a fresh sign-in/session, successful online logout revokes the server-side session before local credentials are cleared; the revoked session cannot use an otherwise unexpired access token.
  - [ ] Using a separate fresh sign-in/session, simulate an offline/network failure during logout and verify local credentials still clear.
  - [ ] Using a third fresh sign-in/session, simulate a non-success HTTP response during logout and verify local credentials still clear.
  - [ ] For each failed revocation case, record that the remote session may remain live until its absolute 30-day expiry, plus the pilot risk owner and mitigation in Notes.
  - [ ] No refresh token or credential value was recorded in the evidence.
- **Notes:**

### 6. Real English AI pipeline validation

- [ ] **Result:** `PENDING`
- **Owner:**
- **Date (UTC):**
- **Evidence location:**
- **Checks:**
  - [ ] One representative English showing recording completed in staging.
  - [ ] Deepgram transcription completed with timed transcript segments.
  - [ ] Anthropic zone detection, observation extraction, and report generation completed.
  - [ ] Every sampled observation links to its transcript segment, raw media, timestamps, model, prompt version, confidence, and review status.
  - [ ] Voice-tag links resolve only within the configured maximum forward gap; long-silence and post-final tags remain unresolved.
  - [ ] From the repository root, replace the visibly invalid placeholder with the staging Visit UUID, then run:
    ```sh
    cd backend
    VISIT_ID='REPLACE_WITH_STAGING_VISIT_UUID'
    uv run python scripts/ai_cost_report.py --visit-id "$VISIT_ID"
    ```
    Require the output to identify that same Visit UUID and contain its recorded token usage and estimated cost result; attach the output as evidence.
- **Notes:**

### 7. Stripe test-mode billing

- [ ] **Result:** `PENDING`
- **Owner:**
- **Date (UTC):**
- **Evidence location:**
- **Checks:**
  - [ ] A new staging workspace completed the 14-day trial setup.
  - [ ] Test-mode Checkout redirected successfully.
  - [ ] Signed `checkout.session.completed` activated the expected entitlement.
  - [ ] Duplicate webhook delivery was idempotent and did not duplicate state or charges.
  - [ ] Subscription update and deletion events produced the expected entitlement state.
  - [ ] Customer-portal redirect succeeded.
- **Notes:**

### 8. SMTP, private report delivery, and delivery status

- [ ] **Result:** `PENDING`
- **Owner:**
- **Date (UTC):**
- **Evidence location:**
- **Checks:**
  - [ ] A staging email was delivered through the configured SMTP provider.
  - [ ] The report remained private and its share link opened only with the intended token.
  - [ ] PDF rendering completed and the delivered PDF was inspected.
  - [ ] Delivery status, provider message ID, and any retry/outcome state were recorded.
  - [ ] The share link was revoked and the revoked URL returned HTTP 404.
  - [ ] The report was explicitly confirmed by the agent before any delivery action.
- **Notes:**

### 9. Private-bucket CORS

- [ ] **Result:** `PENDING`
- **Owner:**
- **Date (UTC):**
- **Evidence location:**
- **Checks:**
  - [ ] The exact staging dashboard origin can upload through a presigned URL.
  - [ ] The preflight response allows only the configured dashboard origin, required method, and `Content-Type` header.
  - [ ] An unrelated origin is rejected and receives no allow-origin response.
  - [ ] Media and branding buckets remain private; no public bucket policy was introduced.
- **Notes:**

### 10. Physical-device airplane-mode capture and recovery

- [ ] **Result:** `PENDING`
- **Owner:**
- **Date (UTC):**
- **Evidence location:**
- **Device / OS:**
- **Checks:**
  - [ ] A development build was tested on a physical iOS or Android device.
  - [ ] Online sign-in, consent, showing start, audio, two voice tags, two photos, and video succeeded.
  - [ ] Airplane mode during capture preserved elapsed time and all local media after ending and force-quitting.
  - [ ] Reopening an unfinished showing recovered audio without losing the prior capture.
  - [ ] Restoring connectivity resumed sync without duplicate media or premature processing.
  - [ ] Offline report access remained read-only and did not offer edit, confirm, or share actions.
  - [ ] Rejected media was visible to the agent and did not silently disappear.
- **Notes:**

### 11. Workspace isolation

- [ ] **Result:** `PENDING`
- **Owner:**
- **Date (UTC):**
- **Evidence location:**
- **Checks:**
  - [ ] Two independent staging users/workspaces were created.
  - [ ] Workspace B could not list, read, edit, share, or deliver Workspace A's subjects, contacts, visits, media, reports, or markers.
  - [ ] Cross-workspace resource access returned the documented not-found behavior rather than leaking existence.
  - [ ] Stripe webhook workspace metadata and authenticated resource paths remained workspace-scoped.
- **Notes:**

### 12. Two-week controlled pilot

- [ ] **Result:** `PENDING`
- **Owner:**
- **Date (UTC):**
- **Evidence location:**
- **Pilot dates:**
- **Participants:**  `PENDING` — target 3–5 active buyer's agents
- **Checks:**
  - [ ] Each participant completed the fresh-sign-in gate before the first trial showing.
  - [ ] The pilot ran for two weeks with an incident and feedback log.
  - [ ] Weekly showing capture rate was measured against the target of at least 80%.
  - [ ] Client Reports Delivered and report-send rate were recorded as the primary trust signals.
  - [ ] At least three participants' willingness to continue was recorded.
  - [ ] Real willingness to pay after trial was recorded separately from hypothetical interview feedback.
  - [ ] Consent, retention, AI quality, delivery, and offline incidents were reviewed before the final decision.
- **Notes:**

## Final decision

### Go/no-go approval

- [ ] **Decision:** `PENDING` — `GO` / `NO-GO`
- **Decision owner:**
- **Decision date (UTC):**
- **Evidence location:**
- **Blocking failures or accepted exceptions:**
- **Reason for decision:**

### Rollback and incident readiness

- [ ] Rollback owner and contact are recorded in Run metadata.
- [ ] Incident lead and contact are recorded in Run metadata.
- [ ] The last known-good commit and deployment rollback procedure are recorded.
- [ ] The team knows how to disable new trial capture without deleting queued local captures.
- [ ] The team knows how to revoke affected auth sessions, disable sharing, and preserve evidence for investigation.
- [ ] Customer communication owner and escalation path are recorded.

**Final notes:**
