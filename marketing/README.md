# Homean marketing site

The `marketing/` app is the public, English-only pilot website for Homean. It is a
separate Next.js 15 App Router application and does not share the dashboard’s
authenticated route. Pages are exported as static HTML. The comparison form keeps
notes in page memory; a Cloudflare Worker records allowlisted daily aggregate
marketing events in D1, without note contents or user identifiers. It does not use
the Mac mini application's database.

## Local development

```sh
cp .env.example .env.local
npm ci
npm run dev
```

The public build-time values are documented in `.env.example` and must be provisioned
before a real deployment:

- `NEXT_PUBLIC_SITE_URL` — canonical site and sitemap origin.
- `NEXT_PUBLIC_APP_URL` — authenticated dashboard URL used by the secondary sign-in link.
- `NEXT_PUBLIC_CONTACT_EMAIL` — public contact address shown in the footer.
- `NEXT_PUBLIC_SITE_INDEXABLE` — public-content indexing gate. Use `false` for
  nonpublic builds; `true` enables index/follow, allows search crawlers and keeps
  GPTBot independently blocked. It does not enable live-client capture.

Local development uses clearly non-production defaults when the first three values are
omitted. A production build fails fast unless all three are supplied and valid: the two
URLs must use `http` or `https`, and the pilot value must be an email address. CI uses
reserved `.invalid` values to exercise that production path without implying live
provisioning.

The Render Blueprint is an alternative deployment reference. The active public
site uses Cloudflare; see `wrangler.jsonc` and the rollout record below.

## Brand assets

Public brand language lives in `lib/brand.ts`; dashboard copy is externalized in
`../dashboard/messages/en.json`. The approved strategy is documented in
[`Homean_Brand_Strategy_v1.md`](../docs/Homean_Brand_Strategy_v1.md).

After editing `public/og.svg`, run `node scripts/render-social.mjs` from this
directory to regenerate the matching marketing and dashboard share images.

## Checks

```sh
npm audit --audit-level=high
npm test
npm run typecheck
npm run lint
npm run build
```

`npm run build` writes the static export to `out/`. Public resources are available;
live-client workflows still require the separate pilot acceptance checks.

## Cloudflare deployment

The static export is configured for Cloudflare Workers Static Assets. Supply all public
build-time values when previewing or deploying. Noncanonical preview hosts also
receive an HTTP noindex header from the Worker.

```sh
npm run cf:deploy
```

The checked-in `.env.production` contains Homean's non-secret public deployment values,
so canonical, Open Graph, sitemap, and cross-site links stay aligned with production.

The current indexable public deployment is <https://homean.com> and links to the
private dashboard at <https://app.homean.com>. The public sitemap has nine pages.

See [search discovery rollout](../docs/Homean_Search_Discovery_Rollout.md) for
release evidence and limits, and [owner TODO](../docs/Homean_Owner_TODO.md) for
account setup and decisions still needed. Keep `lib/public-pages.ts` synchronized
with public routes; it supplies sitemap dates and the measurement allowlist.
