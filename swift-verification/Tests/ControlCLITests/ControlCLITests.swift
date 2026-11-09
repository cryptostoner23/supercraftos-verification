import Foundation
import XCTest

final class ControlCLITests: XCTestCase {
    private func invoke(_ operation: String, _ input: String) throws -> (Int32, Data) {
        let process = Process()
        let binary: URL
        if let configured = ProcessInfo.processInfo.environment["SUPERCRAFTOS_CLI_BINARY"], !configured.isEmpty {
            binary = URL(fileURLWithPath: configured)
        } else {
            binary = URL(fileURLWithPath: CommandLine.arguments[0]).deletingLastPathComponent().appendingPathComponent("supercraftos-check")
        }
        process.executableURL = binary
        let stdin = Pipe(); let stdout = Pipe(); let stderr = Pipe()
        process.standardInput = stdin; process.standardOutput = stdout; process.standardError = stderr
        try process.run()
        stdin.fileHandleForWriting.write(try JSONSerialization.data(withJSONObject: ["operation": operation, "input": input]))
        try stdin.fileHandleForWriting.close()
        let output = stdout.fileHandleForReading.readDataToEndOfFile()
        process.waitUntilExit()
        return (process.terminationStatus, output)
    }

    func testJSONThroughCLI() throws {
        let (status, data) = try invoke("json", "{\"b\":2,\"a\":1}")
        XCTAssertEqual(status, 0)
        let response = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: String])
        let output = try XCTUnwrap(response["output"])
        XCTAssertTrue(output.firstIndex(of: "a")! < output.firstIndex(of: "b")!)
    }

    func testUnicodeThroughCLI() throws {
        let (encodedStatus, data) = try invoke("encode", "iPad ✓")
        XCTAssertEqual(encodedStatus, 0)
        let response = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: String])
        let (decodedStatus, decoded) = try invoke("decode", try XCTUnwrap(response["output"]))
        XCTAssertEqual(decodedStatus, 0)
        let decodedResponse = try XCTUnwrap(JSONSerialization.jsonObject(with: decoded) as? [String: String])
        XCTAssertEqual(decodedResponse["output"], "iPad ✓")
    }

    func testInvalidInputThroughCLI() throws {
        XCTAssertNotEqual(try invoke("json", "{").0, 0)
        XCTAssertNotEqual(try invoke("decode", "%%%").0, 0)
        XCTAssertNotEqual(try invoke("invalid", "x").0, 0)
    }
}
