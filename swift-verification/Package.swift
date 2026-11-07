// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "SuperCraftOSVerification",
    platforms: [.macOS(.v14), .iOS(.v17)],
    products: [.executable(name: "supercraftos-check", targets: ["ControlCLI"])],
    targets: [
        .target(name: "ControlCore"),
        .executableTarget(name: "ControlCLI", dependencies: ["ControlCore"]),
        .testTarget(name: "ControlCLITests", dependencies: ["ControlCore"]),
        .testTarget(name: "ControlCoreTests", dependencies: ["ControlCore"])
    ]
)
