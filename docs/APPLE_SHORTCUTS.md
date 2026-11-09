# Apple Shortcuts

The native iOS 17 app includes four App Intents: Open Workspace, Send Agent Task,
Check Task, and Get Task Output. The Shortcuts page contains Apple’s ShortcutsLink.
After installation, iOS exposes the actions in Shortcuts; users compose or edit
personal automations there. This is not a silent installer for arbitrary workflows.

Save a working HTTPS backend and access key in the app’s Connection settings first.
Actions use that connection and its device-only Keychain credential. The device
must be unlocked to access the key. Credentials are not embedded in a shortcut.

- Notes: Find Notes → Get Text → Send Task. Map note text to Shared Content and put
  the instruction in Task. Only explicitly supplied text is sent to the backend.
- Sites: a Share Sheet shortcut receives URLs; map Shortcut Input to Shared Content.
  Use Get Contents of URL when the task needs downloaded content rather than a URL.
- Databases: use the database app’s action or its authenticated HTTPS API action,
  then pass selected output as Shared Content. This does not automatically grant
  database access to the agent. Configure service credentials in the appropriate
  app/server connection; do not paste secrets into task instructions.
- Results: Send Task returns the tracking ID immediately. Store that ID, then run
  Check Task. Once completed, Get Task Output returns a text file with the summary
  and file list. Get Text from Input → Append to Note saves the summary. Set File
  Path to a listed path to download that artifact, then Save File. Artifacts are
  checked against the completion receipt’s byte count and SHA-256.

Every Send Task invocation creates one new logical task. A control-session refresh
keeps the same idempotency key. On an uncertain network error, inspect Tasks before
invoking Send Task again. Long-running jobs continue on the server; iOS is not held
open waiting for execution. Pending/failed/blocked jobs are not reported as completed
output. Shortcuts can schedule a later status check without sending another task.

Validation boundary: source packaging and Linux Swift parsing/core tests can run in
this workspace. App Intents metadata, Apple SDK type checking, Siri discovery,
ShortcutsLink navigation, Notes/Files chaining, and device Keychain behavior require
an Apple build and device test. Those checks have not been completed here.

References: [App Shortcuts](https://developer.apple.com/documentation/appintents/app-shortcuts),
[ShortcutsLink](https://developer.apple.com/documentation/appintents/shortcutslink),
[IntentFile](https://developer.apple.com/documentation/appintents/intentfile).
