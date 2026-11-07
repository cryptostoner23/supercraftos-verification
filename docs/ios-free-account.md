# Installing on your own devices with free personal Apple accounts

**Short answer: yes, you can run the full app *with* the custom keyboard on your
own iPhone or iPad, on a free personal Apple account, with no payment. You
cannot publish to TestFlight, because Apple does not allow free accounts to
distribute.**

The facts below are taken from Apple's own documentation, not from folklore.

## What a free personal team can and cannot do

Apple's [supported capabilities table for iOS][caps] has three columns: the
paid Apple Developer Program (`ADP`), the Enterprise Program (`ADEP`), and
`Apple Developer`, which is a free Apple Account that has accepted the
developer agreement. Apple's legend for that column is explicit:

> Apple Developer: Apple Account holders who have agreed to the Apple Developer
> Agreement to access certain resources on the Apple Developer website. No cost
> is associated with this agreement and **developers can't distribute apps**.

| | Free personal team |
| --- | --- |
| Run on your own registered device | **Yes** |
| App groups | **Yes** (Apple lists it as supported) |
| Keychain sharing | **Yes** |
| Background modes | **Yes** |
| App extensions | Yes, as a target type |
| **TestFlight** | **No** |
| **App Store distribution** | **No** |
| Ad hoc distribution | No |
| Push notifications, iCloud, App Groups containers in the portal | No |

Apple's [account overview][overview] gives the Personal Team limits:

- Up to **10 App IDs**, expiring after **7 days**
- Up to **3 devices**, expiring after **7 days**
- Up to **3 apps per device**
- Provisioning profiles expire **7 days** after issuance, so you rebuild and
  reinstall before then

[caps]: https://developer.apple.com/help/account/reference/supported-capabilities-ios/
[overview]: https://developer.apple.com/help/account/basics/about-your-developer-account/

## What two personal Apple accounts actually give you

An important correction to the natural assumption: **the app and the keyboard
extension must be signed by the same team.** An embedded extension has to
carry the same Team ID as its host app, and the App Group has to live on that
one team. So you cannot sign the app with one Apple ID and the keyboard with
the other. Two accounts do not unlock anything that one account cannot do.

What two accounts do give you is operational headroom:

| | One account | Two accounts |
| --- | --- | --- |
| Device slots | 3 | **6** |
| App ID headroom | 10 | **20** |
| Profile refresh clock | one 7-day window | **two staggered 7-day windows** |
| Recovery from a 10-App-ID limit | delete App IDs | use the other account |

The staggered clock is the useful one. A free profile lasts 7 days; when it
lapses the app stops launching. With two accounts you can alternate: rebuild
and reinstall with account A, and a week later with account B, and the app
never sits broken for a full week.

## The steps

### 1. Register your devices

For each account, in Xcode: **Settings > Accounts > [your Apple ID] > Manage
Certificates**, or on the developer portal under **Devices**. Every device
that will run the app must be registered against the account that signs it.
The limit is three devices per account.

### 2. Build the full app with the keyboard

```bash
export SUPERCRAFTOS_BACKEND_URL="https://your-backend-host"
scripts/ios_release.sh full
```

`full` activates the keyboard dependency in the XcodeGen spec, so the app
embeds `SuperCraftOSKeyboard.appex`. The backend address is baked into the
extension at build time through `SUPERCRAFTOS_BACKEND_URL`, which means:

- **No App Group is needed.** The extension reads its address from its own
  bundle and opens its own control session with `GET /api/session`, which is
  unauthenticated. The keyboard therefore carries **no entitlements at all**.
- The App Group is still supported and is the better long-term design, because
  then the app's address setting is the single source of truth. Enable it by
  uncommenting `CODE_SIGN_ENTITLEMENTS: SuperCraftOSKeyboard.entitlements` in
  `ios_app_dist/ci_xcode/project.yml`. A free account cannot manage App Group
  containers in the portal, which is why it is off by default.

### 3. Install and run

```bash
scripts/install_ios.sh device
```

In Xcode, set **Signing & Capabilities > Team** to the Personal Team for the
account that owns the registered device. The extension's target needs the same
team.

### 4. Enable the keyboard

Settings > General > Keyboard > Keyboards > Add New Keyboard > SuperCraftOS >
Allow Full Access. Full Access is required by Apple's own rules for any
keyboard that reaches the network, and the AI tiles call your backend.

## The caveats that are real

- **7-day expiry.** The app stops launching when the profile lapses. Rebuild
  and reinstall, or alternate accounts. This is Apple's design, not a bug.
- **No TestFlight.** If you need to install on someone else's phone, or on
  more than three devices, you need the paid program. There is no free
  workaround; sideloading tools have the same 7-day limit because they use the
  same free provisioning.
- **The keyboard needs Full Access** and therefore the backend URL must be
  correct. If the AI tiles report that the backend is not configured, the
  address was not baked in, or the App Group was expected but is not
  provisioned.
- **The backend must be reachable over HTTPS.** The app and the extension both
  refuse non-HTTPS addresses, by design.

## When something refuses to install

These are the messages that actually come up, and what each one means.

| What it says | What it is | What to do |
| --- | --- | --- |
| **"Required firewall urls are missing"**, or any other refusal when you tap the profile button | iOS rejected the configuration profile. The profile on the server now carries only Apple's documented Profile Service payload, so a web clip in it can no longer be the cause. | Skip the profile. Read the identifier with one command on a computer, or let Sideloadly read it from the device: [the fallbacks](https://agent.commetai.ca/ios/udid). |
| "The profile is not signed" | Expected. The profile is unsigned by design; it only reports the identifier once. | Tap Install anyway. |
| "The profile could not be installed because it is not signed" and it refuses | Some iOS builds refuse unsigned profiles outright. | Use the fallbacks above. |
| "Personal development teams do not support App Groups" | The App Group entitlement is on. | It is off by default. Do not turn it on with a free account: `CODE_SIGN_ENTITLEMENTS` is commented out in `ios_app_dist/ci_xcode/project.yml`. |
| "The app expired" | The seven day free profile lapsed. | Sign again, or let SideStore renew it. |
| "Unable to Verify App" | The certificate is not trusted yet. | Settings → General → VPN & Device Management → your Apple ID → Trust, on cellular data. |

## What you do not need

- A second App ID in the portal, if the App Group is off. The extension's App
  ID is created automatically by Xcode's automatic signing.
- The App Group.
- Any App Store Connect record.
- Any payment.
