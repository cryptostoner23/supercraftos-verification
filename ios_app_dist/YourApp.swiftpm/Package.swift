// swift-tools-version: 5.9
import PackageDescription
import AppleProductTypes

let package = Package(
    name: "SuperCraftOS",
    platforms: [.iOS("17.0")],
    products: [
        .iOSApplication(
            name: "SuperCraftOS",
            targets: ["AppModule"],
            bundleIdentifier: "com.supercraftos.control",
            displayVersion: "1.0",
            bundleVersion: "1",
            supportedDeviceFamilies: [.pad, .phone],
            supportedInterfaceOrientations: [.portrait, .landscapeRight, .landscapeLeft]
        )
    ],
    targets: [.executableTarget(name: "AppModule", path: ".")]
)
