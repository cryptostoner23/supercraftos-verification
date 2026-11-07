# SuperCraftOS iOS — v1.0.0

Native **iOS 17+** SwiftUI control app for SuperCraftOS, plus a custom
`UIInputViewController` + SwiftUI keyboard extension that reproduces the
Raycast for iOS keyboard layout.

Compiled on the Bitrise macOS **Xcode 27 / iOS 27.0 SDK** stack and verified.
The bundle checks are in `manifest.json`.

> The deployment target is **iOS 26.0**, not 17.0, because iOS 26 is the
> first release with Apple's Foundation Models framework. At that floor the
> keyboard can run Apple's on-device model, so the text actions keep working
> with no network and no account. The SDK used to compile is the current one,
> iOS 27.0.

## Pick your download

| File | What it is | What you need |
| --- | --- | --- |
| `SuperCraftOS-Swift-Playgrounds.swiftpm.zip` | The full app as an iPad Swift Playgrounds bundle | An **iPad** and the free Swift Playgrounds app. **No Apple account, no Mac, no payment.** No keyboard |
| `SuperCraftOS-iOS-Device-WithKeyboard-unsigned.ipa` | The full app **with the custom keyboard embedded**, for iPhone and iPad, unsigned device build | A sideload tool (Sideloadly or AltStore) and a free Apple ID |
| `SuperCraftOS-iOS-Device-unsigned.ipa` | The app alone, unsigned device build | Same |
| `SuperCraftOS-iOS-Simulator.app.zip` | The app for the iOS Simulator | A Mac with Xcode |
| `SuperCraftOSKeyboard.appex.zip` | The keyboard extension on its own, for inspection | Nothing, it must ship inside the app |
| `SuperCraftOS-iOS-Device-WithKeyboard-unsigned.app.zip` | The same keyboard build, unpacked | Same as the .ipa |
| `SuperCraftOSKeyboard-iOS-Device-unsigned.appex.zip` | The keyboard extension, device build, unpacked | Same |

## Route A — iPad, no Apple account, no Mac, no payment

1. Install **Swift Playgrounds** from the App Store on your iPad.
2. Open `SuperCraftOS-Swift-Playgrounds.swiftpm.zip` with it.
3. Run it. The app asks for your backend address in **Connection**; enter the
   HTTPS address of your SuperCraftOS control center.

You get the whole app: Mission, Product Lab with the 3D preview and CAD
export, Engine, Grant Ops, Workflows, Integrations, Tools, Accounts.

The keyboard is not in this route, because Apple does not allow Swift
Playgrounds to host app extensions. That is a platform rule, not a choice.

## Route B — iPhone or iPad, full app with the keyboard, free

Needs a sideload tool. **Sideloadly** runs on Linux, Windows and macOS;
**AltStore** runs on macOS and Windows. Both re-sign the app with your own
free Apple ID.

1. Download `SuperCraftOS-iOS-Device-WithKeyboard-unsigned.ipa`.
2. Connect the iPhone by USB and trust it.
3. In Sideloadly, choose the .ipa, enter your Apple ID, press **Start**.
4. On the iPhone, Settings > General > VPN & Device Management > trust your
   Apple ID.
5. Settings > General > Keyboard > Keyboards > Add New Keyboard >
   SuperCraftOS, then turn on **Allow Full Access** (Apple requires it for any
   keyboard that uses the network).
6. In the app, open **Connection** and enter your backend address.

Free Apple ID notes: the app must be re-signed every **7 days**, you can have
**3 apps per device**, and **10 registered App IDs**. With two Apple IDs you
can alternate between them so the app is never broken for a full week. The
app and the keyboard must be signed by the **same** Apple ID, because an
embedded extension has to carry the same Team ID as its host app.

This route is **not verified by us**, because we have no device and no Apple
account. Route A is the one we can vouch for end to end.

## What the keyboard does

It is not a mock. Every tile is bound to a real action:

- **Ask AI** and the text actions send the text around your cursor to the
  SuperCraftOS agent through `POST /api/workflows` and insert the real reply.
- **If the agent cannot be reached**, the same action falls back to Apple's
  **on-device model** (Foundation Models) and says so. The keyboard works
  offline.
- **Maps**, **YouTube** and **Google** open real destinations.
- **Shift + Control + C** copies to the pasteboard, **Cmd + Option + V** pastes
  it back.
- The header toolbar, the two column tile grid, the dedicated `Fn` tab and the
  bottom input controls follow the specified layout exactly, and the compiled
  binary is checked for every one of those strings.

## Reproduce it

```bash
git clone https://github.com/cryptostoner94/SuperCraftOS
cd SuperCraftOS
python3 scripts/build_release_assets.py --out release/ios
```

The CI pipeline, the toolchain facts and the API surface are documented in
`docs/bitrise-integration.md`. The keyboard specification is in
`docs/ios-keyboard-extension.md`.
