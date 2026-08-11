# Homean — Full Project Plan v1 (All Phases)

> Companion to: `Homean_Full_Feature_Roadmap_v1.2.md` (what & why) and
> `Homean_Build_Plan_v1.md` (Phase 1 execution detail, milestones M0–M7).
>
> This document is the **complete engineering plan across all four phases** — Phase 1 MVP
> through the Phase 4 network hypothesis. Only Phase 1 is scheduled for development now.
> Phase 2+ milestones exist so you can see the whole arc, estimate long-term effort, and
> verify that Phase 1 architecture decisions actually carry the later phases. Their Codex
> prompts are **drafts**: revise them against validation learnings before use.
>
> **Rule inherited from the roadmap: milestones do not start on a calendar — they start
> when their gate passes.**

------------------------------------------------------------------------

## Gate map (what unlocks what)

| Gate | Evidence required | Unlocks |
|---|---|---|
| **G1** — H1/H2 validated | ≥80% of showings recorded; healthy Client-Reports-Delivered rate; ≥3 trial agents continue & show real willingness to pay | Phase 2A (M8–M11) |
| **G2** — link-data signal | Share-link open/engagement data (built in M4) shows the simple link is *insufficient* for buyers | Phase 2B full Buyer Portal (M12). If links suffice → **skip/defer M12** |
| **G3** — sharing intent | Phase 2 stable + specific agents *volunteer* to share semi-publicly | Phase 3 experiment (M13) |
| **G4** — H3+H4 validated | M13 shows real sharing behavior AND shared content is genuinely used by buyers | Phase 4 evaluation (M14) — evaluation, not automatic build |

Milestone estimates below assume 1–2 engineers + Codex; treat as rough sizing for planning,
not commitments.

------------------------------------------------------------------------

## Phase 1 — Showing Intelligence (M0–M7) — ACTIVE

Fully specified with Codex prompts in `Homean_Build_Plan_v1.md`. Summary:

| M | Scope | Est. |
|---|---|---|
| M0 | Monorepo, docker-compose, CI, AGENTS.md | 2–3 d |
| M1 | Generic schema + migrations, auth, User/Workspace graph, real_estate vertical pack | 1 wk |
| M2 | Contacts/properties, visit lifecycle, presigned media capture API | 1 wk |
| M3 | AI pipeline: Deepgram STT → zones → evidence-chained observations → draft report (Claude) | 1.5–2 wk |
| M4 | Review/edit APIs, confirm gates, branding, HTML/PDF, share links + open tracking, email | 1–1.5 wk |
| M5 | Web dashboard: full workspace, report editor, transcript playback, compare view | 2–3 wk |
| M6 | Expo mobile capture app, offline-first sync | 2–3 wk |
| M7 | Stripe (14-day trial), hardening, consent groundwork, deploy | 1–1.5 wk |

**Phase-1 architecture already pre-pays for later phases** — verify these survive code review,
because every later milestone leans on them:

- `Workspace`/`Membership`/`ProfessionalProfile` split → M8 teams is UI + invitations, no migration
- Key-based i18n + `Workspace.language` + prompt `output_language` param → M9 languages
- Share-link open tracking → the G2 decision data for M12
- Observation edit/dismiss/confirm records + `pipeline_runs` → AI quality loop (continuous track)
- Generic Subject/Zone/Observation + vertical YAML → M14's second-vertical option
- Report content as structured JSONB with per-bullet observation ids → M12 buyer interactions & M13 redaction

------------------------------------------------------------------------

## Phase 2A — Team Collaboration, Languages, Integrations (M8–M11) — GATED ON G1

### M8 — Team workspaces (roadmap items 26–29)

Multi-member workspaces: invitations, roles, shared records, team branding.

**Draft Codex prompt:**

```
[Global Context Prompt from AGENTS.md]

Task: Team collaboration on the existing Workspace/Membership foundation.

1. Roles: membership.role (owner | admin | member). Existing solo users become owner via
   migration. Permission matrix (enforced in services, not routers):
   - member: full CRUD on own showings/clients; read team property history (see 4)
   - admin: + manage members, team branding, all showings read; edit only with explicit
     per-showing reassignment
   - owner: + billing, workspace deletion
2. Invitations: POST /team/invites (email, role) -> tokenized email; accept flow joins the
   existing user or routes through signup; invites expire in 7 days, revocable. Seat count
   surfaced for M11 billing changes.
3. Ownership & visibility: visits/contacts/subjects keep created_by; list endpoints gain
   scope=mine|team filters. Default remains "mine" everywhere - collaboration is opt-in
   visibility, consistent with the private-by-default principle.
4. Team property history (roadmap 29): on a subject detail, members see *metadata* of other
   members' visits to the same subject (date, agent, status) and can request/open the full
   report only if its creator enabled team_shared on that visit (per-visit toggle,
   default off).
5. Team branding: workspace_branding becomes team-level with per-member contact overrides;
   report renderer resolves member override -> team default.
6. Dashboard: /team settings page (member list, invites, roles), scope toggle on home,
   team-shared toggle on showing page.
7. Tests: permission matrix table-driven tests; invite lifecycle; the privacy default
   (nothing visible team-wide without explicit toggles).
```

Est. 2 wk.

### M9 — Multi-language enablement (roadmap 31c–31e; first language: Chinese)

Activates the i18n groundwork. Three decoupled dimensions: recording language, UI language,
report language.

**Draft Codex prompt:**

```
[Global Context Prompt from AGENTS.md]

Task: Turn on multi-language. English remains default; add zh (Mandarin) as the first
additional language end-to-end.

1. Config model: workspace.ui_language; per-visit recording_language (default from
   workspace, settable at capture time); per-report output_language (report can be
   re-generated in another language for the same visit).
2. STT: TranscriptionProvider.transcribe already takes language - verify Deepgram zh
   support quality; add provider fallback config per language (e.g. alternative provider
   for zh if Deepgram underperforms; keep the interface, add impl).
3. Pipeline: prompts already parameterize output_language. Add: zone/category display
   labels per language in the vertical pack YAML (labels: {en: ..., zh: ...}); report
   templates per language where layout differs. Extraction runs in the recording
   language; report generation renders in output_language (cross-language: transcript zh
   -> report en and vice versa must both work).
4. Multi-version reports (roadmap 31e): reports table gains language; a visit can hold one
   report per language; share links point to a specific language version; "generate in
   another language" action re-runs only the report step against confirmed observations.
5. UI: dashboard + mobile language switcher; translate messages catalogs to zh (machine
   draft, marked for native review); date/number locale formatting.
6. WeChat channel evaluation (roadmap 31d): no API integration - verify share-link pages
   render correctly in WeChat's in-app browser (viewport, og tags, no blocked assets) and
   add a "copy link for WeChat" affordance. Document findings.
7. Tests: cross-language pipeline over fakes; per-language report versions; catalog
   completeness check in CI (no missing keys per locale).
```

Est. 2 wk (+ native-speaker review of zh output quality — human task, not Codex).

### M10 — External integrations (roadmap 30, 31, 31a, 31b)

**Order by user demand from Phase 1 feedback — do not build all four speculatively.**

**Draft Codex prompt (per integration; run separately):**

```
[Global Context Prompt from AGENTS.md]

Task: Integration framework + the <NAME> integration.

1. (First integration only) Framework: integrations table (workspace_id, provider,
   status, encrypted OAuth tokens, settings JSONB), generic OAuth2 connect/disconnect
   flow, per-provider sync job pattern (Celery beat), sync_log table, /settings/
   integrations dashboard page with connect buttons and last-sync status.
2. Providers, in likely priority order (confirm against user interviews):
   a. CRM (Follow Up Boss first): two-way contact sync (their contacts <-> our Contacts,
      idempotent matching by email/phone, conflict = most-recent-wins with log); push a
      timeline event to the CRM when a report is sent.
   b. Calendar (Google): read showing appointments; one-click "start showing from event"
      on mobile (pre-fills property from event location, client from attendee).
   c. Email (Gmail send-as): report emails sent via the agent's own mailbox.
   d. Cloud storage (Google Drive): nightly archive of confirmed report PDFs + originals
      to a Homean folder.
3. Every provider behind an interface with a fake; no provider SDK types leak past the
   integration module. Webhooks where offered; polling fallback.
4. Tests: sync idempotency, token refresh, disconnect cleanup, matching conflicts.
```

Est. 1–1.5 wk per integration.

### M11 — Usage analytics & seat billing (roadmap 35 + billing evolution)

**Draft Codex prompt:**

```
[Global Context Prompt from AGENTS.md]

Task: Analytics for agents/teams + seat-based billing.

1. Metrics service over existing data (visits, report_sends, report_share_views):
   per-agent and per-team weekly/monthly: showings recorded, reports generated, reports
   sent (North Star), link open rate, median time-to-send. Materialized into a daily
   rollup table; timezone-aware.
2. Dashboard /analytics: trend charts, team comparison (admin+ only), CSV export.
   These link-open numbers are the G2 decision input for the Buyer Portal - surface
   them prominently.
3. Billing: migrate Stripe to per-seat quantity on the workspace subscription; seat count
   = active memberships; proration on invite/remove; grandfather existing solo plans.
4. Voice-command extension groundwork (roadmap 36): define the tag grammar
   ("note:", "concern:", "follow up:") as vertical-pack config consumed by the extraction
   prompt - improves structured capture without new mobile UI.
```

Est. 1–1.5 wk.

------------------------------------------------------------------------

## Phase 2B — Buyer Portal (M12) — GATED ON G2

**Decision first**: M11's link-open data answers whether buyers need more than the share
link. If open rates are high and agents report no buyer friction → **defer/skip this
milestone entirely** (explicitly sanctioned by the roadmap).

### M12 — Buyer Portal (roadmap 32–34)

**Draft Codex prompt:**

```
[Global Context Prompt from AGENTS.md]

Task: Buyer-facing portal. Buyers see ONLY what their agent explicitly shared - the
private-by-default principle extends to buyers.

1. Buyer identity: separate buyer_users table (magic-link email auth only, no passwords);
   linked to Contact records by verified email. A buyer sees reports across agents only
   through per-report grants.
2. Sharing model: sending a report to a client (existing flow) now also creates a
   report_grant (contact_id, report_id, revocable). Portal home = list of granted
   reports, grouped by property, newest first.
3. Portal (dashboard/ app, /portal/* routes, separate auth context): report view
   (existing renderer), buyer-side comparison of their own granted reports (reuse the
   compare component), and per-observation reactions/comments (roadmap 33): interested /
   concerned / question + free text, visible to the agent on the showing page with
   notification (email + dashboard badge).
4. Offer-prep assist (roadmap 34): "Export for offer" - selected observations + photos
   compiled into a clean DOCX/PDF appendix via the existing renderer pipeline.
5. Agent controls: per-client portal enable/disable; revoking a grant removes access
   immediately.
6. Tests: grant scoping (buyer A never sees buyer B's or ungranted reports), magic-link
   expiry, comment notification flow, revocation.
```

Est. 2–2.5 wk.

------------------------------------------------------------------------

## Phase 3 — Controlled Sharing Experiment (M13) — GATED ON G3

Not a product launch: an instrumented experiment for volunteer agents, validating H4.

### M13 — Semi-public sharing (roadmap 37–42)

**Draft Codex prompt:**

```
[Global Context Prompt from AGENTS.md]

Task: Controlled semi-public sharing behind a per-workspace feature flag
(sharing_experiment), enabled manually for volunteer agents only. Default private is
untouched: every share is per-report, opt-in, twice-confirmed.

1. Feature flag infra (first use): workspace_flags table + backend guard + dashboard
   conditional UI.
2. Share flow on a confirmed report: "Share publicly" -> mandatory redaction step:
   client identity always stripped; toggles for exact address (street-only mode),
   agent identity (anonymous mode), photo inclusion (per-photo). Produces a NEW
   public_report snapshot (copy, not a view - later edits to the private report never
   leak). Then a consent screen (plain-language summary of what becomes visible) ->
   second confirm -> submitted_for_review.
3. Human review queue (roadmap 42): internal /admin/review app (simple, role-gated to
   Homean staff) to approve/reject with reason. Only approved snapshots go live at
   /p/{slug}. Takedown = immediate unpublish, hard-delete snapshot after 30 days.
4. Instrumentation (roadmap 40): views, dwell (beacon), referrer class, per-section
   engagement on public pages; per-agent share funnel (started -> redacted -> consented
   -> approved -> viewed). This is the H4 evidence - build the metrics before the
   feature is offered to anyone.
5. Repeatable-property focus (roadmap 41): tag subjects with building/complex identifier
   (attributes.building_id, entered by agent); experiment dashboards segment by
   repeatable vs unique properties.
6. Tests: redaction completeness (snapshot contains zero contact PII by construction -
   test walks the snapshot JSON against forbidden fields), review-gate enforcement,
   takedown, flag-off invisibility.
```

Est. 2 wk + ongoing manual review operations.

------------------------------------------------------------------------

## Phase 4 — Buyer Intelligence Network (M14) — GATED ON G4 — OUTLINE ONLY

Deliberately **no Codex prompts**: if G4 passes, the right design will come from Phase 3
data, and anything written today would be fiction. Planning outline (roadmap 43–48):

| Workstream | Contents | Depends on |
|---|---|---|
| Public browse & search | Indexed public reports by property/neighborhood; SEO; buyer accounts from M12 | M13 snapshots at volume |
| Cross-agent aggregation | Same-property timelines across agents; entity resolution on subjects (address canonicalization becomes a real subsystem) | Data volume |
| Trust & verification | GPS proof-of-visit, recording-continuity signals, contributor reputation — mobile capture changes + fraud modeling | Legal/privacy review |
| Contributor economics | Revenue share on views/licensing; payout infra (Stripe Connect) | Business model validation |
| B2B data/API | Licensed access for data/AI companies; consent chain from agents | Contributor terms |
| Second vertical (optional, parallel) | Fill a new vertical YAML + prompts + report template + service layer; the architecture doc estimates 1–2 wk — decided by market signal, not architecture | Any phase |

Est. only if greenlit: a quarter-scale effort; re-plan from scratch at that point.

------------------------------------------------------------------------

## Continuous tracks (all phases, no gates)

| Track | Cadence | Contents |
|---|---|---|
| AI quality loop | Monthly from Phase 1 trial onward | Review agent edits vs AI output (data exists from M4); revise prompt templates; bump prompt_version; regression-check on a fixture set of recordings |
| Cost & model tuning | Monthly | `pipeline_runs` cost review; per-step model downgrades (`claude-sonnet-4-6` / `claude-haiku-4-5`) where quality holds; STT provider pricing review |
| Privacy/compliance | Each phase boundary | Consent flows (recording, then sharing), data deletion/export (buyer PII especially at M12), counsel review before M13 goes live |
| Platform upkeep | Ongoing | Expo/Next/FastAPI upgrades, backup restore drills, dependency audits |

------------------------------------------------------------------------

## How to use this plan

- **Now**: execute `Homean_Build_Plan_v1.md` (M0–M7) with Codex.
- **At each gate**: check the evidence in the gate map against Discovery/Experiment logs;
  only then promote the next milestone's draft prompt to a real one — expect to revise it
  against what validation taught you (screens, priorities, even whole milestones like M12
  may be cut).
- **For investors/partners**: this doc + the roadmap show the full product arc and rough
  effort; the gates show discipline. Phase 2–4 content is not a commitment and should not
  appear in customer-facing material.
