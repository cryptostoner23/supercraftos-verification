# Bitrise build pipeline for the SuperCraftOS iOS app and keyboard extension

Checked against first-party Bitrise documentation and against live builds of the
`SuperCraftOS` app (slug `0150bf6e-006f-4263-b1ce-680875b745b4`, repository
`cryptostoner94/SuperCraftOS`, provider `github-app`). Every statement below
that is marked **verified** was observed in a real build log or artifact list
from that app.

## What the pipeline produces

| Artifact | Contents | Installable |
| --- | --- | --- |
| `SuperCraftOS-iOS-Simulator.app.zip` | Host app with the custom keyboard embedded at `PlugIns/SuperCraftOSKeyboard.appex` | Simulator only, unsigned |
| `SuperCraftOSKeyboard.appex.zip` | The keyboard extension on its own, for inspection | No, must ship inside the host app |
| `SuperCraftOS-Swift-Playgrounds.swiftpm.zip` | The iPad Swift Playgrounds bundle | Yes, open in Swift Playgrounds on iPad |

A signed device `.ipa` is **not** produced. That needs an Apple Developer account
connected to the Bitrise app, a distribution certificate, and a provisioning
profile covering both `com.supercraftos.control` and
`com.supercraftos.control.keyboard`. No such material exists in this
repository or on this machine, so the signed path is kept separate and
unverified in `docs/bitrise-release-workflow.yml`.

## The verified workflow

`bitrise.yml` defines a single `run_tests` workflow that runs on every push to
`master`:

1. **`git-clone@8`** — clones the repository.
2. **Verify iPad export and Swift package** — runs `scripts/package_ipad.py`,
   then `swift build` and `swift test` for `swift-verification`. The test suite
   includes `KeyboardCatalogTests`, which asserts the keyboard tab sequence,
   the tile set, the two column split, the badge palette, the required shortcut
   combinations, that every shortcut description is exactly two words, and the
   action bound to every tile.
3. **Inventory the iOS SDK and its on-device AI frameworks** — records the Xcode
   version, the simulator and device SDK paths, the AI capable frameworks
   present in the SDK, and type checks the FoundationModels compile probes
   against the simulator SDK. This is what makes the toolchain claim provable
   on every build instead of assumed.
4. **Build SwiftUI iOS app and keyboard extension for Simulator** — installs
   XcodeGen if missing, generates `ios_app_dist/ci_xcode/SuperCraftOS.xcodeproj`
   from `ios_app_dist/ci_xcode/project.yml`, runs `xcodebuild` for the
   `generic/platform=iOS Simulator` destination, asserts that the app bundle and
   `PlugIns/SuperCraftOSKeyboard.appex` both exist, prints the extension bundle
   identifier, and packages the app, the extension, and the Playgrounds bundle
   into the deploy directory.
5. **Compile iOS app and keyboard extension for device** — the same project
   built for `generic/platform=iOS` in `Release`, proving the arm64 device
   architecture compiles, then `lipo -info` on both binaries.
6. **`deploy-to-bitrise-io@2`** — publishes the packaged artifacts.

The Xcode project is generated rather than committed, because a committed
`.xcodeproj` carries absolute paths and a merge-hostile `project.pbxproj`. The
single source of truth for the project graph is
`ios_app_dist/ci_xcode/project.yml`.

## Verified build history

| Build | Result | What it proved |
| --- | --- | --- |
| 8 | error | `SCNScene(mdlAsset:)` does not exist in Swift |
| 10 | error | `UIView.translatesAutoresizingMask` was renamed |
| 12 | error | `SCNScene(url:options:)` throws on the iOS 27 SDK |
| 14 | **success** | First green build: app, keyboard extension, simulator and device architectures, artifacts published |
| 17 | **success** | Same pipeline with the pending grant and quest work merged back in |
| 20 | **success** | The keyboard became agent backed and App Group shared |
| 22 | **success** | FoundationModels compile probes pass against the iOS 27 SDK |
| 24 | **success** | Final state, with the availability case probe |

## Toolchain facts confirmed in the build log

| Fact | Value |
| --- | --- |
| Xcode | 27.0 (`/Applications/Xcode-27.0.0.app`) |
| SDK | `iphonesimulator27.0` |
| Machine | `g2.mac.m2pro.6c-14g`, macOS Tahoe 27 image |
| Swift | 5.9 language mode, SwiftUI 8.0.84.1 |
| Deployment target | iOS 26.0, the floor for Apple's on-device AI |
| Simulator binary | universal, `arm64` + `x86_64` |

The SDK version and the deployment target are independent. The code compiles
against the iOS 27 SDK and runs on iOS 26 and later.

## API surface used

All calls use `https://api.bitrise.io/v0.1` with the personal access token in
the `Authorization` header as the raw token value.

| Call | Purpose |
| --- | --- |
| `GET /apps` | Confirm token access and locate the app by slug |
| `POST /apps/{app-slug}/builds` | Trigger a build with `hook_info.type = bitrise` and `build_params.workflow_id` |
| `GET /apps/{app-slug}/builds` | List builds and their terminal states |
| `GET /apps/{app-slug}/builds/{build-slug}` | Poll one build until it reaches a terminal state |
| `GET /apps/{app-slug}/builds/{build-slug}/log` | Read the full build log as JSON log chunks |
| `GET /apps/{app-slug}/builds/{build-slug}/artifacts` | List published artifacts |
| `GET /apps/{app-slug}/builds/{build-slug}/artifacts/{artifact-slug}` | Get the expiring download URL for one artifact |

`scripts/bitrise_build.py` wraps all of these:

```bash
python3 scripts/bitrise_build.py trigger --workflow run_tests --branch master
python3 scripts/bitrise_build.py status <build-slug>
python3 scripts/bitrise_build.py log <build-slug> --grep "error:"
python3 scripts/bitrise_build.py artifacts <build-slug> --download release/ios
```

`scripts/verify_ios_artifacts.py` then checks a downloaded app bundle: bundle
identifiers, the embedded `PlugIns/SuperCraftOSKeyboard.appex`, the
`com.apple.keyboard-service` extension point, the principal class, the
`RequestsOpenAccess` attribute, the minimum OS version, and the binary
architectures.

## API and SDK behaviours that caused real build failures

These were found by building, not by reading documentation.

1. **`SCNScene(mdlAsset:)` does not exist in Swift.** The Objective-C
   `initWithMDLAsset:` is not exposed to Swift, so the call failed with
   *argument passed to call that takes no arguments*. Use
   `SCNScene(url:options:)` instead, and drop the `ModelIO` import.
2. **`SCNScene(url:options:)` throws on the iOS 27 SDK.** The modern signature
   is `init(url:options:) throws`, so the call must be written as
   `try? SCNScene(url: mesh, options: nil)`.
3. **`UIView.translatesAutoresizingMask` was renamed** to
   `translatesAutoresizingMaskIntoConstraints` in the current UIKit SDK.
4. **XcodeGen resolves `INFOPLIST_FILE` against the project directory**, which
   is `ios_app_dist/ci_xcode/`, so an extension Info.plist outside that
   directory needs the `../KeyboardExtension/Info.plist` form.
5. **An app extension target needs `GENERATE_INFOPLIST_FILE: NO`** when it
   carries its own `Info.plist` with the `NSExtension` dictionary, which cannot
   be expressed through `INFOPLIST_KEY_` settings.

## Repository layout for the Xcode project

| Path | Role |
| --- | --- |
| `ios_app_dist/ci_xcode/project.yml` | XcodeGen spec: app target, keyboard extension target, schemes |
| `ios_app_dist/KeyboardExtension/` | Keyboard extension sources and `Info.plist` |
| `ios_app_dist/YourApp.swiftpm/` | The app sources as shipped in the Playgrounds bundle |
| `swift-verification/Sources/ControlCore/KeyboardCatalog.swift` | The keyboard catalog, shared by the app and the test suite |
| `swift-verification/Tests/ControlCLITests/KeyboardCatalogTests.swift` | Assertions on the exact keyboard specification |

## Setup that is still required for a device install

1. Connect an Apple Developer account to the Bitrise app and register
   `com.supercraftos.control` and `com.supercraftos.control.keyboard`.
2. Add the workflow in `docs/bitrise-release-workflow.yml` to the Bitrise app
   and run it on demand.
3. On the device, open Settings > General > Keyboard > Keyboards > Add New
   Keyboard, choose SuperCraftOS, then switch to it with the globe key.

Until that is done, the honest deliverable is the simulator build, the device
architecture compile proof, and the Swift Playgrounds bundle.
