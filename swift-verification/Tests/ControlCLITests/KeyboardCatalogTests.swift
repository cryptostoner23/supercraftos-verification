import Foundation
import XCTest
@testable import ControlCore

/// Locks the SuperCraftOS keyboard specification so that any change to the
/// header toolbar, the action tile grid, the Fn tab, or the bottom input
/// controls fails the build instead of silently drifting.
final class KeyboardCatalogTests: XCTestCase {

    func testToolbarTabSequenceIsExact() {
        XCTAssertEqual(
            KeyboardTabKind.ordered.map(\.rawValue),
            ["recents", "aiActions", "voice", "execution", "fn", "presets", "gifs", "search"]
        )
    }

    func testToolbarTabIconsAreExact() {
        XCTAssertEqual(KeyboardTabKind.ordered.map(\.symbol), [
            "clock", "sparkles", "waveform", "bolt.fill", "fn", "slider.horizontal.3", "gif", "magnifyingglass"
        ])
    }

    func testGifsTabUsesAWordBadgeBecauseThereIsNoSymbol() {
        // There is no SF Symbol for a GIF badge, so the tab carries the word.
        XCTAssertEqual(KeyboardTabKind.gifs.badge, .letter("GIF", .blue))
        XCTAssertEqual(KeyboardTabKind.search.badge, .symbol("magnifyingglass", .white))
        XCTAssertEqual(KeyboardTabKind.aiActions.badge, .symbol("sparkles", .white))
    }

    func testSearchTabIsPinnedToTheTrailingEdge() {
        XCTAssertTrue(KeyboardTabKind.search.isPinnedTrailing)
        XCTAssertEqual(KeyboardTabKind.ordered.last, .search)
        XCTAssertEqual(KeyboardTabKind.ordered.filter(\.isPinnedTrailing).count, 1)
    }

    func testActionTileTitlesAreExactAndOrdered() {
        XCTAssertEqual(KeyboardCatalog.actionTileTitles, [
            "Ask AI",
            "Ask About Webpage",
            "Change Tone to Casual",
            "Rephrase as",
            "Rephrase as Tweet",
            "Explain Code by Step",
            "Fix Spelling and Grammar",
            "Improve Writing",
            "Translate",
            "Maps",
            "YouTube",
            "Google"
        ])
    }

    func testActionGridIsTwoColumns() {
        XCTAssertEqual(KeyboardCatalog.leftColumn().count, 6)
        XCTAssertEqual(KeyboardCatalog.rightColumn().count, 6)
        XCTAssertEqual(KeyboardCatalog.leftColumn().first?.title, "Ask AI")
        XCTAssertEqual(KeyboardCatalog.rightColumn().first?.title, "Ask About Webpage")
        XCTAssertEqual(KeyboardCatalog.actionTiles.count, 12)
    }

    func testAskAIIsTheLargeLeftHandCard() {
        let hero = KeyboardCatalog.actionTiles.filter(\.isHero)
        XCTAssertEqual(hero.count, 1)
        XCTAssertEqual(hero.first?.title, "Ask AI")
        XCTAssertEqual(KeyboardCatalog.leftColumn().first?.isHero, true)
    }

    func testEveryTileCarriesABadge() {
        for tile in KeyboardCatalog.actionTiles {
            let tint: KeyboardBadgeTint
            switch tile.badge {
            case .symbol(let name, let value):
                XCTAssertFalse(name.isEmpty, "\(tile.title) is missing its badge glyph")
                tint = value
            case .letter(let text, let value):
                XCTAssertFalse(text.isEmpty, "\(tile.title) is missing its badge letter")
                tint = value
            case .overlay(let first, let second, let value):
                XCTAssertFalse(first.isEmpty)
                XCTAssertFalse(second.isEmpty)
                tint = value
            }
            XCTAssertTrue(
                KeyboardBadgeTint.allCases.contains(tint),
                "\(tile.title) badge must use the red / blue / white palette"
            )
        }
    }

    func testBadgePaletteIsFullyUsed() {
        var used = Set<KeyboardBadgeTint>()
        for tile in KeyboardCatalog.actionTiles {
            switch tile.badge {
            case .symbol(_, let value), .letter(_, let value), .overlay(_, _, let value):
                used.insert(value)
            }
        }
        XCTAssertEqual(used, Set(KeyboardBadgeTint.allCases))
    }

    func testBadgeTintsUseTheRedBlueWhitePalette() {
        XCTAssertEqual(KeyboardBadgeTint.allCases.count, 3)
        XCTAssertEqual(KeyboardBadgeTint.red.hex, "#FF453A")
        XCTAssertEqual(KeyboardBadgeTint.blue.hex, "#0A84FF")
        XCTAssertEqual(KeyboardBadgeTint.white.hex, "#FFFFFF")
    }

    func testFnTabIncludesTheRequiredShortcuts() {
        XCTAssertEqual(KeyboardCatalog.shortcutCombinations, [
            "Shift + Control + C",
            "Cmd + Shift + P",
            "Cmd + Option + V",
            "Cmd + S",
            "Cmd + N"
        ])
    }

    func testEveryShortcutDescriptionIsExactlyTwoWords() {
        for shortcut in KeyboardCatalog.shortcuts {
            XCTAssertEqual(
                shortcut.wordCount, 2,
                "\(shortcut.combination) must carry an exact two word description, found \"\(shortcut.description)\""
            )
        }
    }

    func testRequiredShortcutDescriptionsAreExact() {
        let expected: [String: String] = [
            "Shift + Control + C": "Copy Code",
            "Cmd + Shift + P": "Command Palette"
        ]
        for (combination, description) in expected {
            let match = KeyboardCatalog.shortcuts.first { $0.combination == combination }
            XCTAssertNotNil(match, "missing shortcut \(combination)")
            XCTAssertEqual(match?.description ?? "", description)
        }
    }

    // MARK: - Action behaviour

    func testEveryActionTileIsBoundToAnAction() {
        for tile in KeyboardCatalog.actionTiles {
            switch tile.kind {
            case .ask:
                continue
            case .transform(let template):
                XCTAssertTrue(template.contains("{text}"), "\(tile.title) transform template needs a {text} placeholder")
            case .openURL(let template):
                XCTAssertTrue(template.contains("{text}"), "\(tile.title) URL template needs a {text} placeholder")
                XCTAssertTrue(template.hasPrefix("https://"), "\(tile.title) must open an https URL")
            }
        }
    }

    func testIntegrationTilesOpenRealDestinations() {
        let expected: [String: String] = [
            "maps": "https://maps.apple.com/?q={text}",
            "youtube": "https://www.youtube.com/results?search_query={text}",
            "google": "https://www.google.com/search?q={text}"
        ]
        for (id, template) in expected {
            let match = KeyboardCatalog.actionTiles.first { $0.id == id }
            XCTAssertEqual(match?.kind, .openURL(template), "\(id) must open \(template)")
        }
    }

    func testTextActionsAreAgentTransforms() {
        let expected = ["ask-about-webpage", "change-tone", "rephrase-as", "rephrase-as-tweet",
                        "explain-code", "fix-spelling", "improve-writing", "translate"]
        for id in expected {
            let match = KeyboardCatalog.actionTiles.first { $0.id == id }
            guard case .transform = match?.kind else {
                XCTFail("\(id) must run an agent transform")
                continue
            }
        }
    }

    func testAskAIIsTheOnlyFreeQuestion() {
        let asking = KeyboardCatalog.actionTiles.filter { $0.kind == .ask }
        XCTAssertEqual(asking.count, 1)
        XCTAssertEqual(asking.first?.title, "Ask AI")
    }

    func testEveryTextActionHasAnOnDeviceInstruction() {
        for tile in KeyboardCatalog.actionTiles {
            switch tile.kind {
            case .ask, .transform:
                let instruction = tile.kind.instruction
                XCTAssertNotNil(instruction, "\(tile.title) needs an on-device instruction")
                XCTAssertFalse(instruction?.contains("{text}") ?? true,
                               "\(tile.title) instruction must not contain the placeholder")
            case .openURL:
                XCTAssertNil(tile.kind.instruction)
            }
        }
    }

    func testClipboardShortcutsUseTheSystemPasteboard() {
        let copy = KeyboardCatalog.shortcuts.first { $0.combination == "Shift + Control + C" }
        XCTAssertEqual(copy?.action, .copyToPasteboard)
        let paste = KeyboardCatalog.shortcuts.first { $0.combination == "Cmd + Option + V" }
        XCTAssertEqual(paste?.action, .pasteFromPasteboard)
    }


    // MARK: - Backend endpoint policy

    func testPublicAddressesMustUseHTTPS() {
        XCTAssertTrue(BackendEndpointPolicy.isValid("https://agent.example.com"))
        XCTAssertFalse(BackendEndpointPolicy.isValid("http://agent.example.com"))
        XCTAssertNotNil(BackendEndpointPolicy.rejectionReason(for: "http://agent.example.com"))
    }

    func testLocalNetworkAddressesMayUseHTTP() {
        for address in ["http://127.0.0.1:8787", "http://localhost:8787",
                        "http://192.168.1.50:8787", "http://10.0.0.7:8787",
                        "http://172.16.4.2:8787", "http://169.254.1.1:8787",
                        "http://macbook.local:8787", "https://192.168.1.50:8787"] {
            XCTAssertTrue(BackendEndpointPolicy.isValid(address), address)
            XCTAssertNil(BackendEndpointPolicy.rejectionReason(for: address), address)
        }
    }

    func testAddressesWithCredentialsOrQueryAreRejected() {
        XCTAssertFalse(BackendEndpointPolicy.isValid("https://user:pass@agent.example.com"))
        XCTAssertFalse(BackendEndpointPolicy.isValid("https://agent.example.com/?token=1"))
        XCTAssertFalse(BackendEndpointPolicy.isValid("https://agent.example.com/#frag"))
        XCTAssertFalse(BackendEndpointPolicy.isValid(""))
        XCTAssertFalse(BackendEndpointPolicy.isValid("agent.example.com"))
    }

    func testPrivateHostDetection() {
        for host in ["127.0.0.1", "localhost", "::1", "192.168.0.1", "10.1.2.3", "172.20.0.1", "169.254.0.1", "box.local"] {
            XCTAssertTrue(BackendEndpointPolicy.isLocalHost(host), host)
        }
        for host in ["8.8.8.8", "172.32.0.1", "172.15.0.1", "203.0.113.9", "example.com"] {
            XCTAssertFalse(BackendEndpointPolicy.isLocalHost(host), host)
        }
    }

    // MARK: - Shared configuration

    func testSharedConfigurationKeysAreStable() {        XCTAssertEqual(KeyboardSharedConfiguration.appGroup, "group.com.supercraftos.control")
        XCTAssertEqual(KeyboardSharedConfiguration.backendKey, "supercraftos.backend")
        XCTAssertEqual(KeyboardSharedConfiguration.tokenKey, "supercraftos.token")
    }

    func testSharedConfigurationRoundTrips() {
        let store = KeyboardSharedConfiguration.defaults()
        let previousBackend = store.string(forKey: KeyboardSharedConfiguration.backendKey)
        let previousToken = store.string(forKey: KeyboardSharedConfiguration.tokenKey)
        defer {
            if let previousBackend {
                store.set(previousBackend, forKey: KeyboardSharedConfiguration.backendKey)
            } else {
                store.removeObject(forKey: KeyboardSharedConfiguration.backendKey)
            }
            if let previousToken {
                store.set(previousToken, forKey: KeyboardSharedConfiguration.tokenKey)
            } else {
                store.removeObject(forKey: KeyboardSharedConfiguration.tokenKey)
            }
        }
        KeyboardSharedConfiguration.publish(backend: "https://example.invalid", token: "token-value")
        XCTAssertEqual(KeyboardSharedConfiguration.backend(), "https://example.invalid")
        XCTAssertEqual(KeyboardSharedConfiguration.token(), "token-value")
        KeyboardSharedConfiguration.publish(backend: "https://example.invalid", token: nil)
        XCTAssertNil(KeyboardSharedConfiguration.token())
    }
}
