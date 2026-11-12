# Capturing an iOS device UDID without a Mac

The Apple developer portal needs a device's UDID before it can put that device
into a development or ad hoc provisioning profile. The usual way to read it is
`idevice_id` or Xcode, and both need a computer. This is the way to do it with
nothing but the device and a link.

## What the user does

On each device, in Safari:

1. Open **https://agent.commetai.ca/ios/udid**
2. Tap **Install the profile on this device** (the pink button).
3. iOS shows the profile. Tap **Allow**, then **Install**.
   iOS says the profile is not signed. That is expected, install it anyway.
4. iOS asks for permission to send the device identifier. Tap **Allow**.
5. The UDID arrives at the server and the page shows it, in full, ready to
   copy into the developer portal under
   **Certificates, Identifiers and Profiles → Devices → +**.

Then remove the profile:

**Settings → General → VPN & Device Management → SuperCraftOS device UDID →
Remove Profile → Remove**.

The Home Screen icon that the profile added goes away with it.

If the profile reports nothing, the same page has a manual field where the
user can type a UDID they read from the device or from a computer. It posts to
the same endpoint.

## How the capture works

The profile at `https://agent.commetai.ca/ios/udid.mobileconfig` carries two
payloads. `scripts/udid_capture.py` writes it.

### The "Profile Service" payload does the capture

This is Apple's documented OTA profile service payload. The payload type is the
literal string `Profile Service`, and it carries a `PayloadContent` **dict**
with the URL the device must call and the device attributes it must report:

```xml
<key>PayloadType</key><string>Profile Service</string>
<key>PayloadContent</key>
<dict>
  <key>URL</key><string>https://agent.commetai.ca/ios/udid</string>
  <key>DeviceAttributes</key>
  <array>
    <string>UDID</string><string>DEVICE_NAME</string><string>PRODUCT</string>
    <string>VERSION</string><string>SERIAL</string>
  </array>
</dict>
```

When the profile is installed, the device POSTs a PKCS#7 signed plist with
those attributes to the URL, and the server answers with a redirect to the
capture page, so the user lands on the page that shows the UDID.

Sources for this payload:

- Apple, *Over-the-Air Profile Delivery and Configuration*, the "Profile
  Service Payload" section. It gives the payload type, the `URL` and
  `DeviceAttributes` keys, the list of attributes a device can report
  (`UDID`, `VERSION`, `PRODUCT`, `SERIAL`, `MEID`, `IMEI`, `ICCID`) and the
  rule that the device sends the attributes back in response to the URL.
  <https://developer.apple.com/library/archive/documentation/NetworkingInternet/Conceptual/iPhoneOTAConfiguration/profile-service/profile-service.html>
- The public UDID finder services run this same payload in production today:
  the Capgo and Capawesome tools (the profile is served at
  `https://capgo.app/api/tools/ios-udid-finder/profile`, payload type
  `Profile Service`, attributes `UDID`, `DEVICE_NAME`, `PRODUCT`, `VERSION`,
  `SERIAL`, `IMEI`, `MEID`), the open source `udid.tools` project
  (<https://github.com/udid-tools/core>), and `getudid.co`.
- Josh Wright, *Getting an iPhone UDID from Mobile Safari*
  <https://joshwright.com/tips/getting-an-iphone-udid-from-mobile-safari/>.

### The web clip payload carries the `$(UDID)` placeholder, but Apple documents no such substitution

The profile also carries a `com.apple.webClip.managed` payload whose
`PayloadURL` is

```
https://agent.commetai.ca/ios/udid?src=webclip&udid=$(UDID)
```

**The `$(UDID)` substitution is not confirmed.** Apple does not document it:

- The WebClip payload reference
  (<https://developer.apple.com/documentation/devicemanagement/webclip>)
  describes the `URL` key as "The URL of the web clip" and says nothing about
  variables.
- *Web Clips payload settings* in Apple's Platform Deployment guide
  (<https://support.apple.com/guide/deployment/web-clips-payload-settings-depbc7c7808/web>)
  documents `Label`, `URL`, `Is removable`, `Icon`, `Precomposed icon` and
  `Full screen`, and no variables.
- The only payload variables Apple documents are the macOS only
  `%HardwareUUID%`, `%SerialNumber%` and friends, and those work in the VPN
  payload on a Mac, not on iOS
  (<https://support.apple.com/guide/deployment/variables-settings-device-management-payloads-dep04666af94/web>).

So the web clip is carried because it was asked for, and because it is
harmless if the placeholder is not substituted: the icon lands on the Home
Screen and opens the capture page, and the capture itself does not depend on
it. The `Profile Service` payload is what actually reports the UDID.

## What the server does

`scripts/ios_udid_service.py` is a small stdlib HTTP server, a sibling of the
bundle upload service:

| Route | What it does |
| --- | --- |
| `GET /udid` | the capture page, with the UDID the server received |
| `GET /udid?udid=...&name=...` | records a UDID, then shows the page |
| `POST /udid` | the Profile Service callback, and the manual entry form |
| `GET /udid.mobileconfig` | the profile to install |
| `GET /udid.webclip.mobileconfig` | the web clip payload on its own |
| `GET /udid.service.mobileconfig` | the Profile Service payload on its own |
| `GET /health` | liveness and the device count |

The routes answer with or without the `/ios` prefix, the same way the upload
service does, so Caddy can proxy the path unchanged.

The captured devices are stored in `data/ios-devices.json`, which is
gitignored. One record per device, keyed by UDID, with the name, model, iOS
version, serial number, the source of the capture and the first and last time
it was seen. The public page shows the device you are holding in full and
masks the others, so a UDID is not published for every device in the list.

Both UDID shapes are accepted: the 40 character form
(`b59769e6c28b73b1195009d4b21c0123456789ab`) and the 25 character form Apple
uses since 2018 on A12 and later (`00008110-001965E62213801E`).

## The service on this server

- systemd unit: `/etc/systemd/system/supercraftos-ios-udid.service`, on
  `127.0.0.1:8798`.
- Caddy route in `/etc/caddy/Caddyfile`:

  ```
  @udid path /ios/udid /ios/udid.mobileconfig /ios/udid.webclip.mobileconfig /ios/udid.service.mobileconfig
  handle @udid {
      reverse_proxy 127.0.0.1:8798
  }
  ```

  It sits before the `@ios` static file route, which would otherwise answer
  for `/ios/udid`.
- The store path and the public base url come from `IOS_UDID_STORE` and
  `IOS_UDID_BASE_URL`.

Regenerate the profile by hand with:

```bash
.venv/bin/python scripts/udid_capture.py --output /tmp/udid.mobileconfig
.venv/bin/python scripts/udid_capture.py --variant webclip --print
```

The tests are in `test_ios_udid_capture.py` and run in the pipeline:

```bash
.venv/bin/python -m unittest -q test_ios_udid_capture.py
```

## Caveats

- The profile is not signed, so iOS calls it an unverified profile. Tap
  Install anyway. Nothing on the device changes: the profile only reports the
  device identifier.
- Open the link in **Safari**. In-app browsers do not install profiles.
- If the device has Stolen Device Protection, iOS can refuse the install.
  The device has to be unlocked and the passcode known.
- The web clip payload adds a Home Screen icon. Removing the profile removes
  the icon.
- A UDID is an identifier, not a secret, but it is kept off the public page
  for the devices that are not in front of the user.
