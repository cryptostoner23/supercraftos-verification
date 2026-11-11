import SwiftUI

// MARK: - Tasks
struct TasksView: View {
    @State private var tasks = [
        TaskItem(title: "Draft Q3 proposal", status: .running, progress: 0.62, evidence: ["drive.pdf", "notes"]),
        TaskItem(title: "Verify grant deadlines", status: .done, progress: 1.0, evidence: ["web"]),
        TaskItem(title: "Compose client follow-up", status: .queued, progress: 0, evidence: []),
    ]
    @State private var query = ""

    var filtered: [TaskItem] {
        query.isEmpty ? tasks : tasks.filter { $0.title.localizedCaseInsensitiveContains(query) }
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
                        ForEach(filtered) { task in
                            NavigationLink {
                                TaskDetailView(task: task)
                            } label: {
                                TaskRow(task: task)
                            }
                            .swipeActions {
                                Button(role: .destructive) {
                                    tasks.removeAll { $0.id == task.id }
                                } label: { Label("Delete", systemImage: "trash") }
                                Button {
                                    if let i = tasks.firstIndex(where: { $0.id == task.id }) {
                                        tasks[i].paused.toggle()
                                    }
                                } label: { Label(task.paused ? "Resume" : "Pause", systemImage: task.paused ? "play" : "pause") }
                                .tint(Tactical.accent)
                            }
                        }
                    }
                    .listStyle(.plain)
                    .scrollContentBackground(.hidden)
                    .refreshable { _ = (0..<2).map { _ in } ; await Task.sleep(600_000_000) }
                }
            }
            .background(Tactical.bg)
            .searchable(text: $query, prompt: "Search tasks")
            .navigationTitle("Tasks")
        }
    }
}

struct TaskRow: View {
    let task: TaskItem
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(task.title).font(.headline).foregroundStyle(Tactical.ink)
                Spacer()
                Text(task.status.rawValue.uppercased())
                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                    .padding(.horizontal, 8).padding(.vertical, 4)
                    .background(task.status.color.opacity(0.16), in: Capsule())
                    .foregroundStyle(task.status.color)
            }
            ProgressView(value: task.progress).tint(Tactical.accent)
            if !task.evidence.isEmpty {
                HStack(spacing: 6) {
                    ForEach(task.evidence, id: \.self) { e in
                        Text(e).font(.caption2.monospaced())
                            .padding(.horizontal, 6).padding(.vertical, 2)
                            .background(Tactical.surface2, in: Capsule())
                            .foregroundStyle(Tactical.muted)
                    }
                }
            }
        }
        .padding(.vertical, 6)
    }
}

struct TaskDetailView: View {
    let task: TaskItem
    let steps = ["Plan scope", "Gather sources", "Draft output", "Verify & cite", "Hand off"]
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                TacticalPanel {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text(task.title).font(.title3.bold()).foregroundStyle(Tactical.ink)
                            Spacer()
                            Text(task.status.rawValue.uppercased())
                                .font(.system(size: 10, weight: .bold, design: .monospaced))
                                .padding(.horizontal, 8).padding(.vertical, 4)
                                .background(task.status.color.opacity(0.16), in: Capsule())
                                .foregroundStyle(task.status.color)
                        }
                        ProgressView(value: task.progress).tint(Tactical.accent)
                        Text("\(Int(task.progress * 100))% complete").font(.caption.monospaced()).foregroundStyle(Tactical.muted)
                    }
                }
                TacticalPanel {
                    VStack(alignment: .leading, spacing: 10) {
                        MonoLabel(text: "EXECUTION LEDGER")
                        ForEach(Array(steps.enumerated()), id: \.offset) { i, s in
                            HStack(spacing: 10) {
                                Image(systemName: i < (task.status == .done ? steps.count : min(task.status == .running ? 2 : 0, steps.count)) ? "checkmark.circle.fill" : "circle")
                                    .foregroundStyle(i < (task.status == .done ? steps.count : min(task.status == .running ? 2 : 0, steps.count)) ? Tactical.ok : (i == 2 && task.status == .running ? Tactical.accent : Tactical.muted))
                                Text(s).font(.subheadline).foregroundStyle(Tactical.ink)
                                Spacer()
                                if i == 2 && task.status == .running {
                                    Text("LIVE").font(.caption2.monospaced().bold()).foregroundStyle(Tactical.accent)
                                }
                            }
                        }
                    }
                }
                if !task.evidence.isEmpty {
                    TacticalPanel {
                        VStack(alignment: .leading, spacing: 8) {
                            MonoLabel(text: "EVIDENCE")
                            ForEach(task.evidence, id: \.self) { e in
                                HStack {
                                    Image(systemName: "doc.text").foregroundStyle(Tactical.accent)
                                    Text(e).font(.subheadline).foregroundStyle(Tactical.ink)
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
}

// MARK: - Digital Me
struct DigitalMeView: View {
    @EnvironmentObject private var backend: Concept2Backend
    @State private var localMemories = [
        MemoryEntry(note: "Prefers concise answers and SwiftUI.", tag: "fact", confidence: 0.95),
        MemoryEntry(note: "Working on client follow-ups + Q3 proposal.", tag: "project", confidence: 0.88),
        MemoryEntry(note: "Uses aloop.agent@gmail.com for accounts.", tag: "identity", confidence: 0.99),
    ]
    var memories: [MemoryEntry] {
        if !backend.memories.isEmpty {
            return backend.memories.prefix(5).map { MemoryEntry(note: $0, tag: "live", confidence: 0.9) }
        }
        return localMemories
    }
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
                            StatusDot(color: Tactical.ok)
                        }
                    }
                    TacticalPanel {
                        VStack(alignment: .leading, spacing: 10) {
                            MonoLabel(text: "PLAYBOOKS")
                            HStack {
                                statBlock("3", "playbooks")
                                statBlock("47", "memories")
                                statBlock("0.9", "avg confidence")
                            }
                        }
                    }
                    TacticalPanel {
                        VStack(alignment: .leading, spacing: 10) {
                            MonoLabel(text: "MEMORY")
                            ForEach(memories) { m in
                                HStack(alignment: .top, spacing: 10) {
                                    Image(systemName: "brain").foregroundStyle(Tactical.accent)
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(m.note).font(.subheadline).foregroundStyle(Tactical.ink)
                                        Text("\(m.tag) · \(Int(m.confidence * 100))%")
                                            .font(.caption2.monospaced()).foregroundStyle(Tactical.muted)
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

// MARK: - Lab
struct LabView: View {
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    TacticalPanel {
                        VStack(alignment: .leading, spacing: 8) {
                            MonoLabel(text: "PRODUCT LAB")
                            Text("Enclosure v3").font(.title3.bold()).foregroundStyle(Tactical.ink)
                            Text("STEP → STL → DXF export ready").font(.caption).foregroundStyle(Tactical.muted)
                        }
                    }
                    TacticalPanel {
                        VStack(alignment: .leading, spacing: 8) {
                            MonoLabel(text: "GRANTS")
                            Text("3 programme routes").font(.headline).foregroundStyle(Tactical.ink)
                            Text("Deadline 02 Dec 2026").font(.caption.monospaced()).foregroundStyle(Tactical.muted)
                        }
                    }
                    TacticalPanel {
                        VStack(alignment: .leading, spacing: 8) {
                            MonoLabel(text: "INTEGRATIONS")
                            integrationRow("Gmail", connected: true)
                            integrationRow("Composio", connected: true)
                            integrationRow("Notion", connected: false)
                        }
                    }
                }
                .padding(16)
            }
            .background(Tactical.bg)
            .navigationTitle("Lab")
        }
    }
    private func integrationRow(_ name: String, connected: Bool) -> some View {
        HStack {
            Text(name).font(.subheadline).foregroundStyle(Tactical.ink)
            Spacer()
            StatusDot(color: connected ? Tactical.ok : Tactical.muted)
        }
    }
}

// MARK: - More
struct MoreView: View {
    @Binding var offline: Bool
    var body: some View {
        NavigationStack {
            List {
                Section {
                    Toggle(isOn: $offline) { Label("Simulate offline", systemImage: "wifi.slash") }
                        .tint(Tactical.accent)
                }
                Section("Settings") {
                    Label("Connection", systemImage: "network")
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
