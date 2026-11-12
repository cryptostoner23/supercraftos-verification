# SideStore deep links

SideStore registers the `sidestore` URL scheme, and its own source says what
each form does. The source is the project's repository, and the handler is
`SideStore/DeepLinks/URLHandler.swift`:

    https://raw.githubusercontent.com/SideStore/SideStore/main/SideStore/DeepLinks/URLHandler.swift

| Link | What it does |
| --- | --- |
| `sidestore://install?url=<url>` | Downloads the app at that address and starts the import, which is where SideStore resigns it with the user's own Apple ID and the device's own pairing |
| `sidestore://source?url=<url>` | Adds a source |
| `sidestore://pairing?urlname=<name>` | Exports the pairing file |

The scheme is declared in the project's `AltStore/Info.plist`:

    https://raw.githubusercontent.com/SideStore/SideStore/main/AltStore/Info.plist

This is why the install page can hand the whole job to SideStore in one tap:
the page gives it the address of the unsigned bundle, and SideStore does the
signing and the install on the device. The Apple ID and the device identifier
never leave the device and never reach the build server.

SideStore's own README states that it "resigns apps with your personal
development certificate" and "will periodically refresh your apps in the
background, to keep their normal 7-day development period from expiring",
which is what keeps the app installed without anyone doing anything.
