import SwiftUI

@MainActor
struct AutonomousTasksView: View {
    @ObservedObject var store: BackendStore
    let onCreate: () -> Void
    @State private var selected: AutonomousJob?
    @State private var search = ""
    @State private var statusFilter = "All"
    private var filteredJobs: [AutonomousJob] {
        store.jobs.filter { job in
            let matchesStatus = statusFilter == "All"
                || (statusFilter == "Active" && job.canCancel)
                || (statusFilter == "Attention" && ["blocked", "failed"].contains(job.status))
                || (statusFilter == "Completed" && job.status == "completed")
            return matchesStatus && (search.isEmpty || [job.query, job.id, job.result.summary ?? ""].joined(separator: " ").localizedCaseInsensitiveContains(search))
        }
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 5) {
                    Text("Execution queue").font(.title2.bold())
                    Text("\(store.jobs.filter { $0.status == "running" }.count) running · \(store.jobs.count) total")
                        .font(.body).foregroundStyle(.secondary)
                }
                Spacer()
                Button(action: onCreate) { Label("New task", systemImage: "plus") }
                    .buttonStyle(.borderedProminent)
                    .disabled(store.backend.isEmpty)
            }
            if let status = store.agentStatus {
                Label("\(status.workers) workers available", systemImage: "server.rack")
                    .font(.body.weight(.semibold)).foregroundStyle(status.workers > 0 ? .mint : .orange)
                if !status.modelConfigured { Text("Configure a model credential on the server to run tasks.").foregroundStyle(.orange) }
            }
            if store.jobs.isEmpty { ContentUnavailableView("No tasks yet", systemImage: "checklist", description: Text("Start a task with the + button.")) }
            TextField("Search goals, results, or task IDs", text: $search)
                .textFieldStyle(.roundedBorder)
                .accessibilityIdentifier("task-search")
            Picker("Task status", selection: $statusFilter) {
                ForEach(["All", "Active", "Attention", "Completed"], id: \.self) { Text($0) }
            }.pickerStyle(.menu).accessibilityIdentifier("task-filter")
            if !store.jobs.isEmpty && filteredJobs.isEmpty {
                ContentUnavailableView.search(text: search)
            }
            ForEach(filteredJobs) { job in
                Button { selected = job } label: {
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            Label(job.status.capitalized, systemImage: job.status == "completed" ? "checkmark.circle.fill" : "arrow.triangle.2.circlepath")
                                .font(.body.bold())
                                .foregroundStyle(job.status == "completed" ? .mint : .pink)
                            Spacer()
                            Text("\(job.steps)/\(job.maxSteps) steps").font(.body.monospaced())
                                .foregroundStyle(.secondary)
                        }
                        Text(job.query).font(.title3.weight(.semibold)).lineLimit(3)
                        if let summary = job.result.summary, !summary.isEmpty {
                            Text(summary).font(.body).foregroundStyle(.secondary).lineLimit(3)
                        }
                        if let error = job.error { Text(error).font(.body).foregroundStyle(.orange).lineLimit(2) }
                    }.frame(maxWidth: .infinity, alignment: .leading).padding(18)
                        .background(Color.white.opacity(0.06), in: RoundedRectangle(cornerRadius: 18))
                        .overlay(RoundedRectangle(cornerRadius: 18).stroke(Color.white.opacity(0.10)))
                }.buttonStyle(.plain).accessibilityIdentifier("task-row-\(job.id)")
            }
        }.sheet(item: $selected) { job in AutonomousTaskDetail(store: store, initialJob: job) }
    }
}

@MainActor
struct AutonomousTaskDetail: View {
    @ObservedObject var store: BackendStore
    let initialJob: AutonomousJob
    @State private var events: [AgentTraceItem] = []
    @State private var cursor = 0
    @State private var downloads: [String: URL] = [:]
    @State private var downloadInProgress: String?
    @State private var failure: String?
    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var scenePhase
    private var job: AutonomousJob { store.jobs.first { $0.id == initialJob.id } ?? initialJob }
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    Text(job.query).font(.title2.bold()).textSelection(.enabled)
                    Label(job.status.capitalized, systemImage: job.status == "completed" ? "checkmark.circle.fill" : job.canCancel ? "clock" : "exclamationmark.circle")
                        .font(.headline).foregroundStyle(job.status == "completed" ? .mint : job.canCancel ? .white : .orange)
                    Text(job.status == "completed" ? "Result ready. Open the files and evidence below." : job.canCancel ? "Activity updates while this screen is open." : "Review the recorded reason before retrying.")
                        .font(.body).foregroundStyle(.secondary)
                    Text("Task ID: \(job.id)").font(.body.monospaced()).textSelection(.enabled)
                    ShareLink(item: job.id) { Label("Share task ID", systemImage: "number") }
                    Text("\(job.steps) of \(job.maxSteps) action budget used").font(.body)
                    if job.canCancel { Button("Cancel task", role: .destructive) { change("cancel") }.disabled(store.busy) }
                    if job.canRetry { Button("Retry task") { change("retry") }.disabled(store.busy) }
                    if let error = job.error { Text(error).foregroundStyle(.orange).textSelection(.enabled) }
                    if let summary = job.result.summary { Text(summary).textSelection(.enabled) }
                    if job.result.review?.accepted == true { Label("Acceptance review passed", systemImage: "checkmark.seal") }
                    if job.status == "completed" {
                        ForEach(job.result.files ?? []) { file in
                            VStack(alignment: .leading, spacing: 4) {
                                Text(file.path).font(.body.monospaced())
                                Text("\(file.bytes) bytes").font(.body).foregroundStyle(.secondary)
                                if let url = downloads[file.path] { ShareLink(item: url) { Label("Save or share file", systemImage: "square.and.arrow.up") } }
                                else {
                                    Button(downloadInProgress == file.path ? "Downloading…" : "Download file") {
                                        downloadInProgress = file.path; failure = nil
                                        Task {
                                            defer { downloadInProgress = nil }
                                            do { downloads[file.path] = try await store.downloadTaskFile(jobID: job.id, file: file) }
                                            catch { failure = error.localizedDescription }
                                        }
                                    }.disabled(downloadInProgress != nil)
                                }
                            }
                        }
                    }
                    if let evidence = job.result.nativeEvidence, !evidence.isEmpty {
                        Text("Tool evidence").font(.title2.bold())
                        ForEach(Array(evidence.enumerated()), id: \.offset) { _, item in
                            DisclosureGroup(item.name.replacingOccurrences(of: "_", with: " ")) {
                                Text(item.result.formatted).font(.body.monospaced()).textSelection(.enabled)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                            }
                        }
                    }
                    ForEach(Array((job.result.checks ?? []).enumerated()), id: \.offset) { _, check in
                        DisclosureGroup("Exit \(check.exitCode.map(String.init) ?? "incomplete") · \(check.command ?? "Command")") {
                            Text(check.output).font(.body.monospaced()).textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                    if let failure { Text(failure).foregroundStyle(.orange) }
                    if let error = store.error { Text(error).foregroundStyle(.orange) }
                    Text("Activity").font(.title2.bold())
                    if events.isEmpty { Text("No activity has been recorded yet.").font(.body).foregroundStyle(.secondary) }
                    ForEach(events.reversed()) { event in
                        VStack(alignment: .leading, spacing: 6) {
                            HStack { Text(event.label).font(.headline); Spacer(); Text(Date(timeIntervalSince1970: event.at), style: .time).font(.caption.monospaced()) }
                            if let tool = event.toolName { Label(tool, systemImage: "wrench.and.screwdriver").font(.body.monospaced()) }
                            if let action = event.action { Text(action).font(.body) }
                            if let outcome = event.outcome { Text(outcome).font(.body.bold()) }
                            if let message = event.message { Text(message).font(.body).foregroundStyle(.secondary).textSelection(.enabled) }
                        }.frame(maxWidth: .infinity, alignment: .leading).padding(12).background(.white.opacity(0.04), in: RoundedRectangle(cornerRadius: 12))
                    }
                }.padding().frame(maxWidth: .infinity, alignment: .leading)
            }.navigationTitle("Autonomous task").navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
                .task(id: scenePhase == .active) {
                    guard scenePhase == .active else { return }
                    while !Task.isCancelled {
                        do {
                            await store.refresh()
                            let page = try await store.taskTrace(job.id, after: cursor)
                            let existing = Set(events.map(\.id))
                            events.append(contentsOf: page.timeline.filter { !existing.contains($0.id) })
                            if let next = page.nextCursor { cursor = next }
                            else if let last = page.timeline.last { cursor = max(cursor, last.id) }
                            if events.count > 2000 { events.removeFirst(events.count - 2000) }
                            failure = nil
                        }
                        catch is CancellationError { return }
                        catch { failure = error.localizedDescription }
                        if !job.canCancel { break }
                        do { try await Task.sleep(for: .seconds(3)) } catch { return }
                    }
                }
        }.preferredColorScheme(.dark)
    }
    private func change(_ action: String) { Task { await store.perform("/api/jobs/\(job.id)/\(action)") } }
}
