import Foundation
#if canImport(SwiftUI)
import SwiftUI
import CryptoKit
#endif

enum AppConfig {
    /// The backend the app talks to unless the user changes it.
    ///
    /// The build setting supplies the initial server address. The Connection
    /// sheet accepts the user's private access link, keeps its key in Keychain,
    /// and saves only the origin in endpoint bookmarks.
    static let defaultBackend: String = {
        if let configured = Bundle.main.object(forInfoDictionaryKey: "SUPERCRAFTOSBackendURL") as? String {
            let trimmed = configured.trimmingCharacters(in: .whitespacesAndNewlines)
            if !trimmed.isEmpty, !trimmed.contains("$(") { return trimmed }
        }
        return ""
    }()

    /// A private device build can provision its gateway credential in Info.plist.
    /// Public builds omit this key and continue to use the Keychain-only flow.
    static let provisionedAccessKey: String = {
        guard let value = Bundle.main.object(forInfoDictionaryKey: "SUPERCRAFTOSAccessKey") as? String else { return "" }
        let key = value.trimmingCharacters(in: .whitespacesAndNewlines)
        return key.utf8.count >= 32 && key.utf8.count <= 512 && key.utf8.allSatisfy { (33...126).contains($0) } ? key : ""
    }()
}

struct RuntimeStatus: Decodable {
    let runtime: String
    let tools: Int
    let integrations: Int
    let healthyIntegrations: Int
    let workflows: Int
    let awaitingApproval: Int
    let memoryMB: Double
    let memoryLimitMB: Double
    let usage: TokenUsage?
    let runtimeSnapshot: RuntimeSnapshot?

    enum CodingKeys: String, CodingKey {
        case runtime, tools, integrations, workflows
        case healthyIntegrations = "healthy_integrations"
        case awaitingApproval = "awaiting_approval"
        case memoryMB = "memory_mb"
        case memoryLimitMB = "memory_limit_mb"
        case usage
        case runtimeSnapshot = "runtime_snapshot"
    }
}

struct TokenUsage: Decodable {
    let inputTokens: Int?
    let outputTokens: Int?
    let requests: Int?
    let costUSD: Double?
    let unpricedRequests: Int?
    enum CodingKeys: String, CodingKey {
        case inputTokens = "input_tokens", outputTokens = "output_tokens", requests
        case costUSD = "cost_usd", unpricedRequests = "unpriced_requests"
    }
}

struct RuntimeSnapshot: Decodable {
    let lark: String?
    let mode: String?
    let sandbox: String?
    let timestamp: Double?
}

struct IntegrationHealth: Decodable, Identifiable {
    let name: String
    let status: String
    let latencyMS: Double?
    let detail: String?
    var id: String { name }
    enum CodingKeys: String, CodingKey {
        case name, status, detail
        case latencyMS = "latency_ms"
    }
}

struct RegistrationOutcome: Decodable, Identifiable {
    let name: String
    let status: String
    let detail: String?
    var id: String { name }
}

struct DeveloperAccount: Decodable, Identifiable {
    let id: String
    let name: String
    let status: String
    let reason: String
    let credentialVerified: Bool
    let credentialPresent: Bool
    let checkedAt: Double?
    enum CodingKeys: String, CodingKey {
        case id, name, status, reason
        case credentialVerified = "credential_verified", credentialPresent = "credential_present", checkedAt = "checked_at"
    }
}
private struct AccountCatalogResponse: Decodable { let providers: [DeveloperAccount] }

struct TelemetrySample: Identifiable {
    let id = UUID()
    let date: Date
    let memoryMB: Double
}

struct LogEntry: Identifiable {
    let id = UUID()
    let date: Date
    let level: String
    let message: String
}

struct AgentTool: Decodable, Identifiable {
    let name: String
    let description: String?
    let inputSchema: JSONValue?
    var id: String { name }
}

struct AgentWorkflow: Decodable, Identifiable {
    let threadID: String
    let query: String?
    let status: String?
    let artifact: String?
    let error: String?
    let plan: String?
    var id: String { threadID }
    enum CodingKeys: String, CodingKey {
        case threadID = "thread_id"
        case query, status, artifact, error, plan
    }
}

private struct ToolResponse: Decodable { let tools: [AgentTool] }
private struct WorkflowResponse: Decodable { let workflows: [AgentWorkflow] }
private struct IntegrationResponse: Decodable { let integrations: [IntegrationHealth] }
private struct RegistrationResponse: Decodable { let registrations: [RegistrationOutcome] }

struct PlatformInfo: Decodable, Identifiable {
    let id: String
    let name: String
    let url: String
    let license: String
    let cost: String
    let features: String
    let access: String
    let installed: Bool?
    let release: PlatformRelease?
}

struct PlatformRelease: Decodable {
    let status: String?
    let latestVersion: String?
    enum CodingKeys: String, CodingKey { case status; case latestVersion = "latest_version" }
}

private struct PlatformResponse: Decodable { let platforms: [PlatformInfo] }

struct EngineCapability: Decodable, Identifiable {
    let id: String
    let name: String
    let features: String
    let enabled: Bool
    let runs: Int
    let successes: Int
    let routingScore: Double
    enum CodingKeys: String, CodingKey { case id, name, features, enabled, runs, successes; case routingScore = "routing_score" }
}
private struct CapabilityResponse: Decodable { let capabilities: [EngineCapability] }

struct GrantOpportunity: Decodable, Identifiable {
    let id: String; let name: String; let chain: String; let officialURL: String
    let applicationURL: String; let payment: String; let cadence: String; let topics: [String]
    let evidence: String
    let fundingType: String?
    let status: String?
    let submissionSurface: String?
    var identity: String { id }
    enum CodingKeys: String, CodingKey {
        case id, name, chain, payment, cadence, topics, evidence, status
        case officialURL = "official_url"
        case applicationURL = "application_url"
        case fundingType = "funding_type"
        case submissionSurface = "submission_surface"
    }
    var identifiableID: String { id }
}
private struct GrantCatalogResponse: Decodable { let programs: [GrantOpportunity] }

struct GrantProfile: Encodable {
    let projectName: String
    let summary: String
    let topics: [String]
    let chains: [String]
    let budgetUSD: Double
    var repositoryURL = ""
    var team = ""
    var milestones: [String] = []
    var problem = ""
    var solution = ""
    var publicGoodsCase = ""
    var useOfFunds = ""
    var contactEmail = ""
    var successMetrics: [String] = []
    var budgetBreakdownUSD: [String: Double] = [:]
    enum CodingKeys: String, CodingKey {
        case summary, topics, chains, team, milestones, problem, solution
        case repositoryURL = "repository_url"
        case projectName = "project_name"
        case budgetUSD = "budget_usd"
        case publicGoodsCase = "public_goods_case"
        case useOfFunds = "use_of_funds"
        case contactEmail = "contact_email"
        case successMetrics = "success_metrics"
        case budgetBreakdownUSD = "budget_breakdown_usd"
    }
}

struct GrantScreenRow: Decodable, Identifiable {
    let program: GrantOpportunity
    let score: Int
    let fit: String
    let matchedTopics: [String]
    let chainMatch: Bool
    let evidence: [GrantEvidence]
    let nextAction: String
    var id: String { program.id }
    enum CodingKeys: String, CodingKey {
        case program, score, fit, evidence
        case matchedTopics = "matched_topics"
        case chainMatch = "chain_match"
        case nextAction = "next_action"
    }
}

struct GrantEvidence: Decodable {
    let url: String
    let kind: String
}

private struct GrantScreenResponse: Decodable { let results: [GrantScreenRow] }

struct GrantDraft: Decodable {
    let id: String
    let status: String
    let programID: String
    let draft: GrantDraftBody
    let missingInformation: [String]?
    let submission: GrantSubmissionState?
    enum CodingKeys: String, CodingKey {
        case id, status, draft, submission
        case programID = "program_id"
        case missingInformation = "missing_information"
    }
}

struct GrantSubmissionState: Codable {
    let status: String
    let reason: String?
    let receipt: JSONValue?
}
struct SavedGrantApplication: Codable, Identifiable {
    let id: String
    let title: String
    let programme: String
    let budgetUSD: Double
    let status: String
    let submission: GrantSubmissionState
    enum CodingKeys: String, CodingKey {
        case id, title, programme, status, submission
        case budgetUSD = "budget_usd"
    }
    var recordJSON: String {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        return (try? String(decoding: encoder.encode(self), as: UTF8.self)) ?? "Record unavailable"
    }
}
struct SavedGrantApplicationsResponse: Decodable { let packages: [SavedGrantApplication] }


struct GrantDraftBody: Decodable {
    let title: String
    let programme: String
    let budgetUSD: Double
    let deliveryPlan: [String]
    enum CodingKeys: String, CodingKey { case title, programme; case budgetUSD = "budget_usd", deliveryPlan = "delivery_plan" }
}

private struct GrantProfileEnvelope: Encodable { let profile: GrantProfile }
private struct GrantDraftRequest: Encodable {
    let programID: String
    let profile: GrantProfile
    enum CodingKeys: String, CodingKey { case profile; case programID = "program_id" }
}

struct QuestSource: Decodable, Identifiable {
    let id: String
    let name: String
    let url: String
    let kind: String
    let provider: String
}

struct QuestLead: Decodable, Identifiable {
    let id: String
    let provider: String
    let kind: String
    let title: String
    let url: String
    let sourceURL: String
    let discoveredAt: Int?
    let score: Double?
    enum CodingKeys: String, CodingKey {
        case id, provider, kind, title, url, score
        case sourceURL = "source_url"
        case discoveredAt = "discovered_at"
    }
}

struct QuestScreenResult: Decodable {
    let lead: QuestLead
    let eligibility: String
    let reason: String?
}

indirect enum QuestJSONValue: Decodable {
    case text(String), number(Double), flag(Bool), list([QuestJSONValue]), object([String: QuestJSONValue]), null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() { self = .null }
        else if let value = try? container.decode(String.self) { self = .text(value) }
        else if let value = try? container.decode(Bool.self) { self = .flag(value) }
        else if let value = try? container.decode(Double.self) { self = .number(value) }
        else if let value = try? container.decode([QuestJSONValue].self) { self = .list(value) }
        else { self = .object(try container.decode([String: QuestJSONValue].self)) }
    }

    var summary: String {
        switch self {
        case .text(let value): return value
        case .number(let value): return String(value)
        case .flag(let value): return String(value)
        case .list(let values): return values.map(\.summary).joined(separator: ", ")
        case .object(let values):
            for key in ["receipt_url", "url", "transaction_hash", "tx_hash", "application_id", "id"] {
                if let value = values[key] { return "\(key): \(value.summary)" }
            }
            return values.keys.sorted().map { "\($0): \(values[$0]?.summary ?? "")" }.joined(separator: " · ")
        case .null: return ""
        }
    }
}

struct QuestActionResult: Decodable {
    let leadID: String
    let status: String
    let reason: String?
    let receipt: QuestJSONValue?
    enum CodingKeys: String, CodingKey {
        case status, reason, receipt
        case leadID = "lead_id"
    }
}

private struct QuestSourcesResponse: Decodable { let sources: [QuestSource] }
struct QuestSourceError: Decodable { let sourceID: String; let reason: String; let detail: String?; enum CodingKeys: String, CodingKey { case sourceID = "source_id", reason, detail } }
private struct QuestDiscoverResponse: Decodable { let leads: [QuestLead]; let errors: [QuestSourceError]?; let checkedAt: Int?; enum CodingKeys: String, CodingKey { case leads, errors; case checkedAt = "checked_at" } }
private struct QuestScreenResponse: Decodable { let results: [QuestScreenResult] }
private struct QuestRunResponse: Decodable { let results: [QuestActionResult] }

struct ProductSpec: Codable, Equatable {
    var name = "Sensor enclosure"
    var idea = ""
    var template = "enclosure"
    var widthMM = 100.0
    var depthMM = 70.0
    var heightMM = 35.0
    var wallMM = 3.0
    var holeMM = 0.0
    var material = "PLA"
    var process = "FDM"
    var loadN = 0.0
    enum CodingKeys: String, CodingKey {
        case name, idea, template, material, process
        case widthMM = "width_mm", depthMM = "depth_mm", heightMM = "height_mm", wallMM = "wall_mm", holeMM = "hole_mm", loadN = "load_n"
    }
    var effectiveHeightMM: Double { template == "plate" ? wallMM : heightMM }
    var localChecks: [String] {
        var messages: [String] = []
        if wallMM * 2 >= min(widthMM, depthMM) || (template != "plate" && wallMM >= heightMM) { messages.append("Wall thickness leaves no usable interior.") }
        if process == "FDM" && wallMM < 1.2 { messages.append("Wall is below the assumed three-pass 0.4 mm nozzle screen.") }
        if holeMM > 0 && holeMM * 5 >= min(widthMM, depthMM) { messages.append("Hole layout has insufficient edge distance.") }
        if process == "FDM" && material.hasPrefix("Aluminum") { messages.append("Aluminum is incompatible with the assumed desktop FDM process.") }
        return messages
    }
}

struct DesignCheck: Decodable, Identifiable {
    let code: String
    let status: String
    let detail: String
    var id: String { code }
}

struct ProductReport: Decodable {
    let id: String?
    let readiness: String
    let checks: [DesignCheck]
    let scope: String
    let files: [String: String]?
    let massEstimateG: Double?
    let geometry: ProductGeometry?
    let beamScreen: ProductBeam?
    let nextSteps: [String]?
    enum CodingKeys: String, CodingKey {
        case id, readiness, checks, scope, files, geometry
        case massEstimateG = "mass_estimate_g", beamScreen = "beam_screen", nextSteps = "next_steps"
    }
}

struct ProductGeometry: Decodable {
    let validSolid: Bool
    let volumeMM3: Double
    let stepRoundtripValid: Bool
    enum CodingKeys: String, CodingKey { case validSolid = "valid_solid", volumeMM3 = "volume_mm3", stepRoundtripValid = "step_roundtrip_valid" }
}

struct ProductBeam: Decodable {
    let bendingStressMPa: Double
    let tipDeflectionMM: Double
    let assumedAllowableMPa: Double
    let model: String
    enum CodingKeys: String, CodingKey {
        case bendingStressMPa = "bending_stress_mpa", tipDeflectionMM = "tip_deflection_mm", assumedAllowableMPa = "assumed_allowable_mpa", model
    }
}

#if canImport(SwiftUI)
@MainActor
// ── Digital Me models ───────────────────────────────────────────────────────
struct DigitalMeIdentity: Decodable {
    let id: String
    let name: String
    let createdAt: Int?
    enum CodingKeys: String, CodingKey { case id, name; case createdAt = "created_at" }
}

struct DigitalMePlaybookSummary: Decodable, Identifiable {
    let id: String
    let title: String
}

struct DigitalMeMemoryEntry: Decodable, Identifiable {
    let id: String
    let note: String
    let at: Int?
}

struct DigitalMeProfile: Decodable {
    let identity: DigitalMeIdentity
    let memoryEntries: Int
    let playbooks: Int
    let playbookSummaries: [DigitalMePlaybookSummary]
    enum CodingKeys: String, CodingKey {
        case identity
        case memoryEntries = "memory_entries"
        case playbooks
        case playbookSummaries = "playbook_summaries"
    }
}

struct DigitalMeMemoryResponse: Decodable {
    let entries: [DigitalMeMemoryEntry]
}

final class BackendStore: ObservableObject {
    @Published var status: RuntimeStatus?
    @Published var tools: [AgentTool] = []
    @Published var workflows: [AgentWorkflow] = []
    @Published var integrations: [IntegrationHealth] = []
    @Published var registrations: [RegistrationOutcome] = []
    @Published var accounts: [DeveloperAccount] = []
    @Published var samples: [TelemetrySample] = []
    @Published var log: [LogEntry] = []
    @Published var platforms: [PlatformInfo] = []
    @Published var capabilities: [EngineCapability] = []
    @Published var grants: [GrantOpportunity] = []
    @Published var grantScreens: [GrantScreenRow] = []
    @Published var grantDrafts: [GrantDraft] = []
    @Published var savedGrantApplications: [SavedGrantApplication] = []
    @Published var questErrors: [QuestSourceError] = []
    @Published var questSources: [QuestSource] = []
    @Published var questLeads: [QuestLead] = []
    @Published var questScreens: [QuestScreenResult] = []
    @Published var questActions: [QuestActionResult] = []
    @Published var questCheckedAt: Int?
    @Published var productReport: ProductReport?
    @Published var productMesh: URL?
    @Published var productExports: [URL] = []
    @Published var error: String?
    @Published var busy = false
    /// True while a user-initiated write is in flight. A background refresh must
    /// never cancel or swallow a command the user just gave, so the two are
    /// tracked separately: `busy` covers any network work, `mutating` covers the
    /// writes, and a write waits for a refresh instead of being dropped.
    @Published var mutating = false
    @Published var lastUpdated: Date?
    @Published private(set) var backend: String
    @Published var jobs: [AutonomousJob] = []
    @Published var agentStatus: AgentStatus?
    @Published var digitalMe: DigitalMeProfile?
    @Published var digitalMeMemory: [DigitalMeMemoryEntry] = []
    @Published var productSpec = ProductSpec() {
        didSet {
            if productSpec != oldValue { productReport = nil; productMesh = nil; productExports = [] }
        }
    }
    @Published var bookmarks: [String] {
        didSet { UserDefaults.standard.set(bookmarks, forKey: "supercraftos.bookmarks") }
    }
    private var client: BackendClient?
    private var syncCounter = 0

    private static let clock: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm:ss"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        return formatter
    }()
    private static let goodStatuses: Set<String> = ["active", "authenticated", "reachable", "verified", "passed", "ready", "completed", "credential_present"]

    init(client injectedClient: BackendClient? = nil) {
        let saved = UserDefaults.standard.string(forKey: "supercraftos.backend") ?? AppConfig.defaultBackend
        backend = (try? BackendConnection(address: saved).origin) ?? ""
        bookmarks = Array(Set((UserDefaults.standard.stringArray(forKey: "supercraftos.bookmarks") ?? [])
            .compactMap { try? BackendConnection(address: $0).origin })).sorted()
        if let injectedClient {
            client = injectedClient
            backend = injectedClient.connection.origin
            return
        }
        #if DEBUG
        if ProcessInfo.processInfo.environment["SUPERCRAFTOS_UI_FIXTURES"] == "1" {
            client = CIBackendFixture.makeClient(accessKey: ProcessInfo.processInfo.environment["SUPERCRAFTOS_FIXTURE_AUTH_FAILURE"] == "1" ? "invalid-fixture-key" : CIBackendFixture.accessKey)
            backend = CIBackendFixture.origin
            return
        }
        #endif
        let provisioned = backend == AppConfig.defaultBackend ? AppConfig.provisionedAccessKey : ""
        let key = provisioned.isEmpty ? (CredentialStore.load(origin: backend) ?? "") : provisioned
        if let connection = try? BackendConnection(address: backend, accessKey: key) {
            if !provisioned.isEmpty { try? CredentialStore.save(provisioned, origin: connection.origin) }
            client = BackendClient(connection: connection)
        }
    }

    /// Bookmarks contain origins only. Credentials remain in the Keychain.
    func addBookmark(_ address: String) {
        guard let origin = try? BackendConnection(address: address).origin else { return }
        bookmarks = [origin] + bookmarks.filter { $0 != origin }
    }

    func removeBookmark(_ address: String) {
        bookmarks.removeAll { $0 == address }
    }

    private func clearState() {
        status = nil; tools = []; workflows = []; integrations = []; registrations = []; accounts = []
        samples = []; log = []; platforms = []; capabilities = []; grants = []; jobs = []; agentStatus = nil
        digitalMe = nil; digitalMeMemory = []
        questErrors = []; questSources = []; questLeads = []; questScreens = []; questActions = []; questCheckedAt = nil
        productSpec = ProductSpec(); productReport = nil; productMesh = nil; productExports = []
        grantDrafts = []; savedGrantApplications = []
        lastUpdated = nil; syncCounter = 0
    }

    func connect(address: String, accessKey: String) async {
        await mutate {
            var connection = try BackendConnection(address: address, accessKey: accessKey)
            if connection.accessKey.isEmpty, let saved = CredentialStore.load(origin: connection.origin) {
                connection = try BackendConnection(address: connection.origin, accessKey: saved)
            }
            guard !connection.accessKey.isEmpty else { throw BackendError.authenticationRequired }
            // Keychain may be unavailable on cloud simulators; the connection still works
            // because the access key is carried in the BackendClient's bearer credential.
            try? CredentialStore.save(connection.accessKey, origin: connection.origin)
            self.clearState()
            self.backend = connection.origin
            self.addBookmark(connection.origin)
            UserDefaults.standard.set(connection.origin, forKey: "supercraftos.backend")
            self.client = BackendClient(connection: connection)
            try await self.load()
        }
    }

    func disconnect() {
        guard !busy else { return }
        do {
            if !backend.isEmpty { try CredentialStore.save("", origin: backend) }
            client = nil; backend = ""; UserDefaults.standard.removeObject(forKey: "supercraftos.backend")
            clearState(); error = nil
        } catch { self.error = error.localizedDescription }
    }

    private func request(_ path: String, body: Data? = nil, idempotencyKey: String? = nil) async throws -> Data {
        guard let client else { throw BackendError.invalidURL }
        return try await client.data(path, body: body, idempotencyKey: idempotencyKey)
    }

    private func load() async throws {
        let decoder = JSONDecoder()
        async let statusData = request("/api/status")
        async let toolsData = request("/api/tools")
        async let workflowsData = request("/api/workflows")
        async let integrationsData = request("/api/integrations")
        async let registrationsData = request("/api/registrations")
        async let accountsData = request("/api/accounts")
        async let platformsData = request("/api/capabilities")
        async let grantsData = request("/api/grants/catalog")
        async let applicationsData = request("/api/grants/packages")
        async let jobsData = request("/api/jobs")
        async let agentData = request("/api/agent/status")
        async let digitalMeData = request("/api/digital_me/profile")
        async let digitalMeMemoryData = request("/api/digital_me/memory")
        let nextStatus = try decoder.decode(RuntimeStatus.self, from: await statusData)
        let nextTools = try decoder.decode(ToolResponse.self, from: await toolsData)
        let nextWorkflows = try decoder.decode(WorkflowResponse.self, from: await workflowsData)
        let nextIntegrations = try decoder.decode(IntegrationResponse.self, from: await integrationsData)
        let nextRegistrations = try decoder.decode(RegistrationResponse.self, from: await registrationsData)
        let nextAccounts = try decoder.decode(AccountCatalogResponse.self, from: await accountsData)
        let nextPlatforms = try decoder.decode(CapabilityResponse.self, from: await platformsData)
        let nextGrants = try decoder.decode(GrantCatalogResponse.self, from: await grantsData)
        let nextApplications = try decoder.decode(SavedGrantApplicationsResponse.self, from: await applicationsData)
        let nextJobs = try decoder.decode(AgentJobsResponse.self, from: await jobsData)
        let nextAgent = try decoder.decode(AgentStatus.self, from: await agentData)
        recordSync(previousStatus: status, previousWorkflows: workflows, previousIntegrations: integrations, previousRegistrations: registrations,
                   nextStatus: nextStatus, nextWorkflows: nextWorkflows.workflows, nextIntegrations: nextIntegrations.integrations, nextRegistrations: nextRegistrations.registrations)
        status = nextStatus; tools = nextTools.tools; workflows = nextWorkflows.workflows
        integrations = nextIntegrations.integrations; registrations = nextRegistrations.registrations
        accounts = nextAccounts.providers
        capabilities = nextPlatforms.capabilities
        grants = nextGrants.programs; savedGrantApplications = nextApplications.packages
        jobs = nextJobs.jobs; agentStatus = nextAgent
        if let meData = try? await digitalMeData, let me = try? decoder.decode(DigitalMeProfile.self, from: meData) {
            digitalMe = me
        }
        if let memData = try? await digitalMeMemoryData, let mem = try? decoder.decode(DigitalMeMemoryResponse.self, from: memData) {
            digitalMeMemory = mem.entries
        }
        if let sourcesData = try? await request("/api/quests/sources"),
           let sources = try? decoder.decode(QuestSourcesResponse.self, from: sourcesData) {
            questSources = sources.sources
        }
        if nextStatus.runtime == "running" {
            samples.append(TelemetrySample(date: Date(), memoryMB: nextStatus.memoryMB))
            samples = Array(samples.suffix(60))
        }
        lastUpdated = Date()
    }

    func refresh() async {
        // A refresh is a read. It yields to a command the user just gave, and it
        // never blocks one: the command waits for the read to finish instead.
        guard !busy, !mutating else { return }
        busy = true; error = nil
        defer { busy = false }
        do { try await load() }
        catch is CancellationError { }
        catch { self.error = error.localizedDescription; note("error", "SYNC FAILED · \(error.localizedDescription)") }
    }

    /// Runs a user-initiated write.
    ///
    /// A write is never dropped because a background refresh happened to be in
    /// flight. It waits for the read to finish, and while it runs no other
    /// read or write may start, so the state it loads is the state it wrote.
    private func mutate<T>(_ work: () async throws -> T) async -> T? {
        // Wait for any in-flight network work to finish, so the write is not lost.
        while busy {
            try? await Task.sleep(for: .milliseconds(50))
            if Task.isCancelled { return nil }
        }
        mutating = true
        busy = true; error = nil
        defer { busy = false; mutating = false }
        do { return try await work() }
        catch {
            self.error = error.localizedDescription
            note("error", "COMMAND FAILED · \(error.localizedDescription)")
            return nil
        }
    }

    func perform(_ path: String, body: [String: String] = [:]) async {
        await mutate {
            _ = try await self.request(path, body: JSONEncoder().encode(body))
            self.note("task", "CMD \(path) ACCEPTED")
            try await self.load()
        }
    }

    func screenGrants(_ profile: GrantProfile) async {
        await mutate {
            let body = try JSONEncoder().encode(GrantProfileEnvelope(profile: profile))
            let data = try await self.request("/api/grants/screen", body: body)
            self.grantScreens = try JSONDecoder().decode(GrantScreenResponse.self, from: data).results
            self.note("task", "SCREENED \(self.grantScreens.count) FUNDING ROUTES")
        }
    }

    func draftGrant(_ programID: String, profile: GrantProfile) async {
        await mutate {
            let body = try JSONEncoder().encode(GrantDraftRequest(programID: programID, profile: profile))
            let data = try await self.request("/api/grants/draft", body: body)
            let draft = try JSONDecoder().decode(GrantDraft.self, from: data)
            self.grantDrafts.removeAll { $0.programID == programID }
            self.grantDrafts.append(draft)
            self.note("task", "DRAFT \(draft.id) PERSISTED")
        }
    }

    func submitGrant(_ packageID: String) async {
        await mutate {
            let body = try JSONEncoder().encode(["package_id": packageID])
            let data = try await self.request("/api/grants/submit", body: body)
            let result = try JSONDecoder().decode(GrantDraft.self, from: data)
            self.grantDrafts.removeAll { $0.id == result.id }
            self.grantDrafts.append(result)
            self.note("task", "GRANT INTAKE · \(result.submission?.status ?? "unknown") · \(result.id)")
        }
    }

    func submitTask(query: String, maxSteps: Int, runAt: Date?, idempotencyKey: String) async -> AutonomousJob? {
        await mutate {
            let body = try JSONEncoder().encode(AgentSubmission(query: query, maxSteps: maxSteps, runAt: runAt?.timeIntervalSince1970))
            let data = try await self.request("/api/jobs", body: body, idempotencyKey: idempotencyKey)
            let job = try JSONDecoder().decode(AutonomousJob.self, from: data)
            self.jobs.removeAll { $0.id == job.id }; self.jobs.insert(job, at: 0)
            self.note("task", "AUTONOMOUS TASK QUEUED · \(job.id.prefix(8))")
            return job
        }
    }

    func taskTrace(_ id: String, after cursor: Int = 0) async throws -> AgentTrace {
        try JSONDecoder().decode(AgentTrace.self, from: await request("/api/jobs/\(id)/trace?after=\(cursor)"))
    }

    func executeTool(_ name: String, arguments: String) async throws -> JSONValue {
        guard let data = arguments.data(using: .utf8),
              let object = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw NSError(domain: "ToolArguments", code: 1, userInfo: [NSLocalizedDescriptionKey: "Arguments must be a valid JSON object."])
        }
        let body = try JSONSerialization.data(withJSONObject: ["name": name, "arguments": object])
        return try JSONDecoder().decode(JSONValue.self, from: await request("/api/tools/call", body: body))
    }

    func taskEvents(_ id: String) async throws -> [AgentEvent] {
        var events: [AgentEvent] = []; var cursor = 0
        // A task has bounded steps; paginate so a long run does not hide its final receipt.
        for _ in 0..<8 {
            let data = try await request("/api/jobs/\(id)/events?after=\(cursor)")
            let page = try JSONDecoder().decode(AgentEventsResponse.self, from: data).events
            events += page
            if page.count < 500 { break }
            guard let last = page.last, last.id > cursor else { break }
            cursor = last.id
        }
        return events
    }

    func downloadTaskFile(jobID: String, file: AgentFile) async throws -> URL {
        let path = try file.endpoint(jobID: jobID)
        let data = try await request(path)
        guard data.count == file.bytes, SHA256.hash(data: data).map({ String(format: "%02x", $0) }).joined() == file.sha256 else { throw BackendError.invalidResponse }
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent("SuperCraftOSTasks", isDirectory: true).appendingPathComponent(jobID, isDirectory: true)
        var destination = directory
        for part in try file.components() { destination.appendPathComponent(part) }
        try FileManager.default.createDirectory(at: destination.deletingLastPathComponent(), withIntermediateDirectories: true)
        try data.write(to: destination, options: .atomic)
        return destination
    }

    func registerAccount(_ provider: String, idempotencyKey: String) async -> String? {
        await mutate {
            let data = try await self.request("/api/accounts/register", body: JSONEncoder().encode(["provider": provider]), idempotencyKey: idempotencyKey)
            let job = try JSONDecoder().decode(AutonomousJob.self, from: data)
            self.jobs.removeAll { $0.id == job.id }; self.jobs.insert(job, at: 0)
            return job.id
        }
    }

    func executionMemory() async throws -> AgentMemory {
        try JSONDecoder().decode(AgentMemory.self, from: await request("/api/agent/memory"))
    }

    func forgetLesson(_ id: String) async throws {
        _ = try await request("/api/agent/memory/forget", body: JSONEncoder().encode(["id": id]))
    }

    func addDigitalMeMemory(note: String) async {
        await mutate {
            let body = try JSONEncoder().encode(["entry": ["note": note]])
            _ = try await self.request("/api/digital_me/memory", body: body)
            self.note("task", "DIGITAL ME MEMORY SAVED")
            try await self.load()
        }
    }

    func discoverQuests() async {
        await mutate {
            let body = try JSONSerialization.data(withJSONObject: ["limit": 30])
            let data = try await self.request("/api/quests/discover", body: body)
            let response = try JSONDecoder().decode(QuestDiscoverResponse.self, from: data)
            self.questLeads = response.leads
            self.questErrors = response.errors ?? []
            self.questCheckedAt = response.checkedAt
            self.questScreens = []
            self.questActions = []
            self.note("task", "QUEST RADAR · \(response.leads.count) leads discovered")
        }
    }

    func screenQuests() async {
        guard !questLeads.isEmpty else { return }
        await mutate {
            let body = try JSONSerialization.data(withJSONObject: ["lead_ids": self.questLeads.map(\.id), "profile": [:]])
            let data = try await self.request("/api/quests/screen", body: body)
            let response = try JSONDecoder().decode(QuestScreenResponse.self, from: data)
            self.questScreens = response.results
            self.note("task", "QUEST RADAR · \(response.results.count) eligibility checks")
        }
    }

    func runQuest(_ leadID: String, walletConnected: Bool) async {
        await mutate {
            let body = try JSONSerialization.data(withJSONObject: ["lead_ids": [leadID], "max_actions": 1, "profile": ["wallet_connected": walletConnected, "allow_gas_spend": false]])
            let data = try await self.request("/api/quests/run", body: body)
            let response = try JSONDecoder().decode(QuestRunResponse.self, from: data)
            self.questActions.removeAll { $0.leadID == leadID }
            self.questActions.append(contentsOf: response.results)
            for item in response.results { self.note("task", "QUEST \(String(item.leadID.prefix(8))) → \(item.status)") }
        }
    }

    private func recordSync(previousStatus: RuntimeStatus?, previousWorkflows: [AgentWorkflow], previousIntegrations: [IntegrationHealth], previousRegistrations: [RegistrationOutcome],
                            nextStatus: RuntimeStatus, nextWorkflows: [AgentWorkflow], nextIntegrations: [IntegrationHealth], nextRegistrations: [RegistrationOutcome]) {
        if previousStatus?.runtime != nextStatus.runtime {
            var suffix = ""
            if let previous = previousStatus?.runtime { suffix = " (was \(previous))" }
            note("state", "RUNTIME \(nextStatus.runtime.uppercased())\(suffix)")
        }
        if previousWorkflows.isEmpty {
            if !nextWorkflows.isEmpty { note("state", "BOOT \(nextWorkflows.count) CHECKPOINTS TRACKED") }
        } else {
            let before = Dictionary(previousWorkflows.map { ($0.id, $0.status ?? "") }, uniquingKeysWith: { first, _ in first })
            for workflow in nextWorkflows {
                let identifier = String(workflow.id.prefix(8))
                if let previous = before[workflow.id] {
                    if previous != (workflow.status ?? "") {
                        note(workflow.status == "failed" ? "error" : "task", "WORKFLOW \(identifier) → \(workflow.status ?? "unknown")")
                    }
                } else {
                    note("task", "WORKFLOW+ \(identifier) · \(String((workflow.query ?? "task").prefix(64)))")
                }
            }
        }
        if previousIntegrations.isEmpty {
            if !nextIntegrations.isEmpty { note("state", "BOOT \(nextIntegrations.count) INTEGRATIONS TRACKED") }
        } else {
            let before = Dictionary(previousIntegrations.map { ($0.id, $0.status) }, uniquingKeysWith: { first, _ in first })
            for integration in nextIntegrations where before[integration.id] != integration.status {
                let suffix = before[integration.id].map { " (was \($0))" } ?? ""
                note(Self.goodStatuses.contains(integration.status) ? "ok" : "warn", "INTEGRATION \(integration.name) → \(integration.status)\(suffix)")
            }
        }
        if previousRegistrations.isEmpty {
            if !nextRegistrations.isEmpty { note("state", "BOOT \(nextRegistrations.count) ACCOUNTS TRACKED") }
        } else {
            let before = Dictionary(previousRegistrations.map { ($0.id, $0.status) }, uniquingKeysWith: { first, _ in first })
            for registration in nextRegistrations where before[registration.id] != registration.status {
                let suffix = before[registration.id].map { " (was \($0))" } ?? ""
                note("task", "ACCOUNT \(registration.name) → \(registration.status)\(suffix)")
            }
        }
        syncCounter += 1
        if syncCounter == 1 || syncCounter % 3 == 1 {
            note("sync", "SYNC tools=\(nextStatus.tools) workflows=\(nextStatus.workflows) gates=\(nextStatus.awaitingApproval) memory=\(Int(nextStatus.memoryMB.rounded()))MB")
        }
    }

    private func note(_ level: String, _ message: String) {
        log.insert(LogEntry(date: Date(), level: level, message: "\(Self.clock.string(from: Date())) \(message)"), at: 0)
        if log.count > 240 { log.removeLast(log.count - 240) }
    }

    func generateProduct(_ spec: ProductSpec) async {
        await mutate {
            self.productReport = nil; self.productMesh = nil; self.productExports = []
            let data = try await self.request("/api/products/build", body: JSONEncoder().encode(spec))
            let report = try JSONDecoder().decode(ProductReport.self, from: data)
            guard spec == self.productSpec else { return }
            self.productReport = report
            guard let id = report.id, UUID(uuidString: id) != nil else { throw BackendError.invalidResponse }
            let directory = FileManager.default.temporaryDirectory.appendingPathComponent("SuperCraftOSProducts", isDirectory: true)
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            // Bound cache growth; export/share before generating the next revision.
            for file in try FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil) { try FileManager.default.removeItem(at: file) }
            for name in ["model.stl", "model.step", "profile.dxf", "report.json"] {
                guard report.files?[name] == "/api/products/\(id)/files/\(name)" else { throw BackendError.invalidResponse }
                let artifact = try await self.request("/api/products/\(id)/files/\(name)")
                let destination = directory.appendingPathComponent(name)
                try artifact.write(to: destination, options: .atomic)
                self.productExports.append(destination)
                if name == "model.stl" { self.productMesh = destination }
            }
            self.note("ok", "CAD SOLID \(id.prefix(8)) EXPORTED")
        }
    }

    func invalidateProductDraft() { productReport = nil; productMesh = nil; productExports = [] }

    func interpretProduct(_ idea: String) async -> ProductSpec? {
        await mutate {
            let data = try await self.request("/api/products/interpret", body: JSONEncoder().encode(["idea": idea]))
            return try JSONDecoder().decode(ProductSpec.self, from: data)
        }
    }
}
#endif

enum LocalUtilities {
    static func formatJSON(_ input: String) throws -> String {
        let data = Data(input.utf8)
        let object = try JSONSerialization.jsonObject(with: data, options: [.fragmentsAllowed])
        let output = try JSONSerialization.data(withJSONObject: object, options: [.prettyPrinted, .sortedKeys, .fragmentsAllowed])
        return String(decoding: output, as: UTF8.self)
    }

    static func encodeBase64(_ input: String) -> String { Data(input.utf8).base64EncodedString() }

    static func decodeBase64(_ input: String) throws -> String {
        guard let data = Data(base64Encoded: input), let result = String(data: data, encoding: .utf8) else {
            throw LocalUtilityError.invalidBase64
        }
        return result
    }
}

enum LocalUtilityError: LocalizedError {
    case invalidBase64
    var errorDescription: String? { "Input must be valid Base64 encoding UTF-8 text." }
}
