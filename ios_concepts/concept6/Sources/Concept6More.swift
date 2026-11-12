import SwiftUI

// MARK: - Tasks (real jobs)
struct NeuralTasksView: View {
    @EnvironmentObject private var backend: Concept6Backend
    @State private var query = ""

    var filtered: [Job] {
        query.isEmpty ? backend.jobs : backend.jobs.filter { $0.query.localizedCaseInsensitiveContains(query) }
    }

    var body: some View {
        NavigationStack {
            Group {
                if filtered.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "magnifyingglass").font(.largeTitle).foregroundStyle(Neural.muted)
                        Text("No matching tasks").font(.headline)
                        Text("Try a different search.").font(.subheadline).foregroundStyle(Neural.muted)
                        Button("Clear search") { query = "" }.buttonStyle(.bordered)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    List {
                        ForEach(filtered) { job in
                            NavigationLink {
                                NeuralTaskDetailView(job: job)
                            } label: {
                                NeuralJobRow(job: job)
                            }
                        }
                    }
                    .listStyle(.plain).scrollContentBackground(.hidden)
                    .refreshable { await backend.refresh() }
                }
            }
            .background(Neural.bg)
            .searchable(text: $query, prompt: "Search tasks")
            .navigationTitle("Tasks")
        }
    }
}

struct NeuralJobRow: View {
    let job: Job
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(job.query).font(.headline).foregroundStyle(Neural.ink)
                    .lineLimit(2)
                Spacer()
                Text(job.status.uppercased())
                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                    .padding(.horizontal, 8).padding(.vertical, 4)
                    .background(NeuralJobColor.color(job.statusColorName).opacity(0.16), in: Capsule())
                    .foregroundStyle(NeuralJobColor.color(job.statusColorName))
            }
            HStack(spacing: 12) {
                Text("\(job.steps) steps").font(.caption.monospaced()).foregroundStyle(Neural.muted)
                if let s = job.summary {
                    Text(s).font(.caption).foregroundStyle(Neural.muted).lineLimit(1)
                }
            }
        }
        .padding(.vertical, 6)
    }
}

struct NeuralTaskDetailView: View {
    let job: Job
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                NeuralPanel {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text(job.query).font(.title3.bold()).foregroundStyle(Neural.ink)
                            Spacer()
                            Text(job.status.uppercased())
                                .font(.system(size: 10, weight: .bold, design: .monospaced))
                                .padding(.horizontal, 8).padding(.vertical, 4)
                                .background(NeuralJobColor.color(job.statusColorName).opacity(0.16), in: Capsule())
                                .foregroundStyle(NeuralJobColor.color(job.statusColorName))
                        }
                        Text("\(job.steps) steps · started \(formatted(job.created))")
                            .font(.caption.monospaced()).foregroundStyle(Neural.muted)
                    }
                }
                if let plan = job.result?.plan, !plan.isEmpty {
                    NeuralPanel {
                        VStack(alignment: .leading, spacing: 10) {
                            NeuralMono(text: "EXECUTION PLAN")
                            ForEach(Array(plan.enumerated()), id: \.offset) { i, s in
                                HStack(alignment: .top, spacing: 10) {
                                    Image(systemName: "circle").foregroundStyle(Neural.accent)
                                    Text(s).font(.subheadline).foregroundStyle(Neural.ink)
                                }
                            }
                        }
                    }
                }
                if let checks = job.result?.checks, !checks.isEmpty {
                    NeuralPanel {
                        VStack(alignment: .leading, spacing: 10) {
                            NeuralMono(text: "CHECKS")
                            ForEach(checks, id: \.command) { c in
                                HStack(alignment: .top, spacing: 10) {
                                    Image(systemName: (c.exitCode == 0) ? "checkmark.circle.fill" : "xmark.circle.fill")
                                        .foregroundStyle((c.exitCode == 0) ? Neural.ok : Neural.danger)
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(c.command).font(.caption.monospaced()).foregroundStyle(Neural.ink)
                                        if let o = c.output {
                                            Text(o).font(.caption2.monospaced()).foregroundStyle(Neural.muted).lineLimit(3)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                if let s = job.summary {
                    NeuralPanel {
                        VStack(alignment: .leading, spacing: 8) {
                            NeuralMono(text: "SUMMARY")
                            Text(s).font(.subheadline).foregroundStyle(Neural.ink)
                        }
                    }
                }
                if let files = job.result?.files, !files.isEmpty {
                    NeuralPanel {
                        VStack(alignment: .leading, spacing: 8) {
                            NeuralMono(text: "ARTIFACTS")
                            ForEach(files, id: \.path) { f in
                                HStack {
                                    Image(systemName: "doc.text").foregroundStyle(Neural.accent)
                                    Text(f.path).font(.caption.monospaced()).foregroundStyle(Neural.ink)
                                    Spacer()
                                    if let b = f.bytes {
                                        Text("\(b)B").font(.caption2.monospaced()).foregroundStyle(Neural.muted)
                                    }
                                }
                            }
                        }
                    }
                }
            }
            .padding(16)
        }
        .background(Neural.bg)
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
struct NeuralMeView: View {
    @EnvironmentObject private var backend: Concept6Backend
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    NeuralPanel {
                        HStack(spacing: 14) {
                            ZStack {
                                Circle().fill(Neural.accent.opacity(0.18)).frame(width: 56, height: 56)
                                Text("DM").font(.title2.bold()).foregroundStyle(Neural.accent)
                            }
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Digital Me").font(.title3.bold()).foregroundStyle(Neural.ink)
                                Text("Predictive, proactive memory").font(.caption).foregroundStyle(Neural.muted)
                            }
                            Spacer()
                            if let e = backend.error, !backend.connected {
                                Text("⚠︎").foregroundStyle(Neural.danger)
                            } else {
                                PulseDot(color: backend.loading ? Neural.warn : Neural.ok)
                            }
                        }
                    }
                    NeuralPanel {
                        VStack(alignment: .leading, spacing: 10) {
                            NeuralMono(text: "LIVE PROFILE")
                            HStack {
                                statBlock("\(backend.memoryEntries)", "memories")
                                statBlock("\(backend.playbooks)", "playbooks")
                            }
                            if !backend.brainProfile.isEmpty {
                                Text(backend.brainProfile).font(.subheadline).foregroundStyle(Neural.ink)
                            }
                        }
                    }
                    if !backend.brainTopics.isEmpty {
                        NeuralPanel {
                            VStack(alignment: .leading, spacing: 10) {
                                NeuralMono(text: "TOPICS")
                                NeuralChips(items: backend.brainTopics)
                            }
                        }
                    }
                    NeuralPanel {
                        VStack(alignment: .leading, spacing: 10) {
                            NeuralMono(text: "MEMORY")
                            if backend.memories.isEmpty {
                                Text("No notes ingested yet.").font(.subheadline).foregroundStyle(Neural.muted)
                            } else {
                                ForEach(backend.memories.prefix(6)) { m in
                                    HStack(alignment: .top, spacing: 10) {
                                        Image(systemName: "brain").foregroundStyle(Neural.accent)
                                        VStack(alignment: .leading, spacing: 2) {
                                            Text(m.note).font(.subheadline).foregroundStyle(Neural.ink)
                                            Text(m.notebook ?? "").font(.caption2.monospaced()).foregroundStyle(Neural.muted)
                                        }
                                    }
                                }
                            }
                        }
                    }
                    NeuralPanel {
                        VStack(alignment: .leading, spacing: 10) {
                            NeuralMono(text: "PLAYBOOKS")
                            if backend.playbookList.isEmpty {
                                Text("No playbooks yet.").font(.subheadline).foregroundStyle(Neural.muted)
                            } else {
                                ForEach(backend.playbookList.prefix(4)) { pb in
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text(pb.title).font(.subheadline.bold()).foregroundStyle(Neural.ink)
                                        if let when = pb.when {
                                            Text(when).font(.caption).foregroundStyle(Neural.muted)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                .padding(16)
            }
            .background(Neural.bg)
            .navigationTitle("Digital Me")
        }
    }
    private func statBlock(_ v: String, _ label: String) -> some View {
        VStack(spacing: 2) {
            Text(v).font(.system(size: 26, weight: .bold, design: .rounded)).foregroundStyle(Neural.accent)
            Text(label).font(.caption).foregroundStyle(Neural.muted)
        }
        .frame(maxWidth: .infinity)
    }
}

struct NeuralChips: View {
    let items: [String]
    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 90), spacing: 8)], alignment: .leading, spacing: 8) {
            ForEach(items, id: \.self) { item in
                Text(item)
                    .font(.caption).foregroundStyle(Neural.ink)
                    .padding(.horizontal, 10).padding(.vertical, 5)
                    .background(Neural.surface2, in: Capsule())
            }
        }
    }
}

// MARK: - Lab
struct NeuralLabView: View {
    @EnvironmentObject private var backend: Concept6Backend
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    NeuralPanel {
                        VStack(alignment: .leading, spacing: 8) {
                            NeuralMono(text: "CAPABILITIES")
                            VStack(alignment: .leading, spacing: 10) {
                                ForEach(backend.capabilities) { cap in
                                    HStack(alignment: .top, spacing: 10) {
                                        PulseDot(color: cap.enabled ? Neural.ok : Neural.muted)
                                        VStack(alignment: .leading, spacing: 2) {
                                            Text(cap.name).font(.subheadline.bold()).foregroundStyle(Neural.ink)
                                            if let f = cap.features {
                                                Text(f).font(.caption).foregroundStyle(Neural.muted)
                                            }
                                            Text("\(cap.runs) runs · \(Int(cap.routingScore * 100))% route")
                                                .font(.caption2.monospaced()).foregroundStyle(Neural.muted)
                                        }
                                    }
                                }
                            }
                        }
                    }
                    NeuralPanel {
                        VStack(alignment: .leading, spacing: 8) {
                            NeuralMono(text: "INTEGRATIONS")
                            VStack(alignment: .leading, spacing: 10) {
                                ForEach(backend.integrationList) { int in
                                    HStack {
                                        Text(int.name).font(.subheadline).foregroundStyle(Neural.ink)
                                        Spacer()
                                        Text(int.status.replacingOccurrences(of: "_", with: " ").uppercased())
                                            .font(.system(size: 9, weight: .bold, design: .monospaced))
                                            .foregroundStyle(int.status == "connected" || int.status == "configured" ? Neural.ok : Neural.muted)
                                    }
                                }
                            }
                        }
                    }
                }
                .padding(16)
            }
            .background(Neural.bg)
            .navigationTitle("Lab")
        }
    }
}

// MARK: - More
struct NeuralMoreView: View {
    @Binding var offline: Bool
    @EnvironmentObject private var backend: Concept6Backend
    var body: some View {
        NavigationStack {
            List {
                Section {
                    Toggle(isOn: $offline) { Label("Simulate offline", systemImage: "wifi.slash") }
                        .tint(Neural.accent)
                }
                Section("Connection") {
                    HStack {
                        Label("Backend", systemImage: "network")
                        Spacer()
                        Text(backend.connected ? "connected" : "offline")
                            .font(.caption.monospaced()).foregroundStyle(backend.connected ? Neural.ok : Neural.danger)
                    }
                    HStack {
                        Label("Runtime", systemImage: "cpu")
                        Spacer()
                        Text(backend.runtime).font(.caption.monospaced()).foregroundStyle(Neural.muted)
                    }
                }
                Section("Settings") {
                    Label("Keyboard", systemImage: "keyboard")
                    Label("Billing", systemImage: "creditcard")
                }
            }
            .scrollContentBackground(.hidden)
            .background(Neural.bg)
            .navigationTitle("More")
        }
    }
}
