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

    // On iPhone the primary destinations are a fixed, non-scrolling HStack; all
    // other destinations live behind the "More" menu. There is no swipeable
    // compact-navigation ScrollView, so drive the real hierarchy directly.
    private let primaryTabs = ["Mission", "Tasks", "Grant Ops", "Product Lab"]

    private func openScreen(_ title: String) {
        if primaryTabs.contains(title) {
            let button = app.buttons["navigation-" + title]
            XCTAssertTrue(button.waitForExistence(timeout: 10), "\(title) tab is missing")
            button.tap()
            return
        }
        let more = app.buttons["navigation-more"]
        XCTAssertTrue(more.waitForExistence(timeout: 10), "navigation-more is missing")
        more.tap()
        let menuItem = app.buttons[title]
        XCTAssertTrue(menuItem.waitForExistence(timeout: 10), "\(title) is missing from More")
        menuItem.tap()
    }

    func testEveryScreenOpens() {
        for title in ["Mission", "Tasks", "Memory", "Quests", "Product Lab", "Engine", "Grant Ops",
                      "Workflows", "Integrations", "Tools", "Accounts", "Shortcuts"] {
            openScreen(title)
            let heading = title == "Mission" ? "mobile-mission" : title
            let element: XCUIElement = title == "Mission"
                ? app.buttons[heading]
                : app.staticTexts[heading]
            XCTAssertTrue(element.waitForExistence(timeout: 10), "\(title) content did not open")
        }
    }

    func testTheLiveRuntimeReachesTheScreen() {
        XCTAssertTrue(app.staticTexts["2 WORKERS ONLINE"].waitForExistence(timeout: 15))
        XCTAssertFalse(app.staticTexts["OFFLINE"].exists)
    }

    func testMissionWorkspaceIsInteractive() {
        openScreen("Mission")
        // The mission surface exposes the compose entry point and its sheet.
        let newTask = app.buttons["New autonomous task"]
        XCTAssertTrue(newTask.waitForExistence(timeout: 10))
        newTask.tap()
        XCTAssertTrue(app.textViews["Autonomous task request"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.buttons["START AUTONOMOUS TASK"].exists)
        app.buttons["Close"].tap()
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
        // Dismiss the keyboard so the action button is not covered.
        if app.keyboards.count > 0 { app.swipeDown() }
        // Wait for the run button to be hittable, then tap it directly (coordinate
        // taps are unreliable across simulator toolchains).
        let hittable = NSPredicate(format: "isHittable == true")
        let runExpectation = XCTNSPredicateExpectation(predicate: hittable, object: run)
        _ = XCTWaiter.wait(for: [runExpectation], timeout: 10)
        XCTAssertTrue(run.isHittable, "START AUTONOMOUS TASK is not tappable")
        run.tap()
        XCTAssertTrue(waitUntilGone(app.buttons["Close"], timeout: 20), "task was not accepted")
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

    func testTaskSearchAndDetailAreUsable() {
        openScreen("Tasks")
        let search = app.textFields["task-search"]
        XCTAssertTrue(search.waitForExistence(timeout: 10))
        search.tap()
        search.typeText("Fixture completed task")
        let row = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "task-row-")).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 15), "no task row appeared for the search")
        if app.keyboards.count > 0 { app.swipeDown() }
        for _ in 0..<6 where !row.isHittable { app.scrollViews["workspace-scroll"].swipeUp() }
        XCTAssertTrue(row.isHittable, "the searched task row is not reachable")
        row.tap()
        let done = app.buttons["Done"]
        XCTAssertTrue(done.waitForExistence(timeout: 20), "the task detail sheet did not open")
        done.tap()
    }

    func testSavedGrantShowsTheProviderConfirmation() {
        openScreen("Grant Ops")
        XCTAssertTrue(app.staticTexts["FUNDING RADAR"].waitForExistence(timeout: 12))
        // The saved-applications section sits deep below the fold; scroll to it.
        let title = app.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", "Fixture application")).firstMatch
        var foundTitle = title.waitForExistence(timeout: 5)
        var swipes = 0
        while !foundTitle && swipes < 30 {
            app.swipeUp()
            swipes += 1
            foundTitle = title.exists
        }
        XCTAssertTrue(foundTitle, "saved application did not appear")
        // "Provider confirmation" is a DisclosureTriangle (not a Button). Scroll
        // it into view, then tap it to reveal the confirmation receipt text.
        let disclosure = app.descendants(matching: .any)
            .matching(NSPredicate(format: "label == %@", "Provider confirmation")).firstMatch
        var foundDisclosure = disclosure.waitForExistence(timeout: 5)
        var swipes2 = 0
        while (!foundDisclosure || !disclosure.isHittable) && swipes2 < 12 {
            app.swipeUp()
            swipes2 += 1
            foundDisclosure = disclosure.exists
        }
        XCTAssertTrue(foundDisclosure && disclosure.isHittable, "provider confirmation disclosure not reachable")
        disclosure.tap()
        let receipt = app.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", "Fixture provider accepted")).firstMatch
        XCTAssertTrue(receipt.waitForExistence(timeout: 10), "provider confirmation text missing after expanding")
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
