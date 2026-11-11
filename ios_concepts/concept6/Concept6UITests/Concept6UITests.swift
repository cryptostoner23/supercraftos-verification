import XCTest

final class Concept6UITests: XCTestCase {
    func testTabsAndNavigation() {
        let app = XCUIApplication()
        app.launch()
        for tab in ["Mission", "Tasks", "Me", "Lab", "More"] {
            XCTAssertTrue(app.tabBars.buttons[tab].waitForExistence(timeout: 5), "tab \(tab) missing")
        }
        app.tabBars.buttons["Tasks"].tap()
        XCTAssertTrue(app.navigationBars["Tasks"].waitForExistence(timeout: 5), "Tasks did not open")
        let firstRow = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", "Research funding routes")).firstMatch
        if firstRow.waitForExistence(timeout: 5) {
            firstRow.tap()
            XCTAssertTrue(app.navigationBars["Task detail"].waitForExistence(timeout: 5), "Task detail did not open")
        }
        app.tabBars.buttons["Mission"].tap()
        XCTAssertTrue(app.buttons["New autonomous task"].waitForExistence(timeout: 5))
    }
}
