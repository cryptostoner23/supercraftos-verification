# Two devices, two free Apple accounts

You have an **iPad** and an **iPhone**, each signed into a different Apple
account. That is a good configuration, and it is better than using one
account for both.

## Why two accounts is better than one

| | One account for both devices | One account per device (yours) |
| --- | --- | --- |
| Devices | 2 of 3 slots | 1 of 3 slots each, 2 total |
| **Profile expiry** | Both expire on the **same day**. Re-sign both at once. | **Staggered.** Re-sign the iPad one week, the iPhone the next. The app is never broken on both at once |
| App IDs | 10 | 20 |

Free personal profiles last **7 days**. With one account you would have a day
where neither device has a working app. With two you always have one.

**One rule that is not negotiable:** the app and the keyboard extension must be
signed by the **same** Apple account for a given device, because an embedded
extension has to carry the same Team ID as its host app. So you never mix
them. Account A signs the iPad build (app and keyboard together), account B
signs the iPhone build (app and keyboard together).

## The assignment

| Device | Apple account | What to build |
| --- | --- | --- |
| **iPad** | Account A | `scripts/ios_release.sh full` with account A's signing, then sideload to the iPad |
| **iPhone** | Account B | `scripts/ios_release.sh full` with account B's signing, then sideload to the iPhone |

The two builds are separate binaries with the same bundle identifiers and
different Team IDs. That is fine: they never meet on the same device.

## The iPad has a second, easier route

The iPad does **not** need any of this to run the app. Install **Swift
Playgrounds** from the App Store and open
`SuperCraftOS-Swift-Playgrounds.swiftpm.zip`. No Apple account, no Mac, no
sideloading, no 7-day clock, no expiry.

Use that if you only want the app on the iPad. Use the sideload route on the
iPad if you specifically want the **keyboard** there too.

## The steps, per device

Sideloadly runs on Linux, Windows and macOS, and it automates the entire free
provisioning dance: it reads the device UDID, registers it with Apple, creates
the App IDs, generates the certificate and profile, signs the app, and
installs it. You do not have to touch the developer portal.

If there is no computer at all, and the only thing you need from Apple is the
UDID, the device can report it by itself: open
**https://agent.commetai.ca/ios/udid** in Safari on the device and install the
profile it offers. See [the UDID capture guide](ios-udid-capture.md).

### On the iPad

1. Download `SuperCraftOS-iOS-Device-WithKeyboard-unsigned.ipa` from
   https://github.com/cryptostoner94/SuperCraftOS/releases/tag/v1.0.0
   (your repository is private, so sign in to GitHub first).
2. Plug the iPad into the machine running Sideloadly, and tap **Trust** on
   the iPad.
3. In Sideloadly: pick the .ipa, enter **Apple ID A**, press **Start**.
4. On the iPad: **Settings > General > VPN & Device Management >** your Apple
   ID **> Trust**.
5. **Settings > General > Keyboard > Keyboards > Add New Keyboard >
   SuperCraftOS**, then switch to it with the globe key and turn on
   **Allow Full Access**.
6. Open the app, go to **Connection**, and enter your backend address.

### On the iPhone

Exactly the same, with **Apple ID B**.

## Rebuilding with your own backend address

The keyboard needs to know where your SuperCraftOS control center is. The
address is baked into the extension at build time:

```bash
export SUPERCRAFTOS_BACKEND_URL="https://your-backend-host"
scripts/ios_release.sh full
```

That produces a fresh `.ipa` in `build/ios/ipa/`. Sideload it as above. If you
skip this, the app itself still works because you set the address in
**Connection**, but the keyboard's AI tiles will report that the backend is
not configured.

To rebuild just the ipa from a downloaded bundle, without Xcode:

```bash
python3 scripts/package_ipa.py <path/to/SuperCraftOS.app> release/ios/SuperCraftOS.ipa
```

## Keeping both alive

Every 7 days, re-sign and reinstall each device. Sideloadly does the whole
procedure again in about a minute per device. Offset them by a few days so
the two expiry clocks do not line up.

The free tier also limits you to **3 apps per device**. The SuperCraftOS app
counts as one, and the keyboard extension does not count separately, because
it is inside the app.

## What can still go wrong

- **The keyboard extension may not be signed by the sideload tool.** If
  Sideloadly or AltStore cannot provision the extension's App ID, the app
  still installs, just without the keyboard. In that case use the iPad's
  Swift Playgrounds route for the app, and run the keyboard from the device
  that does sign. We cannot test this without a device and an Apple account,
  so treat it as the most likely failure point.
- **The device must be trusted** and the developer mode enabled on newer iOS
  versions, or the install will be refused.
- **The iOS version must be 26 or later.** The app targets iOS 26 because
  that is the floor for Apple's on-device model.
