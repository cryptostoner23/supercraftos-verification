import Foundation
import XCTest
@testable import SuperCraftOS

/// Decodes authenticated HTTP fixtures with the app’s models on an iOS runtime.
/// The separate live workflow opts into the same GET contract checks.
///
/// The Python contract test checks the same contract from the server side.
/// This one proves the Swift side of it: that the models in AppConfig.swift
/// decode the endpoint payloads used by the native client.
final class LiveBackendContractTests: XCTestCase {

    private struct ToolsReply: Decodable { let tools: [AgentTool] }
    private struct WorkflowsReply: Decodable { let workflows: [AgentWorkflow] }
    private struct IntegrationsReply: Decodable { let integrations: [IntegrationHealth] }
    private struct RegistrationsReply: Decodable { let registrations: [RegistrationOutcome] }
    private struct CapabilitiesReply: Decodable { let capabilities: [EngineCapability] }
    private struct GrantCatalogReply: Decodable { let programs: [GrantOpportunity] }
    private struct QuestSourcesReply: Decodable { let sources: [QuestSource] }
    private struct ControlSession: Decodable { let token: String }

    private var backend: BackendClient!

    override func setUp() async throws {
        try await super.setUp()
        backend = try BackendTestConfiguration.client()
    }

    private func get(_ path: String) async throws -> Data {
        try await backend.data(path)
    }

    private func post(_ path: String, _ body: [String: Any]) async throws -> Data {
        try await backend.data(path, body: JSONSerialization.data(withJSONObject: body))
    }

    func testRuntimeStatusDecodes() async throws {
        let status = try JSONDecoder().decode(RuntimeStatus.self, from: try await get("/api/status"))
        XCTAssertGreaterThanOrEqual(status.memoryLimitMB, 0)
        XCTAssertGreaterThanOrEqual(status.tools, 0)
    }

    func testToolsDecode() async throws {
        let reply = try JSONDecoder().decode(ToolsReply.self, from: try await get("/api/tools"))
        XCTAssertFalse(reply.tools.isEmpty)
    }

    func testWorkflowsDecode() async throws {
        let reply = try JSONDecoder().decode(WorkflowsReply.self, from: try await get("/api/workflows"))
        for workflow in reply.workflows {
            XCTAssertFalse(workflow.threadID.isEmpty)
        }
    }

    func testIntegrationsDecode() async throws {
        let reply = try JSONDecoder().decode(IntegrationsReply.self, from: try await get("/api/integrations"))
        XCTAssertFalse(reply.integrations.isEmpty)
    }

    func testRegistrationsDecode() async throws {
        let reply = try JSONDecoder().decode(RegistrationsReply.self, from: try await get("/api/registrations"))
        XCTAssertFalse(reply.registrations.isEmpty)
    }

    func testCapabilitiesDecode() async throws {
        let reply = try JSONDecoder().decode(CapabilitiesReply.self, from: try await get("/api/capabilities"))
        XCTAssertFalse(reply.capabilities.isEmpty)
    }

    func testGrantCatalogDecodes() async throws {
        let reply = try JSONDecoder().decode(GrantCatalogReply.self, from: try await get("/api/grants/catalog"))
        XCTAssertFalse(reply.programs.isEmpty)
        for program in reply.programs {
            XCTAssertFalse(program.name.isEmpty)
            XCTAssertFalse(program.topics.isEmpty)
        }
    }

    func testQuestSourcesDecode() async throws {
        let reply = try JSONDecoder().decode(QuestSourcesReply.self, from: try await get("/api/quests/sources"))
        XCTAssertFalse(reply.sources.isEmpty)
    }

    func testAgentWorkflowReplyDecodes() async throws {
        let data = try await post("/api/workflows", ["query": "Contract check: reply with the word READY"])
        let result = try JSONDecoder().decode(AgentWorkflow.self, from: data)
        XCTAssertFalse(result.threadID.isEmpty)
    }

    func testProductSpecReplyDecodes() async throws {
        let data = try await post("/api/products/interpret", ["idea": "A small enclosure for a sensor"])
        let spec = try JSONDecoder().decode(ProductSpec.self, from: data)
        XCTAssertFalse(spec.name.isEmpty)
        XCTAssertTrue(["enclosure", "plate", "bracket"].contains(spec.template))
    }
}
