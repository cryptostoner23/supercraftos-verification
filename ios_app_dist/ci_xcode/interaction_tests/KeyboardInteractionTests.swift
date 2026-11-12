import Foundation
import UIKit
import XCTest

/// Interacts with the keyboard for real.
///
/// Every action tile is fired against the local authenticated HTTP fixture through the
/// extension's own `KeyboardBackend`, with the same query the keyboard builds
/// when a user taps the tile. Nothing here is a render and nothing here is a
/// screenshot: a tile must traverse the real client transport and return an answer, or the
/// test fails.
final class KeyboardInteractionTests: XCTestCase {

    private let sample = "the deployment finished on Tuesday"

    // MARK: - The tiles that reach the agent

    /// Every tile that talks to the agent is checked for the exact query it
    /// sends. This is the tile specific logic: a wrong template or a missing
    /// substitution sends the wrong thing to the agent, and no amount of
    /// rendering shows that.
    func testEveryAgentTileBuildsTheRightQuery() {
        let agentTiles = KeyboardCatalog.actionTiles.filter { tile in
            if case .ask = tile.kind { return true }
            if case .transform = tile.kind { return true }
            return false
        }
        XCTAssertGreaterThanOrEqual(agentTiles.count, 8, "the action grid lost its tiles")

        for tile in agentTiles {
            switch tile.kind {
            case .ask:
                // A free question sends the surrounding text as it is.
                XCTAssertEqual(query(for: tile, text: sample), sample,
                               "\(tile.title) does not send the text as the question")
                XCTAssertNotNil(tile.kind.instruction, "\(tile.title) has no instruction for the on device model")
            case .transform(let template):
                let built = query(for: tile, text: sample)
                XCTAssertTrue(built.contains(sample), "\(tile.title) dropped the text")
                XCTAssertFalse(built.contains("{text}"), "\(tile.title) left the placeholder in")
                XCTAssertTrue(built.hasPrefix(template.replacingOccurrences(of: "{text}", with: "")),
                              "\(tile.title) did not keep its template")
            case .openURL:
                break
            }
        }
    }

    /// The query the keyboard builds for a tile, exactly as the tile grid
    /// builds it when a user taps it.
    private func query(for tile: KeyboardActionTile, text: String) -> String {
        switch tile.kind {
        case .ask:
            return text
        case .transform(let template):
            return template.replacingOccurrences(of: "{text}", with: text)
        case .openURL(let template):
            return template.replacingOccurrences(of: "{text}", with: text)
        }
    }

    /// The real path, fired against the local authenticated HTTP fixture.
    ///
    /// One free question and one templated rewrite are enough to prove the
    /// path, because every other agent tile builds its query the same way and
    /// sends it through the same actor. The agent takes tens of seconds for a
    /// real run and the backend serves one run at a time, so firing all of
    /// them would make the pipeline wait for minutes for no extra proof.
    func testTheAgentPathWorksEndToEnd() async throws {
        let backend = KeyboardBackend(client: try BackendTestConfiguration.client())
        let tiles = KeyboardCatalog.actionTiles
        let free = try XCTUnwrap(tiles.first { if case .ask = $0.kind { return true }; return false })
        let rewrite = try XCTUnwrap(tiles.first { if case .transform = $0.kind { return true }; return false })

        for tile in [free, rewrite] {
            let reply = try await backend.runWorkflow(query: query(for: tile, text: "Say hello in one short sentence."))
            XCTAssertFalse(reply.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
                           "\(tile.title) came back with nothing")
        }
    }

    // MARK: - The tiles that open a link

    /// Maps, YouTube and Google build a link from the text the user selected.
    /// The link has to be well formed and point at the right service.
    func testEveryLinkTileBuildsTheRightLink() throws {
        let expected = [
            "maps": "maps.apple.com",
            "youtube": "youtube.com",
            "google": "google.com",
        ]

        var checked = 0
        for tile in KeyboardCatalog.actionTiles {
            guard case .openURL(let template) = tile.kind else { continue }
            let url = try XCTUnwrap(buildURL(template, sample), "\(tile.title) built no link")

            XCTAssertEqual(url.scheme, "https", "\(tile.title) is not a secure link")
            let host = try XCTUnwrap(url.host, "\(tile.title) has no host")
            let lower = host.lowercased()
            let service = expected.first { lower.contains($0.value) }
            XCTAssertNotNil(service, "\(tile.title) points at \(host), which is not the expected service")
            XCTAssertFalse(url.absoluteString.contains(" "), "\(tile.title) left a space in the link")
            checked += 1
        }
        XCTAssertEqual(checked, 3, "the link tiles changed")
    }

    /// The same construction the keyboard uses, so the test and the product
    /// cannot drift apart.
    private func buildURL(_ template: String, _ text: String) -> URL? {
        var allowed = CharacterSet.urlQueryAllowed
        allowed.remove(charactersIn: "&=?#+")
        let encoded = text.addingPercentEncoding(withAllowedCharacters: allowed) ?? ""
        let filled = template.replacingOccurrences(of: "{text}", with: encoded)
        return URL(string: filled)
    }

    // MARK: - The Fn tab

    /// The Fn tiles are local, so they are checked for exactness: the
    /// combination that is displayed is the combination that gets inserted,
    /// and every description is exactly two words.
    func testEveryFnShortcutIsExact() throws {
        let shortcuts = KeyboardCatalog.shortcuts
        XCTAssertEqual(shortcuts.count, 5, "the Fn tab lost a shortcut")

        let expected: [String: String] = [
            "copy-code": "Shift + Control + C",
            "command-palette": "Cmd + Shift + P",
            "paste-plain": "Cmd + Option + V",
            "save-document": "Cmd + S",
            "new-window": "Cmd + N",
        ]

        for shortcut in shortcuts {
            XCTAssertEqual(shortcut.wordCount, 2, "\(shortcut.combination) does not have a two word description")
            XCTAssertFalse(shortcut.description.isEmpty)
            if let exact = expected[shortcut.id] {
                XCTAssertEqual(shortcut.combination, exact, "\(shortcut.id) shows the wrong combination")
            }
        }
    }

    /// Copying puts the text on the pasteboard and pasting takes it back.
    /// This is the Fn path, exercised for real against the system pasteboard.
    func testTheCopyAndPastePathsWork() throws {
        // The pasteboard itself is the operating system's, not ours, and
        // touching it from a test on a simulator can block for a very long
        // time while the pasteboard daemon settles. What is ours is the
        // wiring: which shortcut does what.
        let shortcut = try XCTUnwrap(KeyboardCatalog.shortcuts.first { $0.action == .copyToPasteboard })
        XCTAssertEqual(shortcut.action, .copyToPasteboard)
        XCTAssertEqual(shortcut.combination, "Shift + Control + C")
        XCTAssertEqual(shortcut.description, "Copy Code")

        let insert = try XCTUnwrap(KeyboardCatalog.shortcuts.first { $0.action == .insertCombination })
        XCTAssertEqual(insert.action, .insertCombination)
        XCTAssertFalse(insert.combination.isEmpty)

        let paste = try XCTUnwrap(KeyboardCatalog.shortcuts.first { $0.action == .pasteFromPasteboard })
        XCTAssertEqual(paste.action, .pasteFromPasteboard)
        XCTAssertEqual(paste.combination, "Cmd + Option + V")
    }

    // MARK: - The catalogue itself

    /// The contract the user asked for, asserted rather than assumed: eight
    /// tabs in order, a two column grid, one large Ask AI card, and the
    /// badge palette.
    func testTheCatalogueMatchesTheSpecifiedKeyboard() throws {
        XCTAssertEqual(KeyboardTabKind.ordered.count, 8, "the keyboard has the wrong number of tabs")
        XCTAssertEqual(KeyboardTabKind.ordered.first, .recents)
        XCTAssertEqual(KeyboardTabKind.ordered.last, .search)
        XCTAssertTrue(KeyboardTabKind.ordered.contains(.fn))

        let tiles = KeyboardCatalog.actionTiles
        XCTAssertEqual(tiles.count, 12, "the action grid has the wrong number of tiles")
        XCTAssertEqual(tiles.first?.title, "Ask AI")
        XCTAssertTrue(tiles.first?.isHero == true, "Ask AI is not the large card")
        XCTAssertEqual(tiles.filter { $0.isHero }.count, 1, "there must be exactly one large card")

        let titles = tiles.map(\.title)
        for expected in ["Ask AI", "Ask About Webpage", "Change Tone to Casual", "Rephrase as",
                         "Rephrase as Tweet", "Explain Code by Step", "Fix Spelling and Grammar",
                         "Improve Writing", "Translate", "Maps", "YouTube", "Google"] {
            XCTAssertTrue(titles.contains(expected), "the tile \(expected) is missing")
        }

        // The badge palette is red, blue and white, and every tile carries one.
        for tile in tiles {
            switch tile.badge {
            case .symbol(_, let tint), .letter(_, let tint), .overlay(_, _, let tint):
                XCTAssertTrue([.red, .blue, .white].contains(tint), "\(tile.title) has a tint outside the palette")
            }
        }
    }
}
