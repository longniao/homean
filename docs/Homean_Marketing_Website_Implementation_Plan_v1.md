# Homean Marketing Website — Implementation Plan v1

**Status:** Approved for implementation; public launch remains gated by counsel review
**Date:** August 15, 2026
**Audience:** Engineering, design, product, pilot operations

## 1. Decision

Build a small, English-only marketing website for recruiting and supporting Homean's
controlled Phase 1 pilot.

This is a go-to-market asset, not a new product surface. It does not change the frozen
MVP, introduce buyer self-tour, publish showing reports, create a marketplace, or begin
the buyer-led SEO strategy. The current product remains a private showing-report tool
for individual buyer's agents.

The intended domain split is:

- `homean.com`: public marketing website.
- `app.homean.com`: authenticated dashboard.
- The existing backend and mobile application remain unchanged.

The website may be implemented and previewed before counsel approval, but it must not be
promoted to the public production domain until the public recording, disclosure, privacy,
and retention wording has been approved.

## 2. Governing product boundaries

The website must follow these sources, in priority order:

1. `Homean_Product_Document_v1.1.md`
2. `Homean_Technical_Architecture_v1.1.md`
3. `Homean_Full_Feature_Roadmap_v1.2.md`
4. `Homean_Pilot_Acceptance_Checklist.md`

`Buyer_Self_Tour_Mode.md` and `Homean_Buyer_Led_SEO_Strategy.md` are unapproved future
hypotheses. They must not supply the v1 website's audience, navigation, claims, or calls
to action.

### In scope

- Explain the current product to buyer's agents.
- Establish trust before a demo or pilot conversation.
- Show the capture, review, and delivery workflow.
- Invite suitable buyer's agents to request pilot access.
- Link existing users to the authenticated application.
- Provide accurate privacy and product-principle information without claiming legal or
  regulatory approval.

### Out of scope

- Buyer-facing acquisition or self-tour messaging.
- Public reports, searchable property content, or a marketplace.
- Pricing claims before willingness-to-pay validation.
- Customer logos, testimonials, usage totals, or performance claims without evidence.
- A blog, CMS, programmatic SEO, comparison pages, or downloadable lead magnets.
- A lead database, new backend endpoint, CRM integration, analytics tracker, cookies, or
  embedded third-party forms.
- Publishing counsel-pending consent, disclosure, or retention language as approved law.

## 3. Success criteria

The first release succeeds when:

- A buyer's agent can understand the product, audience, workflow, and pilot status in
  under one minute.
- The primary call to action opens a pre-addressed email requesting pilot access; the
  site has no web form or account creation.
- Existing users can reach the dashboard through a clearly labeled sign-in link.
- The page works at 320 px through large desktop widths, with keyboard navigation,
  visible focus, semantic landmarks, and reduced-motion support.
- Metadata, canonical URL, sitemap, robots file, and social preview are truthful and do
  not expose unapproved claims.
- Tests, lint, type checking, production build, and credential-free deployment validation
  pass in CI.

Pilot recruitment and downstream product success continue to be measured by the product
document's metrics, especially Client Reports Delivered. Page traffic is not a product
validation metric.

## 4. Architecture

Create a separate `marketing/` application rather than moving or weakening the dashboard's
authenticated `/` route.

- Next.js 15 App Router with strict TypeScript.
- Tailwind CSS using the repository's existing toolchain conventions.
- Static export through `output: "export"`; no application server is required.
- Render static-site deployment, represented in `infra/render.yaml` and validated by the
  repository's release tooling.
- No backend dependency and no paid-provider calls.
- No runtime secrets. Public build-time values are documented in `marketing/.env.example`:
  - `NEXT_PUBLIC_SITE_URL`
  - `NEXT_PUBLIC_APP_URL`
  - `NEXT_PUBLIC_PILOT_EMAIL`
  - `NEXT_PUBLIC_SITE_INDEXABLE` (defaults to `false` until counsel approves public launch)

The checked-in Render Blueprint leaves the site URL and pilot email as externally
provisioned values (`sync: false`) and derives the app URL from the dashboard service.
Those values must be provisioned before deployment; they are not assumed by the Blueprint.
- All user-facing strings live in one typed content module or English message catalog so
  future localization does not require searching component markup.

Official implementation references:

- Next.js static export: <https://nextjs.org/docs/app/guides/static-exports>
- Render Blueprint specification: <https://render.com/docs/blueprint-spec>
- Render static sites: <https://render.com/docs/static-sites>

## 5. Information architecture and copy

### Header

- Homean wordmark and accessible home link.
- Anchors to `How it works`, `For agents`, and `Trust`.
- Secondary `Sign in` link to `NEXT_PUBLIC_APP_URL`.
- Primary `Request pilot access` action.

### Hero

- Primary message: **Turn every showing into a professional client report.**
- Explain that Homean lets a buyer's agent capture a walkthrough once, review the
  structured draft, and deliver a polished report.
- Show a code-native product composition: capture timeline, evidence-linked observation,
  and client report. Mark all sample content as illustrative.
- Avoid unsupported promises such as perfect accuracy, guaranteed time savings, legal
  compliance, or replacing the agent's judgment.

### Problem and outcome

- Show the scattered current workflow: photos, voice notes, memory, and follow-up texts.
- Contrast it with one private, reviewable showing record.
- Keep the framing on agent professionalism and client service, not consumer pressure on
  agents.

### How it works

1. Capture naturally on the mobile app, including offline conditions.
2. Review the AI-organized draft and its evidence in the dashboard.
3. Confirm and deliver a private report to the client.

Explicitly state that AI output is a draft and nothing is delivered without the agent's
confirmation.

### Product proof

- Use a fictional, clearly labeled sample property.
- Demonstrate transcript evidence, photos, room observations, review state, and report
  delivery without implying the sample is a real customer record.
- Do not reproduce private data from development, staging, or a pilot.

### Trust principles

- Private by default.
- Agent-reviewed before delivery.
- Evidence remains connected to source media.
- Offline-first capture protects the field workflow.
- Do not use words such as `compliant`, `legally protected`, or `counsel approved` until
  that approval has actually been recorded.

### Pilot call to action

- State that Homean is preparing a small pilot for active buyer's agents.
- CTA uses a `mailto:` link built from `NEXT_PUBLIC_PILOT_EMAIL`, with a short prefilled
  subject and body.
- Do not create an in-site form or silently collect visitor information.
- Keep unrestricted product signup out of the primary acquisition path.

### FAQ and footer

Answer only high-confidence questions:

- Who is Homean for?
- Does Homean send AI output automatically?
- Are reports public?
- What happens without connectivity?
- How can an agent join the pilot?

Footer includes sign in, pilot email, privacy summary, and a pilot-stage statement.

## 6. Visual direction

Use an **editorial field dossier** direction: the precision of an agent's property file
combined with the warmth of a well-designed home journal.

- Warm mineral-paper background, deep evergreen ink, charcoal text, and one restrained
  clay or safety-orange accent.
- Characterful editorial display typography paired with a calm, highly legible body face.
- Asymmetric grids, evidence tabs, measured rule lines, timestamp details, and subtle
  floor-plan geometry.
- One coordinated entrance sequence and purposeful hover/focus states; respect
  `prefers-reduced-motion`.
- Use CSS, HTML, and local SVG geometry for the product composition. Do not add stock
  property photography or generic AI imagery merely to fill space.
- Avoid purple gradients, glassmorphism, generic SaaS card grids, invented dashboards,
  oversized rounded pills everywhere, and visual claims unsupported by the real product.

The marketing site should feel related to the dashboard's evergreen brand without copying
the authenticated workspace layout.

## 7. Required implementation files

The exact split may change during implementation, but the deliverable should include:

- `marketing/app/` routes, metadata, sitemap, robots, and global styles.
- Reusable components for navigation, product composition, workflow, trust, FAQ, and CTA.
- A typed English content source.
- `marketing/public/` assets that contain no customer data and no stale `K` branding.
- `marketing/.env.example` and `marketing/README.md`.
- Strict TypeScript, ESLint, Tailwind, test, and build configuration.
- A lockfile committed with the application.
- A dedicated marketing CI job.
- Render static-site configuration and any validator updates/tests required by the new
  service.

## 8. Testing and acceptance

Automated checks must cover:

- Header navigation, sign-in URL, and pilot email CTA.
- The agent-confirmation and private-by-default statements.
- No unresolved tag, broken internal anchor, or placeholder domain in rendered copy.
- Metadata and static routes build successfully.
- Responsive layout has no known overflow at 320 px.
- Reduced-motion behavior is present.
- Render Blueprint validation recognizes the marketing static site and publish directory.

Required commands:

```sh
cd marketing
npm ci
npm audit --audit-level=high
npm test
npm run typecheck
npm run lint
npm run build
```

Then run the repository's credential-free release preflight or the relevant structural
subset. Do not deploy, change DNS, submit forms, send email, or call paid services during
tests.

## 9. Delivery sequence

1. Scaffold the static application and its tests.
2. Implement the page structure and externalized English content.
3. Execute the visual direction and responsive/accessibility pass.
4. Add metadata, sitemap, robots, and truthful social-preview treatment.
5. Integrate CI and Render Blueprint validation.
6. Run focused and full relevant checks.
7. Review the complete diff for product-scope and claim accuracy.
8. Commit only after independent review.
9. Preview in staging.
10. Publish to `homean.com` only after counsel approves the public wording and the pilot
    owner records a go decision.

## 10. Definition of done

- The marketing site is a separate static application and does not alter dashboard auth.
- Copy is English-only, agent-facing, truthful, and consistent with the frozen Phase 1
  product.
- Buyer self-tour and buyer-led SEO concepts do not appear.
- The site has no web form or account creation; the pilot CTA opens a pre-addressed
  email link.
- The primary CTA requests pilot access by email; sign in remains available but secondary.
- Accessibility, reduced motion, metadata, tests, CI, build, and deployment validation pass.
- Counsel-pending wording remains visibly gated from public launch.
- No unrelated files, secrets, generated build output, or user-owned documents are
  committed.
