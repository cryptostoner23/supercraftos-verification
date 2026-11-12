# iOS delivery

Three things have to be true for the app to be installable, and all three are
now implemented and verified on the Bitrise build:

| Requirement | Where it is satisfied |
| --- | --- |
| A real app icon | `ios_app_dist/ci_xcode/Assets.xcassets/AppIcon.appiconset`, generated reproducibly by `scripts/generate_app_icons.py`, verified in the built bundle |
| A launch screen and export compliance declaration | `INFOPLIST_KEY_UILaunchScreen_Generation` and `INFOPLIST_KEY_ITSAppUsesNonExemptEncryption` in `ios_app_dist/ci_xcode/project.yml` |
| A privacy manifest | `PrivacyInfo.xcprivacy` for the app, declaring the `UserDefaults` reason `CA92.1` |

## The app ships standalone

The app is a **single target with no app extensions and no entitlements**. That
is a deliberate decision, and it is the difference between a simple install and
a fiddly one.

Embedding the custom keyboard extension would make the app require:

- a second App ID, `com.supercraftos.control.keyboard`,
- the App Group `group.com.supercraftos.control` on the app's own provisioning
  profile, which is where profile generation usually goes wrong,
- an Allow Full Access permission prompt for the user.

None of that is needed for the app itself, so none of it is in the shipped
build. What remains for the app is the one requirement every iOS app has: a
code signature from an Apple Developer account.

The keyboard is not deleted. It is still **built, compiled and verified on
every CI push** as its own target and scheme, so it cannot rot against the
current SDK, and it is still published as a build artifact. Re-enabling it is a
single uncommented block in `ios_app_dist/ci_xcode/project.yml`, described in
`docs/ios-keyboard-extension.md`.

## Path A: installed locally

### On a simulator, with no Apple account

This needs only macOS with Xcode. It is the path that works today.

```bash
scripts/install_ios.sh simulator "iPhone 16"
```

or, step by step:

```bash
scripts/ios_release.sh simulator
xcrun simctl boot "iPhone 16"
xcrun simctl install booted build/ios/simulator/Build/Products/Debug-iphonesimulator/SuperCraftOS.app
xcrun simctl launch booted com.supercraftos.control
```

### On your own devices, with a free personal Apple account

**This works with no payment**, including the keyboard extension. Two personal
Apple IDs give you two signing teams, six device slots, and staggered 7-day
profile refreshes. The full procedure, with Apple's own limits and the exact
caveats, is in [the free account guide](ios-free-account.md).

```bash
export SUPERCRAFTOS_BACKEND_URL="https://your-backend-host"
scripts/ios_release.sh full
scripts/install_ios.sh device
```

`full` builds the app with the keyboard embedded. Because the backend address
is baked into the extension at build time, the extension needs **no App Group
and no entitlements**, which is what lets a free personal team sign it.

### On a physical device with a paid account

On a Mac with Xcode and a paid Apple Developer account:

```bash
scripts/ios_release.sh device
scripts/install_ios.sh device
```

`ios_release.sh device` archives in Release for `generic/platform=iOS` and
exports with `ExportOptions-development.plist`. Xcode resolves the signing
identity from your connected team.

The only App ID the app needs is `com.supercraftos.control`.

## Path B: TestFlight

TestFlight is the distribution path for anything that is not your own device.
It needs a paid Apple Developer account and an App Store Connect record for
`com.supercraftos.control`.

### Once, in the Bitrise app

1. **App settings > Apple Developer account**: connect your team so Xcode can
   sign automatically.
2. **Secrets**: `APP_STORE_CONNECT_TEAM_ID`, `ASC_API_KEY_ID`,
   `ASC_API_ISSUER_ID`, and `ASC_API_KEY_PATH` pointing at an App Store
   Connect API key (the `.p8` file, uploaded as a secret). The key needs the
   App Manager role so it can upload builds.
3. **App Store Connect**: create the app record for `com.supercraftos.control`.

### Then, on demand

Add the workflow from `docs/bitrise-release-workflow.yml` to the Bitrise app
and run it. It:

1. generates the Xcode project,
2. archives with `xcode-archive@6` using `distribution_method: app-store`,
   which maps to `app-store-connect` on Xcode 15.3 and later,
3. exports the IPA with `export-xcarchive@4`,
4. uploads it to App Store Connect with `xcrun altool`, falling back to
   `iTMSTransporter`,
5. publishes the IPA as a build artifact.

The build then appears in TestFlight. Internal testers are added in App Store
Connect, and the app installs from there like any other TestFlight app.

### The same thing on your own Mac

```bash
scripts/ios_release.sh testflight
scripts/upload_to_testflight.sh build/ios/ipa/SuperCraftOS.ipa
```

with `ASC_API_KEY_ID`, `ASC_API_ISSUER_ID`, and `ASC_API_KEY_PATH` set.

## The unsigned artifacts, and what they are for

`scripts/bitrise_build.py artifacts <build-slug> --download data/release/ios`
publishes three artifacts on every green build:

| Artifact | What it is | Installable |
| --- | --- | --- |
| `SuperCraftOS-iOS-Simulator.app.zip` | The standalone host app, no extensions | On a simulator, with no Apple account |
| `SuperCraftOSKeyboard.appex.zip` | The keyboard extension, built and verified but not embedded | No, iOS only loads it from inside its containing app |
| `SuperCraftOS-Swift-Playgrounds.swiftpm.zip` | The iPad Swift Playgrounds bundle | Yes, in Swift Playgrounds on iPad |

## Verifying a delivery

```bash
python3 scripts/verify_ios_artifacts.py data/release/ios/SuperCraftOS-iOS-Simulator.app.zip
python3 scripts/verify_ios_artifacts.py data/release/ios/SuperCraftOSKeyboard.appex.zip
python3 scripts/release_manifest.py data/release/ios --build <build-slug>
```

The app verifier checks the bundle identifiers, the minimum iOS version, the
app icon, the launch screen, the export compliance key, the privacy manifest,
the binary architectures, and that the app contains no embedded app extension.
The keyboard verifier checks the extension point, the principal class, the
package type, the open access attribute, the privacy manifest, the
architectures, and that the compiled binary carries the exact specified
vocabulary and the runtime contract.
