# The Mac build client

The 2015 MacBook Air is the signing and installation client. It is not the
compiler. The Bitrise macOS stack already compiles, tests and archives the app
with Xcode 27 against the iOS 27 SDK, and publishes the device bundles to
`https://agent.commetai.ca/ios/`. The Mac only has to sign that bundle with
your Apple ID and put it on the phone.

## What macOS the 2015 MacBook Air can run

macOS Monterey 12.x is the ceiling. Ventura 13 and later dropped the 2015
MacBook Air, so it can never run a current Xcode, whatever the disk space
allows.

## Xcode compatibility, and why you do not need it

| Xcode | Needs macOS | Installed size | Works on a 2015 Air |
| --- | --- | --- | --- |
| 27 / 26 | Tahoe 26.6+ | ~40 GB | no |
| 16.4 | Sequoia 15.3+ | ~17 GB | no |
| 15.4 | Sonoma 14.x | ~11 GB | no |
| **14.2** | **Monterey 12.5+** | **~12 GB** | **yes, and it is the newest that fits** |
| 14.1 / 14.0.x | Monterey 12.5+ | ~12 GB | yes, marginally lighter |
| 13.4.1 | Monterey 12.0+ | ~7 GB | yes, the lightest with a usable SDK |
| 12.5.1 | Catalina 10.15+ | ~5 GB | yes, the absolute lightest |

**Even if you install Xcode 14.2, it cannot build this project.** Its SDK is
iOS 16.2, so it cannot compile an app that targets iOS 17, and it has never
heard of Foundation Models. The extension would not build.

So the recommendation is the opposite of what it first looks like:

**Install no Xcode on the 2015 MacBook Air at all.**

| | Xcode on the Air | iloader on the Air |
| --- | --- | --- |
| Disk on the internal drive | 12 GB of the 30 GB, and Xcode also litters `~/Library` | **0 GB** |
| Can build this project | no, the SDK is too old | not needed, the bundle is prebuilt |
| Can sign with your free Apple ID | yes, but with a 2022 toolchain | yes |
| Can install on the iPhone | yes | yes |
| Can refresh the app every 7 days | no | yes, through SideStore |

iloader is a 19 MB standalone application. It signs any ipa with your Apple ID
and installs it, and it can install SideStore so the app renews itself over
Wi-Fi forever.

## If you want Xcode on it anyway

Install **Xcode 14.2** and put it on the external drive, which is what the
`/Volumes/EAGET/` volume is for:

```bash
# on the Mac, with the EAGET drive attached
cd /Volumes/EAGET
curl -L -o Xcode_14.2.xip https://download.developer.apple.com/Developer_Tools/Xcode_14.2/Xcode_14.2.xip
# the xip unzips to Xcode.app, and it must be moved to the volume before it is
# expanded, or the extraction writes to the internal disk
mv Xcode.app /Volumes/EAGET/Xcode.app   # expand in place, on the external volume
sudo xcode-select -s /Volumes/EAGET/Xcode.app/Contents/Developer
```

Extract the `.xip` on the external volume so nothing lands on the internal
disk, then point `xcode-select` at it. Expect roughly 12 GB on the volume and
essentially nothing on the internal disk.

Xcode 14.2 is useful for general iOS development on that machine. It is not
used to build SuperCraftOS, and the headless build script never opens the GUI.

## What the client actually does

```
scripts/mac_build.sh --install
```

1. finds the Mac over the reverse tunnel, or over the Tailscale tailnet
2. syncs `master` down
3. clears the macOS quarantine flags
4. fetches the prebuilt device bundle from `https://agent.commetai.ca/ios/`
5. signs it with your Apple ID and installs it on the connected iPhone
6. fetches the signed bundle back to the server

Nothing is written to the internal disk except the small iloader application.
Every build artefact, cache and archive stays inside `/Volumes/EAGET/`.
