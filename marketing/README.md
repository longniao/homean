# Homean marketing site

The `marketing/` app is the public, English-only pilot website for Homean. It is a
separate Next.js 15 App Router application and does not share the dashboard’s
authenticated route. The app is exported as static HTML and has no backend, analytics,
cookies, forms, or runtime secrets.

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
- `NEXT_PUBLIC_SITE_INDEXABLE` — publication gate. Keep `false` until counsel approves
  public launch wording; `true` enables index/follow metadata and an allow-all robots file.

Local development uses clearly non-production defaults when the first three values are
omitted. A production build fails fast unless all three are supplied and valid: the two
URLs must use `http` or `https`, and the pilot value must be an email address. CI uses
reserved `.invalid` values to exercise that production path without implying live
provisioning.

The checked-in Render Blueprint intentionally marks the site URL and pilot email as
`sync: false` and derives the app URL from the dashboard service. Provision the two synced
values in Render before a deployment; the Blueprint does not assume an unconfirmed domain
or inbox.

## Checks

```sh
npm audit --audit-level=high
npm test
npm run typecheck
npm run lint
npm run build
```

`npm run build` writes the static export to `out/`. Do not publish the site to the public
domain until the pilot owner records a go decision and counsel approves public recording,
disclosure, privacy, and retention wording.

## Cloudflare deployment

The static export is configured for Cloudflare Workers Static Assets. Supply all public
build-time values when previewing or deploying; keep the publication gate false until the
approval above is recorded.

```sh
npm run cf:deploy
```

The checked-in `.env.production` contains Homean's non-secret public deployment values,
so canonical, Open Graph, sitemap, and cross-site links stay aligned with production.

The current non-indexable Cloudflare deployment is <https://homean.com> and links to the
dashboard at <https://app.homean.com>.
