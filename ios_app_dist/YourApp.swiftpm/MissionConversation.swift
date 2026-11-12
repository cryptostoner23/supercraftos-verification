import SwiftUI

/// A request, observed execution and its deliverables remain in one place.
@MainActor
struct MissionConversation: View {
    @ObservedObject var store: BackendStore
    let connect: () -> Void
    let details: (AutonomousJob) -> Void

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 30) {
                if store.backend.isEmpty || store.status == nil {
                    Button(action: connect) { Label("Connect your workspace", systemImage: "network") }
                        .buttonStyle(.borderedProminent)
                }
                if let error = store.error {
                    Label(error, systemImage: "wifi.exclamationmark").font(.callout).foregroundStyle(.orange)
                }
                if store.jobs.isEmpty {
                    VStack(alignment: .leading, spacing: 14) {
                        Image(systemName: "sparkle").font(.largeTitle).foregroundStyle(.mint)
                        Text("What shall we make happen?").font(.largeTitle.bold())
                        Text("Build software, research a decision, or run a workflow. Actions and results appear here as they happen.")
                            .foregroundStyle(.secondary)
                    }.padding(.vertical, 48)
                }
                ForEach(Array(store.jobs.prefix(12).reversed())) { job in
                    ConversationTurn(store: store, initialJob: job) { details(job) }
                }
            }.padding(20).frame(maxWidth: 860).frame(maxWidth: .infinity)
        }
        .defaultScrollAnchor(.bottom)
        .refreshable { await store.refresh() }
        .accessibilityIdentifier("mission-conversation")
    }
}

@MainActor
private struct ConversationTurn: View {
    @ObservedObject var store: BackendStore
    let initialJob: AutonomousJob
    let details: () -> Void
    @Environment(\.scenePhase) private var scenePhase
    @State private var events: [AgentTraceItem] = []
    @State private var cursor = 0
    @State private var failure: String?
    @State private var checkedAt: Date?
    @State private var downloads: [String: URL] = [:]
    @State private var downloading: String?
    private var job: AutonomousJob { store.jobs.first { $0.id == initialJob.id } ?? initialJob }
    private var milestones: [AgentTraceItem] {
        events.filter { !["thinking", "queued", "command_started"].contains($0.kind) }
    }
    private var statusIcon: String {
        job.status == "completed" ? "checkmark.circle.fill" : job.canCancel ? "circle.dotted" : "exclamationmark.circle"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            HStack {
                Spacer(minLength: 36)
                Text(job.query).textSelection(.enabled).padding(16)
                    .background(.white.opacity(0.09), in: RoundedRectangle(cornerRadius: 22))
            }
            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 10) {
                    Image(systemName: "sparkle").foregroundStyle(.mint)
                    Text("SuperCraftOS").font(.headline)
                    Spacer()
                    Label(job.status.capitalized, systemImage: statusIcon)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(job.status == "completed" ? Color.mint : job.canCancel ? Color.secondary : Color.orange)
                }
                if let summary = job.result.summary, !summary.isEmpty {
                    Text(summary).textSelection(.enabled)
                } else if let latest = milestones.last {
                    Text(latest.message ?? latest.label).foregroundStyle(.secondary)
                } else {
                    Text(job.canCancel ? "Waiting for the first execution event…" : "No execution result recorded.")
                        .foregroundStyle(.secondary)
                }
                if job.canCancel {
                    HStack {
                        ProgressView().controlSize(.small)
                        Text("\(job.steps) actions used · updates every 3s").font(.caption).foregroundStyle(.secondary)
                    }
                }
                if let error = job.error { Text(error).font(.callout).foregroundStyle(.orange).textSelection(.enabled) }
                if let failure {
                    Label("Activity connection interrupted: \(failure)", systemImage: "wifi.exclamationmark")
                        .font(.caption).foregroundStyle(.orange)
                } else if let checkedAt {
                    Text("Activity checked \(checkedAt.formatted(date: .omitted, time: .standard))")
                        .font(.caption2).foregroundStyle(.secondary)
                }
                ForEach(Array(milestones.suffix(3))) { event in
                    HStack(alignment: .top, spacing: 10) {
                        Image(systemName: event.outcome == "error" ? "exclamationmark.circle" : event.kind == "observation" ? "checkmark" : "arrow.turn.down.right")
                            .foregroundStyle(event.outcome == "error" ? Color.orange : Color.mint)
                        VStack(alignment: .leading, spacing: 3) {
                            Text(event.toolName?.replacingOccurrences(of: "_", with: " ") ?? event.label).font(.callout.weight(.medium))
                            if let message = event.message { Text(message).font(.caption).foregroundStyle(.secondary).lineLimit(3) }
                        }
                    }
                }
                if job.status == "completed" {
                    ForEach(job.result.files ?? []) { file in
                        HStack {
                            Image(systemName: "doc.zipper").foregroundStyle(.mint)
                            VStack(alignment: .leading) {
                                Text(file.path).font(.callout).lineLimit(1)
                                Text(ByteCountFormatter.string(fromByteCount: Int64(file.bytes), countStyle: .file))
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                            Spacer()
                            if let url = downloads[file.path] {
                                ShareLink(item: url) { Image(systemName: "square.and.arrow.up") }
                            } else {
                                Button {
                                    downloading = file.path
                                    Task {
                                        defer { downloading = nil }
                                        do { downloads[file.path] = try await store.downloadTaskFile(jobID: job.id, file: file) }
                                        catch { failure = error.localizedDescription }
                                    }
                                } label: { Image(systemName: downloading == file.path ? "hourglass" : "arrow.down.circle") }
                                    .disabled(downloading != nil).accessibilityLabel("Download \(file.path)")
                            }
                        }.padding(12).background(.white.opacity(0.04), in: RoundedRectangle(cornerRadius: 12))
                    }
                }
                HStack(spacing: 18) {
                    Button("Evidence & controls", action: details)
                    if job.canCancel { Button("Stop", role: .destructive) { Task { await store.perform("/api/jobs/\(job.id)/cancel") } } }
                    if job.canRetry { Button("Resume") { Task { await store.perform("/api/jobs/\(job.id)/retry") } } }
                }.font(.caption).disabled(store.mutating)
            }.frame(maxWidth: .infinity, alignment: .leading)
        }
        .accessibilityIdentifier("mission-row-\(job.id)")
        .task(id: scenePhase == .active) {
            guard scenePhase == .active else { return }
            while !Task.isCancelled {
                do {
                    let page = try await store.taskTrace(job.id, after: cursor)
                    let existing = Set(events.map(\.id))
                    events.append(contentsOf: page.timeline.filter { !existing.contains($0.id) })
                    if events.count > 500 { events.removeFirst(events.count - 500) }
                    if let next = page.nextCursor { cursor = next }
                    checkedAt = Date(); failure = nil
                } catch is CancellationError { return }
                catch { failure = error.localizedDescription }
                if !job.canCancel { return }
                do { try await Task.sleep(for: .seconds(3)) } catch { return }
            }
        }
    }
}
