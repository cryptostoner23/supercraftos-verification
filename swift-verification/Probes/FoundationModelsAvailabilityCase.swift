// Compile probe: records the exact shape of the model availability check, so
// the on-device AI path can be implemented without guessing the enum cases.
import Foundation
import FoundationModels

@available(iOS 26.0, *)
func probeFoundationModelsAvailabilityCase() -> Bool {
    if case .available = SystemLanguageModel.default.availability { return true }
    return false
}
