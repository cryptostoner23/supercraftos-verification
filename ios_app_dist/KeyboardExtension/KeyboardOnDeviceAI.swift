import Foundation
#if canImport(FoundationModels)
import FoundationModels
#endif

/// On-device text transformation using Apple's Foundation Models framework.
///
/// This is the offline path. When the SuperCraftOS agent cannot be reached,
/// the keyboard still rewrites, fixes and explains text on the device, with no
/// network and no account. It requires a device that supports Apple
/// Intelligence; the availability check reports that honestly.
enum KeyboardOnDeviceAI {

    enum Failure: LocalizedError {
        case unsupportedDevice
        case noReply

        var errorDescription: String? {
            switch self {
            case .unsupportedDevice:
                return "On-device AI is not available on this device."
            case .noReply:
                return "The on-device model returned no usable reply."
            }
        }
    }

    /// Whether the device can run the on-device language model.
    static var isAvailable: Bool {
        #if canImport(FoundationModels)
        if #available(iOS 26.0, *) {
            if case .available = SystemLanguageModel.default.availability { return true }
        }
        #endif
        return false
    }

    /// Rewrites text on the device using the on-device language model.
    static func transform(_ text: String, instruction: String) async throws -> String {
        #if canImport(FoundationModels)
        if #available(iOS 26.0, *) {
            guard isAvailable else { throw Failure.unsupportedDevice }
            let session = LanguageModelSession()
            let response = try await session.respond(to: "\(instruction)\n\n\(text)")
            let content = response.content.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !content.isEmpty else { throw Failure.noReply }
            return content
        }
        #endif
        throw Failure.unsupportedDevice
    }
}
