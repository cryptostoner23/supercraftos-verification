# Bitrise setup for this repository

The iOS app is a plain Xcode app plus a custom keyboard extension. The Xcode
project is generated from `ios_app_dist/ci_xcode/project.yml` with XcodeGen, so
no `.xcodeproj` is committed.

| Field | Value in this repository |
| --- | --- |
| Repository | `https://github.com/cryptostoner94/SuperCraftOS` |
| Branch | `master` |
| Project type | `iOS` |
| App slug | `0150bf6e-006f-4263-b1ce-680875b745b4` |
| Connection provider | `github-app` |
| CI config location | `repository` (the `bitrise.yml` at the repository root) |
| Workflow | `run_tests`, triggered by a push to `master` |
| Scheme | `SuperCraftOS` |
| App bundle identifier | `com.supercraftos.control` |
| Keyboard bundle identifier | `com.supercraftos.control.keyboard` |
| Minimum iOS | 17.0 |
| Version | 1.0 (build 1) |
| Device families | iPhone and iPad, portrait and both landscape orientations |

## What the checked-in iOS assets are

`ios_app_dist/YourApp.swiftpm/` is an **iPad Swift Playgrounds app bundle**, not
an Xcode project. Its `Package.swift` declares a single `.iOSApplication`
product named `SuperCraftOS` with the target `AppModule`, bundle identifier
`com.supercraftos.control`, minimum iOS 17.0, version 1.0 (build 1), and both
device families. The distribution artifact for that route is
`ios_app_dist/YourApp.swiftpm.zip`, which can be opened directly in Swift
Playgrounds on iPad.

The custom keyboard extension is **not** part of the Playgrounds bundle.
Swift Playgrounds cannot host app extensions, so the keyboard is built only
through the Xcode project that Bitrise generates, as an app extension embedded
in the host app.

## Generating the Xcode project locally

```bash
brew install xcodegen
xcodegen generate --spec ios_app_dist/ci_xcode/project.yml
open ios_app_dist/ci_xcode/SuperCraftOS.xcodeproj
```

Then build for the simulator:

```bash
xcodebuild -project ios_app_dist/ci_xcode/SuperCraftOS.xcodeproj \
  -scheme SuperCraftOS -configuration Debug \
  -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' \
  CODE_SIGNING_ALLOWED=NO build
```

`CODE_SIGNING_ALLOWED=NO` is required for an unsigned simulator build. A device
build needs real signing, which is described in `docs/bitrise-integration.md`.

## Server side credentials

`scripts/bitrise_build.py` and `bitrise_monitor.py` read:

| Variable | Purpose |
| --- | --- |
| `BITRISE_API_TOKEN` | Personal access token, sent as the raw `Authorization` header value |
| `BITRISE_APP_SLUG` | The app slug above |
| `LARK_APP_ID`, `LARK_APP_SECRET`, `LARK_NOTIFY_CHAT_ID` | Optional, for the Lark build notifications |

The Bitrise token and app slug are already present in the server side `.env`.
Keep every value server side and out of Git. A personal access token is created
in Bitrise account security settings and shown only once. The app slug is
visible in the project URL after the app is created.

## Repository access

The app uses the `github-app` connection provider, so the GitHub App
installation, not the personal access token, controls which repository Bitrise
can clone. If a clone step starts failing with a permission error, check the
GitHub App installation and its repository access list, and confirm the
`master` branch is not excluded from clone.

## Notifications

`bitrise_monitor.py` polls the build list API and sends deduplicated build
transitions through the existing Lark bot. It activates only when all five
variables above are present and records seen states in
`data/bitrise-build-states.json`, keyed by build slug.
