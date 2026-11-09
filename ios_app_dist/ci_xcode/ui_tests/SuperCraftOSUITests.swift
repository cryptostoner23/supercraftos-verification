import XCTest

/// Drives the shipped SwiftUI screens with a deterministic, authenticated HTTP
/// fixture in a Debug build. No test launches a live model or changes agent state.
final class SuperCraftOSUITests: XCTestCase {
    private var app: XCUIApplication!

    override func setUp() {
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchEnvironment["SUPERCRAFTOS_UI_FIXTURES"] = "1"
        app.launch()
    }

    override func tearDown() {
        app.terminate()
        app = nil
        super.tearDown()
    }

    private func waitUntilGone(_ element: XCUIElement, timeout: TimeInterval) -> Bool {
        XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: element)], timeout: timeout) == .completed
    }

    private func openScreen(_ title: String) {
        let button = app.buttons["navigation-" + title]
        _ = button.waitForExistence(timeout: 5)
        if !button.exists && app.buttons["navigation-more"].exists {
            app.buttons["navigation-more"].tap()
            let menuItem = app.buttons[title]
            XCTAssertTrue(menuItem.waitForExistence(timeout: 5), "\(title) is missing from More")
            menuItem.tap()
            return
        }
        let sidebar = app.scrollViews["sidebar-navigation"]
        let compact = app.scrollViews["compact-navigation"]
        // Reach either end before reversing, so every destination remains usable
        // on small iPads and iPhones as the navigation catalog grows.
        for _ in 0..<8 where !button.isHittable {
            if sidebar.exists { sidebar.swipeUp() } else { compact.swipeLeft() }
        }
        for _ in 0..<8 where !button.isHittable {
            if sidebar.exists { sidebar.swipeDown() } else { compact.swipeRight() }
        }
        XCTAssertTrue(button.isHittable, "\(title) is unreachable")
        button.tap()
    }

    func testEveryScreenOpens() {
        for title in ["Mission", "Tasks", "Memory", "Quests", "Product Lab", "Engine", "Grant Ops",
                      "Workflows", "Integrations", "Tools", "Accounts", "Shortcuts"] {
            openScreen(title)
            let heading = title == "Mission" ? "Mission stream" : title
            XCTAssertTrue(app.staticTexts[heading].waitForExistence(timeout: 10), "\(title) content did not open")
        }
    }

    func testTheLiveRuntimeReachesTheScreen() {
        XCTAssertTrue(app.staticTexts["2 WORKERS ONLINE"].waitForExistence(timeout: 15))
        XCTAssertFalse(app.staticTexts["OFFLINE"].exists)
    }

    func testEveryVisualisationModeSwitches() {
        openScreen("Mission")
        if app.buttons["navigation-more"].exists {
            XCTAssertTrue(app.buttons["mission-action-Product Lab"].waitForExistence(timeout: 10))
            XCTAssertTrue(app.buttons["mission-action-Grant Ops"].exists)
            return
        }
        let diagnostics = app.buttons["mission-diagnostics"]
        XCTAssertTrue(diagnostics.waitForExistence(timeout: 10))
        diagnostics.tap()
        for mode in ["WIRING", "CONSTELLATION", "VORTEX", "LATTICE"] {
            let button = app.buttons[mode]
            XCTAssertTrue(button.waitForExistence(timeout: 10), "the \(mode) mode is missing")
            button.tap()
            XCTAssertTrue(button.exists, "the \(mode) mode vanished after the tap")
        }
    }

    func testARequestReachesTheAgent() {
        openScreen("Mission")
        let newTask = app.buttons["New autonomous task"]
        XCTAssertTrue(newTask.waitForExistence(timeout: 10))
        newTask.tap()
        let field = app.textViews["Autonomous task request"]
        XCTAssertTrue(field.waitForExistence(timeout: 10))
        let query = "Reply with the single word: ready."
        field.tap(); field.typeText(query)
        XCTAssertTrue((field.value as? String)?.contains(query) == true)
        let run = app.buttons["START AUTONOMOUS TASK"]
        XCTAssertTrue(run.isEnabled)
        run.tap()
        XCTAssertTrue(waitUntilGone(app.buttons["Close"], timeout: 15), "task was not accepted")
        openScreen("Tasks")
        XCTAssertTrue(app.staticTexts[query].waitForExistence(timeout: 10), "the submitted task never reached the task list")
    }

    func testTheConnectionSheetShowsTheLiveAddress() {
        let settings = app.buttons["Connection settings"]
        XCTAssertTrue(settings.waitForExistence(timeout: 10))
        settings.tap()
        let address = app.textFields["Private access link or HTTPS address"]
        XCTAssertTrue(address.waitForExistence(timeout: 10))
        XCTAssertEqual(address.value as? String, "https://fixture.supercraftos.test")
        XCTAssertTrue(app.secureTextFields["Access key (if not included in the link)"].exists)
        app.buttons["Close"].tap()
    }

    func testTheWorkflowListOpensAWorkflow() {
        openScreen("Workflows")
        let row = app.buttons.matching(identifier: "workflow-row").firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 15), "workflow data never reached the list")
        for _ in 0..<5 where !row.isHittable { app.scrollViews["workspace-scroll"].swipeUp() }
        XCTAssertTrue(row.isHittable, "the workflow row cannot be tapped")
        row.tap()
        let detail = app.staticTexts["workflow-detail-query"]
        XCTAssertTrue(detail.waitForExistence(timeout: 10), "tapping the row did not open its detail sheet")
        XCTAssertEqual(detail.label, "Fixture workflow ready for review")
        XCTAssertTrue(app.staticTexts["Fixture workflow output"].exists, "the workflow artifact is missing")
        app.buttons["Done"].tap()
        XCTAssertTrue(waitUntilGone(detail, timeout: 10), "the workflow detail did not close")
    }

    func testMissionOpensTheSelectedTaskDirectly() {
        openScreen("Mission")
        XCTAssertTrue(app.staticTexts["2 WORKERS ONLINE"].waitForExistence(timeout: 10))
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = "Mission workspace"
        attachment.lifetime = .keepAlways
        add(attachment)
        let mission = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "mission-row-")).firstMatch
        for _ in 0..<6 where !mission.isHittable { app.swipeUp() }
        XCTAssertTrue(mission.waitForExistence(timeout: 10))
        mission.tap()
        XCTAssertTrue(app.staticTexts["Fixture task complete"].waitForExistence(timeout: 10))
        app.buttons["Done"].tap()
    }

    func testTaskSearchAndToolEvidenceAreUsable() {
        openScreen("Tasks")
        let search = app.textFields["task-search"]
        XCTAssertTrue(search.waitForExistence(timeout: 10))
        search.tap()
        search.typeText("Fixture completed task")
        let row = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "task-row-")).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 10))
        if app.keyboards.count > 0 { app.swipeDown() }
        for _ in 0..<4 where !row.isHittable { app.scrollViews["workspace-scroll"].swipeUp() }
        row.tap()
        XCTAssertTrue(app.staticTexts["Fixture task complete"].waitForExistence(timeout: 10))
        let evidence = app.buttons["screen product design"]
        for _ in 0..<4 where !evidence.isHittable { app.swipeUp() }
        XCTAssertTrue(evidence.exists)
        evidence.tap()
        XCTAssertTrue(app.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", "prototype_candidate")).firstMatch.waitForExistence(timeout: 10))
        app.buttons["Done"].tap()
    }

    func testSavedGrantShowsTheProviderConfirmation() {
        openScreen("Grant Ops")
        let application = app.staticTexts["Fixture application"]
        for _ in 0..<8 where !application.isHittable { app.scrollViews["workspace-scroll"].swipeUp() }
        XCTAssertTrue(application.waitForExistence(timeout: 10))
        let confirmation = app.buttons["grant-provider-confirmation"].firstMatch
        for _ in 0..<4 where !confirmation.isHittable { app.scrollViews["workspace-scroll"].swipeUp() }
        XCTAssertTrue(confirmation.exists)
        confirmation.tap()
        XCTAssertTrue(app.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", "Fixture provider accepted")).firstMatch.waitForExistence(timeout: 10))
        XCTAssertTrue(app.buttons["Export application record"].exists)
    }

    func testUnauthorizedGatewayShowsConnectionGuidance() {
        app.terminate()
        app.launchEnvironment["SUPERCRAFTOS_FIXTURE_AUTH_FAILURE"] = "1"
        app.launch()
        XCTAssertTrue(app.staticTexts["Connection needs a valid private access link or access key."].waitForExistence(timeout: 15))
        XCTAssertTrue(app.staticTexts["OFFLINE"].exists)
        XCTAssertTrue(app.buttons["Connect"].exists)
    }
}
