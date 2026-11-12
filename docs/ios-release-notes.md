# SuperCraftOS iOS — v1.0.0

Native **iOS 17+** SwiftUI control app for SuperCraftOS, plus a custom
`UIInputViewController` + SwiftUI keyboard extension that reproduces the
Raycast for iOS keyboard layout.

The app runs on **iOS 17 and later**. The keyboard extension targets **iOS 26**,
the release that introduced Apple's on-device model, which it uses as the offline
fallback.

Built, tested and archived on the Bitrise macOS **Xcode 27 / iOS 27.0 SDK**
stack. The app is pre-pointed at the live control center, so it works the moment
it is installed.

## Downloads

| File | What it is | Installable |
| --- | --- | --- |
| `SuperCraftOS-Swift-Playgrounds.swiftpm.zip` | The full app as an iPad Swift Playgrounds bundle | **Yes** — iPad + the free Swift Playgrounds app. No Apple account, no Mac, no signing |
| `SuperCraftOS-iOS-Device-WithKeyboard-unsigned.ipa` | The full app **with the custom keyboard embedded**, iPhone and iPad, unsigned device build | After re-signing with your Apple ID |
| `SuperCraftOS-iOS-Device-unsigned.ipa` | The app on its own, unsigned device build | After re-signing with your Apple ID |
| `SuperCraftOS-iOS-Simulator.app.zip` | The app for the iOS Simulator | A Mac with Xcode |
| `SuperCraftOSKeyboard.appex.zip` | The keyboard extension on its own, for inspection | No, iOS only loads it from inside its app |
| `SuperCraftOS-iOS-Device-WithKeyboard-unsigned.app.zip` | The same keyboard build, unpacked | As the .ipa |

## Install, free, no Apple Developer Program

### On the iPad, the easiest route

1. App Store → install **Swift Playgrounds**.
2. Open `SuperCraftOS-Swift-Playgrounds.swiftpm.zip` in Safari, save it to Files.
3. Files → tap the zip → **Open with → Swift Playgrounds** → **Run**.
4. In the app, open **Connection**. It is already pointed at the control center.

No account, no signing, no expiry, no Developer Mode. The app only, no keyboard.

### On the iPhone or iPad, with the keyboard

The app and the keyboard extension are two separate registrations, so a free
Apple account has to sign both.

1. Download `iloader` for your platform — <https://github.com/nab138/iloader/releases>.
   Windows, Linux and macOS are all supported. It needs no Xcode.
2. Plug the device in over USB, open iloader, and sign in with the Apple ID
   **on that device**.
3. Choose **Install SideStore** first. SideStore re-signs the app in the
   background over Wi-Fi every 7 days, so you never have to do this again.
4. Open SideStore, tap **+**, and install
   `SuperCraftOS-iOS-Device-WithKeyboard-unsigned.ipa`.
5. On the device: Settings → General → Keyboard → Keyboards → Add New Keyboard →
   **SuperCraftOS**, switch to it with the globe key, and turn on
   **Allow Full Access**. Apple requires it for any keyboard that uses the
   network.
6. Open the app → **Connection**.

With two Apple accounts, give each device its own. Their 7-day signing windows
then run in parallel, so the app is never broken on both at once.

## What the app does

Eight live screens against your own control center: **Mission** (runtime,
token economy, memory, the LangGraph topology graph), **Product Lab** (AI design
brief → parametric spec → screened CAD export with STEP, STL and DXF),
**Engine** (capability catalog and routing policy), **Grant Ops**, **Workflows**
(the durable LangGraph queue with approve and deny), **Integrations** (health
evidence), **Tools** (the MCP catalog) and **Accounts** (registration outcomes).

## What the keyboard does

It is not a mock. Every tile is bound to a real action:

- **Ask AI** and the text actions send the text around your cursor to the agent
  through `POST /api/workflows` and insert the real reply.
- **If the agent cannot be reached**, the same action falls back to Apple's
  **on-device model** (Foundation Models) and says so. The keyboard works
  offline.
- **Maps**, **YouTube** and **Google** open real destinations.
- **Shift + Control + C** copies to the pasteboard, **Cmd + Option + V** pastes it
  back.
- The header toolbar, the two column tile grid, the dedicated **Fn** tab and the
  bottom input controls follow the specified layout exactly. The compiled binary
  is checked for every one of those strings.

## Verification

- The app and the keyboard are compiled for the simulator **and** the arm64
  device architecture on every build.
- The keyboard components are **rendered on a real iOS runtime** and the images
  are published as build artifacts.
- The app is **launched in a simulator** and photographed, connected to the live
  agent.
- A **live contract test** runs from both sides, the VPS and the iOS Simulator,
  and holds the backend to the decoding contract of the Swift models. It caught
  four real defects, including the app discarding the reason the backend gave it
  and the product lab failing permanently once its workspace filled. See
  `docs/ios-live-contract.md`.
- The App Store Connect archive is produced with signing disabled, so the only
  thing left for a signed build is an Apple identity.
