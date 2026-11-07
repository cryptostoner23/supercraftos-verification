import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

/// Unified API Client for Digital Me × SuperCraftOS
/// Connects the iOS app to the unified backend endpoints.
struct UnifiedAPIClient {
    let connection: BackendConnection
    private let session: URLSession
    private var controlToken: String?

    init(connection: BackendConnection) {
        self.connection = connection
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = 190
        config.timeoutIntervalForResource = 200
        config.httpShouldSetCookies = false
        self.session = URLSession(configuration: config)
    }

    mutating func data(_ path: String, body: Data? = nil, idempotencyKey: String? = nil) async throws -> Data {
        guard !connection.accessKey.isEmpty else { throw BackendError.authenticationRequired }
        return try await send(path, body: body, idempotencyKey: idempotencyKey, retrySession: true)
    }

    private mutating func send(_ path: String, body: Data?, idempotencyKey: String?, retrySession: Bool) async throws -> Data {
        if body != nil && controlToken == nil {
            let data = try await send("/api/session", body: nil, idempotencyKey: nil, retrySession: false)
            struct Session: Decodable { let token: String }
            let token = try JSONDecoder().decode(Session.self, from: data).token
            guard !token.isEmpty else { throw BackendError.tokenUnavailable }
            controlToken = token
        }
        var request = URLRequest(url: try connection.url(path))
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if !connection.accessKey.isEmpty {
            request.setValue("Bearer " + connection.accessKey, forHTTPHeaderField: "Authorization")
        }
        if let body {
            request.httpMethod = "POST"
            request.httpBody = body
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.setValue(controlToken, forHTTPHeaderField: "X-SuperCraftOS-Token")
            if let idempotencyKey { request.setValue(idempotencyKey, forHTTPHeaderField: "Idempotency-Key") }
        }
        let (data, response) = try await session.data(for: request)
        guard let response = response as? HTTPURLResponse else { throw BackendError.invalidResponse }
        if response.statusCode == 401 { controlToken = nil; throw BackendError.authenticationRequired }
        if response.statusCode == 403 && body != nil && retrySession {
            controlToken = nil
            return try await send(path, body: body, idempotencyKey: idempotencyKey, retrySession: false)
        }
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

func unifiedReason(query: String, intent: String, context: [String: String] = [:], preferredModel: String? = nil) async throws -> UnifiedReasoningResponse {
    var client = UnifiedAPIClient(connection: try BackendConnection(address: "https://api.supercraftos.app", accessKey: "test-key"))

    let requestBody = try? JSONSerialization.data(withJSONObject: [
        "intent": intent,
        "query": query,
        "context": context,
        "preferred_model": preferredModel ?? "general",
        "temperature": 0.7
    ]) ?? Data()

    let data = try await client.data("/api/v1/unified/reason", body: requestBody)
    return try JSONDecoder().decode(UnifiedReasoningResponse.self, from: data)
}

func unifiedSearch(query: String, topK: Int = 5) async throws -> [String: String] {
    var client = UnifiedAPIClient(connection: try BackendConnection(address: "https://api.supercraftos.app", accessKey: "test-key"))

    let requestBody = try? JSONSerialization.data(withJSONObject: ["query": query, "top_k": topK]) ?? Data()
    let data = try await client.data("/api/v1/unified/search", body: requestBody)

    let response = try JSONDecoder().decode(UnifiedSearchResponse.self, from: data)
    return [
        "query": query,
        "entries": response.entries.joined(separator: ","),
        "metadata": response.metadata?.merging([:]) { $1 } ?? [:]
    ]
}

func unifiedAgentStatus() async throws -> [String: String] {
    var client = UnifiedAPIClient(connection: try BackendConnection(address: "https://api.supercraftos.app", accessKey: "test-key"))

    let data = try await client.data("/api/v1/unified/agents")
    return [:]
}

func unifiedModelRoute(taskType: String, complexity: String, costSensitive: Bool = true) async throws -> [String: String] {
    var client = UnifiedAPIClient(connection: try BackendConnection(address: "https://api.supercraftos.app", accessKey: "test-key"))

    let requestBody = try JSONSerialization.data(withJSONObject: ["task_type": taskType, "complexity": complexity, "cost_sensitive": costSensitive])
    let data = try await client.data("/api/v1/unified/model/route", body: requestBody)
    return [:]
}

func unifiedHealth() async throws -> [String: String] {
    var client = UnifiedAPIClient(connection: try BackendConnection(address: "https://api.supercraftos.app", accessKey: "test-key"))

    let data = try await client.data("/api/v1/unified/health/detailed")
    return [:]
}

/// Unified reasoning response model
struct UnifiedReasoning: Codable {
    let intent: String?
    let query: String?
    let retrieved_context: [String]
    let analysis: String?
    let confidence: Double?
    let timestamp: String?
}
