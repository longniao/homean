# Kawu Capture

Expo SDK 57 managed-workflow app for capture-only real-estate showing visits. Editing remains in the Kawu dashboard.

## Local setup

1. Copy `.env.example` to `.env` and set `EXPO_PUBLIC_API_URL` to an API URL reachable from the device. `localhost` does not refer to the development computer on a physical phone.
2. Run `npm install` and `npm start`.
3. Use a development build for background audio behavior. Expo Go can exercise screens and queue logic, but native background modes require the config plugins in `app.json` to be compiled into the app.

Audio files are recorded directly into the app document directory. Photos are copied from camera cache into the document directory before being queued. JWTs are stored in SecureStore; capture metadata, upload state, retry times, and voice-tag offsets are stored in SQLite.

## Sync semantics

The durable queue creates the remote showing, presigns each media item, uploads it, calls `complete`, and only calls `finish` after every media item completes. An interrupted PUT resumes from its persisted step by safely retrying the same presigned PUT; the current backend does not expose multipart byte-range upload APIs.

Property and client selection are optional during capture. Subject-less drafts sync and process normally; a property must be attached in the desktop dashboard before confirmation and delivery.

Voice tags are stored locally with exact offsets. The current media API accepts only audio, photo, and video and has no marker metadata endpoint, so marker rows remain durable local metadata rather than being disguised as empty media.

## Manual airplane-mode acceptance test

Use a development build on a physical iOS or Android device.

1. Sign in while online. From Home, select a client/property or type an address, then tap **Begin recording**.
2. Record for at least 30 seconds. Add two voice tags and take two photos at visibly different elapsed times.
3. Enable airplane mode while recording. Continue for another 30 seconds, take another photo, and end the showing.
4. Verify Home shows the visit as **Local** or **Needs retry**, and that force-quitting/reopening the app preserves the visit and its captured elapsed time/media.
5. Start another recording, force-quit without tapping End, reopen, and verify the recovered recording offers **Resume recording**. Resume, add media, then end it.
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
