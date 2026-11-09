# Install SuperCraftOS with a free Apple account

Use the cloud-built **unsigned device IPA**, then sign and install it on your
trusted Mac. A paid Apple Developer Program membership is not required for this
personal-device route. Free provisioning expires after **seven days**; plan to
refresh the app before then. Apple's Personal Team limits also include ten App
IDs and three devices per platform. This is not permanent distribution.
[Apple account limits](https://developer.apple.com/help/account/basics/about-your-developer-account)

## First choice: install with SideStore

Open <https://agent.commetai.ca/ios/install.html> on the iPhone or iPad, in
Safari, and follow step 1 there.

1. If SideStore is not installed, tap **Open SideInstaller setup** and follow
   its on-device instructions, including the profile step. SideInstaller is a
   separate third-party project and its certificate may be rejected by iOS.
   If that happens, follow the
   [official SideStore setup](https://docs.sidestore.io/docs/installation/prerequisites),
   which requires a computer for the first install and LocalDevVPN for
   installation and refresh.
2. Once SideStore itself opens and is signed in on this device, return to the
   installation page, check that confirmation, and tap **Install SuperCraftOS**.
   SideStore imports the unsigned device IPA and presents the actual signing
   and installation result. Approve its Apple Account and iOS prompts.

The iCloud session on the device cannot be reused by a web page as a signing
identity. Do not download a generic configuration profile expecting it to
sign the app. SideStore shows the actual signing and installation result;
the web page cannot verify that iOS accepted or launched the app.

The app needs iOS 17 or later. The optional keyboard needs iOS 26 or later.

## Second choice: install on your Mac

1. Download the app-only
   [unsigned device IPA](https://agent.commetai.ca/ios/SuperCraftOS-iOS-Device-unsigned.ipa).
   It must be the device artifact, not a simulator ZIP. If the URL is unavailable,
   obtain that same named artifact from the successful Bitrise device build;
   a failed pipeline or an empty install manifest does not establish readiness.
2. Install [Sideloadly from its official site](https://sideloadly.io/index.html)
   on the Mac. The vendor lists macOS 10.12 and later, including Monterey.
   Building this app locally is unnecessary: signing the cloud artifact avoids
   requiring the current build SDK on the 2015 MacBook Air.
3. Connect the unlocked iPhone/iPad by USB, accept the Trust prompt, and select
   that device in Sideloadly. Drag the IPA into its window. Use **Apple ID
   Sideload**, enter your free Apple Account in that local application, and
   press Start. Complete its password and two-factor prompts yourself.
   App-specific passwords are not supported for this free-account flow.
4. On the device, trust the developer under Settings → General → VPN & Device
   Management if requested. Enable Settings → Privacy & Security → Developer
   Mode, restart, and confirm. If the setting is absent, pair/connect the device
   to the Mac first.
   [Apple Developer Mode](https://developer.apple.com/documentation/xcode/enabling-developer-mode-on-a-device)
5. Open SuperCraftOS and verify that it launches and reaches your configured
   backend. Record the build, device OS and profile expiry. A successful download,
   compile or installation command alone does not prove this step.

Sideloadly is a third-party signing application: Apple credentials are entered
there, never in these scripts, this chat, or the SuperCraftOS VPS. Use the
vendor's documented setup and prompts.
[Sideloadly setup and account FAQ](https://sideloadly.io/faq)

The current standalone app targets iOS/iPadOS **17.0 or later**; the optional
keyboard targets **26.0 or later**. The helper prints the actual
`MinimumOSVersion` in the downloaded artifact; a future build
can differ. Start with the standalone app. The optional keyboard requires its
own compatible signing/profile and may consume another App ID; App Group
entitlements must match the available profiles.

## Refresh before seven days

Enable Sideloadly automatic refresh during installation. Its daemon needs the
Mac running and the device reachable over USB or configured Wi-Fi sync on the
same network. Keep a manual reminder: if refresh fails, the profile still expires.
Reinstall over the existing app with the **same Apple Account and bundle ID**;
back up important data before refreshing. Free accounts permit three sideloaded
apps per device.
[Refresh and free-account restrictions](https://sideloadly.io/faq)

An `itms-services` manifest or “Install” link on a web page does not supply local
free-account signing. The supported route here uses the Mac and USB for the
initial installation; this guide does not promise browser OTA installation.

## Optional command helpers

These commands require a complete checkout and Python 3.9 or later. The GUI route
above needs neither Python nor a local source build.

```sh
# Download, inspect, reveal the IPA and open the local Sideloadly UI:
bash scripts/install_on_device.sh

# Use a specific cloud artifact already downloaded; check the phone's OS:
bash scripts/install_on_device.sh --ipa "$HOME/Downloads/SuperCraftOS-iOS-Device-unsigned.ipa" --ios-version 26.1

# Inspect/prepare only, without opening a GUI or claiming installation:
bash scripts/install_on_device.sh --ipa /path/to/device.ipa --no-open
```

Optional `--sha256 EXPECTED_HASH` checks a digest obtained from the trusted build
artifact. `--url HTTPS_URL` selects another build; `--output FILE` controls the
download location. `--with-keyboard` selects the optional combined build.
`scripts/supercraftos_install.sh` and `scripts/install_ios.sh free` use the same
local preparation flow. The old single-file `curl | bash` server-password flow
has been retired; run from the checkout or use the GUI steps.

Exit status zero from preparation means the IPA was prepared, **not installed**.
No Apple account, password or two-factor code is accepted by these helpers.

## USB installation of an already signed IPA

If you already possess a correctly signed development/ad-hoc IPA with unexpired
profiles covering your device, install it without repeating Apple login:

```sh
# Select the actual provisioning UDID from Finder or idevice_id -l.
bash scripts/install_ios.sh device \
  --ipa /path/to/already-signed.ipa \
  --udid YOUR_DEVICE_UDID --ios-version 26.1
```

The helper decodes each app/extension profile with macOS `security`, checks its
expiry, device UDID and bundle identifier, and runs `codesign --verify`. The
device still makes the final provisioning/entitlement decision. Unsigned,
expired or mismatched profiles cause failure before the install command.
[Apple provisioning-profile reference](https://developer.apple.com/documentation/technotes/tn3125-inside-code-signing-provisioning-profiles)

By default it uses `ideviceinstaller` when present, supporting both its modern
`install FILE` and older `-i FILE` interface. Otherwise it uses Xcode's `devicectl`
with an explicit device and an extracted `.app`, preserving executable modes.
Choose explicitly with `--tool ideviceinstaller` or `--tool devicectl`.
[ideviceinstaller documentation](https://github.com/libimobiledevice/ideviceinstaller/blob/master/README.md),
[Apple device command-line tools](https://developer.apple.com/documentation/xcode/interacting-with-devices-using-the-command-line)

Older Xcode may lack `devicectl`; use Sideloadly for the initial signing/install,
or separately install a compatible libimobiledevice/ideviceinstaller release
for the already-signed route. Do not upgrade Xcode blindly on the 2015 Mac.
To select an existing external-drive Xcode for one command:

```sh
DEVELOPER_DIR="/Volumes/YOUR_DISK/Xcode.app/Contents/Developer" \
  bash scripts/install_ios.sh device --ipa /path/to/signed.ipa --udid YOUR_DEVICE_UDID
```

Before device verification, collect `sw_vers`, `python3 --version`, the real
external Xcode path/version, the phone's OS, and whether Finder detects the
trusted USB device. The offline tests validate commands and failure handling;
they do not sign an app with Apple or prove a physical launch.
