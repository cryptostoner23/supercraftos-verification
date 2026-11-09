import SwiftUI

@MainActor
struct AccountOperationsView: View {
    @ObservedObject var store: BackendStore
    @State private var provider = "firecrawl"
    @State private var requestID = UUID().uuidString
    @State private var submitted: String?
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("Developer accounts").font(.title2.bold())
            Text("Verify a server-held credential or ask the agent to complete a supported free account flow. Keys stay on the server; the task returns redacted verification evidence.").font(.subheadline).foregroundStyle(.secondary)
            Picker("Platform", selection: $provider) {
                ForEach(["firecrawl", "steel", "hyperbrowser", "peerpush", "devhunt"], id: \.self) { Text($0.capitalized).tag($0) }
            }.pickerStyle(.menu).onChange(of: provider) { _, _ in requestID = UUID().uuidString; submitted = nil }
            Button("Verify or set up account") {
                Task {
                    if let id = await store.registerAccount(provider, idempotencyKey: requestID) {
                        submitted = id
                    }
                }
            }.buttonStyle(.borderedProminent).disabled(store.busy || store.backend.isEmpty || submitted != nil)
            if let submitted {
                Label("Account task queued. Open Tasks for progress and the result.", systemImage: "checkmark.circle")
                Text(submitted).font(.body.monospaced()).textSelection(.enabled)
            }
            if let error = store.error { Text(error).foregroundStyle(.orange) }
            Text("Recorded account state").font(.headline)
            Button("Refresh verification receipts") { Task { await store.refresh() } }.disabled(store.busy)
            ForEach(store.accounts) { entry in
                VStack(alignment: .leading, spacing: 6) {
                    Text(entry.name).font(.headline)
                    Text(entry.status.replacingOccurrences(of: "_", with: " ")).font(.subheadline)
                    Text(entry.reason).font(.body).foregroundStyle(.secondary)
                    if let checked = entry.checkedAt {
                        Text(Date(timeIntervalSince1970: checked), style: .relative).font(.subheadline)
                    }
                }.frame(maxWidth: .infinity, alignment: .leading).padding().background(Color.white.opacity(0.05), in: RoundedRectangle(cornerRadius: 10))
            }
            Text("Email verification, sign-in challenges, unavailable adapters and rejected credentials remain visible blockers. A pending flow is never shown as a working API connection.").font(.body).foregroundStyle(.secondary)
        }
    }
}
