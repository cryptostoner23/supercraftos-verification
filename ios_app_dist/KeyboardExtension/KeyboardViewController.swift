import UIKit
import SwiftUI

// UIInputViewController host for the SwiftUI keyboard.
final class KeyboardViewController: UIInputViewController {

    private var hostingController: UIHostingController<KeyboardRootView>?
    private var heightConstraint: NSLayoutConstraint?
    private let backend = KeyboardBackend()

    override func viewDidLoad() {
        super.viewDidLoad()

        view.backgroundColor = UIColor(red: 0.110, green: 0.110, blue: 0.118, alpha: 1.0)

        let root = KeyboardRootView(
            backend: backend,
            context: { [weak self] in self?.documentContext() ?? "" },
            insert: { [weak self] text in self?.textDocumentProxy.insertText(text) },
            open: { [weak self] url in self?.openURL(url) },
            copy: { text in UIPasteboard.general.string = text },
            paste: { UIPasteboard.general.string },
            onGlobe: { [weak self] in self?.advanceToNextInputMode() }
        )
        let host = UIHostingController(rootView: root)
        addChild(host)
        host.view.translatesAutoresizingMaskIntoConstraints = false
        host.view.backgroundColor = .clear
        view.addSubview(host.view)
        NSLayoutConstraint.activate([
            host.view.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            host.view.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            host.view.topAnchor.constraint(equalTo: view.topAnchor),
            host.view.bottomAnchor.constraint(equalTo: view.bottomAnchor)
        ])
        host.didMove(toParent: self)
        hostingController = host

        let constraint = view.heightAnchor.constraint(equalToConstant: 320)
        constraint.priority = UILayoutPriority(999)
        constraint.isActive = true
        heightConstraint = constraint
    }

    override func viewWillLayoutSubviews() {
        super.viewWillLayoutSubviews()
        hostingController?.view.setNeedsLayout()
    }

    /// The text around the insertion point, used as the context for every action.
    private func documentContext() -> String {
        let before = textDocumentProxy.documentContextBeforeInput ?? ""
        let after = textDocumentProxy.documentContextAfterInput ?? ""
        return (before + after).trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private func openURL(_ url: URL) {
        extensionContext?.open(url, completionHandler: nil)
    }
}
