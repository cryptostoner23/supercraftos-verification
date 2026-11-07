import Foundation

// Catalog of the SuperCraftOS custom keyboard. Foundation only, no UIKit or SwiftUI,
// so the exact same specification can be asserted by the portable SwiftPM test suite
// that runs on every CI build (see swift-verification/Tests/ControlCLITests).

public enum KeyboardTabKind: String, CaseIterable, Hashable {
    case recents
    case aiActions
    case voice
    case execution
    case fn
    case presets
    case gifs
    case search

    /// Top icon row order, left to right.
    public static let ordered: [KeyboardTabKind] = [
        .recents, .aiActions, .voice, .execution, .fn, .presets, .gifs, .search
    ]

    public var title: String {
        switch self {
        case .recents: return "Recents"
        case .aiActions: return "AI Actions"
        case .voice: return "Voice / Audio"
        case .execution: return "Lighting / Execution"
        case .fn: return "Fn"
        case .presets: return "Presets / Sliders"
        case .gifs: return "GIFs"
        case .search: return "Search"
        }
    }

    public var symbol: String {
        switch self {
        case .recents: return "clock"
        case .aiActions: return "sparkles"
        case .voice: return "waveform"
        case .execution: return "bolt.fill"
        case .fn: return "fn"
        case .presets: return "slider.horizontal.3"
        case .gifs: return "gif"
        case .search: return "magnifyingglass"
        }
    }

    /// The badge drawn in the toolbar.
    ///
    /// There is no SF Symbol for a GIF badge, so that tab carries a word badge
    /// instead. Rendering the toolbar on a simulator is what proved it.
    public var badge: KeyboardBadge {
        switch self {
        case .gifs: return .letter("GIF", .blue)
        default: return .symbol(symbol, .white)
        }
    }

    /// The search pill is pinned to the trailing edge of the toolbar.
    public var isPinnedTrailing: Bool { self == .search }
}

public enum KeyboardBadgeTint: String, CaseIterable, Hashable {
    case red
    case blue
    case white

    /// Hex value used by the rendered badge.
    public var hex: String {
        switch self {
        case .red: return "#FF453A"
        case .blue: return "#0A84FF"
        case .white: return "#FFFFFF"
        }
    }
}

/// What an action tile does when it is tapped.
public enum KeyboardActionKind: Equatable {
    /// Send the surrounding document context to the agent as a free question.
    case ask
    /// Send the surrounding document context to the agent through a prompt template.
    /// The template contains the `{text}` placeholder.
    case transform(String)
    /// Open a URL built from the surrounding document context.
    /// The template contains the `{text}` placeholder.
    case openURL(String)

    /// The instruction without the text, for a model that receives the text
    /// separately, such as the on-device Foundation Models path.
    public var instruction: String? {
        switch self {
        case .ask:
            return "Answer the question below."
        case .transform(let template):
            let stripped = template.replacingOccurrences(of: "{text}", with: "")
            let trimmed = stripped.trimmingCharacters(in: .whitespacesAndNewlines)
            return trimmed.isEmpty ? nil : trimmed
        case .openURL:
            return nil
        }
    }
}

/// What a Fn shortcut trigger does when it is tapped.
public enum KeyboardShortcutAction: Equatable {
    /// Copy the surrounding document context to the system pasteboard.
    case copyToPasteboard
    /// Insert the system pasteboard contents as plain text.
    case pasteFromPasteboard
    /// Insert the key combination as text.
    case insertCombination
}

public enum KeyboardBadge: Equatable {
    /// Single SF Symbol glyph.
    case symbol(String, KeyboardBadgeTint)
    /// Text glyph, used for the "Improve Writing" capital I and the Google "G".
    case letter(String, KeyboardBadgeTint)
    /// Two overlapping SF Symbol glyphs, used for the checkmark + pencil badge.
    case overlay(String, String, KeyboardBadgeTint)
}

public struct KeyboardActionTile: Equatable, Identifiable {
    public let id: String
    public let title: String
    public let subtitle: String?
    public let badge: KeyboardBadge
    /// The Ask AI card is the large left hand action card of the grid.
    public let isHero: Bool
    /// What the tile does when it is tapped.
    public let kind: KeyboardActionKind

    public init(id: String, title: String, subtitle: String? = nil, badge: KeyboardBadge,
                isHero: Bool = false, kind: KeyboardActionKind = .ask) {
        self.id = id
        self.title = title
        self.subtitle = subtitle
        self.badge = badge
        self.isHero = isHero
        self.kind = kind
    }
}

public struct KeyboardShortcut: Equatable, Identifiable {
    public let id: String
    /// Exact key combination as displayed on the tile.
    public let combination: String
    /// Exact two word functional description.
    public let description: String
    /// What the trigger does when it is tapped.
    public let action: KeyboardShortcutAction

    public init(id: String, combination: String, description: String,
                action: KeyboardShortcutAction = .insertCombination) {
        self.id = id
        self.combination = combination
        self.description = description
        self.action = action
    }

    public var wordCount: Int {
        description.split(separator: " ").count
    }
}

public enum KeyboardCatalog {

    /// Action tile grid, two columns, ordered left to right then top to bottom.
    public static let actionTiles: [KeyboardActionTile] = [
        KeyboardActionTile(
            id: "ask-ai",
            title: "Ask AI",
            subtitle: "Prompt the assistant",
            badge: .symbol("sparkles", .red),
            isHero: true,
            kind: .ask
        ),
        KeyboardActionTile(
            id: "ask-about-webpage",
            title: "Ask About Webpage",
            badge: .symbol("questionmark.circle", .blue),
            kind: .transform("The user is reading a webpage. Answer the question about the page content below.\n\n{text}")
        ),
        KeyboardActionTile(
            id: "change-tone",
            title: "Change Tone to Casual",
            badge: .symbol("message.bubble", .blue),
            kind: .transform("Rewrite the following text in a casual tone. Return only the rewritten text.\n\n{text}")
        ),
        KeyboardActionTile(
            id: "rephrase-as",
            title: "Rephrase as",
            badge: .symbol("arrow.triangle.2.circlepath", .red),
            kind: .transform("Rephrase the following text. Return only the rephrased text.\n\n{text}")
        ),
        KeyboardActionTile(
            id: "rephrase-as-tweet",
            title: "Rephrase as Tweet",
            badge: .symbol("bird", .blue),
            kind: .transform("Rewrite the following text as a tweet. Return only the tweet.\n\n{text}")
        ),
        KeyboardActionTile(
            id: "explain-code",
            title: "Explain Code by Step",
            badge: .symbol("chevron.left.forwardslash.chevron.right", .white),
            kind: .transform("Explain the following code step by step.\n\n{text}")
        ),
        KeyboardActionTile(
            id: "fix-spelling",
            title: "Fix Spelling and Grammar",
            badge: .overlay("checkmark", "pencil", .blue),
            kind: .transform("Fix spelling and grammar in the following text. Return only the corrected text.\n\n{text}")
        ),
        KeyboardActionTile(
            id: "improve-writing",
            title: "Improve Writing",
            badge: .letter("I", .white),
            kind: .transform("Improve the writing of the following text. Return only the improved text.\n\n{text}")
        ),
        KeyboardActionTile(
            id: "translate",
            title: "Translate",
            subtitle: "Google Translate",
            badge: .symbol("character.book.closed", .blue),
            kind: .transform("Translate the following text to English. Return only the translation.\n\n{text}")
        ),
        KeyboardActionTile(
            id: "maps",
            title: "Maps",
            subtitle: "Apple Maps",
            badge: .symbol("map", .blue),
            kind: .openURL("https://maps.apple.com/?q={text}")
        ),
        KeyboardActionTile(
            id: "youtube",
            title: "YouTube",
            badge: .symbol("play.rectangle", .red),
            kind: .openURL("https://www.youtube.com/results?search_query={text}")
        ),
        KeyboardActionTile(
            id: "google",
            title: "Google",
            badge: .letter("G", .white),
            kind: .openURL("https://www.google.com/search?q={text}")
        )
    ]

    /// Dedicated Fn tab shortcut trigger keys.
    public static let shortcuts: [KeyboardShortcut] = [
        KeyboardShortcut(id: "copy-code", combination: "Shift + Control + C", description: "Copy Code",
                         action: .copyToPasteboard),
        KeyboardShortcut(id: "command-palette", combination: "Cmd + Shift + P", description: "Command Palette"),
        KeyboardShortcut(id: "paste-plain", combination: "Cmd + Option + V", description: "Paste Plain",
                         action: .pasteFromPasteboard),
        KeyboardShortcut(id: "save-document", combination: "Cmd + S", description: "Save Document"),
        KeyboardShortcut(id: "new-window", combination: "Cmd + N", description: "New Window")
    ]

    /// Left hand column of the two column grid.
    public static func leftColumn() -> [KeyboardActionTile] {
        actionTiles.enumerated().compactMap { $0.offset % 2 == 0 ? $0.element : nil }
    }

    /// Right hand column of the two column grid.
    public static func rightColumn() -> [KeyboardActionTile] {
        actionTiles.enumerated().compactMap { $0.offset % 2 == 1 ? $0.element : nil }
    }

    /// Exact tile titles, in grid order.
    public static var actionTileTitles: [String] { actionTiles.map(\.title) }

    /// Exact key combinations, in Fn tab order.
    public static var shortcutCombinations: [String] { shortcuts.map(\.combination) }
}

/// Where a backend address may point, and whether plaintext HTTP is allowed.
///
/// The app and the keyboard share this policy so they never disagree about
/// which endpoint they are allowed to talk to. The rule is deliberately
/// narrow: a public host must use HTTPS, and plaintext HTTP is only ever
/// allowed to a host on the local network, so the app keeps working on a LAN
/// with no internet, no VPN and no mesh tunnel.
public enum BackendEndpointPolicy {

    /// The message shown when an address is rejected.
    public static func rejectionReason(for raw: String) -> String? {
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return "Enter a backend address." }
        guard let url = URL(string: trimmed), url.host != nil else {
            return "That is not a valid address."
        }
        guard url.user == nil, url.password == nil else {
            return "Remove the credentials from the address."
        }
        guard url.query == nil, url.fragment == nil else {
            return "Remove the query and fragment from the address."
        }
        switch url.scheme?.lowercased() {
        case "https":
            return nil
        case "http":
            if allowsPlaintext(host: url.host ?? "") { return nil }
            return "Plain HTTP is only allowed on the local network. Use HTTPS for a public address."
        default:
            return "The address must start with https."
        }
    }

    /// Whether the address is acceptable.
    public static func isValid(_ raw: String) -> Bool {
        rejectionReason(for: raw) == nil
    }

    /// Whether plaintext HTTP may be used to reach the host.
    public static func allowsPlaintext(host: String) -> Bool {
        isLocalHost(host)
    }

    /// Whether the host is on the local network, so a plaintext or self
    /// addressed endpoint is legitimate there.
    public static func isLocalHost(_ host: String) -> Bool {
        let name = host.lowercased().trimmingCharacters(in: CharacterSet(charactersIn: "[]"))
        if name == "localhost" || name == "::1" || name.hasSuffix(".local") { return true }
        if name.hasPrefix("127.") { return true }
        if name.hasPrefix("10.") { return true }
        if name.hasPrefix("192.168.") { return true }
        if name.hasPrefix("169.254.") { return true }
        if name.hasPrefix("172.") {
            let parts = name.split(separator: ".")
            if parts.count == 4, let second = Int(parts[1]), (16...31).contains(second) { return true }
        }
        return false
    }
}

/// Configuration shared between the SuperCraftOS app and its keyboard extension.
///
/// The app owns the backend address and the control session token. The keyboard
/// extension runs in a separate process with a separate container, so both are
/// published into the shared App Group suite. On a simulator, or when the App
/// Group is not provisioned, the suite falls back to the standard defaults.
public enum KeyboardSharedConfiguration {
    public static let appGroup = "group.com.supercraftos.control"
    public static let backendKey = "supercraftos.backend"
    public static let tokenKey = "supercraftos.token"

    /// The shared preferences container, or the standard one when the App Group
    /// suite is unavailable.
    public static func defaults() -> UserDefaults {
        UserDefaults(suiteName: appGroup) ?? .standard
    }

    /// Publish the backend address and control token for the keyboard extension.
    /// The value is written to the shared App Group suite and to the standard
    /// defaults, so the host app keeps working when the App Group is absent.
    public static func publish(backend: String, token: String?) {
        for store in [defaults(), .standard] {
            store.set(backend, forKey: backendKey)
            if let token, !token.isEmpty {
                store.set(token, forKey: tokenKey)
            } else {
                store.removeObject(forKey: tokenKey)
            }
        }
    }

    /// The configured backend address, or an empty string.
    public static func backend() -> String {
        let shared = defaults().string(forKey: backendKey) ?? ""
        if !shared.isEmpty { return shared }
        return UserDefaults.standard.string(forKey: backendKey) ?? ""
    }

    /// The cached control session token, when the app has already connected.
    public static func token() -> String? {
        let shared = defaults().string(forKey: tokenKey)
        if let shared, !shared.isEmpty { return shared }
        return UserDefaults.standard.string(forKey: tokenKey)
    }
}
