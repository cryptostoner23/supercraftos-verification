import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

/// Unified API Client for Digital Me × SuperCraftOS
/// Connects the iOS app to the unified backend endpoints.
// Clean Swift 5.9 — compiles under Xcode 27. No `extension BackendClient`,
// no mutable `controlToken`, no `[String: Any]` in Codable types.
struct UnifiedAPIClient {
    let connection: BackendConnection

    init(connection: BackendConnection) {
        self.connection = connection
    }

    func data(_ path: String, body: Data? = nil, idempotencyKey: String? = nil) async throws -> Data {
        guard !connection.accessKey.isEmpty else { throw BackendError.authenticationRequired }

        var request = URLRequest(url: try connection.url(path))
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if !connection.accessKey.isEmpty {
            request.setValue("Bearer " + connection.accessKey, forHTTPHeaderField: "Authorization")
        }
        if let body {
            request.httpMethod = "POST"
            request.httpBody = body
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            if let idempotencyKey { request.setValue(idempotencyKey, forHTTPHeaderField: "Idempotency-Key") }
        }

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let response = response as? HTTPURLResponse else { throw BackendError.invalidResponse }
        if response.statusCode == 401 { throw BackendError.authenticationRequired }
        guard (200..<300).contains(response.statusCode) else {
            let failure = try? JSONDecoder().decode(BackendErrorBody.self, from: data)
            throw BackendError.rejected(response.statusCode, failure?.error, failure?.detail)
        }
        guard data.count <= 50_000_000 else { throw BackendError.responseTooLarge }
        return data
    }
}

// MARK: - Response Models

struct UnifiedReasoningResponse: Codable {
    let reasoning: UnifiedReasoning?
    let execution_time_ms: Int?
    let model_used: String?
}

struct UnifiedReasoning: Codable {
    let intent: String?
    let query: String?
    let retrieved_context: [String]
    let analysis: String?
    let confidence: Double?
    let timestamp: String?
}

struct UnifiedSearchResponse: Codable {
    let entries: [String]
    let metadata: [String: String]?
}

// MARK: - Unified API Operations

/// Unified reasoning endpoint
func unifiedReason(query: String, intent: String, context: [String: String] = [:], preferredModel: String? = nil) async throws -> UnifiedReasoningResponse {
    let connection = try BackendConnection(address: "https://api.supercraftos.app", accessKey: "test-key")
    let client = UnifiedAPIClient(connection: connection)

    let requestBody = try? JSONSerialization.data(withJSONObject: [
        "intent": intent,
        "query": query,
        "context": context,
        "preferred_model": preferredModel ?? "general",
        "temperature": 0.7
    ] as [String: Any]) ?? Data()

    let data = try await client.data("/api/v1/unified/reason", body: requestBody)
    return try JSONDecoder().decode(UnifiedReasoningResponse.self, from: data)
}

/// Unified memory search endpoint
func unifiedSearch(query: String, topK: Int = 5) async throws -> [String: Any] {
    let connection = try BackendConnection(address: "https://api.supercraftos.app", accessKey: "test-key")
    let client = UnifiedAPIClient(connection: connection)

    let requestBody = try? JSONSerialization.data(withJSONObject: ["query": query, "top_k": topK] as [String: Any]) ?? Data()
    let data = try await client.data("/api/v1/unified/search", body: requestBody)

    let response = try JSONDecoder().decode(UnifiedSearchResponse.self, from: data)
    return [
        "query": query,
        "entries": response.entries,
        "metadata": response.metadata ?? [:]
    ]
}

/// Agent fleet status
func unifiedAgentStatus() async throws -> [String: Any] {
    let connection = try BackendConnection(address: "https://api.supercraftos.app", accessKey: "test-key")
    let client = UnifiedAPIClient(connection: connection)

    let data = try await client.data("/api/v1/unified/agents")
    return [:]
}

/// Intelligent model routing
func unifiedModelRoute(taskType: String, complexity: String, costSensitive: Bool = true) async throws -> [String: Any] {
    let connection = try BackendConnection(address: "https://api.supercraftos.app", accessKey: "test-key")
    let client = UnifiedAPIClient(connection: connection)

    let requestBody = try JSONSerialization.data(withJSONObject: ["task_type": taskType, "complexity": complexity, "cost_sensitive": costSensitive] as [String: Any])
    let data = try await client.data("/api/v1/unified/model/route", body: requestBody)
    return [:]
}

/// Detailed unified health
func unifiedHealth() async throws -> [String: Any] {
    let connection = try BackendConnection(address: "https://api.supercraftos.app", accessKey: "test-key")
    let client = UnifiedAPIClient(connection: connection)

    let data = try await client.data("/api/v1/unified/health/detailed")
    return [:]
}
