# Android app — Gumroad Automation

Kotlin + Jetpack Compose (Material 3), MVVM, Hilt, Retrofit/OkHttp, Room (offline
read cache), DataStore + EncryptedSharedPreferences, WorkManager, local notifications.
Free/open-source only. Talks **only** to the backend API (`/api/v1`) — the Gumroad
token never reaches the device.

## Build the debug APK

```bash
cd android
./gradlew assembleDebug
# APK: app/build/outputs/apk/debug/app-debug.apk
```

CI (GitHub Actions) runs the same command and uploads the APK as an artifact.
Requires JDK 17 on the build machine. No Android SDK is committed — CI installs it
via `android-actions/setup-android`.

## Point the app at your backend

1. Run the backend locally (see `../docs/SETUP.md`).
2. **Emulator:** default `http://10.0.2.2:8000/api/v1` works out of the box.
3. **Real device:** open **Settings → Backend connection** and enter your PC's LAN IP,
   e.g. `http://192.168.1.10:8000` (same Wi-Fi, backend running, firewall open),
   or use `adb reverse tcp:8000 tcp:8000` and keep `http://10.0.2.2:8000`.
4. Log in, add a Gumroad account, paste the access token in **Connect**.

## Background sync — honest limits

WorkManager periodic work has a **15-minute minimum interval**, and Android may
delay, batch, or stop background work (Doze, battery optimizations, manufacturer
restrictions). Background sync is best-effort, **not guaranteed**. True 24/7
automation while the phone is offline requires a continuously running server
(a later phase — the backend is Docker-ready for that).

## Run unit tests

```bash
./gradlew testDebugUnitTest
```
