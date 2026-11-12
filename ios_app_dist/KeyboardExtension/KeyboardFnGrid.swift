import SwiftUI

// Dedicated Fn tab: grid of shortcut trigger keys.
// Every tile shows the exact key combination and an exact two word description.

struct KeyboardFnGrid: View {
    let shortcuts: [KeyboardShortcut]
    let onSelect: (KeyboardShortcut) -> Void

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(alignment: .top, spacing: KeyboardTheme.gutter) {
                column(KeyboardCatalog.shortcuts.enumerated().compactMap { $0.offset % 2 == 0 ? $0.element : nil })
                column(KeyboardCatalog.shortcuts.enumerated().compactMap { $0.offset % 2 == 1 ? $0.element : nil })
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
        }
        .background(KeyboardTheme.container)
    }

    @ViewBuilder
    private func column(_ items: [KeyboardShortcut]) -> some View {
        VStack(spacing: KeyboardTheme.gutter) {
            ForEach(items) { shortcut in
                shortcutTile(shortcut)
            }
        }
        .frame(width: KeyboardTheme.columnWidth)
    }

    private func shortcutTile(_ shortcut: KeyboardShortcut) -> some View {
        Button {
            onSelect(shortcut)
        } label: {
            VStack(alignment: .leading, spacing: 8) {
                Text(shortcut.combination)
                    .font(.system(size: 12, weight: .semibold, design: .monospaced))
                    .foregroundStyle(KeyboardTheme.label)
                    .lineLimit(1)
                    .minimumScaleFactor(0.75)
                Text(shortcut.description)
                    .font(.system(size: 13, weight: .bold))
                    .foregroundStyle(KeyboardTheme.label)
                    .lineLimit(2)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 0)
            }
            .padding(KeyboardTheme.tilePadding)
            .frame(maxWidth: .infinity, minHeight: 74, alignment: .topLeading)
            .background(KeyboardTheme.tile)
            .clipShape(RoundedRectangle(cornerRadius: KeyboardTheme.tileCornerRadius, style: .continuous))
        }
        .buttonStyle(.plain)
    }
}
