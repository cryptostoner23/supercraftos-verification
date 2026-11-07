import UIKit
import Social
import UniformTypeIdentifiers

/// "Save to SuperCraftOS" share extension.
///
/// Receives text shared from Apple Notes (share sheet) and sends it to the
/// SuperCraftOS backend ingest endpoint (/api/notes/ingest), where it is stored
/// encrypted and summarized into Digital Me memory.
///
/// Networking and credential handling reuse the same BackendClient and
/// CredentialStore sources as the main app. The extension looks up the access
/// key for the configured origin in the Keychain; if it is not present (for
/// example because the app and extension do not share a Keychain access group),
/// the user should configure it so the extension can authenticate.
final class ShareViewController: SLComposeServiceViewController {

    private var backendURL = "https://agent.commetai.ca"
    private var client: BackendClient?

    override func viewDidLoad() {
        super.viewDidLoad()
        if let configured = Bundle.main.object(forInfoDictionaryKey: "SUPERCRAFTOS_BACKEND_URL") as? String,
           !configured.isEmpty, !configured.contains("$(") {
            backendURL = configured
        }
        // Reuse the app's Keychain credential for this origin if one exists.
        if let origin = try? BackendConnection(address: backendURL).origin,
           let key = CredentialStore.load(origin: origin),
           let connection = try? BackendConnection(address: origin, accessKey: key) {
            client = BackendClient(connection: connection)
        }
        placeholder = "Confirm note text…"
    }

    override func isContentValid() -> Bool {
        !contentText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    override func didSelectPost() {
        let text = contentText ?? ""
        guard let client, !text.isEmpty else {
            finish()
            return
        }
        let firstLine = text.split(separator: "\n").first.map(String.init) ?? ""
        let title = String(firstLine.prefix(200)).trimmingCharacters(in: .whitespacesAndNewlines)
        let body: [String: String] = [
            "title": title.isEmpty ? "Imported Apple Note" : title,
            "body": text,
            "format": "text",
            "source": "apple_notes",
            "notebook": "Apple Notes",
        ]
        guard let payload = try? JSONEncoder().encode(body) else {
            finish()
            return
        }
        Task {
            do {
                _ = try await client.data("/api/notes/ingest", body: payload)
            } catch {
                // Surface nothing more than a failed send; the user can retry
                // from the Notes screen import button.
            }
            finish()
        }
    }

    private func finish() {
        extensionContext?.completeRequest(returningItems: nil) { _ in }
    }
}
