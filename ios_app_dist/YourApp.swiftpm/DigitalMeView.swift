import SwiftUI

/// Digital Me screen: identity, memory, and reasoning interface.
/// Makes real calls to `/api/digital_me/*` through the backend store.
@MainActor
struct DigitalMeView: View {
    @ObservedObject var store: BackendStore
    @State private var newMemory = ""
    @State private var error: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                identityCard
                memoryCard
                if let identity = store.digitalMe?.identity {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Digital Me identity").font(.headline)
                        Text("ID: \(identity.id)").font(.subheadline.monospaced()).textSelection(.enabled)
                        Text("Name: \(identity.name)").font(.body)
                        if let createdAt = identity.createdAt {
                            Text("Created: \(Date(timeIntervalSince1970: TimeInterval(createdAt)), format: .dateTime)").font(.subheadline).foregroundStyle(.secondary)
                        }
                    }.frame(maxWidth: .infinity, alignment: .leading)
                        .padding(18)
                        .background(ConsoleStyle.panel, in: RoundedRectangle(cornerRadius: 18))
                        .overlay(RoundedRectangle(cornerRadius: 18).stroke(ConsoleStyle.line))
                }
                if let error { Text(error).foregroundStyle(.orange).font(.body) }
            }.padding()
        }
        .task(id: store.backend) { await reload() }
    }

    private var identityCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Digital Me", systemImage: "laptop.compute").font(.title2.bold())
            Text("Your persistent identity, memory and reasoning layer.").foregroundStyle(.secondary)
            if let profile = store.digitalMe {
                HStack(spacing: 16) {
                    stat("MEMORY ENTRIES", profile.memoryEntries)
                    stat("PLAYBOOKS", profile.playbooks)
                }
            } else if error == nil {
                ProgressView().frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(18)
        .background(ConsoleStyle.panel, in: RoundedRectangle(cornerRadius: 18))
        .overlay(RoundedRectangle(cornerRadius: 18).stroke(ConsoleStyle.line))
    }

    private var memoryCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Memory").font(.headline)
            HStack {
                TextField("Add a memory (e.g. a decision or lesson)", text: $newMemory)
                    .textFieldStyle(.roundedBorder)
                Button("Save") {
                    let note = newMemory.trimmingCharacters(in: .whitespacesAndNewlines)
                    guard !note.isEmpty else { return }
                    Task { await store.addDigitalMeMemory(note: note); newMemory = "" }
                }
                .disabled(newMemory.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || store.busy)
            }
            if store.digitalMeMemory.isEmpty {
                Text("No memories yet. Add your first one above.").foregroundStyle(.secondary)
            } else {
                ForEach(store.digitalMeMemory) { entry in
                    HStack(alignment: .top) {
                        Image(systemName: "brain").foregroundStyle(ConsoleStyle.cyan)
                        Text(entry.note).font(.body)
                    }
                    .padding(.vertical, 4)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(18)
        .background(ConsoleStyle.panel, in: RoundedRectangle(cornerRadius: 18))
        .overlay(RoundedRectangle(cornerRadius: 18).stroke(ConsoleStyle.line))
    }

    private func stat(_ label: String, _ value: Int) -> some View {
        VStack(spacing: 2) {
            Text("\(value)").font(.system(size: 28, weight: .bold, design: .rounded)).foregroundStyle(ConsoleStyle.pink)
            Text(label).font(.caption).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(12)
        .background(ConsoleStyle.background.opacity(0.6), in: RoundedRectangle(cornerRadius: 12))
    }

    private func reload() async {
        guard !store.backend.isEmpty else { return }
        error = nil
        await store.refresh()
        if let e = store.error, store.digitalMe == nil { self.error = e }
    }
}