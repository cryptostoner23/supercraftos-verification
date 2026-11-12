import Foundation

struct AutonomousJob: Decodable, Identifiable {
    let id: String
    let query: String
    let status: String
    let created: Double
    let runAt: Double
    let steps: Int
    let maxSteps: Int
    let error: String?
    let result: AgentResult
    var canCancel: Bool { ["queued", "running"].contains(status) }
    var canRetry: Bool { ["failed", "blocked", "cancelled"].contains(status) }
    enum CodingKeys: String, CodingKey {
        case id, query, status, created, steps, error, result
        case runAt = "run_at", maxSteps = "max_steps"
    }
}
struct AgentResult: Decodable {
    let summary: String?
    let files: [AgentFile]?
    let checks: [AgentCheck]?
    let review: AgentReview?
    let nativeEvidence: [AgentNativeEvidence]?
    enum CodingKeys: String, CodingKey {
        case summary, files, checks, review
        case nativeEvidence = "native_evidence"
    }
}
struct AgentNativeEvidence: Decodable {
    let name: String
    let result: JSONValue
}
struct AgentReview: Decodable { let accepted: Bool; let issues: [String]? }
struct AgentFile: Decodable, Identifiable {
    let path: String
    let bytes: Int
    let sha256: String
    var id: String { path }
    func components() throws -> [String] {
        let parts = path.components(separatedBy: "/")
        guard !parts.isEmpty, !path.contains("\\"), !path.contains("\0"),
              parts.allSatisfy({ !$0.isEmpty && $0 != "." && $0 != ".." }) else { throw BackendError.invalidResponse }
        return parts
    }
    func endpoint(jobID: String) throws -> String {
        guard jobID.count == 32, jobID.allSatisfy({ "0123456789abcdef".contains($0) }) else { throw BackendError.invalidResponse }
        let allowed = CharacterSet.urlPathAllowed.subtracting(CharacterSet(charactersIn: "/%?#"))
        let encoded = try components().map { $0.addingPercentEncoding(withAllowedCharacters: allowed)! }.joined(separator: "/")
        return "/api/jobs/\(jobID)/files/\(encoded)"
    }
}
struct AgentCheck: Decodable {
    let command: String?
    let exitCode: Int?
    let output: String
    enum CodingKeys: String, CodingKey { case command, output; case exitCode = "exit_code" }
}
struct AgentStatus: Decodable {
    let workers: Int
    let modelConfigured: Bool
    let sandboxCLIAvailable: Bool
    enum CodingKeys: String, CodingKey {
        case workers
        case modelConfigured = "model_configured", sandboxCLIAvailable = "sandbox_cli_available"
    }
}
struct AgentEvent: Decodable, Identifiable {
    let id: Int
    let at: Double
    let kind: String
    let detail: JSONValue
}
struct AgentJobsResponse: Decodable { let jobs: [AutonomousJob] }
struct AgentEventsResponse: Decodable { let events: [AgentEvent] }
struct AgentSubmission: Encodable {
    let query: String
    let maxSteps: Int
    let runAt: Double?
    enum CodingKeys: String, CodingKey { case query; case maxSteps = "max_steps", runAt = "run_at" }
}
indirect enum JSONValue: Codable {
    case object([String: JSONValue]), array([JSONValue]), string(String), number(Double), bool(Bool), null
    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() { self = .null }
        else if let value = try? container.decode(Bool.self) { self = .bool(value) }
        else if let value = try? container.decode(String.self) { self = .string(value) }
        else if let value = try? container.decode(Double.self) { self = .number(value) }
        else if let value = try? container.decode([String: JSONValue].self) { self = .object(value) }
        else { self = .array(try container.decode([JSONValue].self)) }
    }
    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .object(let value): try container.encode(value)
        case .array(let value): try container.encode(value)
        case .string(let value): try container.encode(value)
        case .number(let value): try container.encode(value)
        case .bool(let value): try container.encode(value)
        case .null: try container.encodeNil()
        }
    }
    var formatted: String {
        let encoder = JSONEncoder(); encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        return (try? String(decoding: encoder.encode(self), as: UTF8.self)) ?? "Unavailable event detail"
    }
}

struct AgentMemory: Decodable {
    let mode: String
    let description: String
    let playbooks: [ExecutionPlaybook]
    let lessons: [ExecutionLesson]
}
struct ExecutionPlaybook: Decodable, Identifiable {
    let id: String; let title: String; let when: String; let steps: [String]; let evidence: [String]
}
struct ExecutionLesson: Decodable, Identifiable {
    let id: String; let lesson: String; let accepted: Bool
    let jobID: String; let checksPassed: Int
    enum CodingKeys: String, CodingKey { case id, lesson, accepted; case jobID = "job_id", checksPassed = "checks_passed" }
}

struct AgentTrace: Decodable {
    let timeline: [AgentTraceItem]
    let nextCursor: Int?
    enum CodingKeys: String, CodingKey { case timeline; case nextCursor = "next_cursor" }
}
struct AgentTraceItem: Decodable, Identifiable {
    let id: Int
    let at: Double
    let kind: String
    let label: String
    let action: String?
    let step: Int?
    let toolName: String?
    let outcome: String?
    let message: String?
    enum CodingKeys: String, CodingKey { case id, at, kind, label, action, step, outcome, message; case toolName = "tool_name" }
}
