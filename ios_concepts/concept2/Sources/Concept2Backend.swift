import SwiftUI
import Foundation

@MainActor
final class Concept2Backend: ObservableObject {
    @Published var status: String = "offline"
    @Published var workers: Int = 0
    @Published var memoryCount: Int = 0
    @Published var playbookCount: Int = 0
    @Published var memories: [String] = []
    @Published var loading = true
    @Published var error: String?

    private let service: BackendService
    init(accessKey: String) {
        service = BackendService(accessKey: accessKey)
    }

    func refresh() async {
        loading = true
        defer { loading = false }
        do {
            let statusData = try await service.get("/api/status")
            if let obj = try JSONSerialization.jsonObject(with: statusData) as? [String: Any] {
                workers = obj["agents"] as? Int ?? 0
                status = obj["status"] as? String ?? "online"
            }
            let profileData = try await service.get("/api/digital_me/profile")
            if let obj = try JSONSerialization.jsonObject(with: profileData) as? [String: Any] {
                memoryCount = obj["memory_entries"] as? Int ?? 0
                playbookCount = obj["playbooks"] as? Int ?? 0
            }
            let memData = try await service.get("/api/digital_me/memory?query=recent")
            if let obj = try JSONSerialization.jsonObject(with: memData) as? [String: Any],
               let entries = obj["entries"] as? [[String: Any]] {
                memories = entries.prefix(5).compactMap { $0["note"] as? String }
            }
            error = nil
        } catch {
            self.error = "Backend unreachable: \(error.localizedDescription)"
        }
    }
}
