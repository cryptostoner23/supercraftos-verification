import SwiftUI
import Foundation

@MainActor
final class Concept2Backend: ObservableObject {
    // Connection
    @Published var connected = false
    @Published var error: String?

    // Mission / system
    @Published var runtime = "unknown"
    @Published var tools = 0
    @Published var integrations = 0
    @Published var healthyIntegrations = 0
    @Published var workflows = 0
    @Published var awaitingApproval = 0
    @Published var usageRequests = 0
    @Published var usageTokens = 0
    @Published var usageCost = 0.0
    @Published var agentBrain = false

    // Tasks
    @Published var jobs: [Job] = []

    // Digital Me
    @Published var memoryEntries = 0
    @Published var playbooks = 0
    @Published var brainProfile = ""
    @Published var brainTopics: [String] = []
    @Published var brainIntents: [String] = []
    @Published var memories: [MemoryEntry] = []
    @Published var playbookList: [Playbook] = []

    // Lab
    @Published var capabilities: [Capability] = []
    @Published var integrationList: [Integration] = []

    @Published var loading = true

    private let service: APIClient

    init(accessKey: String) {
        service = APIClient(accessKey: accessKey)
    }

    func refresh() async {
        loading = true
        defer { loading = false }
        do {
            let status = try await service.get("/api/status")
            let st = try JSONDecoder().decode(SystemStatus.self, from: status)
            runtime = st.runtime
            tools = st.tools
            integrations = st.integrations
            healthyIntegrations = st.healthyIntegrations
            workflows = st.workflows
            awaitingApproval = st.awaitingApproval
            agentBrain = st.agentBrain
            usageRequests = st.usage.requests
            usageTokens = st.usage.inputTokens + st.usage.outputTokens
            usageCost = st.usage.costUSD

            await loadJobs()
            await loadDigitalMe()
            await loadLab()

            connected = true
            error = nil
        } catch {
            connected = false
            self.error = error.localizedDescription
        }
    }

    private func loadJobs() async {
        do {
            let data = try await service.get("/api/jobs?limit=20")
            if let obj = try JSONSerialization.jsonObject(with: data) as? [String: Any],
               let arr = obj["jobs"] as? [[String: Any]] {
                let j = try JSONSerialization.data(withJSONObject: arr)
                jobs = try JSONDecoder().decode([Job].self, from: j)
            }
        } catch {
            jobs = []
        }
    }

    private func loadDigitalMe() async {
        do {
            let profileData = try await service.get("/api/digital_me/profile")
            let prof = try JSONDecoder().decode(GameProfile.self, from: profileData)
            memoryEntries = prof.memoryEntries
            playbooks = prof.playbooks

            let brainData = try await service.get("/api/digital_me/brain/status")
            let brain = try JSONDecoder().decode(BrainStatus.self, from: brainData)
            brainProfile = brain.understanding?.profile ?? "No synthesis yet. Ingest notes to teach Digital Me."
            brainTopics = brain.understanding?.topics ?? []
            brainIntents = brain.understanding?.intents ?? []

            let memData = try await service.get("/api/notes?limit=10")
            if let obj = try JSONSerialization.jsonObject(with: memData) as? [String: Any],
               let arr = obj["notes"] as? [[String: Any]] {
                let d = try JSONSerialization.data(withJSONObject: arr)
                memories = try JSONDecoder().decode([MemoryEntry].self, from: d)
            }

            let pbData = try await service.get("/api/agent/memory")
            if let obj = try JSONSerialization.jsonObject(with: pbData) as? [String: Any],
               let arr = obj["playbooks"] as? [[String: Any]] {
                let d = try JSONSerialization.data(withJSONObject: arr)
                playbookList = try JSONDecoder().decode([Playbook].self, from: d)
            }
        } catch {
            // Keep defaults; profile is best-effort.
        }
    }

    private func loadLab() async {
        do {
            let capData = try await service.get("/api/capabilities")
            if let obj = try JSONSerialization.jsonObject(with: capData) as? [String: Any],
               let arr = obj["capabilities"] as? [[String: Any]] {
                let d = try JSONSerialization.data(withJSONObject: arr)
                capabilities = try JSONDecoder().decode([Capability].self, from: d)
            }
            let intData = try await service.get("/api/integrations")
            if let obj = try JSONSerialization.jsonObject(with: intData) as? [String: Any],
               let arr = obj["integrations"] as? [[String: Any]] {
                let d = try JSONSerialization.data(withJSONObject: arr)
                integrationList = try JSONDecoder().decode([Integration].self, from: d)
            }
        } catch {
            // Best-effort.
        }
    }

    func dispatchJob(_ prompt: String) async -> Bool {
        do {
            _ = try await service.post("/api/jobs", body: ["query": prompt])
            await refresh()
            return true
        } catch {
            self.error = error.localizedDescription
            return false
        }
    }
}
