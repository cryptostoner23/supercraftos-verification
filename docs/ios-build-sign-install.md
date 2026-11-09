# Build, sign and install

Use [the current free Apple Account installation guide](FREE_APPLE_INSTALL.md).
The app is compiled on Bitrise and the unsigned device IPA is downloaded to your
Mac. Sign and install locally using a supported sideloading tool, or use a
compatible Xcode with your Personal Team. Keep the external Xcode drive and
existing development files intact.

Initial pairing/installation and periodic renewal must reach the physical
device. Free provisioning expires after seven days. Wireless refresh is a
separate tool/device setup and needs its prerequisites to remain available;
a server publishing a freshly signed IPA does not silently update the phone.
A web download or an `itms-services` link is not proof of a working free-account
installation. TestFlight requires the paid Apple Developer Program.

The standalone app requires iOS 17 or later; the optional keyboard build requires
iOS 26 or later. Select the standalone app first. Keep the same Apple Account
and application identifier for renewal to avoid creating unnecessary App IDs.
Enter your Apple credentials locally in the signing tool, never in chat or in a
VPS shell command. The app's separate private backend access key belongs in its
Connection settings.
