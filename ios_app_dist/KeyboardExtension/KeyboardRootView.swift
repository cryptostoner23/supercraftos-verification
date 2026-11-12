import SwiftUI

// Root of the SuperCraftOS custom keyboard.

struct KeyboardRootView: View {
    @State private var selection: KeyboardTabKind = .aiActions
    @State private var status: String?
    @State private var busy = false
    @State private var showConnection = false

    let backend: KeyboardBackend
    /// The document text around the insertion point.
    let context: () -> String
    /// Inserts text into the host application.
    let insert: (String) -> Void
    /// Opens a URL in the host application.
    let open: (URL) -> Void
    /// Copies text to the system pasteboard.
    let copy: (String) -> Void
    /// Reads the system pasteboard.
    let paste: () -> String?
    /// Switches to the next system keyboard.
    let onGlobe: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 0) {
                KeyboardToolbar(selection: $selection)
                Button { showConnection.toggle() } label: { Image(systemName: "gearshape") }
                    .padding(10).accessibilityLabel("Keyboard connection settings")
            }
            if showConnection { connectionSettings } else { content }
            KeyboardInputBar(
                onSpace: { insert(" ") },
                onBackspace: { insert("\u{8}") },
                onReturn: { insert("\n") },
                onGlobe: onGlobeNext
            )
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .background(KeyboardTheme.canvas)
        .environment(\.colorScheme, .dark)
    }

    private var connectionSettings: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("PRIVATE AGENT CONNECTION").font(.caption.bold())
            Text("Copy your HTTPS private access link, including # and the access key. This keyboard saves its own key on this device. Enable Full Access in Keyboard Settings for network access.")
                .font(.caption2)
            Button("Connect from clipboard") {
                guard let link = paste(), !link.isEmpty else { report("Copy your private access link first."); return }
                Task {
                    do { try await backend.configure(privateLink: link); status = "Connection saved."; showConnection = false }
                    catch { status = error.localizedDescription }
                }
            }.buttonStyle(.borderedProminent)
            Button("Forget keyboard connection", role: .destructive) {
                Task {
                    do { try await backend.disconnect(); status = "Keyboard connection removed." }
                    catch { status = error.localizedDescription }
                }
            }
            if let status { Text(status).font(.caption2) }
        }.padding(12).frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    }

    @ViewBuilder
    private var content: some View {
        ZStack {
            if selection == .fn {
                KeyboardFnGrid(shortcuts: KeyboardCatalog.shortcuts) { shortcut in
                    perform(shortcut)
                }
            } else {
                KeyboardActionGrid(tiles: KeyboardCatalog.actionTiles) { tile in
                    perform(tile)
                }
            }
            if let status {
                Text(status)
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(KeyboardTheme.label)
                    .lineLimit(2)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 7)
                    .background(Color.black.opacity(0.78))
                    .clipShape(Capsule())
                    .padding(.horizontal, 12)
                    .padding(.bottom, 10)
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottom)
            }
        }
    }

    private func onGlobeNext() {
        onGlobe()
    }

    // MARK: - Actions

    private func perform(_ tile: KeyboardActionTile) {
        let text = context().trimmingCharacters(in: .whitespacesAndNewlines)
        switch tile.kind {
        case .openURL(let template):
            guard let url = buildURL(template, text) else {
                report("Could not build a link from this text.")
                return
            }
            self.open(url)
        case .ask:
            guard !text.isEmpty else {
                report("Type or select some text first.")
                return
            }
            runAgent(query: text, instruction: tile.kind.instruction)
        case .transform(let template):
            guard !text.isEmpty else {
                report("Type or select some text first.")
                return
            }
            runAgent(query: template.replacingOccurrences(of: "{text}", with: text),
                     instruction: tile.kind.instruction)
        }
    }

    private func perform(_ shortcut: KeyboardShortcut) {
        let text = context().trimmingCharacters(in: .whitespacesAndNewlines)
        switch shortcut.action {
        case .copyToPasteboard:
            guard !text.isEmpty else {
                report("Nothing to copy.")
                return
            }
            copy(text)
            report("Copied to the pasteboard.")
        case .pasteFromPasteboard:
            guard let value = paste(), !value.isEmpty else {
                report("The pasteboard is empty.")
                return
            }
            insert(value)
        case .insertCombination:
            insert(shortcut.combination)
        }
    }

    private func runAgent(query: String, instruction: String? = nil) {
        Task { @MainActor in
            guard !busy else { return }
            busy = true
            status = "Working…"
            do {
                let reply = try await backend.runWorkflow(query: query)
                insert(reply)
                status = nil
            } catch {
                // The backend is unreachable or refused. Fall back to the
                // on-device model so the keyboard still works offline.
                let text = context().trimmingCharacters(in: .whitespacesAndNewlines)
                if let instruction, !text.isEmpty, KeyboardOnDeviceAI.isAvailable {
                    do {
                        let reply = try await KeyboardOnDeviceAI.transform(text, instruction: instruction)
                        insert(reply)
                        status = "Answered on device."
                    } catch {
                        status = (error as? LocalizedError)?.errorDescription
                            ?? error.localizedDescription
                    }
                } else {
                    status = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
                }
            }
            busy = false
        }
    }

    private func report(_ message: String) {
        Task { @MainActor in status = message }
    }

    private func buildURL(_ template: String, _ text: String) -> URL? {
        var allowed = CharacterSet.urlQueryAllowed
        allowed.remove(charactersIn: "&=?#+")
        let encoded = text.addingPercentEncoding(withAllowedCharacters: allowed) ?? ""
        return URL(string: template.replacingOccurrences(of: "{text}", with: encoded))
    }
}
