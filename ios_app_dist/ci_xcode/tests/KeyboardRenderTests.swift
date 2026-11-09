import SwiftUI
import UIKit
import XCTest
@testable import SuperCraftOSTests

/// Renders the real keyboard components on a simulator and checks they are not
/// blank. The PNGs are written out so the build can publish them as evidence
/// that the specified layout actually renders.
final class KeyboardRenderTests: XCTestCase {

    /// The whole keyboard, composed exactly the way the root view composes it.
    private struct KeyboardComposition: View {
        @State private var selection: KeyboardTabKind = .aiActions

        var body: some View {
            VStack(spacing: 0) {
                KeyboardToolbar(selection: $selection)
                KeyboardActionGrid(tiles: KeyboardCatalog.actionTiles) { _ in }
                    .frame(height: 236)
                    .clipped()
                KeyboardInputBar(onSpace: {}, onBackspace: {}, onReturn: {}, onGlobe: {})
            }
            .frame(width: 390, height: 336)
            .clipped()
            .background(Color(red: 0.110, green: 0.110, blue: 0.118))
            .environment(\.colorScheme, .dark)
        }
    }

    private struct FnComposition: View {
        var body: some View {
            VStack(spacing: 0) {
                KeyboardToolbar(selection: .constant(.fn))
                KeyboardFnGrid(shortcuts: KeyboardCatalog.shortcuts) { _ in }
                    .frame(height: 236)
                    .clipped()
                KeyboardInputBar(onSpace: {}, onBackspace: {}, onReturn: {}, onGlobe: {})
            }
            .frame(width: 390, height: 336)
            .clipped()
            .background(Color(red: 0.110, green: 0.110, blue: 0.118))
            .environment(\.colorScheme, .dark)
        }
    }

    // MARK: - Rendering

    /// Snapshots a view through a real window. ImageRenderer on its own does
    /// not lay out a scrolling grid, so the window is used instead.
    @MainActor
    private func snapshot<V: View>(_ view: V, named name: String) throws -> UIImage {
        let size = CGSize(width: 390, height: 336)
        let window = UIWindow(frame: CGRect(origin: .zero, size: size))
        window.rootViewController = UIHostingController(rootView: view)
        window.isHidden = false
        window.layoutIfNeeded()

        // Let the hosted view settle before drawing.
        let deadline = Date().addingTimeInterval(1.0)
        while Date() < deadline {
            RunLoop.current.run(mode: .default, before: Date().addingTimeInterval(0.05))
        }
        window.layoutIfNeeded()

        let renderer = UIGraphicsImageRenderer(size: size)
        let image = renderer.image { context in
            window.layer.render(in: context.cgContext)
        }
        XCTAssertGreaterThanOrEqual(distinctColours(image), 8, "\(name) rendered blank")
        return image
    }

    /// Counts the distinct colours in an image, which is what tells a real
    /// render apart from an empty background.
    private func distinctColours(_ image: UIImage) -> Int {
        guard let cgImage = image.cgImage else { return 0 }
        let width = cgImage.width
        let height = cgImage.height
        var pixels = [UInt8](repeating: 0, count: width * height * 4)
        guard let context = CGContext(data: &pixels, width: width, height: height,
                                      bitsPerComponent: 8, bytesPerRow: width * 4,
                                      space: CGColorSpaceCreateDeviceRGB(),
                                      bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else {
            return 0
        }
        context.draw(cgImage, in: CGRect(x: 0, y: 0, width: width, height: height))
        var seen = Set<UInt32>()
        for index in stride(from: 0, to: pixels.count, by: 4 * 37) {
            let value = UInt32(pixels[index]) << 16 | UInt32(pixels[index + 1]) << 8 | UInt32(pixels[index + 2])
            seen.insert(value)
            if seen.count > 64 { break }
        }
        return seen.count
    }

    @MainActor
    private func write(_ image: UIImage, named name: String) {
        guard let data = image.pngData() else { return }
        let environment = ProcessInfo.processInfo.environment
        guard let directory = environment["SUPERCRAFTOS_SCREENSHOT_DIR"]
            ?? environment["TEST_RUNNER_SUPERCRAFTOS_SCREENSHOT_DIR"] else { return }
        let url = URL(fileURLWithPath: directory).appendingPathComponent("\(name).png")
        try? FileManager.default.createDirectory(at: url.deletingLastPathComponent(),
                                               withIntermediateDirectories: true)
        try? data.write(to: url)
    }

    // MARK: - Tests

    @MainActor
    func testActionKeyboardRenders() throws {
        let image = try snapshot(KeyboardComposition(), named: "keyboard-ai-actions")
        write(image, named: "keyboard-ai-actions")
    }

    @MainActor
    func testFnKeyboardRenders() throws {
        let image = try snapshot(FnComposition(), named: "keyboard-fn")
        write(image, named: "keyboard-fn")
    }

    @MainActor
    func testToolbarRendersEveryTab() throws {
        for tab in KeyboardTabKind.ordered {
            let view = KeyboardToolbar(selection: .constant(tab))
            let image = try snapshot(view, named: "toolbar-\(tab.rawValue)")
            XCTAssertGreaterThanOrEqual(distinctColours(image), 8, "the toolbar did not render for \(tab.rawValue)")
        }
    }

    // MARK: - Contract

    func testCatalogContract() {
        XCTAssertEqual(KeyboardTabKind.ordered.map(\.rawValue), [
            "recents", "aiActions", "voice", "execution", "fn", "presets", "gifs", "search"
        ])
        XCTAssertEqual(KeyboardCatalog.actionTileTitles, [
            "Ask AI", "Ask About Webpage", "Change Tone to Casual", "Rephrase as",
            "Rephrase as Tweet", "Explain Code by Step", "Fix Spelling and Grammar",
            "Improve Writing", "Translate", "Maps", "YouTube", "Google"
        ])
        XCTAssertEqual(KeyboardCatalog.shortcutCombinations, [
            "Shift + Control + C", "Cmd + Shift + P", "Cmd + Option + V", "Cmd + S", "Cmd + N"
        ])
        for shortcut in KeyboardCatalog.shortcuts {
            XCTAssertEqual(shortcut.wordCount, 2, shortcut.description)
        }
    }

    func testEndpointPolicy() {
        XCTAssertTrue(BackendEndpointPolicy.isValid("https://agent.commetai.ca"))
        XCTAssertTrue(BackendEndpointPolicy.isValid("http://192.168.1.50:8787"))
        XCTAssertTrue(BackendEndpointPolicy.isValid("http://127.0.0.1:8787"))
        XCTAssertFalse(BackendEndpointPolicy.isValid("http://agent.commetai.ca"))
        XCTAssertFalse(BackendEndpointPolicy.isValid("https://user:pass@host"))
    }
}
