# Homean search discovery rollout

Initial rollout September 10, 2026 (UTC). Latest website update September 22, 2026.

## Public discovery surface

Nine canonical, statically rendered pages are published on https://homean.com/:

- `/`
- `/how-it-works/`
- `/about/`
- `/resources/`
- `/resources/showing-report-template/`
- `/resources/sample-showing-report/`
- `/resources/home-comparison-worksheet/`
- `/resources/how-to-compare-homes-after-touring/`
- `/resources/what-to-write-after-a-showing/`

The resource pages include editorial content, print styles, related links, unique titles/descriptions/canonicals, and Article structured data matching the visible content. The two blank templates have editable text downloads. The sample is explicitly fictional. Availability copy distinguishes the dashboard from AI processing/mobile capture still under validation.

Production indexing is enabled in `marketing/.env.production`. `robots.txt` permits search crawlers including OAI-SearchBot, blocks GPTBot separately, and declares the sitemap. This allows discovery; it does not guarantee indexing, rankings, or ChatGPT citations. No special AI-only schema or llms.txt is required for this rollout.

The dashboard has noindex/nofollow metadata. Backend shared reports retain their existing noindex/nofollow/noarchive headers. The marketing workers.dev alias has noindex/nofollow response headers. Customer records, bearer links, and recordings are not in the public sitemap.

## Measurement

Public browser events increment daily aggregate counters in Cloudflare D1 database `homean-marketing-metrics`, binding `MARKETING_METRICS`. This is separate from the Mac mini application backend and contains no customer records.

Stored dimensions: UTC day, allowlisted event, allowlisted public path, broad referral category, count. Events: page_view, signup_click, download_resource, print_resource, comparison_view, print_comparison, comparison_tool_click, comparison_example, print_comparison_example. Sources: direct, google, bing, chatgpt, internal, other. No full URLs, query strings, worksheet contents, user IDs, email addresses, or IP addresses are stored in this table. Browser collection honors DNT and Global Privacy Control and excludes preview hosts.

These are activity counts, not unique people, verified conversions, or attribution of completed signups. Counts may include bots, repeats, and deployment smoke tests; blockers and privacy settings reduce coverage. Reports and product activation are not instrumented by this marketing collector.

Read counters from `marketing/`:

```sh
npx wrangler d1 execute homean-marketing-metrics --remote --command "SELECT day,event,path,source,total FROM daily_metrics ORDER BY day DESC, event, path"
```

Deployment: `npx wrangler d1 migrations apply homean-marketing-metrics --remote`, then `npm run cf:deploy`. Rerun `npx wrangler types --env-interface Env` after binding changes. D1 replaced an attempted Analytics Engine integration because the account's deployment API continued to reject Analytics Engine access after its setup wizard; no production code depends on Analytics Engine.

## Search engine setup

Google Search Console URL-prefix property `https://homean.com/` was verified with a public HTML meta tag. Keep the tag in the root metadata to retain verification. Google fetched the updated robots.txt after a recrawl request. Initial inspection tests still reported the old block, but a subsequent homepage indexing request succeeded: Google confirmed the URL was added to its priority crawl queue. This is an accepted indexing request, not confirmation that the page is indexed. The sitemap was resubmitted after that successful crawl validation. Google reports Success with all six public pages discovered. Actual indexing and rankings remain pending Google processing.

Bing submission is pending approval to use the existing Google identity to sign in to Bing Webmaster Tools. Automatic approval review rejected that cross-service sign-in. Do not work around it or import unrelated Search Console properties.

## Validation

- Marketing: 22 tests, TypeScript, ESLint, static production build.
- Dashboard: 79 tests, TypeScript, deployment build.
- Live HTTP: six public pages return 200 with index/follow and self-canonical URLs; one H1 per page; sitemap and both text downloads return 200.
- Requests with Googlebot, bingbot, and OAI-SearchBot user-agent strings return 200. This is a request check, not proof of access from every crawler IP or guaranteed inclusion.
- Dashboard login returns noindex/nofollow; marketing preview host returns noindex/nofollow.
- Production browser rendering, resource navigation, mobile resource index, and aggregate database writes checked after fixing a client configuration import.

## Next growth work

Use Search Console to choose future topics from actual impressions and queries. Measure the comparison tool and five resources before expanding into more pages. Improve examples using reviewed pilot feedback; publish real case studies only with permission and evidence. Track whether resource visitors become active agents and whether reports help buyers compare homes. Do not fabricate testimonials, customer results, local market expertise, or hundreds of thin location pages.

## Interactive comparison expansion

The existing worksheet URL now includes a free comparison tool for two or three homes. It keeps entered notes in browser memory only, supports editing and confirmed clearing, and presents a printable comparison. Refreshing clears entries. Unknown answers remain labeled, and the tool does not score homes or recommend a winner. Notes for an unnamed third home are retained with a fallback label.

Two supporting guides cover comparing homes after touring and writing a showing recap. Both are linked from the resource index and related-resource navigation and included in the eight-URL sitemap. Google's earlier six-page discovery count above predates this expansion; discovery of the new guides has not been confirmed.

Validation: 26 marketing tests and TypeScript checks pass. Production build includes ESLint. Both new guide URLs return 200 with their expected titles and canonical URLs. A filled desktop comparison was checked in the live browser, and its aggregate comparison_view event was confirmed in D1. Print invocation is unit-tested; visual print-preview and mobile checks remain pending because the Mac locked during browser verification.

References: [Google AI features and SEO](https://developers.google.com/search/docs/appearance/ai-features), [OpenAI crawlers](https://developers.openai.com/api/docs/bots), [Google sitemaps](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap).

## Deployed versions

- Marketing: `4a8e06ca-eb1e-4af3-ac53-7de86b67bff3` (September 22, 2026)
- Dashboard: `33fbbd2b-0960-45c6-8f90-6ca567f86b54`

## Public frontend design refresh

Replaced the overlapping legacy styles with one unified design system. The current palette uses soft white, charcoal, cool gray, and restrained blue accents; the user explicitly rejected green styling. The homepage now uses a shorter headline, a legible report preview, consistent section spacing, and restrained typography. Resource pages and the comparison tool share the same form, card, and reading styles. Mobile navigation remains available; comparison results have a keyboard-focusable horizontal scroll region and a small-screen swipe cue. The unsaved-entry notice remains visible, with full privacy details in a disclosure.

Validation: all 26 marketing tests pass, including palette contrast and comparison behavior. Production build, ESLint, and TypeScript pass. Browser checks covered the desktop homepage, deployed desktop comparison form, 390px mobile homepage/form/results, and absence of page overflow at that mobile width. The earlier mobile-check limitation is resolved; native print-preview verification remains outstanding.

## Resource usefulness and tool discovery

The homepage hero now links directly to the free comparison tool. Visitors can view a filled three-home fictional example and return to their original notes without replacement or mixing. The example is labeled on screen and in print; its views and print actions use separate aggregate event names from personal comparisons. No note contents are included in measurement.

The showing report template pairs all five steps with a filled editorial example in static HTML. The comparison page explains the fictional trade-offs in readable article content, and the showing recap guide adds a rough-note-to-recap example. These are teaching materials, not customer case studies, professional endorsements, or evidence from live AI trials. No new URLs were added; the public sitemap still contains eight pages.

Validation: 31 marketing tests, production build with lint and TypeScript, and desktop/mobile browser checks of the fictional comparison and paired template examples. Tests cover preserving private notes, explicit fictional labeling in printable content, the homepage tool link, and separate aggregate event acceptance. Native print-preview verification remains outstanding. Search impressions, indexing of the new guides, and real agent feedback require subsequent measurement; this release does not establish traffic gains.

## September 22: answer clarity, provenance and owner handoff

The [owner TODO](Homean_Owner_TODO.md) records credentials, business decisions,
physical-device participation, professional review, pilot recruitment and search
account tasks that need the owner's input. Website changes do not complete the
real AI, SMTP, billing or device acceptance gates.

All five existing resources now include a concise direct answer, three visible
question-and-answer pairs, a table of contents, breadcrumbs, an author link and
the substantive update date. These elements are present in static HTML and do not
depend on a browser interaction to reveal content. Related actions connect a
template to its example and a guide to its tool. The two resources discussing
inspection distinctions link to CFPB guidance with its U.S. scope clearly stated.

The new About page explains Homean's purpose, AI-assisted editorial preparation,
fictional examples, correction contact and current availability. It does not claim
a named professional reviewer, real customer outcomes or independent validation.
Homepage and workflow copy now distinguish free public resources from AI/mobile
capabilities that are still under acceptance.

Organization and WebSite structured data share stable identifiers; resource
Article markup includes the visible author/date and a matching BreadcrumbList.
Article social metadata includes dates and the existing PNG preview. The sitemap
and aggregate-event path allowlist now use one public-page inventory. Dates are
explicit editorial values, not build timestamps. Existing Google verification,
OAI-SearchBot allowance, separate GPTBot opt-out and private-app indexing boundaries
are preserved. No new tracking fields or personal-data collection were added.

Validation:

- All 35 marketing tests, ESLint, TypeScript and the static production build passed.
- All nine exported pages passed an HTML check for a single H1, self-canonical,
  indexability, valid JSON-LD and working internal links/fragments.
- Cloudflare deployment dry run and production deployment passed.
- All nine production URLs return 200 with matching canonicals and index/follow.
  The live sitemap contains nine URLs; an unknown resource returns 404.
- Googlebot, bingbot and OAI-SearchBot user-agent checks return 200 on the template
  page. These checks do not establish access from actual crawler IPs or indexing.
- Browser checks covered desktop and 390px mobile template layout, no horizontal
  page overflow at that width, the question-section anchor and the live About page.

Search Console indexing, ranking changes and ChatGPT citations were not verified
by this release. No new sitemap submission, Bing account setup, outreach or
recurring monitoring was performed. Next evaluate actual impressions/clicks and
aggregate resource use, then prioritize content from observed query demand.

References checked September 22:
[Google AI search guidance](https://developers.google.com/search/blog/2025/05/succeeding-in-ai-search),
[Article markup](https://developers.google.com/search/docs/appearance/structured-data/article),
[Breadcrumb markup](https://developers.google.com/search/docs/appearance/structured-data/breadcrumb),
[OpenAI crawler controls](https://developers.openai.com/api/docs/bots).
