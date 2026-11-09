# Signing in on the iPad and the iPhone, and the four account fallback

## The short version

Each device is signed by **its own Apple ID**, through iloader on a computer
once, and then SideStore keeps it alive on its own.

| Device | Apple ID used to sign | Apple ID used in SideStore |
| --- | --- | --- |
| iPad | Account 1 | **Account 1**, the same one |
| iPhone | Account 2 | **Account 2**, the same one |
| Spare | Account 3 | Used when an account is rate limited |
| Spare | Account 4 | Used when an account is rate limited |

**The device's own iCloud sign-in does not matter.** A device can be signed into
iCloud with one Apple ID and the app can be signed with a different one. They
are unrelated. What matters is only that the Apple ID doing the signing can
register that device.

## Step by step, for each device

### 1. Install iloader on a computer

<https://github.com/nab138/iloader/releases> — Windows, Linux and macOS. No
Xcode, no Apple Developer Program, about 19 MB.

### 2. Plug the device in and sign that device's Apple ID into iloader

1. Connect the device by USB. Unlock it and tap **Trust** when it asks.
2. Open iloader, **Add Account**, and sign in with the Apple ID for **that
   device**. Account 1 for the iPad, Account 2 for the iPhone.
3. iloader registers the device with that Apple ID, which is what lets it
   provision a profile for it.
4. In iloader choose **Install SideStore** and let it finish.

### 3. Sign in inside SideStore on the device, with the same Apple ID

1. Open **SideStore**.
2. **Add Account** and sign in with the **same** Apple ID you gave iloader.
3. Tap the **7 DAYS** counter next to SideStore once. That finishes the pairing
   and SideStore starts renewing the certificate in the background.

### 4. Install the app

In SideStore tap **+** and choose
`SuperCraftOS-iOS-Device-WithKeyboard-unsigned.ipa`. SideStore signs it with
the account you are signed in with and installs it.

### 5. Turn the keyboard on

Settings → General → Keyboard → Keyboards → Add New Keyboard → **SuperCraftOS**,
then switch to it with the globe key and turn on **Allow Full Access**. Apple
requires it for any keyboard that uses the network, and the AI tiles call your
agent.

### 6. Point the app at your control center

Open the app, **Connection**, and enter the address. The published build is
already pointed at it.

## What each account can carry

These limits are **per Apple ID**, which is why four accounts help.

| Limit | Per account | With four accounts |
| --- | --- | --- |
| App IDs registered per 7 days | 10 | 40 |
| Apps installed per device | 3 | 12 |
| Devices | 3 | 12 |
| Provisioning profile lifetime | 7 days | 7 days each |

The app and the keyboard extension are **two** registrations, because an
extension has its own App ID. So a device with the keyboard uses two of the
three app slots.

## The fallback, and what is actually true about the timing

**A free Apple ID's profile lasts 7 days, not 14 or 21.** That number is fixed
by Apple. What SideStore changes is that you do not have to be there when it
happens: SideStore renews the certificate automatically in the background over
Wi-Fi, as long as LocalDevVPN is connected. In normal use the app never
expires.

**Where the extra accounts matter** is the common failure: a free account gets
rate limited, and then registration fails with an error and the app stops
renewing. That is when you switch to a spare.

### The swap

1. In iloader on the computer, **Add Account** and sign in with a spare.
2. **Import IPA** and pick the same `.ipa`, or use SideStore's own account
   switching if the version you have offers it.
3. Install it over the top. iOS replaces the app.

Two things to expect on a swap:

- **The app's saved settings may be cleared**, because iOS treats an app signed
  by a different team as a different app. The backend address is one field to
  type again in **Connection**, and the control token is fetched automatically.
- **The keyboard is swapped with it**, since it is inside the app bundle, so
  enable it again in Settings if iOS asks.

### The timing that actually helps

If you want to stretch the life rather than recover from a rate limit, sign the
app with a different account **before** the 7 days are up. Each account carries
its own 7-day window, so two accounts on the same device give you two
independent windows, and four give you four. SideStore can hold more than one
account on some versions, which makes the rotation automatic.

## The rule that actually matters

**The app and the keyboard extension must be signed by the same Apple ID.**
An embedded extension and its host have to belong to one team. If they are
signed by different accounts, the install fails and you will see an error
about the bundle identifier not matching.

## One thing to keep in mind

Apple does not publish a rate limit for free accounts, and the practical
failure mode is an error that says the registration was refused. When that
happens, the account is usually limited for a period of days. That is exactly
what the spares are for.

## Signing all four accounts in one run

`scripts/sign_with_apple_ids.sh` does the whole rotation from the command
line, with the `sign-for-devices` binary in `tools/`:

```bash
scripts/sign_with_apple_ids.sh
```

It signs the newest unsigned device build with the four accounts, in order,
and writes one bundle per account to `release/ios/signed/`:

```
release/ios/signed/harjeev_kohli_at_hotmail.com.ipa
release/ios/signed/cryptostoner94_at_icloud.com.ipa
release/ios/signed/cryptostoner_at_iloud.com.ipa
release/ios/signed/ngboy69_at_hotmail.com.ipa
```

What it asks for, per account:

1. **The Apple ID password**, typed with the echo off. It goes into the
   `SUPERCRAFTOS_APPLE_PASSWORD` environment variable of that one signer run
   and nowhere else. It is never written to a file, never on a command line
   and never in the shell history.
2. **The two factor code**, typed when the signer asks for it. It goes into
   the signer's standard input and is not stored either.

What it does with a failure: **it keeps going.** A rate limited account costs
that one account, the run moves on to the next one, and the table at the end
says which bundles exist:

```
  APPLE ID                       STATE    BUNDLE
  harjeev_kohli@hotmail.com      ok       release/ios/signed/harjeev_kohli_at_hotmail.com.ipa (1.4 MB)
  cryptostoner94@icloud.com      failed   the signer exited with status 1 and wrote no bundle
```

The devices come from `data/ios-devices.json`, the list the UDID capture
service writes, or from `--udid` when you want to be explicit. The run is
safe to repeat: it overwrites the bundle of the account it signs again and
leaves the other ones alone.

Useful options:

```bash
scripts/sign_with_apple_ids.sh --dry-run          # the plan, without signing
scripts/sign_with_apple_ids.sh --list-devices     # the devices it would sign for
scripts/sign_with_apple_ids.sh --shared-password  # type the password once
scripts/sign_with_apple_ids.sh --apple-id a@b.com --apple-id c@d.com
```

To install a bundle it produced, on a Mac with Xcode:

```bash
xcrun devicectl device install app release/ios/signed/harjeev_kohli_at_hotmail.com.ipa
```

or with libimobiledevice, on any machine:

```bash
ideviceinstaller -i release/ios/signed/harjeev_kohli_at_hotmail.com.ipa
```

or through Sideloadly, which is the one that keeps working after the 7 days
are up.
