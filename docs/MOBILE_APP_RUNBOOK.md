# Chicago District Explorer — Mobile App Runbook

How to turn the existing single-file web app into installable iOS/Android apps without forking the core logic. This is an operational runbook (setup once, repeat on each release), not an architecture doc — see [`BUILD_PLAYBOOK_1.md`](BUILD_PLAYBOOK_1.md) for how `index.html` itself is built.

## 0. Decide the approach first

The app is a single dependency-light `index.html` (Leaflet + fetch calls to public APIs, no build step, no framework, no login, no geolocation API use — selection is tap-on-map or address search). Three options, in order of effort:

| Option | Effort | What you get | When to pick it |
|---|---|---|---|
| **PWA (installable, no wrapper)** | Low | "Add to Home Screen" icon, offline shell via service worker, no app-store listing | Fastest path; good enough if store presence isn't required |
| **Capacitor wrapper (recommended)** | Medium | Real iOS + Android app store builds, native splash/icon/permissions, same `index.html` as source of truth | Default choice — no rewrite, keeps the one-file architecture intact |
| **Native rewrite (React Native / Flutter)** | High | Full native UI/perf | Only justified if the web shell becomes the bottleneck — not the case today |

This runbook covers **PWA** (§1) as a prerequisite either way, then **Capacitor** (§2 onward) as the store-distributable path.

---

## 1. Make the app a PWA first

Do this regardless of whether you wrap it — it's required for offline resilience and Capacitor benefits from it too.

1. Add a manifest, `manifest.webmanifest`, alongside `index.html`:
   ```json
   {
     "name": "Chicago District Explorer",
     "short_name": "District Explorer",
     "start_url": "./index.html",
     "display": "standalone",
     "background_color": "#0b3d91",
     "theme_color": "#0b3d91",
     "icons": [
       { "src": "icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
       { "src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png" }
     ]
   }
   ```
2. Link it from `index.html`'s `<head>`: `<link rel="manifest" href="manifest.webmanifest">`.
3. Add a minimal service worker (`sw.js`) that caches `index.html`, Leaflet's CSS/JS, and the app shell — **not** the live API responses (wards, police districts, etc. must stay fresh). The three embedded-data layers (Elected School Board, IL Supreme Court, Board of Review) already work fully offline; the service worker only needs to keep the shell loadable when the network is down, letting each layer's existing per-card error/retry state handle the rest.
4. Register it: `if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js')`.
5. Test: Chrome DevTools → Application → Manifest + Service Workers, confirm both are valid with no errors, then "Add to Home Screen" on a real phone and verify it launches standalone (no browser chrome).

---

## 2. Wrap with Capacitor

Capacitor loads the existing `index.html` into a native WebView shell — no rewrite of the app's logic, HTML, or data layer.

### 2a. One-time project setup

```bash
npm init -y                       # only if there's no package.json yet
npm install @capacitor/core @capacitor/cli
npx cap init "Chicago District Explorer" "org.thursdaysfamous.districtexplorer" --web-dir=.
```

- `--web-dir=.` points Capacitor at the repo root since `index.html` lives there with no build output directory.
- This creates `capacitor.config.json` — commit it.
- Do **not** let this introduce a bundler/build step for `index.html` itself; Capacitor just copies the web dir as-is into each native project's assets.

### 2b. Add platforms

```bash
npm install @capacitor/android @capacitor/ios
npx cap add android
npx cap add ios
```

This generates `android/` and `ios/` native project directories. Commit them (Capacitor expects the native projects to be version-controlled, unlike typical build artifacts).

### 2c. Sync after every change to index.html or data/

```bash
npx cap sync
```

Run this before every native build — it copies the current `index.html` (and `data/`, if referenced) into both native projects and updates native dependencies.

### 2d. Permissions

The app makes outbound HTTPS calls to Socrata, CPD ArcGIS, Cook County GIS, Census TIGERweb, and Nominatim. No native permissions (camera, contacts, precise location) are needed today since selection is tap-on-map, not device geolocation. If a "use my location" feature is added later, add `@capacitor/geolocation` and the corresponding `NSLocationWhenInUseUsageDescription` (iOS `Info.plist`) / `ACCESS_FINE_LOCATION` (Android `AndroidManifest.xml`) entries then — not before, to keep the store privacy questionnaire minimal.

### 2e. Icons and splash screen

```bash
npm install @capacitor/assets --save-dev
```
Provide one square source icon (≥1024×1024, no transparency) and one splash source at `assets/icon.png` and `assets/splash.png`, then:
```bash
npx capacitor-assets generate
```
This generates all iOS/Android icon and splash sizes automatically.

---

## 3. Local test builds

### Android
```bash
npx cap open android
```
Opens Android Studio. Run on an emulator or a USB-connected device (enable Developer Options → USB debugging on the device first). Verify:
- Map loads and is pannable/zoomable with touch
- Tap-to-select works and result cards populate for each layer group
- Address search (Nominatim) returns results
- Killing network mid-session degrades gracefully (per-card retry, not a crash)
- Permalink hash restore works if the app is opened via a deep link

### iOS
```bash
npx cap open ios
```
Opens Xcode. Requires a macOS host and an Apple ID (free for simulator testing; paid Apple Developer Program enrollment for device testing and store submission). Run on the iOS Simulator first, then a physical device via Xcode's signing.

---

## 4. Release builds

### Android (signed APK/AAB)
1. In Android Studio: Build → Generate Signed Bundle/APK.
2. Create (or reuse) a upload keystore — **back it up outside the repo**; losing it blocks future updates to the same app listing.
3. Produce an `.aab` (Android App Bundle) for Play Store upload.

### iOS (signed IPA)
1. In Xcode: set the Team under Signing & Capabilities to the Apple Developer account.
2. Product → Archive, then use the Organizer window to upload to App Store Connect (or export an `.ipa` for TestFlight).

---

## 5. Store submission checklist

Both stores require, at minimum:
- App name, short + full description, category (Reference or Navigation fits)
- Privacy policy URL — required even though the app collects no personal data; state that it makes anonymous requests to the listed public data sources and does not track users
- Screenshots at each required device size (use the simulator/emulator, not marketing mockups, for the first submission)
- Content rating questionnaire (civic/reference data, no user-generated content — should qualify for the lowest rating tier on both stores)
- The **"Not for legal or official use"** disclaimer from the README should appear in the app's own description text and ideally as a one-time in-app notice, since store reviewers may flag civic/legal-adjacent apps that lack one

Android-specific: Google Play Console → create app → complete Data Safety form (no data collected/shared) → upload signed `.aab` → internal testing track first, then production rollout.

iOS-specific: App Store Connect → create app record matching the bundle ID from `capacitor.config.json` → TestFlight build first → submit for review with a note to the reviewer that all boundary data is point-in-polygon lookups against public GIS sources, no account or login exists, and no location permission is requested.

---

## 6. Ongoing release loop

Repeat this sequence for every subsequent release once the app is live in both stores:

1. Change `index.html` / `data/` as normal (same workflow as the web app, per `BUILD_PLAYBOOK_1.md`).
2. `npx cap sync`
3. Bump the version: `capacitor.config.json`'s `appVersion` if tracked there, plus native version bumps (`android/app/build.gradle`'s `versionCode`/`versionName`; Xcode project's Build/Version numbers).
4. Rebuild and re-test per §3 on at least one real device per platform — the Playwright CI suite covers the web app's logic, not the native WebView shell, so a manual pass here is the only check for native-specific regressions (WebView quirks, native permission prompts, deep-link handling).
5. Re-archive/re-sign and submit per §4–5.

## 7. What NOT to do

- Don't add a JS bundler/build step to make `index.html` "cleaner" for Capacitor — it doesn't need one, and it would break the "open directly from `file://`" property the web app deliberately preserves.
- Don't cache live API responses (wards, rosters, boundaries) in the service worker or native shell — staleness would silently misinform users about who represents them. Only the three embedded-data layers are safe offline by design.
- Don't request location, contacts, or any permission the app doesn't use — it inflates the store privacy review for no feature benefit.
