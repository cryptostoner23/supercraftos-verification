import SwiftUI

// MARK: - Palette / design tokens (Obsidian Tactical)
enum Tactical {
    static let bg = Color(red: 0.047, green: 0.043, blue: 0.039)        // #0C0B0A
    static let surface = Color(red: 0.098, green: 0.090, blue: 0.082)   // #191712
    static let surface2 = Color(red: 0.145, green: 0.133, blue: 0.121)  // #25221F
    static let line = Color.white.opacity(0.08)
    static let ink = Color(red: 0.93, green: 0.92, blue: 0.90)
    static let muted = Color(red: 0.66, green: 0.64, blue: 0.61)
    static let accent = Color(red: 0.878, green: 0.663, blue: 0.416)    // amber
    static let ok = Color(red: 0.42, green: 0.78, blue: 0.60)
    static let warn = Color(red: 0.90, green: 0.70, blue: 0.35)
    static let danger = Color(red: 0.82, green: 0.42, blue: 0.38)
}

struct TacticalPanel<Content: View>: View {
    let content: Content
    init(@ViewBuilder content: () -> Content) { self.content = content() }
    var body: some View {
        content
            .padding(16)
            .background(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .fill(Tactical.surface)
                    .overlay(
                        RoundedRectangle(cornerRadius: 18, style: .continuous)
                            .stroke(Tactical.line, lineWidth: 1)
                    )
            )
    }
}

struct MonoLabel: View {
    let text: String
    var body: some View {
        Text(text)
            .font(.system(size: 11, weight: .medium, design: .monospaced))
            .tracking(0.5)
            .foregroundStyle(Tactical.muted)
    }
}

struct StatusDot: View {
    let color: Color
    var body: some View {
        Circle().fill(color).frame(width: 8, height: 8)
    }
}

// MARK: - Models
struct AgentRun: Identifiable {
    let id = UUID()
    let name: String
    var step: Int = 0
    let steps: [String] = ["Plan scope", "Gather sources", "Draft output", "Verify & cite", "Hand off"]
    var active = true
    var started = Date()
}

struct TaskItem: Identifiable {
    let id = UUID()
    let title: String
    let status: TaskStatus
    let progress: Double
    let evidence: [String]
    var paused = false
}

enum TaskStatus: String {
    case running = "Running", done = "Done", queued = "Queued", blocked = "Blocked"
    var color: Color {
        switch self {
        case .running: return Tactical.accent
        case .done: return Tactical.ok
        case .queued: return Tactical.muted
        case .blocked: return Tactical.danger
        }
    }
}

struct MemoryEntry: Identifiable {
    let id = UUID()
    let note: String
    let tag: String
    let confidence: Double
}

// MARK: - Root + Tab Bar
struct Concept2Root: View {
    @State private var tab = 0
    @State private var offline = false
    var body: some View {
        TabView(selection: $tab) {
            MissionView(offline: $offline).tabItem { Label("Mission", systemImage: "scope") }.tag(0)
            TasksView().tabItem { Label("Tasks", systemImage: "checklist") }.tag(1)
            DigitalMeView().tabItem { Label("Digital Me", systemImage: "brain.head.profile") }.tag(2)
            LabView().tabItem { Label("Lab", systemImage: "cube.transparent") }.tag(3)
            MoreView(offline: $offline).tabItem { Label("More", systemImage: "ellipsis") }.tag(4)
        }
        .tint(Tactical.accent)
        .preferredColorScheme(.dark)
        .overlay(alignment: .top) {
            if offline { OfflineBanner() }
        }
    }
}

struct OfflineBanner: View {
    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "wifi.slash").foregroundStyle(Tactical.warn)
            Text("OFFLINE — agents paused").font(.caption.weight(.semibold)).foregroundStyle(Tactical.warn)
        }
        .padding(.horizontal, 14).padding(.vertical, 8)
        .background(.ultraThinMaterial, in: Capsule())
        .padding(.top, 54)
    }
}

// MARK: - Mission
struct MissionView: View {
    @Binding var offline: Bool
    @State private var runs: [AgentRun] = [AgentRun(name: "Yuki", step: 2), AgentRun(name: "Quill", step: 0)]
    @State private var showCompose = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    Text("Command Dashboard").font(.largeTitle.bold())
                    MonoLabel(text: "MISSION / CORE")
                    workersGrid
                    healthPanel
                    feedPanel
                }
                .padding(16)
            }
            .background(Tactical.bg)
            .navigationTitle("Mission")
            .safeAreaInset(edge: .bottom) {
                Button {
                    showCompose = true
                } label: {
                    Label("New autonomous task", systemImage: "plus")
                        .font(.headline)
                        .frame(maxWidth: .infinity).padding(.vertical, 14)
                }
                .buttonStyle(.borderedProminent)
                .tint(Tactical.accent)
                .padding(.horizontal, 16).padding(.bottom, 8)
                .disabled(offline)
            }
            .sheet(isPresented: $showCompose) { ComposeSheet { run in withAnimation { runs.insert(run, at: 0) } } }
        }
    }

    private var workersGrid: some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
            ForEach(runs.prefix(4)) { run in
                TacticalPanel {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            StatusDot(color: offline ? Tactical.muted : Tactical.accent)
                            MonoLabel(text: run.name.uppercased())
                            Spacer()
                            Text(run.active ? "RUN" : "IDLE")
                                .font(.system(size: 10, weight: .bold, design: .monospaced))
                                .foregroundStyle(offline ? Tactical.muted : Tactical.accent)
                        }
                        Text(run.steps[min(run.step, run.steps.count - 1)])
                            .font(.callout.weight(.medium)).foregroundStyle(Tactical.ink)
                        TimelineView(.periodic(from: run.started, by: 1)) { ctx in
                            MonoLabel(text: "ELAPSED \(Int(ctx.date.timeIntervalSince(run.started)))s")
                        }
                    }
                }
            }
        }
    }

    private var healthPanel: some View {
        TacticalPanel {
            VStack(alignment: .leading, spacing: 10) {
                MonoLabel(text: "SYSTEM HEALTH")
                HStack(spacing: 20) {
                    healthBar("AGENTS", 0.82)
                    healthBar("TOOLS", 0.94)
                    healthBar("MEMORY", 0.71)
                }
            }
        }
    }

    private func healthBar(_ name: String, _ v: Double) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            MonoLabel(text: name)
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(Tactical.surface2)
                    Capsule().fill(Tactical.accent).frame(width: geo.size.width * v)
                }
            }
            .frame(height: 6)
            Text("\(Int(v * 100))%").font(.caption.monospaced()).foregroundStyle(Tactical.muted)
        }
    }

    private var feedPanel: some View {
        TacticalPanel {
            VStack(alignment: .leading, spacing: 10) {
                MonoLabel(text: "EXECUTION FEED")
                ForEach(0..<3, id: \.self) { i in
                    HStack(spacing: 8) {
                        Image(systemName: ["doc.text", "globe", "checkmark.circle"][i])
                            .foregroundStyle(Tactical.accent)
                        Text(["Retrieved 3 sources", "Verified references", "Drafted reply"][i])
                            .font(.subheadline).foregroundStyle(Tactical.ink)
                        Spacer()
                        Text(String(format: "%.1fs", Double.random(in: 0.4...2.4)))
                            .font(.caption.monospaced()).foregroundStyle(Tactical.muted)
                    }
                }
            }
        }
    }
}

// MARK: - Compose sheet (true bottom sheet)
struct ComposeSheet: View {
    @Environment(\.dismiss) private var dismiss
    let onRun: (AgentRun) -> Void
    @State private var prompt = ""
    @State private var agent = "Yuki"

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 16) {
                MonoLabel(text: "AUTONOMOUS DISPATCH")
                TextEditor(text: $prompt)
                    .frame(height: 120)
                    .scrollContentBackground(.hidden)
                    .padding(10)
                    .background(RoundedRectangle(cornerRadius: 12).fill(Tactical.surface2))
                Picker("Agent", selection: $agent) {
                    Text("Yuki").tag("Yuki")
                    Text("Quill").tag("Quill")
                }
                .pickerStyle(.segmented)
                Button {
                    let run = AgentRun(name: agent, step: 0)
                    onRun(run)
                    dismiss()
                } label: {
                    Text("Dispatch run").font(.headline).frame(maxWidth: .infinity).padding(.vertical, 12)
                }
                .buttonStyle(.borderedProminent).tint(Tactical.accent)
                .disabled(prompt.trimmingCharacters(in: .whitespaces).isEmpty)
            }
            .padding(20)
            .background(Tactical.bg)
            .navigationTitle("New task")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } } }
        }
        .presentationDetents([.medium])
        .presentationDragIndicator(.visible)
    }
}
