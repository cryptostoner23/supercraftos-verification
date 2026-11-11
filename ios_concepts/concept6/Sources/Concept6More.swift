import SwiftUI

// MARK: - Tasks
struct NeuralTasksView: View {
    @State private var tasks = [
        NeuralTask(title: "Research funding routes", status: .running, progress: 0.7),
        NeuralTask(title: "Draft Q3 proposal", status: .done, progress: 1.0),
        NeuralTask(title: "Compose follow-up", status: .queued, progress: 0),
    ]
    var body: some View {
        NavigationStack {
            List {
                ForEach(tasks) { t in
                    NavigationLink {
                        NeuralTaskDetailView(task: t)
                    } label: {
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Text(t.title).font(.headline).foregroundStyle(Neural.ink)
                                Spacer()
                                Text(t.status.rawValue.uppercased())
                                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                                    .padding(.horizontal, 8).padding(.vertical, 4)
                                    .background(t.status.color.opacity(0.16), in: Capsule())
                                    .foregroundStyle(t.status.color)
                            }
                            ProgressView(value: t.progress).tint(Neural.accent)
                        }
                        .padding(.vertical, 6)
                    }
                    .swipeActions {
                        Button(role: .destructive) {
                            tasks.removeAll { $0.id == t.id }
                        } label: { Label("Delete", systemImage: "trash") }
                    }
                }
            }
            .listStyle(.plain).scrollContentBackground(.hidden)
            .background(Neural.bg)
            .navigationTitle("Tasks")
        }
    }
}

struct NeuralTaskDetailView: View {
    let task: NeuralTask
    let steps = ["Decompose", "Recall", "Execute", "Draft", "Verify"]
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                NeuralPanel {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text(task.title).font(.title3.bold()).foregroundStyle(Neural.ink)
                            Spacer()
                            Text(task.status.rawValue.uppercased())
                                .font(.system(size: 10, weight: .bold, design: .monospaced))
                                .padding(.horizontal, 8).padding(.vertical, 4)
                                .background(task.status.color.opacity(0.16), in: Capsule())
                                .foregroundStyle(task.status.color)
                        }
                        ProgressView(value: task.progress).tint(Neural.accent)
                        Text("\(Int(task.progress * 100))%").font(.caption.monospaced()).foregroundStyle(Neural.muted)
                    }
                }
                NeuralPanel {
                    VStack(alignment: .leading, spacing: 10) {
                        NeuralMono(text: "EXECUTION LEDGER")
                        ForEach(Array(steps.enumerated()), id: \.offset) { i, s in
                            HStack(spacing: 10) {
                                Image(systemName: i < (task.status == .done ? steps.count : min(task.status == .running ? 2 : 0, steps.count)) ? "checkmark.circle.fill" : "circle")
                                    .foregroundStyle(i < (task.status == .done ? steps.count : min(task.status == .running ? 2 : 0, steps.count)) ? Neural.ok : (i == 2 && task.status == .running ? Neural.accent : Neural.muted))
                                Text(s).font(.subheadline).foregroundStyle(Neural.ink)
                                Spacer()
                                if i == 2 && task.status == .running {
                                    Text("LIVE").font(.caption2.monospaced().bold()).foregroundStyle(Neural.accent)
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
                            if let e = backend.error {
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
                                statBlock("\(backend.memoryCount)", "memories")
                                statBlock("\(backend.playbookCount)", "playbooks")
                            }
                            if let e = backend.error {
                                Text(e).font(.caption).foregroundStyle(Neural.danger)
                            }
                        }
                    }
                    NeuralPanel {
                        VStack(alignment: .leading, spacing: 10) {
                            NeuralMono(text: "MEMORY")
                            if backend.memories.isEmpty {
                                ForEach(0..<3, id: \.self) { i in
                                    HStack(alignment: .top, spacing: 10) {
                                        Image(systemName: "brain").foregroundStyle(Neural.accent)
                                        VStack(alignment: .leading, spacing: 2) {
                                            Text(["Prefers concise SwiftUI answers.", "Acme Q3 proposal in progress.", "Uses aloop.agent@gmail.com."][i])
                                                .font(.subheadline).foregroundStyle(Neural.ink)
                                            Text("confidence \(0.9 - Double(i) * 0.08)")
                                                .font(.caption2.monospaced()).foregroundStyle(Neural.muted)
                                        }
                                    }
                                }
                            } else {
                                ForEach(backend.memories, id: \.self) { note in
                                    HStack(alignment: .top, spacing: 10) {
                                        Image(systemName: "brain").foregroundStyle(Neural.accent)
                                        Text(note).font(.subheadline).foregroundStyle(Neural.ink)
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
    private func intentRow(_ name: String, _ v: Double) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(name).font(.subheadline).foregroundStyle(Neural.ink)
                Spacer()
                Text("\(Int(v * 100))%").font(.caption.monospaced()).foregroundStyle(Neural.muted)
            }
            ProgressView(value: v).tint(Neural.accent)
        }
    }
}

// MARK: - Lab
struct NeuralLabView: View {
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    NeuralPanel {
                        VStack(alignment: .leading, spacing: 8) {
                            NeuralMono(text: "PRODUCT LAB")
                            Text("Enclosure v3").font(.title3.bold()).foregroundStyle(Neural.ink)
                            Text("STEP → STL → DXF").font(.caption.monospaced()).foregroundStyle(Neural.muted)
                        }
                    }
                    NeuralPanel {
                        VStack(alignment: .leading, spacing: 8) {
                            NeuralMono(text: "GRANTS")
                            Text("3 programme routes").font(.headline).foregroundStyle(Neural.ink)
                            Text("Deadline 02 Dec 2026").font(.caption.monospaced()).foregroundStyle(Neural.muted)
                        }
                    }
                    NeuralPanel {
                        VStack(alignment: .leading, spacing: 8) {
                            NeuralMono(text: "INTEGRATIONS")
                            row("Gmail", connected: true)
                            row("Composio", connected: true)
                            row("Notion", connected: false)
                        }
                    }
                }
                .padding(16)
            }
            .background(Neural.bg)
            .navigationTitle("Lab")
        }
    }
    private func row(_ name: String, connected: Bool) -> some View {
        HStack {
            Text(name).font(.subheadline).foregroundStyle(Neural.ink)
            Spacer()
            PulseDot(color: connected ? Neural.ok : Neural.muted)
        }
    }
}

// MARK: - More
struct NeuralMoreView: View {
    @Binding var offline: Bool
    var body: some View {
        NavigationStack {
            List {
                Section {
                    Toggle(isOn: $offline) { Label("Simulate offline", systemImage: "wifi.slash") }
                        .tint(Neural.accent)
                }
                Section("Settings") {
                    Label("Connection", systemImage: "network")
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
