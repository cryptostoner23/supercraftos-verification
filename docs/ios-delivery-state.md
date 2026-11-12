# Current iOS delivery

The current release is [Bitrise build 189](https://app.bitrise.io/build/dc033f19-aafa-46e4-87a2-a247563e6fa0),
compiled from `116c522652a104fe4fa8bef97ca78ecddeb4b41a` on 2026-10-30.

[Download the unsigned IPA](https://agent.commetai.ca/ios/SuperCraftOS-build-189-unsigned.ipa)
or the [Swift Playgrounds source archive](https://agent.commetai.ca/ios/SuperCraftOS-Swift-Playgrounds-build-189.swiftpm.zip).
The IPA passed all 15 bundle checks, ZIP CRC and Payload checks, and was downloaded
again over HTTPS with its SHA-256 verified:
`73a3d55db40d3f69814f9ecfd5201c1e2d6ba824c7eb9fa0890479e48d92ddb2`.

The app targets the existing HTTPS gateway. Access keys are entered through the
private connection link and stored in the device Keychain, not embedded in this
release. Existing saved Keychain settings remain available to an update with the
same signing identity and bundle identifier.

This IPA is unsigned. A successful build and download do not establish Apple signing,
installation or physical-device launch. Follow [free personal installation](FREE_APPLE_INSTALL.md)
for local signing; free Personal Team provisioning expires after seven days.
No physical iPhone/iPad launch has been verified in this environment.

The app ships standalone. The optional keyboard has its own target and verification;
it is not embedded in this IPA. Current interaction evidence and external limitations
are recorded in [mission delivery](MISSION_DELIVERY_2026-10-30.md).

This record supersedes the earlier build-155 account/signing claims. A device ID,
iCloud session, manifest page or unsigned download cannot independently establish
that an app has been signed and installed on a physical device.

Build 189 is the successful `ipa_release` device packaging workflow. The preceding
build 188 simulator acceptance run stalled during runner launch and was stopped;
its test cases are not reported as passed. Latest portable Swift tests: 46 passed.
See [provider workflow delivery](FLOW_DELIVERY_2026-10-30.md) for the completed
Skyfire balance tool, submitted grant, and remaining provider access requirements.
