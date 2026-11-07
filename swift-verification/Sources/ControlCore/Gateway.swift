import Foundation

public enum UtilityGateway {
    public static func run(operation: String, input: String) throws -> String {
        guard input.utf8.count <= 262144 else {
            throw NSError(domain: "ControlCLI", code: 2, userInfo: [NSLocalizedDescriptionKey: "Input exceeds 256 KiB"])
        }
        switch operation {
        case "json": return try LocalUtilities.formatJSON(input)
        case "encode": return LocalUtilities.encodeBase64(input)
        case "decode": return try LocalUtilities.decodeBase64(input)
        case "status":
            let status = try JSONDecoder().decode(RuntimeStatus.self, from: Data(input.utf8))
            return "runtime=\(status.runtime) tools=\(status.tools) workflows=\(status.workflows)"
        case "product-report":
            let report = try JSONDecoder().decode(ProductReport.self, from: Data(input.utf8))
            return "readiness=\(report.readiness) solid=\(report.geometry?.validSolid == true) step_roundtrip=\(report.geometry?.stepRoundtripValid == true)"
        default: throw NSError(domain: "ControlCLI", code: 3, userInfo: [NSLocalizedDescriptionKey: "Unknown operation"])
        }
    }
}
