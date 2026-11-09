import SwiftUI

// Bottom system input controls layer.
// Globe at the bottom left corner, wide dark space pill in the middle,
// backspace and return in dark rounded boxes on the right.

struct KeyboardInputBar: View {
    let onSpace: () -> Void
    let onBackspace: () -> Void
    let onReturn: () -> Void
    let onGlobe: () -> Void

    var body: some View {
        HStack(spacing: 8) {
            globeKey
            spaceKey
            backspaceKey
            returnKey
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .background(KeyboardTheme.canvas)
    }

    private var globeKey: some View {
        Button(action: onGlobe) {
            Text("\u{1F310}")
                .font(.system(size: 17))
                .frame(width: 32, height: 38)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Next keyboard")
    }

    private var spaceKey: some View {
        Button(action: onSpace) {
            Text("space")
                .font(.system(size: 13))
                .foregroundStyle(KeyboardTheme.label)
                .frame(maxWidth: .infinity, minHeight: 38)
                .background(KeyboardTheme.key)
                .clipShape(Capsule())
        }
        .buttonStyle(.plain)
    }

    private var backspaceKey: some View {
        Button(action: onBackspace) {
            Text("\u{232B}")
                .font(.system(size: 17, weight: .medium))
                .foregroundStyle(KeyboardTheme.label)
                .frame(width: 42, height: 38)
                .background(KeyboardTheme.key)
                .clipShape(RoundedRectangle(cornerRadius: KeyboardTheme.keyCornerRadius, style: .continuous))
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Delete")
    }

    private var returnKey: some View {
        Button(action: onReturn) {
            Text("\u{21B5}")
                .font(.system(size: 17, weight: .medium))
                .foregroundStyle(KeyboardTheme.label)
                .frame(width: 42, height: 38)
                .background(KeyboardTheme.key)
                .clipShape(RoundedRectangle(cornerRadius: KeyboardTheme.keyCornerRadius, style: .continuous))
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Return")
    }
}
