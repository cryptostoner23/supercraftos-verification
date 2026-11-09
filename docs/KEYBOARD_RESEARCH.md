# Personalized iPhone keyboard — research, and what was built

> **Status: built.** The research below was done on 2026-10-19 and this file
> records where the design came from. The keyboard itself is implemented, is
> compiled and verified on every CI push, and is published as its own artifact.
> The full specification of what exists is in
> [the keyboard extension document](ios-keyboard-extension.md); this file is the
> research that led to it, and the reasoning behind the decisions that were
> made.

Requested conditionally on 2026-10-19: add a personalized keyboard inspired by the supplied Raycast screenshots, only if credits and full delivery/testing are feasible. Workspace balance at research was approximately $3.34. Apple machine provisioning previously failed for insufficient recurring resource capacity; no Apple SDK/device validation is available. Preserve release budget and do not label a keyboard prototype as complete.

> **How that condition was met.** The work was done against the Bitrise macOS
> Xcode stack, which already compiles the app and the extension against
> Apple's current SDK, so the research budget was not spent on new machine
> provisioning. The keyboard is a separate target and is not embedded in the
> shipped app, so the app keeps one App ID and needs no App Group. A full
> build with the keyboard embedded is still compiled and verified in CI on
> every push, so the embedded configuration cannot rot.

The supplied seven PNGs show recent AI commands, AI command tiles, dictation, quicklinks, snippets, GIF recents, and a search view with a GIPHY results grid above a typing keyboard. The search icon changes the keyboard to a searchable selection interface. These are screenshots, not an animation recording.

Raycast describes its implementation as a secondary keyboard with AI transformations, dictation, snippets, dynamic placeholders, quicklinks and recents. Keyboard preferences include model and typing languages. Its dictation flow opens the containing app for the first recording and maintains a temporary background recording session. See [Raycast Keyboard](https://manual.raycast.com/ios/keyboard) and [Dictation](https://manual.raycast.com/ai/dictation).

An original SuperCraftOS implementation should prioritize task templates, concise writing/code actions, reusable snippets, verified artifact links and searchable recent actions. Use the app's violet/cyan visual design, rather than copying Raycast branding or assets. AI processing should send only the explicitly selected text or an explicitly requested field to the user's server; provider keys stay server-side. Preview a transformation before insertion and offer undo. Keep snippet search and basic typing usable offline. GIFs require a configured provider, bounded image caching, cancellation, attribution and a working insert/share fallback; do not show placeholder results.

Apple's supported system-wide route is an Xcode Custom Keyboard Extension using UIInputViewController and textDocumentProxy. A next-keyboard control is required. Network requests need the user's Allow Full Access setting. Keyboard extensions have memory and host-app limitations; microphone capture must be designed through the containing app. An app-specific input view is a different implementation and does not prove a keyboard works in other apps. The Swift Playgrounds app bundle does not include an extension target, so the extension is a separate Xcode target beside it. See [Apple custom keyboards](https://developer.apple.com/documentation/uikit/creating-a-custom-keyboard) and [open access](https://developer.apple.com/documentation/uikit/configuring-open-access-for-a-custom-keyboard).

GIPHY supports real search/trending APIs and an iOS SDK. An app key and visible attribution are required; production access and pricing must be confirmed for the user's account before activation. No GIPHY account, key, paid plan or API usage was created for this research. See [GIPHY API quick start](https://developers.giphy.com/docs/api/quick-start-guide/) and [iOS SDK](https://github.com/Giphy/giphy-ios-sdk).

## What has been done, and what has not

Done, and checked on every CI push: the extension target builds for the
simulator and for the device against the current SDK, the catalog is asserted
by the portable test suite, the tile actions are fired through the
authenticated fixture, and a full build with the keyboard embedded is compiled
and verified so the embedded configuration cannot rot.

Not done, and not claimed: the keyboard has not been signed onto a physical
device and exercised inside another application, so the on-device paths —
switching keyboards, Full Access on and off, insertion and undo, and
persisting a customization — are specified and compiled but not yet observed
on real hardware. GIF results are not wired to a GIPHY account, and dictation
is not implemented, because both need a credential and a permission decision
that are the account holder's to make.
