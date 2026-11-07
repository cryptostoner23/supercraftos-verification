import SwiftUI

// Visual constants for the SuperCraftOS keyboard extension.
// The palette matches the dark mode specification: #2C2C2E container background,
// rounded rectangular tiles, and red / blue / white icon badges.

enum KeyboardTheme {
    /// Toolbar and bottom control bar background.
    static let canvas = Color(red: 0.110, green: 0.110, blue: 0.118)      // #1C1C1E
    /// Action and shortcut grid container background.
    static let container = Color(red: 0.173, green: 0.173, blue: 0.180)  // #2C2C2E
    /// Rounded rectangular action tile background.
    static let tile = Color(red: 0.227, green: 0.227, blue: 0.235)        // #3A3A3C
    /// System input control key background.
    static let key = Color(red: 0.180, green: 0.180, blue: 0.188)         // #2E2E30
    /// Selected toolbar pill.
    static let selected = Color(red: 1.0, green: 1.0, blue: 1.0)
    /// Text on tiles and keys.
    static let label = Color.white

    static let badgeRed = Color(red: 1.000, green: 0.271, blue: 0.231)    // #FF453A
    static let badgeBlue = Color(red: 0.039, green: 0.518, blue: 1.000)   // #0A84FF
    static let badgeWhite = Color.white

    /// Ask AI hero card gradient.
    static let heroStart = Color(red: 0.639, green: 0.290, blue: 0.949)
    static let heroEnd = Color(red: 0.941, green: 0.267, blue: 0.541)

    /// Corner radii.
    static let tileCornerRadius: CGFloat = 12
    static let heroCornerRadius: CGFloat = 16
    static let keyCornerRadius: CGFloat = 8
    static let pillCornerRadius: CGFloat = 16

    /// Tile inner padding.
    static let tilePadding: CGFloat = 12
    /// Icon badge size.
    static let badgeSize: CGFloat = 24
    /// Grid column width.
    static let columnWidth: CGFloat = 172
    /// Grid gutter.
    static let gutter: CGFloat = 10

    static func tint(for badge: KeyboardBadgeTint) -> Color {
        switch badge {
        case .red: return badgeRed
        case .blue: return badgeBlue
        case .white: return badgeWhite
        }
    }
}
