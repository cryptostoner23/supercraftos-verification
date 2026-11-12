import SwiftUI

// Top icon row: rounded pill tab buttons in a dark horizontal toolbar.
// The Search pill is aligned far right.

struct KeyboardToolbar: View {
    @Binding var selection: KeyboardTabKind

    var body: some View {
        HStack(spacing: 6) {
            ForEach(leadingTabs, id: \.self) { tab in
                tabButton(tab)
            }
            Spacer(minLength: 8)
            tabButton(.search)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .background(KeyboardTheme.canvas)
    }

    private var leadingTabs: [KeyboardTabKind] {
        KeyboardTabKind.ordered.filter { !$0.isPinnedTrailing }
    }

    private func tabButton(_ tab: KeyboardTabKind) -> some View {
        let isSelected = selection == tab
        return Button {
            selection = tab
        } label: {
            ZStack {
                if case .letter(let text, let tint) = tab.badge {
                    Text(text)
                        .font(.system(size: 9, weight: .black, design: .rounded))
                        .foregroundStyle(Color.white)
                        .padding(.horizontal, 4)
                        .padding(.vertical, 2)
                        .background(
                            RoundedRectangle(cornerRadius: 5, style: .continuous)
                                .fill(isSelected ? Color.black : KeyboardTheme.tint(for: tint))
                        )
                } else {
                    Image(systemName: tab.symbol)
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundStyle(isSelected ? Color.black : Color.white)
                }
            }
            .frame(width: 34, height: 30)
            .background(isSelected ? KeyboardTheme.selected : KeyboardTheme.tile)
            .clipShape(Capsule())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(tab.title)
    }
}
