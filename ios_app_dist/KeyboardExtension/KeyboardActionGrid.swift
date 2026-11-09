import SwiftUI

// Two column horizontally scrolling action tile grid inside the #2C2C2E container.

struct KeyboardActionGrid: View {
    let tiles: [KeyboardActionTile]
    let onSelect: (KeyboardActionTile) -> Void

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(alignment: .top, spacing: KeyboardTheme.gutter) {
                column(leftColumn)
                column(rightColumn)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
        }
        .background(KeyboardTheme.container)
    }

    private var leftColumn: [KeyboardActionTile] {
        tiles.enumerated().compactMap { $0.offset % 2 == 0 ? $0.element : nil }
    }

    private var rightColumn: [KeyboardActionTile] {
        tiles.enumerated().compactMap { $0.offset % 2 == 1 ? $0.element : nil }
    }

    @ViewBuilder
    private func column(_ items: [KeyboardActionTile]) -> some View {        VStack(spacing: KeyboardTheme.gutter) {
            ForEach(items) { tile in
                if tile.isHero {
                    heroTile(tile)
                } else {
                    actionTile(tile)
                }
            }
        }
        .frame(width: KeyboardTheme.columnWidth)
    }

    private func heroTile(_ tile: KeyboardActionTile) -> some View {
        Button {
            onSelect(tile)
        } label: {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Image(systemName: "sparkles")
                        .font(.system(size: 20, weight: .bold))
                        .foregroundStyle(Color.white)
                    Spacer()
                }
                Spacer(minLength: 0)
                Text(tile.title)
                    .font(.system(size: 20, weight: .bold))
                    .foregroundStyle(Color.white)
                if let subtitle = tile.subtitle {
                    Text(subtitle)
                        .font(.system(size: 11))
                        .foregroundStyle(Color.white.opacity(0.8))
                }
            }
            .padding(KeyboardTheme.tilePadding)
            .frame(maxWidth: .infinity, minHeight: 116, alignment: .bottomLeading)
            .background(
                LinearGradient(
                    colors: [KeyboardTheme.heroStart, KeyboardTheme.heroEnd],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            )
            .clipShape(RoundedRectangle(cornerRadius: KeyboardTheme.heroCornerRadius, style: .continuous))
        }
        .buttonStyle(.plain)
    }

    private func actionTile(_ tile: KeyboardActionTile) -> some View {
        Button {
            onSelect(tile)
        } label: {
            HStack(alignment: .top, spacing: 9) {
                KeyboardBadgeView(badge: tile.badge)
                VStack(alignment: .leading, spacing: 2) {
                    Text(tile.title)
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(KeyboardTheme.label)
                        .multilineTextAlignment(.leading)
                        .fixedSize(horizontal: false, vertical: true)
                    if let subtitle = tile.subtitle {
                        Text(subtitle)
                            .font(.system(size: 10))
                            .foregroundStyle(KeyboardTheme.label.opacity(0.6))
                            .lineLimit(1)
                    }
                }
                Spacer(minLength: 0)
            }
            .padding(KeyboardTheme.tilePadding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(KeyboardTheme.tile)
            .clipShape(RoundedRectangle(cornerRadius: KeyboardTheme.tileCornerRadius, style: .continuous))
        }
        .buttonStyle(.plain)
    }
}
