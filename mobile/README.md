# Kawu Capture

Expo SDK 57 managed-workflow app for capture-only real-estate showing visits. Editing remains in the Kawu dashboard.

## Local setup

1. Copy `.env.example` to `.env` and set `EXPO_PUBLIC_API_URL` to an API URL reachable from the device. `localhost` does not refer to the development computer on a physical phone.
2. Run `npm install` and `npm start`.
3. Use a development build for background audio behavior. Expo Go can exercise screens and queue logic, but native background modes require the config plugins in `app.json` to be compiled into the app.

On Android 13 (API 33) and later, Kawu requests notification permission before
preparing the recorder. This permission is required by the Expo Audio foreground
recording service; if it is denied, recording does not start and the app explains
why instead of attempting a recording that cannot remain active in the background.

Audio files are recorded directly into the app document directory. Photos and videos are copied from camera cache into the document directory before being queued. Each video is queued with the elapsed offset at which recording started. JWTs are stored in SecureStore; capture metadata, upload state, retry times, and voice-tag offsets are stored in SQLite.

## Sync semantics

The durable queue creates the remote showing, presigns each media item, uploads it, calls `complete`, and only calls `finish` after every media item completes. An interrupted PUT resumes from its persisted step by safely retrying the same presigned PUT; the current backend does not expose multipart byte-range upload APIs.

Property and client selection are optional during capture. Subject-less drafts sync and process normally; a property must be attached in the desktop dashboard before confirmation and delivery.

At showing start the agent must attest that they have consent to record. The boolean
`consent_ack` is persisted with the Visit and the report footer uses a counsel-review
placeholder disclosure; no legal language is intended by this product text.

Voice tags are stored locally with exact offsets and sync through the visit marker API after the remote visit exists. Each tag carries its local client id as an idempotency key, so retries after an ambiguous network failure return the same server marker instead of creating a duplicate. Marker acknowledgement is persisted before the showing can be finished.

Video capture is intentionally muted because the continuous `expo-audio` recorder remains the single source for showing audio and its evidence chain.

If the app is reopened with an unfinished showing, it first recovers the persisted
audio segment into the durable media queue and only then clears the recovery row.
The **Resume recording** action stays unavailable during that operation; ending the
showing also waits for recovery, so a fast tap cannot clear or lose the prior segment.

## Manual airplane-mode acceptance test

Use a development build on a physical iOS or Android device.

1. Sign in while online. From Home, select a client/property or type an address, then tap **Begin recording**.
2. Record for at least 30 seconds. Add two voice tags, take two photos, and record a short video at visibly different elapsed times.
3. Enable airplane mode while recording. Continue for another 30 seconds, take another photo, and end the showing.
4. Verify Home shows the visit as **Local** or **Needs retry**, and that force-quitting/reopening the app preserves the visit and its captured elapsed time/media, including the completed video.
5. Start another recording, force-quit without tapping End, reopen, and verify the recovered recording keeps **Resume recording** unavailable until recovery finishes. Resume, add media, then end it.
6. Disable airplane mode. Tap **Sync now** (pull-to-refresh currently triggers the same engine) or foreground the app.
7. Observe state advance through **Syncing**, **Processing**, and **Ready**. Force-quit once during upload and reopen; verify sync resumes without duplicate media records and processing begins only after all media completes.
8. Open the ready report. If backend guards pass, confirm and create a share link. If a sensitive item is pending, verify the app offers **Review on desktop** instead.

## Checks

```sh
npm run typecheck
npm run lint
npm test
npx expo-doctor
```
