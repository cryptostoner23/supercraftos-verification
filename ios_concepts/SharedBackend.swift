import Foundation

/// Tiny shared backend client for the production concept apps.
/// Talks to the real SuperCraftOS backend over the private gateway.
struct BackendService {
    let base: String
    let accessKey: String

    init(base: String = "https://commetai.com", accessKey: String) {
        self.base = base
        self.accessKey = accessKey
    }

    func get(_ path: String) async throws -> Data {
        guard let url = URL(string: base + path) else { throw URLError(.badURL) }
        var req = URLRequest(url: url)
        req.setValue("Bearer " + accessKey, forHTTPHeaderField: "Authorization")
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        let (data, resp) = try await URLSession.shared.data(for: req)
        guard let http = resp as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        return data
    }

    func post(_ path: String, body: [String: Any]) async throws -> Data {
        guard let url = URL(string: base + path) else { throw URLError(.badURL) }
        // Session token for mutations
        let sessionData = try await get("/api/session")
        struct Session: Decodable { let token: String }
        let token = try JSONDecoder().decode(Session.self, from: sessionData).token
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("Bearer " + accessKey, forHTTPHeaderField: "Authorization")
        req.setValue(token, forHTTPHeaderField: "X-SuperCraftOS-Token")
        req.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (data, resp) = try await URLSession.shared.data(for: req)
        guard let http = resp as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        return data
    }
}
