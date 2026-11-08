import SwiftUI
import UniformTypeIdentifiers
import UIKit

/// Apple Notes-style screen.
///
/// Notes are pulled **from the user's Apple Notes app** via two user-driven
/// mechanisms:
///  1. "Import from Apple Notes" — a document picker reads notes exported from
///     Apple Notes (share/export sheet) as .txt / .rtf / .html, then sends them
///     to the backend ingest endpoint.
///  2. The "Save to SuperCraftOS" share extension (ios_app_dist/ShareExtension)
///     receives text shared directly from Apple Notes.
///
/// The backend stores each incoming note encrypted under data/notes/ and feeds a
/// digest into Digital Me memory for context. This screen lists those imported
/// notes and lets the user open, edit, pin, or delete them.
@MainActor
struct AppleNotesView: View {
    @ObservedObject var store: BackendStore
    @State private var importing = false
    @State private var showingComposer = false
    @State private var selectedNote: AppleNote?
    @State private var localError: String?

    private static let importTypes: [UTType] = [.plainText, .rtf, .html]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                importBanner
                Button(action: { importing = true }) {
                    Label("Import all my Notes", systemImage: "square.and.arrow.down.fill")
                        .font(.system(size: 17, weight: .bold, design: .monospaced))
                        .frame(maxWidth: .infinity)
                        .padding(16)
                        .background(ConsoleStyle.cyan, in: RoundedRectangle(cornerRadius: 14))
                        .foregroundStyle(.black)
                }
                .buttonStyle(.plain)
                .disabled(store.backend.isEmpty || store.mutating)
                .accessibilityIdentifier("import-apple-notes")

                if let localError {
                    Text(localError).font(.body).foregroundStyle(.orange)
                }

                if store.notes.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("No imported notes yet").font(.headline)
                        Text("Tap “Import all my Notes” and pick your Apple Notes exports (.txt/.rtf/.html), or share a note directly via the “Save to SuperCraftOS” share extension.")
                            .font(.subheadline).foregroundStyle(.secondary)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(18)
                    .background(ConsoleStyle.panel, in: RoundedRectangle(cornerRadius: 18))
                    .overlay(RoundedRectangle(cornerRadius: 18).stroke(ConsoleStyle.line))
                } else {
                    ForEach(store.notes) { note in
                        noteRow(note)
                    }
                }
            }
            .padding()
        }
        .fileImporter(isPresented: $importing, allowedContentTypes: Self.importTypes, allowsMultipleSelection: true) { result in
            handleImport(result)
        }
        .sheet(item: $selectedNote) { note in
            AppleNoteDetail(store: store, note: note)
        }
        .sheet(isPresented: $showingComposer) {
            AppleNoteComposer(store: store)
        }
        .task(id: store.backend) { await reload() }
    }

    private var importBanner: some View {
        VStack(alignment: .leading, spacing: 6) {
            Label("Apple Notes", systemImage: "note.text").font(.title2.bold())
            Text("Imported from this device’s Apple Notes exports. Each note is stored encrypted on your SuperCraftOS backend and summarized into Digital Me memory.")
                .font(.footnote).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(18)
        .background(ConsoleStyle.panel, in: RoundedRectangle(cornerRadius: 18))
        .overlay(RoundedRectangle(cornerRadius: 18).stroke(ConsoleStyle.line))
    }

    private func noteRow(_ note: AppleNote) -> some View {
        Button { selectedNote = note } label: {
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: note.pinned ? "pin.fill" : "doc.text")
                    .foregroundStyle(note.pinned ? ConsoleStyle.pink : ConsoleStyle.cyan)
                    .font(.title3)
                    .frame(width: 32)
                VStack(alignment: .leading, spacing: 4) {
                    Text(note.title).font(.system(size: 17, weight: .semibold, design: .rounded)).foregroundStyle(.white)
                    if !note.body.isEmpty {
                        Text(note.body).font(.subheadline).foregroundStyle(.white.opacity(0.7))
                            .lineLimit(2)
                    }
                    HStack(spacing: 8) {
                        Text(note.notebook).font(.caption.monospaced()).foregroundStyle(ConsoleStyle.cyan)
                        if note.checklist.isEmpty == false {
                            Label("\(note.checklist.count)", systemImage: "checklist").font(.caption).foregroundStyle(.secondary)
                        }
                        Spacer()
                        Text(Date(timeIntervalSince1970: TimeInterval(note.updatedAt)), format: .dateTime)
                            .font(.caption2).foregroundStyle(.secondary)
                    }
                }
            }
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(ConsoleStyle.panel, in: RoundedRectangle(cornerRadius: 18))
            .overlay(RoundedRectangle(cornerRadius: 18).stroke(ConsoleStyle.line))
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("note-row-\(note.id)")
    }

    private func handleImport(_ result: Result<[URL], Error>) {
        switch result {
        case .failure(let error):
            localError = error.localizedDescription
        case .success(let urls):
            for url in urls { importFile(url) }
        }
    }

    private func importFile(_ url: URL) {
        let format = Self.format(for: url)
        let title = url.deletingPathExtension().lastPathComponent.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let content = Self.readContent(of: url, format: format) else {
            localError = "Could not read \(url.lastPathComponent)"
            return
        }
        Task {
            await store.ingestNote(title: title.isEmpty ? "Imported Apple Note" : title,
                                   body: content, format: format)
            if let error = store.error { localError = error }
        }
    }

    private static func format(for url: URL) -> String {
        switch url.pathExtension.lowercased() {
        case "rtf": return "rtf"
        case "html", "htm": return "html"
        default: return "text"
        }
    }

    private static func readContent(of url: URL, format: String) -> String? {
        guard url.startAccessingSecurityScopedResource() else { return nil }
        defer { url.stopAccessingSecurityScopedResource() }
        guard let data = try? Data(contentsOf: url) else { return nil }
        if format == "rtf" {
            if let attributed = try? NSAttributedString(data: data,
                                                       options: [.documentType: NSAttributedString.DocumentType.rtf],
                                                       documentAttributes: nil) {
                return attributed.string
            }
        }
        return String(data: data, encoding: .utf8)
    }

    private func reload() async {
        guard !store.backend.isEmpty else { return }
        await store.loadNotes()
        if let error = store.error, store.notes.isEmpty { localError = error }
    }
}

/// Full-note editor sheet: shows and edits body, toggles pin, deletes.
@MainActor
private struct AppleNoteDetail: View {
    @ObservedObject var store: BackendStore
    @Environment(\.dismiss) private var dismiss
    let note: AppleNote
    @State private var title: String
    @State private var noteBody: String
    @State private var notebook: String

    init(store: BackendStore, note: AppleNote) {
        self.store = store
        self.note = note
        _title = State(initialValue: note.title)
        _noteBody = State(initialValue: note.body)
        _notebook = State(initialValue: note.notebook)
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    TextField("Title", text: $title).font(.title2.bold())
                    TextField("Notebook", text: $notebook).font(.subheadline.monospaced()).foregroundStyle(ConsoleStyle.cyan)
                    TextEditor(text: $noteBody)
                        .frame(minHeight: 220)
                        .padding(8)
                        .background(ConsoleStyle.background, in: RoundedRectangle(cornerRadius: 12))
                        .overlay(RoundedRectangle(cornerRadius: 12).stroke(ConsoleStyle.line))
                    if !note.checklist.isEmpty {
                        VStack(alignment: .leading, spacing: 6) {
                            Text("Checklist").font(.headline)
                            ForEach(note.checklist, id: \.id) { item in
                                Label {
                                    Text(item.text).strikethrough(item.checked)
                                } icon: {
                                    Image(systemName: item.checked ? "checkmark.square.fill" : "square")
                                        .foregroundStyle(item.checked ? ConsoleStyle.pink : .secondary)
                                }
                            }
                        }
                    }
                }
                .padding()
            }
            .background(ConsoleStyle.background)
            .toolbar {
                ToolbarItemGroup(placement: .topBarLeading) {
                    Button(note.pinned ? "Unpin" : "Pin") { Task { await store.pinNote(id: note.id) } }
                    Button("Delete", role: .destructive) {
                        Task { await store.deleteNote(id: note.id); dismiss() }
                    }
                }
                ToolbarItemGroup(placement: .topBarTrailing) {
                    Button("Save") { save(); dismiss() }.disabled(store.mutating)
                    Button("Done") { dismiss() }
                }
            }
        }
    }

    private func save() {
        let t = title.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !t.isEmpty else { return }
        Task { await store.updateNote(id: note.id, title: t, body: noteBody, notebook: notebook) }
    }
}

/// Creates a new note manually (in addition to imports).
@MainActor
private struct AppleNoteComposer: View {
    @ObservedObject var store: BackendStore
    @Environment(\.dismiss) private var dismiss
    @State private var title = ""
    @State private var noteBody = ""
    @State private var notebook = "Default"

    var body: some View {
        NavigationStack {
            VStack(spacing: 16) {
                TextField("Title", text: $title).font(.title2.bold())
                TextField("Notebook", text: $notebook).font(.subheadline.monospaced()).foregroundStyle(ConsoleStyle.cyan)
                TextEditor(text: $noteBody).frame(minHeight: 220).padding(8)
                    .background(ConsoleStyle.background, in: RoundedRectangle(cornerRadius: 12))
                    .overlay(RoundedRectangle(cornerRadius: 12).stroke(ConsoleStyle.line))
            }
            .padding()
            .background(ConsoleStyle.background)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        let t = title.trimmingCharacters(in: .whitespacesAndNewlines)
                        guard !t.isEmpty else { return }
                        Task { await store.createNote(title: t, body: noteBody, notebook: notebook); dismiss() }
                    }
                    .disabled(title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || store.mutating)
                }
            }
        }
    }
}
