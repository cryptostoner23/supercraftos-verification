import XCTest
import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif
@testable import ControlCore

final class FixtureProtocol: URLProtocol {
    static var handler: ((URLRequest) throws -> (Int, String))?
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        do {
            let (status, text) = try Self.handler!(request)
            let response = HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: "HTTP/1.1", headerFields: ["Content-Type": "application/json"])!
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: Data(text.utf8))
            client?.urlProtocolDidFinishLoading(self)
        } catch { client?.urlProtocol(self, didFailWithError: error) }
    }
    override func stopLoading() {}
}

final class BackendClientTests: XCTestCase {
    func client() throws -> BackendClient {
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [FixtureProtocol.self]
        return BackendClient(connection: try BackendConnection(address: "https://example.test/#access-test"), session: URLSession(configuration: config))
    }
    override func tearDown() { FixtureProtocol.handler = nil }

    func testPrivateLinkSeparatesCredentialFromOrigin() throws {
        let connection = try BackendConnection(address: " https://EXAMPLE.test/agents#access-test ")
        XCTAssertEqual(connection.origin, "https://example.test")
        XCTAssertEqual(connection.accessKey, "access-test")
        XCTAssertEqual(try connection.url("/api/jobs").absoluteString, "https://example.test/api/jobs")
        for address in ["http://example.test", "https://user:pass@example.test", "https://example.test/x", "https://example.test/?token=secret", "https://example.test:0"] {
            XCTAssertThrowsError(try BackendConnection(address: address))
        }
        XCTAssertThrowsError(try BackendConnection(address: "https://example.test", accessKey: "bad key"))
        XCTAssertThrowsError(try connection.url("https://other.test/api/jobs"))
        XCTAssertThrowsError(try connection.url("//other.test/api/jobs"))
    }

    func testMutationAuthenticatesAndRefreshesStaleSessionOnce() async throws {
        var paths: [String] = []
        var sessions = 0
        var posts = 0
        FixtureProtocol.handler = { request in
            XCTAssertEqual(request.value(forHTTPHeaderField: "Authorization"), "Bearer access-test")
            XCTAssertNil(request.url?.fragment)
            paths.append(request.url!.path)
            if request.url!.path == "/api/session" {
                sessions += 1
                return (200, "{\"token\":\"session-\(sessions)\"}")
            }
            posts += 1
            XCTAssertEqual(request.httpMethod, "POST")
            XCTAssertEqual(request.value(forHTTPHeaderField: "Idempotency-Key"), "same-request")
            XCTAssertEqual(request.value(forHTTPHeaderField: "X-SuperCraftOS-Token"), "session-\(sessions)")
            return posts == 1 ? (403, "{}") : (200, "{\"ok\":true}")
        }
        let result = try await client().data("/api/jobs", body: Data("{}".utf8), idempotencyKey: "same-request")
        XCTAssertEqual(String(decoding: result, as: UTF8.self), "{\"ok\":true}")
        XCTAssertEqual(paths, ["/api/session", "/api/jobs", "/api/session", "/api/jobs"])
    }

    func testUnauthorizedDoesNotRetryOrMutate() async throws {
        var calls = 0
        FixtureProtocol.handler = { _ in calls += 1; return (401, "{}") }
        do { _ = try await client().data("/api/jobs", body: Data("{}".utf8)); XCTFail("Expected authentication failure") }
        catch BackendError.authenticationRequired {} catch { XCTFail("Unexpected \(error)") }
        XCTAssertEqual(calls, 1)
    }

    func testPermanentForbiddenIsBounded() async throws {
        var calls = 0
        FixtureProtocol.handler = { request in
            calls += 1
            return request.url!.path == "/api/session" ? (200, "{\"token\":\"token\"}") : (403, "{}")
        }
        do { _ = try await client().data("/api/jobs", body: Data("{}".utf8)); XCTFail("Expected forbidden") }
        catch BackendError.rejected(let status, _, _) { XCTAssertEqual(status, 403) }
        XCTAssertEqual(calls, 4)
    }

    func testRejectedRequestPreservesServerReasonAndDetail() async throws {
        FixtureProtocol.handler = { _ in
            (400, "{\"error\":\"unsupported_design\",\"detail\":\"Supply dimensions\"}")
        }
        do { _ = try await client().data("/api/status"); XCTFail("Expected rejection") }
        catch BackendError.rejected(let code, let reason, let detail) {
            XCTAssertEqual(code, 400)
            XCTAssertEqual(reason, "unsupported_design")
            XCTAssertEqual(detail, "Supply dimensions")
        }
    }

    func testMissingAccessKeyMakesNoAnonymousSessionRequest() async throws {
        var requests = 0
        FixtureProtocol.handler = { _ in requests += 1; return (200, "{}") }
        let config = URLSessionConfiguration.ephemeral; config.protocolClasses = [FixtureProtocol.self]
        let backend = BackendClient(connection: try BackendConnection(address: "https://example.test"), session: URLSession(configuration: config))
        do { _ = try await backend.data("/api/jobs", body: Data("{}".utf8)); XCTFail("Expected authentication failure") }
        catch BackendError.authenticationRequired {}
        XCTAssertEqual(requests, 0)
    }

    func testPrivateKeysNeverUsePlaintextEvenOnTheLAN() {
        for address in ["http://localhost", "http://127.0.0.1", "http://192.168.1.10"] {
            XCTAssertThrowsError(try BackendConnection(address: address, accessKey: "private-key"))
        }
        for key in ["bad\rkey", "bad\nkey", "bad\0key", "bad\u{7f}key"] {
            XCTAssertThrowsError(try BackendConnection(address: "https://example.test", accessKey: key))
        }
    }

    func testDebugFixtureRejectsUnauthorizedAndUnknownRoutes() async throws {
        let unauthorized = CIBackendFixture.makeClient(accessKey: "wrong-key")
        do { _ = try await unauthorized.data("/api/status"); XCTFail("Expected authentication failure") }
        catch BackendError.authenticationRequired {}
        let backend = CIBackendFixture.makeClient()
        let status = try JSONDecoder().decode(RuntimeStatus.self, from: await backend.data("/api/status"))
        XCTAssertEqual(status.runtime, "running")
        do { _ = try await backend.data("/api/not-implemented"); XCTFail("Unknown fixture route must fail") }
        catch BackendError.rejected(let code, let reason, _) {
            XCTAssertEqual(code, 404); XCTAssertEqual(reason, "fixture_route_missing")
        }
    }

    func testQueuedAndCompletedJobModels() throws {
        let data = Data("""
        {"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","query":"Build utility","status":"queued","created":10,"run_at":10,"steps":0,"max_steps":24,"result":{}}
        """.utf8)
        let job = try JSONDecoder().decode(AutonomousJob.self, from: data)
        XCTAssertTrue(job.canCancel); XCTAssertFalse(job.canRetry); XCTAssertNil(job.result.files)
        let file = AgentFile(path: "outputs/report #1%.txt", bytes: 20, sha256: "checksum")
        XCTAssertEqual(try file.endpoint(jobID: job.id), "/api/jobs/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/files/outputs/report%20%231%25.txt")
        for path in ["../secret", "/secret", "a//b", "a/./b", "a\\b", ""] {
            XCTAssertThrowsError(try AgentFile(path: path, bytes: 1, sha256: "").components())
        }
    }
}

final class ExecutionContractTests: XCTestCase {
    func testJSONRPCValidationErrorPreservesMessage() throws {
        let value = try JSONDecoder().decode(BackendErrorBody.self, from: Data(#"{"error":{"code":-32602,"message":"query is required"}}"#.utf8))
        XCTAssertEqual(value.error, "query is required")
    }
    func testTraceDecodesSafeTimelineAndCursor() throws {
        let data = Data(#"{"timeline":[{"id":13,"at":123.5,"kind":"tool_result","label":"Tool completed","tool_name":"grant_catalog","outcome":"success","message":"20 programmes"}],"next_cursor":13}"#.utf8)
        let trace = try JSONDecoder().decode(AgentTrace.self, from: data)
        XCTAssertEqual(trace.nextCursor, 13)
        XCTAssertEqual(trace.timeline.first?.toolName, "grant_catalog")
        XCTAssertEqual(trace.timeline.first?.message, "20 programmes")
    }
    func testGrantProfilePreservesDeliveryEvidence() throws {
        let profile = GrantProfile(projectName: "Public tools", summary: "Defined measurable delivery", topics: ["infrastructure"], chains: ["Ethereum"], budgetUSD: 7500, repositoryURL: "https://github.com/example/repo", team: "Maintainers", milestones: ["Publish reproducible benchmark"])
        let data = try JSONEncoder().encode(profile)
        let encoded = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        XCTAssertEqual(encoded["repository_url"] as? String, "https://github.com/example/repo")
        XCTAssertEqual(encoded["milestones"] as? [String], ["Publish reproducible benchmark"])
    }
    func testPlateUsesThicknessAsEffectiveHeight() {
        var spec = ProductSpec()
        spec.template = "plate"; spec.heightMM = 90; spec.wallMM = 4
        XCTAssertEqual(spec.effectiveHeightMM, 4)
        spec.template = "enclosure"
        XCTAssertEqual(spec.effectiveHeightMM, 90)
    }
    func testToolSchemaRemainsAvailableForExecution() throws {
        let tool = try JSONDecoder().decode(AgentTool.self, from: Data(#"{"name":"example","inputSchema":{"type":"object","required":["query"],"properties":{"query":{"type":"string"}}}}"#.utf8))
        XCTAssertTrue(tool.inputSchema?.formatted.contains("query") == true)
    }
}
