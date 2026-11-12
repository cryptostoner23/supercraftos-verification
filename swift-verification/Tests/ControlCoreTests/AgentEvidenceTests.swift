import XCTest
import Foundation
@testable import ControlCore

final class AgentEvidenceTests: XCTestCase {
    func testToolOnlyCompletionRetainsProviderEvidence() throws {
        let data = Data(#"{"summary":"Screened a bracket","native_evidence":[{"name":"screen_product_design","result":{"readiness":"prototype_candidate","checks":[{"status":"pass"}]}}],"review":{"accepted":true,"issues":[]}}"#.utf8)
        let result = try JSONDecoder().decode(AgentResult.self, from: data)
        XCTAssertNil(result.files)
        XCTAssertEqual(result.nativeEvidence?.count, 1)
        XCTAssertEqual(result.nativeEvidence?.first?.name, "screen_product_design")
        XCTAssertTrue(result.nativeEvidence?.first?.result.formatted.contains("prototype_candidate") == true)
        XCTAssertEqual(result.review?.accepted, true)
    }

    func testCodeCompletionWithoutNativeEvidenceStillDecodes() throws {
        let data = Data(#"{"summary":"Built utility","files":[],"checks":[{"command":"python -m unittest","exit_code":0,"output":"OK"}]}"#.utf8)
        let result = try JSONDecoder().decode(AgentResult.self, from: data)
        XCTAssertNil(result.nativeEvidence)
        XCTAssertEqual(result.checks?.first?.exitCode, 0)
    }

    func testUnsuccessfulToolPayloadIsRetainedWithoutInventedSuccess() throws {
        let data = Data(#"{"native_evidence":[{"name":"submit_grant_application","result":{"status":"unsupported","error":"Authentication required"}}]}"#.utf8)
        let result = try JSONDecoder().decode(AgentResult.self, from: data)
        XCTAssertTrue(result.nativeEvidence?.first?.result.formatted.contains("unsupported") == true)
        XCTAssertNil(result.review)
    }
}

final class SavedGrantReceiptTests: XCTestCase {
    func testProviderConfirmationSurvivesDecodeAndExportWithoutAnInventedReceiptID() throws {
        let data = Data(#"{"packages":[{"id":"application-1","title":"Public fixtures","programme":"Foundation","budget_usd":7500,"status":"submitted","submission":{"status":"submitted","receipt":{"provider_confirmation":"Your response has been submitted.","provider_receipt_id":null}}}]}"#.utf8)
        let response = try JSONDecoder().decode(SavedGrantApplicationsResponse.self, from: data)
        let application = try XCTUnwrap(response.packages.first)
        XCTAssertEqual(application.status, "submitted")
        XCTAssertTrue(application.recordJSON.contains("Your response has been submitted."))
        XCTAssertTrue(application.recordJSON.contains("null"))
        XCTAssertFalse(application.recordJSON.contains("contact_email"))
    }
}
