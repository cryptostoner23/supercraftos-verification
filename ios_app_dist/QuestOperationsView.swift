import SwiftUI

@MainActor
struct QuestOperationsView: View {
    @ObservedObject var store: BackendStore
    @State private var walletConnected = false

    private func actionTitle(_ status: String) -> String {
        switch status {
        case "completed": return "Provider reported completion"
        case "accepted_pending_verification": return "Submitted; awaiting verification"
        case "adapter_unavailable": return "Participation connection unavailable"
        case "ineligible": return "Provider prerequisite missing"
        case "verification_required": return "Outcome needs verification"
        case "already_attempted": return "Previous attempt recorded"
        case "research_only": return "Research lead only"
        case "failed": return "Provider reported failure"
        default: return status.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }

    private func actionColor(_ status: String) -> Color {
        switch status {
        case "completed": return .green
        case "failed", "configuration_error": return .red
        default: return .orange
        }
    }
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                Text("Quest operations").font(.system(size: 30, weight: .bold))
                Text("Find live campaigns, check their requirements, and see the provider's actual action result.").font(.system(size: 19)).foregroundStyle(.secondary)
                HStack {
                    Button("Discover") { Task { await store.discoverQuests() } }
                    Button("Screen leads") { Task { await store.screenQuests() } }.disabled(store.questLeads.isEmpty)
                }.font(.system(size: 19, weight: .semibold)).buttonStyle(.borderedProminent).disabled(store.busy)
                if let checked = store.questCheckedAt {
                    Text("Sources checked " + Date(timeIntervalSince1970: Double(checked)).formatted()).font(.system(size: 17)).foregroundStyle(.secondary)
                }
                ForEach(store.questErrors, id: \.sourceID) { failure in
                    Text("\(failure.sourceID.capitalized): \(failure.detail ?? failure.reason)").font(.system(size: 18)).foregroundStyle(.orange)
                }
                Toggle("Wallet already connected at provider", isOn: $walletConnected).font(.system(size: 18, weight: .medium))
                Text("This reports your provider account state. It does not connect or sign a wallet; gas spending is disabled.")
                    .font(.system(size: 16)).foregroundStyle(.secondary)
                ForEach(store.questLeads) { lead in
                    GroupBox {
                        VStack(alignment: .leading, spacing: 10) {
                            Text(lead.title).font(.system(size: 21, weight: .bold))
                            Text("\(lead.provider.capitalized) · \(lead.kind == "news_lead" ? "news lead" : "quest listing")").font(.system(size: 17)).foregroundStyle(.secondary)
                            if let url = URL(string: lead.url), url.scheme == "https" { Link("Open official listing", destination: url).font(.system(size: 18, weight: .semibold)) }
                            if let screen = store.questScreens.first(where: { $0.lead.id == lead.id }) {
                                Text("Eligibility: \(screen.eligibility.replacingOccurrences(of: "_", with: " "))").font(.system(size: 18, weight: .semibold))
                                if let reason = screen.reason { Text(reason).font(.system(size: 17)).foregroundStyle(.secondary) }
                            } else {
                                Text("Eligibility has not been checked.").font(.system(size: 17)).foregroundStyle(.secondary)
                            }
                            if lead.kind == "quest" {
                                Button("Attempt provider action") { Task { await store.runQuest(lead.id, walletConnected: walletConnected) } }
                                    .font(.system(size: 18, weight: .semibold)).disabled(store.busy)
                            }
                            ForEach(Array(store.questActions.filter { $0.leadID == lead.id }.enumerated()), id: \.offset) { _, action in
                                Divider()
                                Text(actionTitle(action.status)).font(.system(size: 19, weight: .bold)).foregroundStyle(actionColor(action.status))
                                if let reason = action.reason { Text(reason).font(.system(size: 17)).foregroundStyle(.secondary) }
                                if let receipt = action.receipt { Text(receipt.summary).font(.system(size: 16, design: .monospaced)).textSelection(.enabled) }
                            }
                        }.frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                if store.questLeads.isEmpty { Text("No current leads loaded. Tap Discover to check official sources.").font(.system(size: 18)).foregroundStyle(.secondary) }
                DisclosureGroup("Discovery sources") {
                    ForEach(store.questSources) { source in
                        if let url = URL(string: source.url), url.scheme == "https" { Link(source.name, destination: url).font(.system(size: 18)).frame(maxWidth: .infinity, alignment: .leading).padding(.vertical, 5) }
                    }
                }
                Text("A listing is not a completed task or paid reward. Each action result above is the recorded provider status.").font(.system(size: 17)).foregroundStyle(.secondary)
            }.padding()
        }
    }
}
