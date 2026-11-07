import Foundation
import ControlCore

do {
    let input = FileHandle.standardInput.readDataToEndOfFile()
    let request = try JSONSerialization.jsonObject(with: input) as? [String: String]
    guard let request, let operation = request["operation"], let text = request["input"] else {
        throw NSError(domain: "ControlCLI", code: 1, userInfo: [NSLocalizedDescriptionKey: "Expected operation and input strings"])
    }
    let output = try UtilityGateway.run(operation: operation, input: text)
    let result = try JSONSerialization.data(withJSONObject: ["output": output], options: [.sortedKeys])
    print(String(decoding: result, as: UTF8.self))
} catch {
    let data = try JSONSerialization.data(withJSONObject: ["error": error.localizedDescription])
    FileHandle.standardError.write(data)
    exit(1)
}
