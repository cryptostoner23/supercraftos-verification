import XCTest

final class Concept6UITests: XCTestCase {
    private func snap(_ name: String, _ app: XCUIApplication) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    func testTabsAndNavigation() {
        let app = XCUIApplication()
        app.launch()
        for tab in ["Mission", "Tasks", "Me", "Lab", "More"] {
            XCTAssertTrue(app.tabBars.buttons[tab].waitForExistence(timeout: 8), "tab \(tab) missing")
        }
        snap("mission", app)

        app.tabBars.buttons["Tasks"].tap()
        XCTAssertTrue(app.navigationBars["Tasks"].waitForExistence(timeout: 5), "Tasks did not open")
        sleep(2)
        snap("tasks", app)

        let anyRow = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", " ")).firstMatch
        if anyRow.waitForExistence(timeout: 5) {
            anyRow.tap()
            sleep(1)
            snap("task-detail", app)
        }

        app.tabBars.buttons["Me"].tap()
        sleep(2)
        snap("digital-me", app)

        app.tabBars.buttons["Lab"].tap()
        sleep(2)
        snap("lab", app)

        app.tabBars.buttons["More"].tap()
        sleep(1)
        snap("more", app)

        app.tabBars.buttons["Mission"].tap()
        XCTAssertTrue(app.buttons["New autonomous task"].waitForExistence(timeout: 5))
    }
}
