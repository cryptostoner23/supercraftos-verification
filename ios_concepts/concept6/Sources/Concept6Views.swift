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

enum NeuralJobColor {
    static func color(_ name: String) -> Color {
        switch name {
        case "ok": return Neural.ok
        case "danger": return Neural.danger
        case "accent": return Neural.accent
        default: return Neural.muted
        }
    }
}

enum NeuralStatus: String {
    case running = "Running", done = "Done", queued = "Queued", failed = "Failed"
    var color: Color {
        switch self {
        case .running: return Neural.accent
        case .done: return Neural.ok
        case .queued: return Neural.muted
        case .failed: return Neural.danger
        }
    }
}

// MARK: - Root
struct Concept6Root: View {
    @State private var tab = 0
    @State private var offline = false
    @StateObject private var backend = Concept6Backend(accessKey: Concept6BackendConfig.accessKey)
    var body: some View {
        TabView(selection: $tab) {
            NeuralMissionView(offline: $offline).environmentObject(backend).tabItem { Label("Mission", systemImage: "point.3.connected.trianglepath.dotted") }.tag(0)
            NeuralTasksView().environmentObject(backend).tabItem { Label("Tasks", systemImage: "checklist") }.tag(1)
            NeuralMeView().environmentObject(backend).tabItem { Label("Me", systemImage: "brain.head.profile") }.tag(2)
            NeuralLabView().environmentObject(backend).tabItem { Label("Lab", systemImage: "cube.transparent") }.tag(3)
            NeuralMoreView(offline: $offline).environmentObject(backend).tabItem { Label("More", systemImage: "ellipsis") }.tag(4)
        }
        .tint(Neural.accent)
        .preferredColorScheme(.dark)
        .task { await backend.refresh() }
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
    @EnvironmentObject private var backend: Concept6Backend
    @State private var showCompose = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    Text("Command Dashboard").font(.largeTitle.bold())
                    NeuralMono(text: "MISSION / NEURAL CORE")

                    if let err = backend.error, !backend.connected {
                        NeuralPanel {
                            VStack(alignment: .leading, spacing: 8) {
                                NeuralMono(text: "CONNECTION")
                                Text(err).font(.subheadline).foregroundStyle(Neural.danger)
                                Button("Retry") { Task { await backend.refresh() } }
                                    .buttonStyle(.bordered).tint(Neural.accent)
                            }
                        }
                    }

                    statusCard
                    usageCard
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
            .sheet(isPresented: $showCompose) {
                NeuralComposeSheet { prompt in
                    Task {
                        _ = await backend.dispatchJob(prompt)
                    }
                }
            }
        }
    }

    private var statusCard: some View {
        NeuralPanel {
            VStack(alignment: .leading, spacing: 12) {
                NeuralMono(text: "LIVE SYSTEM")
                HStack(spacing: 16) {
                    statBlock("\(backend.tools)", "tools")
                    statBlock("\(backend.integrations)", "integrations")
                    statBlock("\(backend.healthyIntegrations)", "healthy")
                    statBlock("\(backend.workflows)", "workflows")
                }
                HStack {
                    NeuralMono(text: "RUNTIME")
                    Spacer()
                    PulseDot(color: backend.runtime == "running" ? Neural.ok : Neural.warn)
                    Text(backend.runtime.uppercased()).font(.caption.monospaced()).foregroundStyle(Neural.ink)
                }
            }
        }
    }

    private var usageCard: some View {
        NeuralPanel {
            VStack(alignment: .leading, spacing: 10) {
                NeuralMono(text: "USAGE")
                HStack {
                    statSmall("Requests", "\(backend.usageRequests)")
                    statSmall("Tokens", "\(backend.usageTokens)")
                    statSmall("Cost", String(format: "$%.2f", backend.usageCost))
                }
            }
        }
    }

    private var feedCard: some View {
        NeuralPanel {
            VStack(alignment: .leading, spacing: 10) {
                NeuralMono(text: "RECENT TASKS")
                if backend.jobs.isEmpty {
                    Text("No tasks yet.").font(.subheadline).foregroundStyle(Neural.muted)
                } else {
                    ForEach(backend.jobs.prefix(3)) { job in
                        HStack(spacing: 8) {
                            Image(systemName: job.isRunning ? "bolt.fill" : (job.isCompleted ? "checkmark.circle.fill" : "circle"))
                                .foregroundStyle(NeuralJobColor.color(job.statusColorName))
                            Text(job.query).font(.subheadline).foregroundStyle(Neural.ink)
                                .lineLimit(1)
                            Spacer()
                            Text(job.status.uppercased())
                                .font(.system(size: 9, weight: .bold, design: .monospaced))
                                .foregroundStyle(NeuralJobColor.color(job.statusColorName))
                        }
                    }
                }
            }
        }
    }

    private func statBlock(_ v: String, _ label: String) -> some View {
        VStack(spacing: 2) {
            Text(v).font(.system(size: 24, weight: .bold, design: .rounded)).foregroundStyle(Neural.accent)
            Text(label).font(.caption).foregroundStyle(Neural.muted)
        }
        .frame(maxWidth: .infinity)
    }

    private func statSmall(_ label: String, _ v: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label).font(.caption).foregroundStyle(Neural.muted)
            Text(v).font(.headline.monospaced()).foregroundStyle(Neural.ink)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Compose (dispatches a real job)
struct NeuralComposeSheet: View {
    @Environment(\.dismiss) private var dismiss
    let onDispatch: (String) -> Void
    @State private var prompt = ""
    @State private var submitting = false

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 16) {
                NeuralMono(text: "AUTONOMOUS DISPATCH")
                TextEditor(text: $prompt)
                    .frame(height: 120).scrollContentBackground(.hidden).padding(10)
                    .background(RoundedRectangle(cornerRadius: 14).fill(Neural.surface2))
                Button {
                    submitting = true
                    onDispatch(prompt)
                    dismiss()
                } label: {
                    Text(submitting ? "Dispatching…" : "Dispatch run")
                        .font(.headline).frame(maxWidth: .infinity).padding(.vertical, 12)
                }
                .buttonStyle(.borderedProminent).tint(Neural.accent)
                .disabled(prompt.trimmingCharacters(in: .whitespaces).isEmpty || submitting)
            }
            .padding(20).background(Neural.bg)
            .navigationTitle("New task").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } } }
        }
        .presentationDetents([.medium])
        .presentationDragIndicator(.visible)
    }
}
