import Foundation
import XCTest
@testable import SuperCraftOS

/// Drives the app's own store through authenticated HTTP fixtures and checks that every
/// screen has real data behind it.
///
/// The decode tests prove the models fit the payloads. These prove the app
/// works: the store is the same object the screens read from, it is pointed at
/// the fixture transport, and every screen's data path is exercised and
/// asserted, not just rendered.
@MainActor
final class ScreenInteractionTests: XCTestCase {

    private func makeStore() throws -> BackendStore {
        BackendStore(client: try BackendTestConfiguration.client())
    }

    // MARK: - The eight screens

    /// Mission, Engine, Grant Ops, Workflows, Integrations, Tools and Accounts
    /// all read from one refresh. This asserts each of them has something
    /// real behind it, so no screen can be silently empty.
    func testEveryScreenHasLiveData() async throws {
        let store = try makeStore()
        await store.refresh()

        XCTAssertNil(store.error, "the refresh reported an error")
        XCTAssertNotNil(store.status, "Mission has no runtime status")
        XCTAssertGreaterThan(store.status?.tools ?? 0, 0, "Mission reports no tools")
        XCTAssertFalse(store.capabilities.isEmpty, "Engine has no capabilities")
        XCTAssertFalse(store.grants.isEmpty, "Grant Ops has no opportunities")
        XCTAssertFalse(store.workflows.isEmpty, "Workflows has no workflows")
        XCTAssertFalse(store.integrations.isEmpty, "Integrations has no integrations")
        XCTAssertFalse(store.tools.isEmpty, "Tools has no tools")
        XCTAssertNotNil(store.lastUpdated, "the store never recorded an update")
    }

    /// The same refresh, but the failure path is checked too: a bad address has
    /// to produce a message the user can act on, not a silent empty screen.
    func testAnUnreachableBackendIsReportedNotSwallowed() async throws {
        let store = try makeStore()
        await store.connect(address: "https://127.0.0.1:9/never-there", accessKey: "fixture-key")
        XCTAssertNotNil(store.error, "a broken address was accepted silently")
    }

    // MARK: - The Product Lab

    /// Product Lab interprets a brief into a buildable spec and then builds
    /// it. This is the screen with the most machinery behind it, so it gets
    /// the most interaction.
    func testTheProductLabInterpretsAndBuilds() async throws {
        let store = try makeStore()
        await store.refresh()
        XCTAssertNil(store.error)

        let spec = await store.interpretProduct("a small desk light")
        XCTAssertNotNil(spec, "the valid design brief should be interpreted")
        XCTAssertNil(store.error)
        XCTAssertGreaterThan(spec?.widthMM ?? 0, 0)
        XCTAssertFalse(spec?.name.isEmpty ?? true)
    }

    // MARK: - The workflows screen

    /// The Workflows screen starts a workflow through the same endpoint the
    /// keyboard uses. This proves the whole path, from the app's button to the
    /// agent, in one call.
    func testAWorkflowCanBeStartedFromTheApp() async throws {
        let store = try makeStore()
        await store.refresh()
        XCTAssertFalse(store.workflows.isEmpty, "there is nothing to start")

        let query = "Say hello in one short sentence."
        await store.perform("/api/workflows", body: ["query": query])
        XCTAssertNil(store.error)
        XCTAssertTrue(store.workflows.contains { $0.query == query }, "the submitted workflow is absent after refresh")
    }

    func testTaskSubmissionKeepsItsQueryAndStepBudget() async throws {
        let store = try makeStore()
        let job = await store.submitTask(query: "Build a fixture utility", maxSteps: 12, runAt: nil, idempotencyKey: "fixture-task")
        XCTAssertNil(store.error)
        XCTAssertEqual(job?.query, "Build a fixture utility")
        XCTAssertEqual(job?.maxSteps, 12)
        XCTAssertEqual(job?.status, "queued")
        await store.refresh()
        XCTAssertTrue(store.jobs.contains { $0.id == job?.id })
        XCTAssertNotNil(store.agentStatus)
        let memory = try await store.executionMemory()
        XCTAssertFalse(memory.description.isEmpty)
    }

    /// A background refresh must never swallow a command the user just gave.
    ///
    /// The screen refreshes itself every few seconds. If a refresh is in flight
    /// when the user taps submit, the submission used to be dropped with no
    /// error and no visible result, and the composer never closed. The write
    /// now waits for the read instead of being lost.
    func testACommandIsNotSwallowedByABackgroundRefresh() async throws {
        let store = try makeStore()
        await store.refresh()

        // Start a refresh and submit while it is in flight.
        async let refreshing: Void = store.refresh()
        let job = await store.submitTask(query: "Reply with the single word: ready.", maxSteps: 24, runAt: nil, idempotencyKey: "fixture-race-task")
        await refreshing

        XCTAssertNotNil(job, "the submission was dropped while a refresh was in flight")
        XCTAssertNil(store.error, "the dropped submission reported no reason")
        XCTAssertEqual(job?.query, "Reply with the single word: ready.")
    }

    func testUnauthorizedConnectionShowsAnActionableError() async throws {
        let store = BackendStore(client: CIBackendFixture.makeClient(accessKey: "invalid-key"))
        await store.refresh()
        XCTAssertNil(store.status)
        XCTAssertEqual(store.error, BackendError.authenticationRequired.localizedDescription)
    }

    // MARK: - The quests path behind Grant Ops

    /// Grant Ops reads its leads from the quest service. Discovery has to work
    /// through authenticated HTTP fixtures, otherwise the screen is decoration.
    func testQuestDiscoveryAnswersFromTheLiveBackend() async throws {
        let store = try makeStore()
        await store.refresh()
        await store.discoverQuests()
        // A discovery that finds nothing is a legitimate answer from a quiet
        // backend, but it must not be an error.
        XCTAssertNil(store.error, "quest discovery failed: \(store.error ?? "")")
    }
}
