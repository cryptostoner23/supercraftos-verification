import SwiftUI

// MARK: - Palette / design tokens (Neural Graph)
enum Neural {
    static let bg = Color(red: 0.047, green: 0.039, blue: 0.071)        // #0C0A12
    static let surface = Color(red: 0.094, green: 0.078, blue: 0.141)  // #181424
    static let surface2 = Color(red: 0.137, green: 0.114, blue: 0.20)  // #231D33
    static let line = Color.white.opacity(0.09)
    static let ink = Color(red: 0.92, green: 0.93, blue: 0.95)
    static let muted = Color(red: 0.62, green: 0.63, blue: 0.70)
    static let accent = Color(red: 0.42, green: 0.90, blue: 0.78)      // living teal
    static let ok = Color(red: 0.42, green: 0.78, blue: 0.60)
    static let warn = Color(red: 0.90, green: 0.70, blue: 0.35)
    static let danger = Color(red: 0.82, green: 0.42, blue: 0.46)
}

struct NeuralPanel<Content: View>: View {
    let content: Content
    init(@ViewBuilder content: () -> Content) { self.content = content() }
    var body: some View {
        content
            .padding(16)
            .background(
                RoundedRectangle(cornerRadius: 20, style: .continuous)
                    .fill(Neural.surface)
                    .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).stroke(Neural.line, lineWidth: 1))
            )
    }
}

struct NeuralMono: View {
    let text: String
    var body: some View {
        Text(text)
            .font(.system(size: 11, weight: .medium, design: .monospaced))
            .tracking(0.6).foregroundStyle(Neural.muted)
    }
}

struct PulseDot: View {
    let color: Color
    @State private var on = false
    var body: some View {
        Circle().fill(color).frame(width: 8, height: 8)
            .opacity(on ? 1 : 0.4)
            .onAppear { withAnimation(.easeInOut(duration: 1).repeatForever(autoreverses: true)) { on.toggle() } }
    }
}

// MARK: - Models
struct NeuralRun: Identifiable {
    let id = UUID()
    let name: String
    var step = 0
    let steps = ["Decompose", "Recall", "Execute", "Draft", "Verify"]
    var active = true
    var started = Date()
}

struct NeuralTask: Identifiable {
    let id = UUID()
    let title: String
    let status: NeuralStatus
    let progress: Double
}
enum NeuralStatus: String {
    case running = "Running", done = "Done", queued = "Queued"
    var color: Color {
        switch self {
        case .running: return Neural.accent
        case .done: return Neural.ok
        case .queued: return Neural.muted
        }
    }
}

// MARK: - Root
struct Concept6Root: View {
    @State private var tab = 0
    @State private var offline = false
    var body: some View {
        TabView(selection: $tab) {
            NeuralMissionView(offline: $offline).tabItem { Label("Mission", systemImage: "point.3.connected.trianglepath.dotted") }.tag(0)
            NeuralTasksView().tabItem { Label("Tasks", systemImage: "checklist") }.tag(1)
            NeuralMeView().tabItem { Label("Me", systemImage: "brain.head.profile") }.tag(2)
            NeuralLabView().tabItem { Label("Lab", systemImage: "cube.transparent") }.tag(3)
            NeuralMoreView(offline: $offline).tabItem { Label("More", systemImage: "ellipsis") }.tag(4)
        }
        .tint(Neural.accent)
        .preferredColorScheme(.dark)
        .overlay(alignment: .top) { if offline { NeuralOfflineBanner() } }
    }
}

struct NeuralOfflineBanner: View {
    var body: some View {
        Label("OFFLINE — agents paused", systemImage: "wifi.slash")
            .font(.caption.weight(.semibold)).foregroundStyle(Neural.warn)
            .padding(.horizontal, 14).padding(.vertical, 8)
            .background(.ultraThinMaterial, in: Capsule())
            .padding(.top, 54)
    }
}

// MARK: - Mission
struct NeuralMissionView: View {
    @Binding var offline: Bool
    @State private var runs = [NeuralRun(name: "Atlas", step: 3), NeuralRun(name: "Aria", step: 1)]
    @State private var showCompose = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    Text("Command Dashboard").font(.largeTitle.bold())
                    NeuralMono(text: "MISSION / NEURAL CORE")
                    topologyCard
                    runGrid
                    feedCard
                }
                .padding(16)
            }
            .background(Neural.bg)
            .navigationTitle("Mission")
            .safeAreaInset(edge: .bottom) {
                Button {
                    showCompose = true
                } label: {
                    Label("New autonomous task", systemImage: "plus").font(.headline)
                        .frame(maxWidth: .infinity).padding(.vertical, 14)
                }
                .buttonStyle(.borderedProminent).tint(Neural.accent)
                .padding(.horizontal, 16).padding(.bottom, 8)
                .disabled(offline)
            }
            .sheet(isPresented: $showCompose) { NeuralComposeSheet { run in withAnimation { runs.insert(run, at: 0) } } }
        }
    }

    private var topologyCard: some View {
        NeuralPanel {
            VStack(alignment: .leading, spacing: 12) {
                NeuralMono(text: "LIVE TOPOLOGY")
                ZStack {
                    RoundedRectangle(cornerRadius: 16).fill(Neural.surface2)
                    Canvas { ctx, size in
                        let c = CGPoint(x: size.width / 2, y: size.height / 2)
                        for i in 0..<6 {
                            let a = Double(i) / 6 * 2 * .pi
                            let p = CGPoint(x: c.x + cos(a) * 60, y: c.y + sin(a) * 60)
                            var path = Path(); path.move(to: c); path.addLine(to: p)
                            ctx.stroke(path, with: .color(Neural.accent.opacity(0.3)), lineWidth: 1)
                            ctx.fill(Path(ellipseIn: CGRect(x: p.x - 4, y: p.y - 4, width: 8, height: 8)), with: .color(Neural.accent))
                        }
                        ctx.fill(Path(ellipseIn: CGRect(x: c.x - 7, y: c.y - 7, width: 14, height: 14)), with: .color(Neural.accent))
                    }
                    .frame(height: 140)
                }
            }
        }
    }

    private var runGrid: some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
            ForEach(runs.prefix(4)) { run in
                NeuralPanel {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            PulseDot(color: offline ? Neural.muted : Neural.accent)
                            NeuralMono(text: run.name.uppercased())
                            Spacer()
                            Text(run.active ? "RUN" : "IDLE")
                                .font(.system(size: 10, weight: .bold, design: .monospaced))
                                .foregroundStyle(offline ? Neural.muted : Neural.accent)
                        }
                        Text(run.steps[min(run.step, run.steps.count - 1)])
                            .font(.callout.weight(.medium)).foregroundStyle(Neural.ink)
                        TimelineView(.periodic(from: run.started, by: 1)) { ctx in
                            NeuralMono(text: "ELAPSED \(Int(ctx.date.timeIntervalSince(run.started)))s")
                        }
                    }
                }
            }
        }
    }

    private var feedCard: some View {
        NeuralPanel {
            VStack(alignment: .leading, spacing: 10) {
                NeuralMono(text: "EXECUTION FEED")
                ForEach(0..<3, id: \.self) { i in
                    HStack(spacing: 8) {
                        Image(systemName: ["network", "doc.text", "checkmark.circle"][i])
                            .foregroundStyle(Neural.accent)
                        Text(["Fetched 4 sources", "Synthesized findings", "Verification passed"][i])
                            .font(.subheadline).foregroundStyle(Neural.ink)
                        Spacer()
                        Text(String(format: "%.1fs", Double.random(in: 0.4...2.4)))
                            .font(.caption.monospaced()).foregroundStyle(Neural.muted)
                    }
                }
            }
        }
    }
}

// MARK: - Compose
struct NeuralComposeSheet: View {
    @Environment(\.dismiss) private var dismiss
    let onRun: (NeuralRun) -> Void
    @State private var prompt = ""
    @State private var agent = "Atlas"

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 16) {
                NeuralMono(text: "AUTONOMOUS DISPATCH")
                TextEditor(text: $prompt)
                    .frame(height: 120).scrollContentBackground(.hidden).padding(10)
                    .background(RoundedRectangle(cornerRadius: 14).fill(Neural.surface2))
                Picker("Agent", selection: $agent) {
                    Text("Atlas").tag("Atlas")
                    Text("Aria").tag("Aria")
                }
                .pickerStyle(.segmented)
                Button {
                    onRun(NeuralRun(name: agent, step: 0)); dismiss()
                } label: {
                    Text("Dispatch run").font(.headline).frame(maxWidth: .infinity).padding(.vertical, 12)
                }
                .buttonStyle(.borderedProminent).tint(Neural.accent)
                .disabled(prompt.trimmingCharacters(in: .whitespaces).isEmpty)
            }
            .padding(20).background(Neural.bg)
            .navigationTitle("New task").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } } }
        }
        .presentationDetents([.medium])
        .presentationDragIndicator(.visible)
    }
}
