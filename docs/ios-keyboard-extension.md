# SuperCraftOS iOS custom keyboard extension

Native `UIInputViewController` + SwiftUI custom keyboard, compiled and verified by
Bitrise on the macOS Xcode 27 stack. Source lives in `ios_app_dist/KeyboardExtension/`
and is built as an app extension target (`SuperCraftOSKeyboard`).

> **The keyboard is not embedded in the shipped app.** It is built, compiled and
> verified on every CI push as its own target and scheme, and published as its
> own artifact, but the app ships standalone so that it needs only one App ID
> and no App Group on its provisioning profile. See
> [Re-enabling the keyboard](#re-enabling-the-keyboard) below.

## Re-enabling the keyboard

The app target in `ios_app_dist/ci_xcode/project.yml` has the dependency
commented out, with the reason inline. To ship the keyboard again:

1. Uncomment the `dependencies` block on the `SuperCraftOS` target:

   ```yaml
   dependencies:
     - target: SuperCraftOSKeyboard
       embed: true
       codeSign: false
   ```

2. Add the App Group entitlement back to the app target, with
   `CODE_SIGN_ENTITLEMENTS: SuperCraftOSKeyboard.entitlements`. The extension
   already carries that file.

3. Register `com.supercraftos.control.keyboard` as a second App ID and enable
   the App Group `group.com.supercraftos.control` on both identifiers.

4. Restore the "app ships standalone" expectation in
   `scripts/verify_ios_artifacts.py` to "app embeds SuperCraftOSKeyboard.appex",
   and drop the "no embedded app extension" check.

5. Rebuild and re-verify. CI already builds and verifies the extension on
   every push, so the only new failure mode is the embedding itself.

## Target and toolchain

| Item | Value |
| --- | --- |
| SDK | iOS 27.0 (Xcode 27, `iphonesimulator27.0.sdk`) |
| Deployment target | iOS 26.0, the floor for Apple's on-device AI |
| Swift language mode | 5.9 (`SWIFT_VERSION = 5.9`) |
| Extension bundle id | `com.supercraftos.control.keyboard` |
| Host app bundle id | `com.supercraftos.control` |
| Extension point | `com.apple.keyboard-service` |
| Principal class | `$(PRODUCT_MODULE_NAME).KeyboardViewController` |

The SDK version and the deployment target are independent: the code is compiled
against the iOS 27 SDK while the shipped binary still runs on iOS 17 and later.
The simulator build produces a universal binary (`arm64` + `x86_64`) because the
`generic/platform=iOS Simulator` destination does not restrict `ONLY_ACTIVE_ARCH`.

## Layout of the source

| File | Responsibility |
| --- | --- |
| `KeyboardViewController.swift` | `UIInputViewController` host, `UIHostingController` embedding, height constraint, text proxy wiring |
| `KeyboardBackend.swift` | Control session and agent client for the extension |
| `KeyboardRootView.swift` | Root layout: toolbar, content region, bottom input controls, action dispatch |
| `KeyboardToolbar.swift` | Top icon row of rounded pill tab buttons |
| `KeyboardActionGrid.swift` | Two column horizontally scrolling action tile grid |
| `KeyboardFnGrid.swift` | Dedicated Fn tab shortcut trigger grid |
| `KeyboardInputBar.swift` | Bottom system input controls layer |
| `KeyboardBadgeView.swift` | Coloured icon badge anchored left of every tile |
| `KeyboardTheme.swift` | Palette, corner radii, paddings, badge sizes |
| `Info.plist` | Keyboard extension attributes and principal class |
| `swift-verification/Sources/ControlCore/KeyboardCatalog.swift` | The catalog, shared with the portable test suite |

The catalog lives in the SwiftPM package so the exact same file that the app
compiles is asserted by the CI test suite. There is no copy to drift.

## 1. Header toolbar layout

A dark (`#1C1C1E`) horizontal toolbar holding rounded pill tab buttons. The tab
sequence is fixed and left to right:

| # | Tab | Glyph | Trailing |
| --- | --- | --- | --- |
| 1 | Recents | `clock` | no |
| 2 | AI Actions | `sparkles` | no |
| 3 | Voice / Audio | `waveform` | no |
| 4 | Lighting / Execution | `bolt.fill` | no |
| 5 | Fn | `fn` | no |
| 6 | Presets / Sliders | `slider.horizontal.3` | no |
| 7 | GIFs | `gif` | no |
| 8 | Search | `magnifyingglass` | **yes, far right** |

The selected pill is filled white with a black glyph; unselected pills use the
tile colour with a white glyph. The Search pill is pinned to the trailing edge by
a `Spacer`, so it is always aligned far right regardless of tab selection.

## 2. Action tile grid

A two column horizontally scrolling grid inside the `#2C2C2E` container. Tiles are
rounded rectangles (`#3A3A3C`, 12pt radius, 12pt padding). Every tile carries a
small circular icon badge anchored on the left and white text labels.

The Ask AI card is the large left hand action card: 116pt minimum height, a
purple to pink gradient, a large `sparkles` glyph, and the title anchored to the
bottom leading corner.

| Tile | Badge | Tint | Notes |
| --- | --- | --- | --- |
| Ask AI | `sparkles` | red | large left hand card |
| Ask About Webpage | `questionmark.circle` | blue | |
| Change Tone to Casual | `message.bubble` | blue | |
| Rephrase as | `arrow.triangle.2.circlepath` | red | loop glyph |
| Rephrase as Tweet | `bird` | blue | Twitter glyph |
| Explain Code by Step | `chevron.left.forwardslash.chevron.right` | white | code `<>` brackets |
| Fix Spelling and Grammar | `checkmark` + `pencil` | blue | overlaid badge |
| Improve Writing | `I` | white | capital letter badge |
| Translate | `character.book.closed` | blue | Google Translate |
| Maps | `map` | blue | Apple Maps |
| YouTube | `play.rectangle` | red | |
| Google | `G` | white | |

Tiles are ordered left column then right column. Column one is the even
positions, column two the odd positions, so Ask AI is the top tile of the left
column and Ask About Webpage the top tile of the right column.

## 3. Dedicated Fn tab

Selecting the Fn tab replaces the action grid with a grid of shortcut trigger
keys in the same `#2C2C2E` container, using the same two column layout. Every
tile shows the exact key combination and an exact two word description.

| Key combination | Description |
| --- | --- |
| `Shift + Control + C` | Copy Code |
| `Cmd + Shift + P` | Command Palette |
| `Cmd + Option + V` | Paste Plain |
| `Cmd + S` | Save Document |
| `Cmd + N` | New Window |

The two word requirement is enforced by a unit test, not just by convention.

## 4. Bottom system input controls

Directly beneath the grid, on the same dark bar as the toolbar:

- **Space** — wide dark pill, lowercase white `space` text, expands to fill the
  space between the globe and the right hand keys.
- **Backspace / Delete** — `⌫` inside a dark rounded box, 42x38pt.
- **Return / Enter** — `↵` inside a dark rounded box, 42x38pt.
- **Globe** — `🌐` at the bottom left corner, switches to the next system
  keyboard through `advanceToNextInputMode()`.

## Behaviour

Every tile is bound to a real action. Nothing is a decorative stub.

| Control | Action |
| --- | --- |
| Space | Inserts a space through `textDocumentProxy` |
| Backspace | `textDocumentProxy.deleteBackward()` |
| Return | Inserts a newline |
| Globe | `advanceToNextInputMode()` |
| Ask AI | Sends the surrounding document context to the agent as a free question and inserts the reply |
| Ask About Webpage | Sends the context to the agent with a webpage question prompt |
| Change Tone to Casual | Sends the context to the agent with a tone rewrite prompt |
| Rephrase as / Rephrase as Tweet | Sends the context to the agent with a rephrase or tweet prompt |
| Explain Code by Step | Sends the context to the agent with a step by step code prompt |
| Fix Spelling and Grammar | Sends the context to the agent with a correction prompt |
| Improve Writing | Sends the context to the agent with a rewrite prompt |
| Translate | Sends the context to the agent with a translation prompt |
| Maps | Opens `https://maps.apple.com/?q=` with the context |
| YouTube | Opens `https://www.youtube.com/results?search_query=` with the context |
| Google | Opens `https://www.google.com/search?q=` with the context |
| Shift + Control + C | Copies the context to the system pasteboard |
| Cmd + Option + V | Inserts the system pasteboard contents as plain text |
| Cmd + Shift + P, Cmd + S, Cmd + N | Insert the key combination, because a keyboard extension cannot send host application shortcuts |

### How the keyboard reaches the agent

The extension is a separate process with a separate container, so it shares the
backend address and the control session token with the host app through the
App Group `group.com.supercraftos.control`. **This is the one thing that the
App Group exists for, and the one thing that makes the keyboard more
complicated to ship than the app.**

1. The app writes the backend address and the control token into the shared
   suite with `KeyboardSharedConfiguration.publish`.
2. The extension reads them with `KeyboardSharedConfiguration.backend` and
   `KeyboardSharedConfiguration.token`.
3. When no token is cached, the extension opens its own session with
   `GET /api/session`.
4. The agent is driven through `POST /api/workflows` with an
   `X-SuperCraftOS-Token` header, the same endpoint and the same authentication
   the app's Workflows screen uses. The reply's `artifact`, then `plan`, then
   `status` is inserted into the host application.

`KeyboardSharedConfiguration.publish` writes to the App Group suite when one is
available and to the standard defaults otherwise, so the app never fails when
the group is not provisioned. The App Group must be present in the
provisioning profile of both the app and the extension for a signed device
build. On an unsigned simulator build the entitlements are not applied, and the
keyboard reports that the backend is not configured until the app has
connected.

### Status reporting

A transient pill appears over the grid while a request is in flight and when a
request fails. It is an overlay, so the specified layout of the toolbar, the
grid, and the bottom input controls is unchanged.

## On-device AI, and why it is not linked yet

The CI stack is Xcode 27 with the iOS 27 SDK, and that SDK does contain
Apple's on-device AI framework. The `Inventory the iOS SDK and its on-device AI
frameworks` step records this on every build:

```
Xcode 27.0
simulator: .../iPhoneSimulator27.0.sdk
device:    .../iPhoneOS27.0.sdk
FoundationModels.framework
_FoundationModels_SwiftUI.framework
_FoundationModels_UIKit.framework
_CoreSpotlight_FoundationModels.framework
CoreML / Vision / Speech / NaturalLanguage / Translation / MediaIntelligence
```

Three compile probes in `swift-verification/Probes/` are type checked against
the simulator SDK on every build, so the API is proven callable rather than
assumed:

| Probe | Proves |
| --- | --- |
| `FoundationModelsAvailability.swift` | `SystemLanguageModel.default.availability` exists |
| `FoundationModelsAvailabilityCase.swift` | the availability check is `if case .available = ...` |
| `FoundationModelsSession.swift` | `LanguageModelSession()` and `await session.respond(to:)` returning `.content` |

The probes are also the contract for the shipping code.
`ios_app_dist/KeyboardExtension/KeyboardOnDeviceAI.swift` uses exactly this
API, and the deployment target is **iOS 26.0**, which is the first release
that ships Foundation Models. That is the floor, and it is what makes the
framework linkable at all.

### How the keyboard uses both

| Path | When | Where it runs |
| --- | --- | --- |
| The SuperCraftOS agent | Always first | Your VPS, through `POST /api/workflows` |
| The on-device model | When the agent cannot be reached | On the phone, with no network |

So the keyboard still rewrites, fixes, explains and translates text with the
device offline. `SystemLanguageModel.default.availability` decides whether the
hardware supports it, and the keyboard says so plainly rather than failing
silently.

The agent stays the primary path, because it is where the project's model
routing, tool use, approval gates and artifacts already live. The on-device
model is the fallback, not the replacement.

## Toolchain facts confirmed in the build log

| Fact | Value |
| --- | --- |
| Xcode | 27.0 (`/Applications/Xcode-27.0.0.app`) |
| Simulator SDK | `iphonesimulator27.0` |
| Device SDK | `iphoneos27.0` |
| Swift | 5.9 language mode, SwiftUI 8.0.84.1 |
| Deployment target | iOS 26.0, the floor for Apple's on-device AI |
| Simulator binary | universal, `arm64` + `x86_64` |

The SDK version and the deployment target are independent. The code compiles
against the iOS 27 SDK and runs on iOS 26 and later. iOS 26 is the floor
because that is the first release with Foundation Models, and the keyboard
uses it.
The `Inventory the iOS SDK and its on-device AI frameworks` CI step records the
exact Xcode version and lists the AI capable frameworks present in the SDK, so
the toolchain is proven on every build rather than assumed.

## Verification

`swift-verification/Tests/ControlCLITests/KeyboardCatalogTests.swift` asserts the
tab sequence and icons, the trailing Search pill, the tile titles and their
order, the two column split, the Ask AI hero card, the badge palette, the
required shortcut combinations, and that every shortcut description is exactly
two words. Run them with:

```bash
swift test --package-path swift-verification
```

The simulator and device compilations are verified by Bitrise. See
`docs/bitrise-integration.md`.
