# Resend report email

Selected on 2026-09-22. Homean supports Resend through its existing email provider
interface; no database migration or new dependency is required.

## Production configuration

Set these variables only in the Mac mini's `backend/.env` (mode `0600`):

```dotenv
EMAIL_PROVIDER=resend
RESEND_API_KEY=
RESEND_FROM_EMAIL=reports@homean.com
RESEND_FROM_NAME=Homean
```

Create a sending-only API key restricted to the verified Homean domain. Add the
domain in Resend and apply the exact verification DNS records Resend supplies.
Do not overwrite unrelated DNS records. Never commit the key or paste it in chat.
Restart `homean_api` and `homean_worker` after changing configuration. Native
services load `backend/.env`; Docker Compose forwards these variables too.

Missing credentials fail delivery explicitly. There is no fallback to console or
another provider. `console` remains available for local development only.

## Delivery behavior

- Only an agent-confirmed report can reach the existing delivery service.
- Resend receives the private report link and a Base64-encoded PDF attachment.
- The persisted application message ID determines a stable idempotency key.
- Explicit rejections are retryable through the existing failed-send flow.
- Timeouts after connection, server failures, conflicts and malformed success
  responses retain `outcome_unknown`; they are not automatically resent. Resend
  retains idempotency keys for 24 hours, so that alone is not a permanent duplicate
  guarantee. Check Resend's log before resolving an uncertain delivery.
- A provider message ID records API acceptance, not inbox delivery. Bounce and
  delivery webhooks are not implemented; pilot acceptance must verify the inbox.
- Provider error bodies and API keys are not included in saved delivery errors.

## Acceptance still required

1. Configure the key and verify the sending domain.
2. Obtain the owner's explicit authorization for a specific test recipient.
3. Send one confirmed synthetic report, inspect the private link and PDF in the
   inbox, check Resend logs, and verify a second application send is blocked.
4. Record the result in the pilot acceptance checklist. Mock transport tests do
   not send real emails and do not establish domain verification or inbox arrival.

Sources: [Send email](https://resend.com/docs/api-reference/emails/send-email),
[idempotency](https://resend.com/docs/dashboard/emails/idempotency-keys).
