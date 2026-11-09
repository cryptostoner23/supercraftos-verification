import SwiftUI

// Small colored icon badge anchored on the left of every action tile.

struct KeyboardBadgeView: View {
    let badge: KeyboardBadge

    var body: some View {
        ZStack {
            Circle()
                .fill(background)
            content
        }
        .frame(width: KeyboardTheme.badgeSize, height: KeyboardTheme.badgeSize)
    }

    private var background: Color {
        switch badge {
        case .symbol(_, let tint): return KeyboardTheme.tint(for: tint)
        case .letter(_, let tint): return KeyboardTheme.tint(for: tint)
        case .overlay(_, _, let tint): return KeyboardTheme.tint(for: tint)
        }
    }

    @ViewBuilder
    private var content: some View {
        switch badge {
        case .symbol(let name, let tint):
            Image(systemName: name)
                .font(.system(size: 12, weight: .bold))
                .foregroundStyle(foreground(for: tint))
        case .letter(let text, let tint):
            Text(text)
                .font(.system(size: 13, weight: .black, design: .serif))
                .foregroundStyle(foreground(for: tint))
        case .overlay(let first, let second, let tint):
            Image(systemName: first)
                .font(.system(size: 9, weight: .bold))
                .foregroundStyle(foreground(for: tint))
                .offset(x: -3, y: -3)
            Image(systemName: second)
                .font(.system(size: 9, weight: .bold))
                .foregroundStyle(foreground(for: tint))
                .offset(x: 4, y: 4)
        }
    }

    private func foreground(for tint: KeyboardBadgeTint) -> Color {
        tint == .white ? Color.black : Color.white
    }
}
