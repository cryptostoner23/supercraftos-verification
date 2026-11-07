import Foundation

/// The extension has its own Keychain identity. No App Group entitlement or
/// anonymous gateway session is needed, including when signed by a personal team.
actor KeyboardBackend {
    enum Failure: LocalizedError {
        case notConfigured, noReply
        var errorDescription: String? {
            switch self {
            case .notConfigured: return "Open keyboard connection settings and paste your private access link."
            case .noReply: return "The backend returned no usable reply."
            }
        }
    }
    private struct WorkflowReply: Decodable {
        let status: String?
        let plan: String?
        let artifact: String?
        let error: String?
    }
    private var client: BackendClient?
    private static let addressKey = "supercraftos.keyboard.backend"

    init(client: BackendClient? = nil) { self.client = client }

    func configure(privateLink: String) throws {
        let connection = try BackendConnection(address: privateLink)
        guard !connection.accessKey.isEmpty else { throw BackendError.authenticationRequired }
        try CredentialStore.save(connection.accessKey, origin: connection.origin)
        UserDefaults.standard.set(connection.origin, forKey: Self.addressKey)
        client = BackendClient(connection: connection)
    }

    func disconnect() throws {
        if let origin = UserDefaults.standard.string(forKey: Self.addressKey) {
            try CredentialStore.save("", origin: origin)
        }
        client = nil
        UserDefaults.standard.removeObject(forKey: Self.addressKey)
    }

    private func configuredClient() throws -> BackendClient {
        if let client { return client }
        guard let origin = UserDefaults.standard.string(forKey: Self.addressKey),
              let key = CredentialStore.load(origin: origin), !key.isEmpty else { throw Failure.notConfigured }
        let configured = BackendClient(connection: try BackendConnection(address: origin, accessKey: key))
        client = configured
        return configured
    }

    func runWorkflow(query: String) async throws -> String {
        let data = try await configuredClient().data("/api/workflows", body: JSONSerialization.data(withJSONObject: ["query": query]))
        let reply = try JSONDecoder().decode(WorkflowReply.self, from: data)
        if let error = reply.error, !error.isEmpty { throw BackendError.rejected(200, error, nil) }
        if let artifact = reply.artifact, !artifact.isEmpty { return artifact }
        if let plan = reply.plan, !plan.isEmpty { return plan }
        if let status = reply.status, !status.isEmpty { return status }
        throw Failure.noReply
    }
}
