# Homean search discovery rollout

Implemented September 10, 2026 (UTC).

## Public discovery surface

Eight canonical, statically rendered pages are published on https://homean.com/:

- `/`
- `/how-it-works/`
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

Stored dimensions: UTC day, allowlisted event, allowlisted public path, broad referral category, count. Events: page_view, signup_click, download_resource, print_resource, comparison_view, print_comparison. Sources: direct, google, bing, chatgpt, internal, other. No full URLs, query strings, worksheet contents, user IDs, email addresses, or IP addresses are stored in this table. Browser collection honors DNT and Global Privacy Control and excludes preview hosts.

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

- Marketing: `6cbd60a9-6e5a-48d0-a02f-52ff3063b7eb`
- Dashboard: `33fbbd2b-0960-45c6-8f90-6ca567f86b54`
