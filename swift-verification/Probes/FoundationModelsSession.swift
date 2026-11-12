// Compile probe: proves the on-device language model session API is callable.
import Foundation
import FoundationModels

@available(iOS 26.0, *)
func probeFoundationModelsSession() async throws {
    let session = LanguageModelSession()
    let response = try await session.respond(to: "ping")
    _ = response.content
}
