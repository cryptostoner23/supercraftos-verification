import SwiftUI

// MARK: - Tasks (real jobs)
struct TasksView: View {
    @EnvironmentObject private var backend: Concept2Backend
    @State private var query = ""

    var filtered: [Job] {
        query.isEmpty ? backend.jobs : backend.jobs.filter { $0.query.localizedCaseInsensitiveContains(query) }
    }

    var body: some View {
        NavigationStack {
            Group {
                if filtered.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "magnifyingglass").font(.largeTitle).foregroundStyle(Tactical.muted)
                        Text("No matching tasks").font(.headline)
                        Text("Try a different search.").font(.subheadline).foregroundStyle(Tactical.muted)
                        Button("Clear search") { query = "" }.buttonStyle(.bordered)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    List {
                        ForEach(filtered) { job in
                            NavigationLink {
                                TaskDetailView(job: job)
                            } label: {
                                JobRow(job: job)
                            }
                        }
                    }
                    .listStyle(.plain)
                    .scrollContentBackground(.hidden)
                    .refreshable { await backend.refresh() }
                }
            }
            .background(Tactical.bg)
            .searchable(text: $query, prompt: "Search tasks")
            .navigationTitle("Tasks")
        }
    }
}

struct JobRow: View {
    let job: Job
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(job.query).font(.headline).foregroundStyle(Tactical.ink)
                    .lineLimit(2)
                Spacer()
                Text(job.status.uppercased())
                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                    .padding(.horizontal, 8).padding(.vertical, 4)
                    .background(JobStatusColor.color(job.statusColorName).opacity(0.16), in: Capsule())
                    .foregroundStyle(JobStatusColor.color(job.statusColorName))
            }
            HStack(spacing: 12) {
                Text("\(job.steps) steps").font(.caption.monospaced()).foregroundStyle(Tactical.muted)
                if let s = job.summary {
                    Text(s).font(.caption).foregroundStyle(Tactical.muted).lineLimit(1)
                }
            }
        }
        .padding(.vertical, 6)
    }
}

struct TaskDetailView: View {
    let job: Job
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                TacticalPanel {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text(job.query).font(.title3.bold()).foregroundStyle(Tactical.ink)
                            Spacer()
                            Text(job.status.uppercased())
                                .font(.system(size: 10, weight: .bold, design: .monospaced))
                                .padding(.horizontal, 8).padding(.vertical, 4)
                                .background(JobStatusColor.color(job.statusColorName).opacity(0.16), in: Capsule())
                                .foregroundStyle(JobStatusColor.color(job.statusColorName))
                        }
                        Text("\(job.steps) steps · started \(formatted(job.created))")
                            .font(.caption.monospaced()).foregroundStyle(Tactical.muted)
                    }
                }
                if let plan = job.result?.plan, !plan.isEmpty {
                    TacticalPanel {
                        VStack(alignment: .leading, spacing: 10) {
                            MonoLabel(text: "EXECUTION PLAN")
                            ForEach(Array(plan.enumerated()), id: \.offset) { i, s in
                                HStack(alignment: .top, spacing: 10) {
                                    Image(systemName: "circle").foregroundStyle(Tactical.accent)
                                    Text(s).font(.subheadline).foregroundStyle(Tactical.ink)
                                }
                            }
                        }
                    }
                }
                if let checks = job.result?.checks, !checks.isEmpty {
                    TacticalPanel {
                        VStack(alignment: .leading, spacing: 10) {
                            MonoLabel(text: "CHECKS")
                            ForEach(checks, id: \.command) { c in
                                HStack(alignment: .top, spacing: 10) {
                                    Image(systemName: (c.exitCode == 0) ? "checkmark.circle.fill" : "xmark.circle.fill")
                                        .foregroundStyle((c.exitCode == 0) ? Tactical.ok : Tactical.danger)
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(c.command).font(.caption.monospaced()).foregroundStyle(Tactical.ink)
                                        if let o = c.output {
                                            Text(o).font(.caption2.monospaced()).foregroundStyle(Tactical.muted).lineLimit(3)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                if let s = job.summary {
                    TacticalPanel {
                        VStack(alignment: .leading, spacing: 8) {
                            MonoLabel(text: "SUMMARY")
                            Text(s).font(.subheadline).foregroundStyle(Tactical.ink)
                        }
                    }
                }
                if let files = job.result?.files, !files.isEmpty {
                    TacticalPanel {
                        VStack(alignment: .leading, spacing: 8) {
                            MonoLabel(text: "ARTIFACTS")
                            ForEach(files, id: \.path) { f in
                                HStack {
                                    Image(systemName: "doc.text").foregroundStyle(Tactical.accent)
                                    Text(f.path).font(.caption.monospaced()).foregroundStyle(Tactical.ink)
                                    Spacer()
                                    if let b = f.bytes {
                                        Text("\(b)B").font(.caption2.monospaced()).foregroundStyle(Tactical.muted)
                                    }
                                }
                            }
                        }
                    }
                }
            }
            .padding(16)
        }
        .background(Tactical.bg)
        .navigationTitle("Task detail")
        .navigationBarTitleDisplayMode(.inline)
    }
    private func formatted(_ ts: Double) -> String {
        let f = DateFormatter()
        f.dateFormat = "MMM d, HH:mm"
        return f.string(from: Date(timeIntervalSince1970: ts))
    }
}

// MARK: - Digital Me
struct DigitalMeView: View {
    @EnvironmentObject private var backend: Concept2Backend
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    TacticalPanel {
                        HStack(spacing: 14) {
                            ZStack {
                                Circle().fill(Tactical.accent.opacity(0.2)).frame(width: 56, height: 56)
                                Text("DM").font(.title2.bold()).foregroundStyle(Tactical.accent)
                            }
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Digital Me").font(.title3.bold()).foregroundStyle(Tactical.ink)
                                Text("Persistent identity & memory").font(.caption).foregroundStyle(Tactical.muted)
                            }
                            Spacer()
                            StatusDot(color: backend.connected ? Tactical.ok : Tactical.warn)
                        }
                    }
                    TacticalPanel {
                        VStack(alignment: .leading, spacing: 10) {
                            MonoLabel(text: "PROFILE")
                            HStack {
                                statBlock("\(backend.memoryEntries)", "memories")
                                statBlock("\(backend.playbooks)", "playbooks")
                            }
                            if let p = backend.brainProfile as String?, !p.isEmpty {
                                Text(p).font(.subheadline).foregroundStyle(Tactical.ink)
                            }
                        }
                    }
                    if !backend.brainTopics.isEmpty {
                        TacticalPanel {
                            VStack(alignment: .leading, spacing: 10) {
                                MonoLabel(text: "TOPICS")
                                FlowChips(items: backend.brainTopics)
                            }
                        }
                    }
                    TacticalPanel {
                        VStack(alignment: .leading, spacing: 10) {
                            MonoLabel(text: "MEMORY")
                            if backend.memories.isEmpty {
                                Text("No notes ingested yet.").font(.subheadline).foregroundStyle(Tactical.muted)
                            } else {
                                ForEach(backend.memories.prefix(6)) { m in
                                    HStack(alignment: .top, spacing: 10) {
                                        Image(systemName: "brain").foregroundStyle(Tactical.accent)
                                        VStack(alignment: .leading, spacing: 2) {
                                            Text(m.note).font(.subheadline).foregroundStyle(Tactical.ink)
                                            Text(m.notebook ?? "").font(.caption2.monospaced()).foregroundStyle(Tactical.muted)
                                        }
                                    }
                                }
                            }
                        }
                    }
                    TacticalPanel {
                        VStack(alignment: .leading, spacing: 10) {
                            MonoLabel(text: "PLAYBOOKS")
                            if backend.playbookList.isEmpty {
                                Text("No playbooks yet.").font(.subheadline).foregroundStyle(Tactical.muted)
                            } else {
                                ForEach(backend.playbookList.prefix(4)) { pb in
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text(pb.title).font(.subheadline.bold()).foregroundStyle(Tactical.ink)
                                        if let when = pb.when {
                                            Text(when).font(.caption).foregroundStyle(Tactical.muted)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                .padding(16)
            }
            .background(Tactical.bg)
            .navigationTitle("Digital Me")
        }
    }
    private func statBlock(_ v: String, _ label: String) -> some View {
        VStack(spacing: 2) {
            Text(v).font(.system(size: 26, weight: .bold, design: .rounded)).foregroundStyle(Tactical.accent)
            Text(label).font(.caption).foregroundStyle(Tactical.muted)
        }
        .frame(maxWidth: .infinity)
    }
}

struct FlowChips: View {
    let items: [String]
    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 90), spacing: 8)], alignment: .leading, spacing: 8) {
            ForEach(items, id: \.self) { item in
                Text(item)
                    .font(.caption).foregroundStyle(Tactical.ink)
                    .padding(.horizontal, 10).padding(.vertical, 5)
                    .background(Tactical.surface2, in: Capsule())
            }
        }
    }
}

// MARK: - Lab
struct LabView: View {
    @EnvironmentObject private var backend: Concept2Backend
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    TacticalPanel {
                        VStack(alignment: .leading, spacing: 8) {
                            MonoLabel(text: "CAPABILITIES")
                            VStack(alignment: .leading, spacing: 10) {
                                ForEach(backend.capabilities) { cap in
                                    HStack(alignment: .top, spacing: 10) {
                                        StatusDot(color: cap.enabled ? Tactical.ok : Tactical.muted)
                                        VStack(alignment: .leading, spacing: 2) {
                                            Text(cap.name).font(.subheadline.bold()).foregroundStyle(Tactical.ink)
                                            if let f = cap.features {
                                                Text(f).font(.caption).foregroundStyle(Tactical.muted)
                                            }
                                            Text("\(cap.runs) runs · \(Int(cap.routingScore * 100))% route")
                                                .font(.caption2.monospaced()).foregroundStyle(Tactical.muted)
                                        }
                                    }
                                }
                            }
                        }
                    }
                    TacticalPanel {
                        VStack(alignment: .leading, spacing: 8) {
                            MonoLabel(text: "INTEGRATIONS")
                            VStack(alignment: .leading, spacing: 10) {
                                ForEach(backend.integrationList) { int in
                                    HStack {
                                        Text(int.name).font(.subheadline).foregroundStyle(Tactical.ink)
                                        Spacer()
                                        Text(int.status.replacingOccurrences(of: "_", with: " ").uppercased())
                                            .font(.system(size: 9, weight: .bold, design: .monospaced))
                                            .foregroundStyle(int.status == "connected" || int.status == "configured" ? Tactical.ok : Tactical.muted)
                                    }
                                }
                            }
                        }
                    }
                }
                .padding(16)
            }
            .background(Tactical.bg)
            .navigationTitle("Lab")
        }
    }
}

// MARK: - More
struct MoreView: View {
    @Binding var offline: Bool
    @EnvironmentObject private var backend: Concept2Backend
    var body: some View {
        NavigationStack {
            List {
                Section {
                    Toggle(isOn: $offline) { Label("Simulate offline", systemImage: "wifi.slash") }
                        .tint(Tactical.accent)
                }
                Section("Connection") {
                    HStack {
                        Label("Backend", systemImage: "network")
                        Spacer()
                        Text(backend.connected ? "connected" : "offline")
                            .font(.caption.monospaced()).foregroundStyle(backend.connected ? Tactical.ok : Tactical.danger)
                    }
                    HStack {
                        Label("Runtime", systemImage: "cpu")
                        Spacer()
                        Text(backend.runtime).font(.caption.monospaced()).foregroundStyle(Tactical.muted)
                    }
                }
                Section("Settings") {
                    Label("Keyboard", systemImage: "keyboard")
                    Label("Billing", systemImage: "creditcard")
                }
            }
            .scrollContentBackground(.hidden)
            .background(Tactical.bg)
            .navigationTitle("More")
        }
    }
}
