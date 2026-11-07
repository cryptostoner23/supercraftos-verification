#if DEBUG
import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

/// Hermetic HTTP transport used only by debug tests. Unknown requests fail closed;
/// this protocol never forwards traffic to DNS, a gateway, a model or a worker.
enum CIBackendFixture {
    static let origin = "https://fixture.supercraftos.test"
    static let accessKey = "fixture-access-key"
    static let workflowID = "fixture-workflow"
    static let jobID = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    private static let lock = NSLock()
    private static var submittedJobs: [[String: Any]] = []
    private static var submittedWorkflows: [[String: Any]] = []

    static func makeClient(accessKey: String = CIBackendFixture.accessKey) -> BackendClient {
        lock.lock(); submittedJobs = []; submittedWorkflows = []; lock.unlock()
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [CIBackendProtocol.self]
        return BackendClient(connection: try! BackendConnection(address: origin, accessKey: accessKey),
                             session: URLSession(configuration: configuration))
    }

    static func reply(to request: URLRequest) throws -> (Int, Data) {
        lock.lock(); defer { lock.unlock() }
        func json(_ status: Int, _ value: Any) throws -> (Int, Data) {
            (status, try JSONSerialization.data(withJSONObject: value, options: [.sortedKeys]))
        }
        guard request.url?.host == "fixture.supercraftos.test" else {
            throw URLError(.unsupportedURL)
        }
        guard request.value(forHTTPHeaderField: "Authorization") == "Bearer " + accessKey else {
            return try json(401, ["error": "authentication_required"])
        }
        let path = request.url!.path
        let method = request.httpMethod ?? "GET"
        if method == "POST", request.value(forHTTPHeaderField: "X-SuperCraftOS-Token") != "fixture-session" {
            return try json(403, ["error": "invalid_control_token"])
        }
        let workflow: [String: Any] = ["thread_id": workflowID, "query": "Fixture workflow ready for review",
            "status": "completed", "plan": "Inspect the fixture", "artifact": "Fixture workflow output"]
        let initialJob: [String: Any] = ["id": jobID, "query": "Fixture completed task", "status": "completed",
            "created": 1, "run_at": 1, "steps": 1, "max_steps": 24,
            "result": ["summary": "Fixture task complete", "files": [], "checks": [], "review": ["accepted": true],
                       "native_evidence": [["name": "screen_product_design", "result": ["readiness": "prototype_candidate"]]]]]
        if method == "GET" {
            switch path {
            case "/api/session": return try json(200, ["token": "fixture-session"])
            case "/api/status": return try json(200, ["runtime": "running", "tools": 1, "integrations": 1,
                "healthy_integrations": 1, "workflows": 1, "awaiting_approval": 0, "memory_mb": 64, "memory_limit_mb": 512])
            case "/api/tools": return try json(200, ["tools": [["name": "fixture_tool", "description": "Local test tool", "inputSchema": ["type": "object", "properties": [:]]]]])
            case "/api/tools/call": return try json(200, ["jsonrpc": "2.0", "id": 1, "result": ["content": [["type": "text", "text": "Fixture tool completed"]]]])
            case "/api/jobs/" + jobID + "/trace": return try json(200, ["timeline": [["id": 1, "at": 1, "kind": "completed", "label": "Task completed", "outcome": "completed"]], "next_cursor": 1])
            case "/api/workflows": return try json(200, ["workflows": submittedWorkflows + [workflow]])
            case "/api/integrations": return try json(200, ["integrations": [["name": "Fixture", "status": "verified", "latency_ms": 1]]])
            case "/api/registrations": return try json(200, ["registrations": [["name": "Fixture", "status": "verified"]]])
            case "/api/accounts": return try json(200, ["providers": [["id": "fixture", "name": "Fixture", "status": "verified",
                "reason": "Fixture account", "credential_verified": true, "credential_present": true]]])
            case "/api/capabilities": return try json(200, ["capabilities": [["id": "fixture", "name": "Fixture engine",
                "features": "Local tests", "enabled": true, "runs": 1, "successes": 1, "routing_score": 1]]])
            case "/api/grants/catalog": return try json(200, ["programs": [["id": "fixture", "name": "Fixture grant",
                "chain": "test", "official_url": "https://example.test", "application_url": "https://example.test/apply",
                "payment": "test", "cadence": "test", "topics": ["testing"], "evidence": "fixture"]]])
            case "/api/grants/packages": return try json(200, ["packages": [["id": "fixture-grant-record", "title": "Fixture application", "programme": "Fixture programme", "budget_usd": 7500, "status": "submitted", "submission": ["status": "submitted", "receipt": ["provider_confirmation": "Fixture provider accepted the application."]]]]])
            case "/api/jobs": return try json(200, ["jobs": submittedJobs + [initialJob]])
            case "/api/agent/status": return try json(200, ["workers": 2, "model_configured": true, "sandbox_cli_available": true])
            case "/api/agent/memory": return try json(200, ["mode": "verified", "description": "Fixture execution memory", "playbooks": [], "lessons": []])
            case "/api/quests/sources": return try json(200, ["sources": [["id": "fixture", "name": "Fixture quests",
                "url": "https://example.test", "kind": "test", "provider": "fixture"]]])
            case "/api/jobs/" + jobID + "/events": return try json(200, ["events": [["id": 1, "at": 1, "kind": "completed", "detail": ["summary": "Fixture completed"]]]])
            default: return try json(404, ["error": "fixture_route_missing", "detail": method + " " + path])
            }
        }
        let bodyData: Data
        if let data = request.httpBody { bodyData = data }
        else if let stream = request.httpBodyStream {
            stream.open(); defer { stream.close() }
            var buffer = [UInt8](repeating: 0, count: 4096); var data = Data()
            while stream.hasBytesAvailable {
                let count = stream.read(&buffer, maxLength: buffer.count)
                if count <= 0 { break }; data.append(contentsOf: buffer.prefix(count))
            }
            bodyData = data
        } else { bodyData = Data("{}".utf8) }
        let body = (try JSONSerialization.jsonObject(with: bodyData)) as? [String: Any] ?? [:]
        switch path {
        case "/api/jobs":
            guard request.value(forHTTPHeaderField: "Idempotency-Key")?.isEmpty == false else {
                return try json(400, ["error": "missing_idempotency_key"])
            }
            var job = initialJob
            job["id"] = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"; job["query"] = body["query"] ?? ""; job["status"] = "queued"
            job["max_steps"] = body["max_steps"] ?? 24; job["steps"] = 0; job["result"] = [String: String]()
            submittedJobs = [job]
            return try json(200, job)
        case "/api/workflows":
            var reply = workflow; reply["thread_id"] = "fixture-submitted-workflow"; reply["query"] = body["query"] ?? ""
            submittedWorkflows = [reply]
            return try json(200, reply)
        case "/api/products/interpret":
            return try json(200, ["name": "Fixture enclosure", "idea": body["idea"] ?? "", "template": "enclosure",
                "width_mm": 100, "depth_mm": 70, "height_mm": 35, "wall_mm": 3, "hole_mm": 0,
                "material": "PLA", "process": "FDM", "load_n": 0])
        case "/api/quests/discover": return try json(200, ["leads": [], "errors": [], "checked_at": 1])
        case "/api/quests/screen", "/api/quests/run": return try json(200, ["results": []])
        case "/api/agent/memory/forget": return try json(200, ["ok": true])
        default: return try json(404, ["error": "fixture_route_missing", "detail": method + " " + path])
        }
    }
}

private final class CIBackendProtocol: URLProtocol {
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        do {
            let (status, data) = try CIBackendFixture.reply(to: request)
            let response = HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: "HTTP/1.1",
                                           headerFields: ["Content-Type": "application/json"])!
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        } catch { client?.urlProtocol(self, didFailWithError: error) }
    }
    override func stopLoading() {}
}
#endif
