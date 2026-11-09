import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

enum BackendError: LocalizedError {
    case invalidURL, invalidResponse, rejected(Int, String?, String?), tokenUnavailable, invalidAccessKey, authenticationRequired, credentialStorage, responseTooLarge
    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Enter the private HTTPS access link or an HTTPS server origin."
        case .invalidAccessKey: return "The access key contains invalid characters."
        case .authenticationRequired: return "Connection needs a valid private access link or access key."
        case .credentialStorage: return "The access key could not be saved in this device’s Keychain."
        case .responseTooLarge: return "The server response exceeds the download limit."
        case .invalidResponse: return "The backend returned an unexpected response."
        case .rejected(let status, let reason, let detail):
            var text = reason ?? "The backend rejected the request"
            if let detail, !detail.isEmpty { text += " · \(detail)" }
            return "\(text) (HTTP \(status))"
        case .tokenUnavailable: return "The backend did not provide a control session."
        }
    }
}

/// The error body the backend returns for a rejected request.
struct BackendErrorBody: Decodable {
    let error: String?
    let detail: String?
    enum CodingKeys: String, CodingKey { case error, detail }
    private struct RPCError: Decodable { let message: String }
    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        error = (try? values.decode(String.self, forKey: .error))
            ?? (try? values.decode(RPCError.self, forKey: .error).message)
        detail = try? values.decode(String.self, forKey: .detail)
    }
}

struct BackendConnection: Equatable, Sendable {
    let origin: String
    let accessKey: String

    init(address: String, accessKey: String = "") throws {
        guard var parts = URLComponents(string: address.trimmingCharacters(in: .whitespacesAndNewlines)),
              parts.scheme?.lowercased() == "https", let host = parts.host, !host.isEmpty,
              parts.user == nil, parts.password == nil, parts.query == nil,
              ["", "/", "/agents"].contains(parts.path),
              parts.port == nil || (1...65535).contains(parts.port!) else { throw BackendError.invalidURL }
        let fragment = parts.fragment ?? ""
        let supplied = accessKey.trimmingCharacters(in: .whitespacesAndNewlines)
        let key = supplied.isEmpty ? fragment : supplied
        guard key.utf8.count <= 512, key.utf8.allSatisfy({ (33...126).contains($0) }) else {
            throw BackendError.invalidAccessKey
        }
        parts.scheme = "https"; parts.host = host.lowercased(); parts.path = ""; parts.fragment = nil
        guard let origin = parts.url?.absoluteString else { throw BackendError.invalidURL }
        self.origin = origin; self.accessKey = key
    }

    func url(_ path: String) throws -> URL {
        guard path.hasPrefix("/api/"), !path.contains("\\"), !path.contains("#"),
              let url = URL(string: origin + path), url.host == URL(string: origin)?.host else {
            throw BackendError.invalidURL
        }
        return url
    }
}

private final class NoRedirects: NSObject, URLSessionTaskDelegate, @unchecked Sendable {
    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) {
        // An access credential belongs to one explicit origin; redirects require reconnection.
        completionHandler(nil)
    }
}

actor BackendClient {
    nonisolated let connection: BackendConnection
    private let session: URLSession
    private var controlToken: String?

    init(connection: BackendConnection, session: URLSession? = nil) {
        self.connection = connection
        if let session { self.session = session }
        else {
            let config = URLSessionConfiguration.ephemeral
            config.timeoutIntervalForRequest = 190
            config.timeoutIntervalForResource = 200
            config.httpShouldSetCookies = false
            self.session = URLSession(configuration: config, delegate: NoRedirects(), delegateQueue: nil)
        }
    }

    func data(_ path: String, body: Data? = nil, idempotencyKey: String? = nil) async throws -> Data {
        guard !connection.accessKey.isEmpty else { throw BackendError.authenticationRequired }
        return try await send(path, body: body, idempotencyKey: idempotencyKey, retrySession: true)
    }

    private func send(_ path: String, body: Data?, idempotencyKey: String?, retrySession: Bool) async throws -> Data {
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
            request.httpMethod = "POST"; request.httpBody = body
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
