import Foundation

// MARK: - Error

enum APIError: LocalizedError {
    case invalidURL, invalidResponse, unauthorized, rejected(Int, String?), network(String)
    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid backend URL."
        case .invalidResponse: return "The backend returned an unexpected response."
        case .unauthorized: return "Access key was rejected by the backend."
        case .rejected(let code, let msg): return msg ?? "Request failed (HTTP \(code))."
        case .network(let msg): return "Network error: \(msg)"
        }
    }
}

// MARK: - API client

/// Production client for the SuperCraftOS + Digital Me backend.
/// Uses the authenticated gateway (Bearer key) and fetches a control
/// session token for mutations, exactly as the main app does.
struct APIClient {
    let base: String
    let accessKey: String

    init(base: String = "https://commetai.com", accessKey: String) {
        self.base = base
        self.accessKey = accessKey
    }

    private func makeURL(_ path: String) throws -> URL {
        guard let url = URL(string: base + path) else { throw APIError.invalidURL }
        return url
    }

    private func request(_ url: URL, method: String, body: Data?) -> URLRequest {
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        req.setValue("Bearer " + accessKey, forHTTPHeaderField: "Authorization")
        req.timeoutInterval = 30
        if let body {
            req.httpBody = body
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        return req
    }

    func get(_ path: String) async throws -> Data {
        var req = request(try makeURL(path), method: "GET", body: nil)
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        let (data, resp) = try await URLSession.shared.data(for: req)
        guard let http = resp as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else {
            if http.statusCode == 401 { throw APIError.unauthorized }
            let msg = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["error"] as? String
            throw APIError.rejected(http.statusCode, msg)
        }
        return data
    }

    /// Mutation with a control session token (mirrors the gateway contract).
    func post(_ path: String, body: [String: Any]) async throws -> Data {
        let sessionData = try await get("/api/session")
        struct Session: Decodable { let token: String }
        let token = try JSONDecoder().decode(Session.self, from: sessionData).token

        var req = request(try makeURL(path), method: "POST", body: try JSONSerialization.data(withJSONObject: body))
        req.setValue(token, forHTTPHeaderField: "X-SuperCraftOS-Token")
        let (data, resp) = try await URLSession.shared.data(for: req)
        guard let http = resp as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else {
            let msg = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["error"] as? String
            throw APIError.rejected(http.statusCode, msg)
        }
        return data
    }
}

// MARK: - Domain models (shapes verified against the live backend)

struct SystemStatus: Decodable {
    var runtime: String
    var usage: UsageInfo
    var tools: Int
    var integrations: Int
    var healthyIntegrations: Int
    var workflows: Int
    var awaitingApproval: Int
    var agentBrain: Bool
    enum CodingKeys: String, CodingKey {
        case runtime, usage, tools, integrations, workflows
        case healthyIntegrations = "healthy_integrations"
        case awaitingApproval = "awaiting_approval"
        case agentBrain = "agent_brain"
    }
}

struct UsageInfo: Decodable {
    var inputTokens: Int
    var outputTokens: Int
    var costUSD: Double
    var requests: Int
    enum CodingKeys: String, CodingKey {
        case inputTokens = "input_tokens"
        case outputTokens = "output_tokens"
        case costUSD = "cost_usd"
        case requests
    }
}

struct Job: Decodable, Identifiable {
    var id: String
    var query: String
    var status: String
    var created: Double
    var steps: Int
    var result: JobResult?
    var summary: String? { result?.summary }
    var isRunning: Bool { status == "running" || status == "queued" }
    var isCompleted: Bool { status == "completed" }
    var statusColorName: String {
        switch status {
        case "completed": return "ok"
        case "failed", "canceled": return "danger"
        case "running", "queued": return "accent"
        default: return "muted"
        }
    }
}

struct JobResult: Decodable {
    var summary: String?
    var files: [JobFile]?
    var checks: [JobCheck]?
    var plan: [String]?
    var acceptance: [String]?
    var review: JobReview?
}

struct JobFile: Decodable {
    var path: String
    var bytes: Int?
}

struct JobCheck: Decodable {
    var command: String
    var exitCode: Int?
    var output: String?
    var timedOut: Bool?
    enum CodingKeys: String, CodingKey {
        case command, output
        case exitCode = "exit_code"
        case timedOut = "timed_out"
    }
}

struct JobReview: Decodable {
    var accepted: Bool?
    var issues: [String]?
}

struct JobEvent: Decodable {
    var kind: String
    var at: Double
    var step: Int?
    var note: String?
    var detail: [String: String]?
    enum CodingKeys: String, CodingKey { case kind, at, step, note, detail }
}

struct GameProfile: Decodable {
    var identity: IdentityInfo
    var memoryEntries: Int
    var playbooks: Int
    enum CodingKeys: String, CodingKey {
        case identity
        case memoryEntries = "memory_entries"
        case playbooks
    }
}

struct IdentityInfo: Decodable {
    var id: String
    var name: String
    var createdAt: Double
    enum CodingKeys: String, CodingKey {
        case id, name
        case createdAt = "created_at"
    }
}

struct BrainStatus: Decodable {
    var ingestedNoteIDs: Int
    var understanding: Understanding?
    var actions: [BrainAction]?
    enum CodingKeys: String, CodingKey {
        case understanding, actions
        case ingestedNoteIDs = "ingested_note_ids"
    }
}

struct Understanding: Decodable {
    var profile: String?
    var topics: [String]?
    var intents: [String]?
    var priorities: [String]?
}

struct BrainAction: Decodable {
    var action: String
    var confidence: Double?
    var outcome: String?
    var detail: String?
}

struct MemoryEntry: Decodable, Identifiable {
    var id: String
    var note: String
    var tags: [String]?
    var notebook: String?
    var createdAt: Double?
    enum CodingKeys: String, CodingKey {
        case id, note, tags, notebook
        case createdAt = "created_at"
    }
}

struct Playbook: Decodable, Identifiable {
    var id: String
    var title: String
    var when: String?
    var steps: [String]?
    var evidence: [String]?
}

struct Integration: Decodable, Identifiable {
    var id: String { name }
    var name: String
    var status: String
    var detail: String?
    var reconnectSupported: Bool?
    var credentialURL: String?
    enum CodingKeys: String, CodingKey {
        case name, status, detail
        case reconnectSupported = "reconnect_supported"
        case credentialURL = "credential_url"
    }
}

struct Capability: Decodable, Identifiable {
    var id: String
    var name: String
    var features: String?
    var enabled: Bool
    var runs: Int
    var successes: Int
    var routingScore: Double
    enum CodingKeys: String, CodingKey {
        case id, name, features, enabled, runs, successes
        case routingScore = "routing_score"
    }
}

struct LP {
    static func convert(_ raw: Double) -> Date { Date(timeIntervalSince1970: raw) }
}
