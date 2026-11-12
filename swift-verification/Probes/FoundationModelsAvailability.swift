// Compile probe: proves the toolchain SDK exposes a usable FoundationModels API.
// This file is never linked into a shipping target. It is type checked on the
// CI macOS stack against the simulator SDK.
import Foundation
import FoundationModels

@available(iOS 26.0, *)
func probeFoundationModelsAvailability() {
    let model = SystemLanguageModel.default
    _ = model.availability
}
