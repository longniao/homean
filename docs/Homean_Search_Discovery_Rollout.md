# Homean search discovery rollout

Implemented September 10, 2026 (UTC).

## Public discovery surface

Six canonical, statically rendered pages are published on https://homean.com/:

- `/`
- `/how-it-works/`
- `/resources/`
- `/resources/showing-report-template/`
- `/resources/sample-showing-report/`
- `/resources/home-comparison-worksheet/`

The resource pages include editorial content, print styles, related links, unique titles/descriptions/canonicals, and Article structured data matching the visible content. The two blank templates have editable text downloads. The sample is explicitly fictional. Availability copy distinguishes the dashboard from AI processing/mobile capture still under validation.

Production indexing is enabled in `marketing/.env.production`. `robots.txt` permits search crawlers including OAI-SearchBot, blocks GPTBot separately, and declares the sitemap. This allows discovery; it does not guarantee indexing, rankings, or ChatGPT citations. No special AI-only schema or llms.txt is required for this rollout.

The dashboard has noindex/nofollow metadata. Backend shared reports retain their existing noindex/nofollow/noarchive headers. The marketing workers.dev alias has noindex/nofollow response headers. Customer records, bearer links, and recordings are not in the public sitemap.

## Measurement

Public browser events increment daily aggregate counters in Cloudflare D1 database `homean-marketing-metrics`, binding `MARKETING_METRICS`. This is separate from the Mac mini application backend and contains no customer records.

Stored dimensions: UTC day, allowlisted event, allowlisted public path, broad referral category, count. Events: page_view, signup_click, download_resource, print_resource. Sources: direct, google, bing, chatgpt, internal, other. No full URLs, query strings, worksheet contents, user IDs, email addresses, or IP addresses are stored in this table. Browser collection honors DNT and Global Privacy Control and excludes preview hosts.

These are activity counts, not unique people, verified conversions, or attribution of completed signups. Counts may include bots, repeats, and deployment smoke tests; blockers and privacy settings reduce coverage. Reports and product activation are not instrumented by this marketing collector.

Read counters from `marketing/`:

```sh
npx wrangler d1 execute homean-marketing-metrics --remote --command "SELECT day,event,path,source,total FROM daily_metrics ORDER BY day DESC, event, path"
```

Deployment: `npx wrangler d1 migrations apply homean-marketing-metrics --remote`, then `npm run cf:deploy`. Rerun `npx wrangler types --env-interface Env` after binding changes. D1 replaced an attempted Analytics Engine integration because the account's deployment API continued to reject Analytics Engine access after its setup wizard; no production code depends on Analytics Engine.

## Search engine setup

Google Search Console URL-prefix property `https://homean.com/` was verified with a public HTML meta tag. Keep the tag in the root metadata to retain verification. The sitemap was submitted. Initial processing reported that it could not be read; the stored homepage crawl was September 4 and still showed the previous robots.txt block. The live test also reported the robots block. The robots report confirmed a cached 27-byte file last fetched August 29. Google accepted a robots.txt recrawl request; processing and sitemap re-read remain pending. The currently served file permits crawling. Do not report the site as indexed until Google confirms it.

Bing submission is pending approval to use the existing Google identity to sign in to Bing Webmaster Tools. Automatic approval review rejected that cross-service sign-in. Do not work around it or import unrelated Search Console properties.

## Validation

- Marketing: 22 tests, TypeScript, ESLint, static production build.
- Dashboard: 79 tests, TypeScript, deployment build.
- Live HTTP: six public pages return 200 with index/follow and self-canonical URLs; one H1 per page; sitemap and both text downloads return 200.
- Requests with Googlebot, bingbot, and OAI-SearchBot user-agent strings return 200. This is a request check, not proof of access from every crawler IP or guaranteed inclusion.
- Dashboard login returns noindex/nofollow; marketing preview host returns noindex/nofollow.
- Production browser rendering, resource navigation, mobile resource index, and aggregate database writes checked after fixing a client configuration import.

## Next growth work

Use Search Console to choose future topics from actual impressions and queries. Start with the three useful resources before expanding into more pages. Improve examples using reviewed pilot feedback; publish real case studies only with permission and evidence. Track whether resource visitors become active agents and whether reports help buyers compare homes. Do not fabricate testimonials, customer results, local market expertise, or hundreds of thin location pages.

References: [Google AI features and SEO](https://developers.google.com/search/docs/appearance/ai-features), [OpenAI crawlers](https://developers.openai.com/api/docs/bots), [Google sitemaps](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap).

## Deployed versions

- Marketing: `4f29887b-1a06-4e7e-82e3-1727f7e7977d`
- Dashboard: `33fbbd2b-0960-45c6-8f90-6ca567f86b54`
