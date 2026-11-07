import Foundation
#if canImport(SuperCraftOS)
@testable import SuperCraftOS
#endif

/// Only an explicit live opt-in can leave the fixture transport. Missing live
/// credentials fail the suite instead of silently using an anonymous session.
enum BackendTestConfiguration {
    static func client() throws -> BackendClient {
        let env = ProcessInfo.processInfo.environment
        guard env["SUPERCRAFTOS_LIVE_TESTS"] == "1" else { return CIBackendFixture.makeClient() }
        guard let address = env["SUPERCRAFTOS_TEST_BACKEND"],
              let key = env["SUPERCRAFTOS_TEST_ACCESS_KEY"], !key.isEmpty, !key.contains("$(") else {
            throw BackendError.authenticationRequired
        }
        return BackendClient(connection: try BackendConnection(address: address, accessKey: key))
    }
}
