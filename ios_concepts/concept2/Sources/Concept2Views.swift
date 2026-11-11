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

enum JobStatusColor {
    static func color(_ name: String) -> Color {
        switch name {
        case "ok": return Tactical.ok
        case "danger": return Tactical.danger
        case "accent": return Tactical.accent
        default: return Tactical.muted
        }
    }
}

// MARK: - Root + Tab Bar
struct Concept2Root: View {
    @State private var tab = 0
    @State private var offline = false
    @StateObject private var backend = Concept2Backend(accessKey: BackendConfig.accessKey)
    var body: some View {
        TabView(selection: $tab) {
            MissionView(offline: $offline).environmentObject(backend).tabItem { Label("Mission", systemImage: "scope") }.tag(0)
            TasksView().environmentObject(backend).tabItem { Label("Tasks", systemImage: "checklist") }.tag(1)
            DigitalMeView().environmentObject(backend).tabItem { Label("Digital Me", systemImage: "brain.head.profile") }.tag(2)
            LabView().environmentObject(backend).tabItem { Label("Lab", systemImage: "cube.transparent") }.tag(3)
            MoreView(offline: $offline).environmentObject(backend).tabItem { Label("More", systemImage: "ellipsis") }.tag(4)
        }
        .tint(Tactical.accent)
        .preferredColorScheme(.dark)
        .task { await backend.refresh() }
        .overlay(alignment: .top) {
            if offline { OfflineBanner() }
        }
    }
}

struct BackendConfig {
    static var accessKey: String {
        (Bundle.main.object(forInfoDictionaryKey: "SUPERCRAFTOS_ACCESS_KEY") as? String) ?? ""
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
    @EnvironmentObject private var backend: Concept2Backend
    @State private var showCompose = false
    @State private var dispatchMessage: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    Text("Command Dashboard").font(.largeTitle.bold())
                    MonoLabel(text: "MISSION / CORE")

                    if let err = backend.error, !backend.connected {
                        TacticalPanel {
                            VStack(alignment: .leading, spacing: 8) {
                                MonoLabel(text: "CONNECTION")
                                Text(err).font(.subheadline).foregroundStyle(Tactical.danger)
                                Button("Retry") { Task { await backend.refresh() } }
                                    .buttonStyle(.bordered).tint(Tactical.accent)
                            }
                        }
                    }

                    healthPanel
                    usagePanel
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
            .sheet(isPresented: $showCompose) {
                ComposeSheet { prompt in
                    Task {
                        let ok = await backend.dispatchJob(prompt)
                        dispatchMessage = ok ? "Dispatched to your backend." : backend.error
                    }
                }
            }
        }
    }

    private var healthPanel: some View {
        TacticalPanel {
            VStack(alignment: .leading, spacing: 12) {
                MonoLabel(text: "SYSTEM HEALTH")
                HStack(spacing: 20) {
                    statBlock("\(backend.tools)", "tools")
                    statBlock("\(backend.integrations)", "integrations")
                    statBlock("\(backend.healthyIntegrations)", "healthy")
                    statBlock("\(backend.workflows)", "workflows")
                }
                HStack {
                    Text("RUNTIME").font(.caption.monospaced()).foregroundStyle(Tactical.muted)
                    Spacer()
                    StatusDot(color: backend.runtime == "running" ? Tactical.ok : Tactical.warn)
                    Text(backend.runtime.uppercased()).font(.caption.monospaced()).foregroundStyle(Tactical.ink)
                }
            }
        }
    }

    private var usagePanel: some View {
        TacticalPanel {
            VStack(alignment: .leading, spacing: 10) {
                MonoLabel(text: "USAGE")
                HStack {
                    statSmall("Requests", "\(backend.usageRequests)")
                    statSmall("Tokens", "\(backend.usageTokens)")
                    statSmall("Cost", String(format: "$%.2f", backend.usageCost))
                }
            }
        }
    }

    private var feedPanel: some View {
        TacticalPanel {
            VStack(alignment: .leading, spacing: 10) {
                MonoLabel(text: "RECENT TASKS")
                if backend.jobs.isEmpty {
                    Text("No tasks yet.").font(.subheadline).foregroundStyle(Tactical.muted)
                } else {
                    ForEach(backend.jobs.prefix(3)) { job in
                        HStack(spacing: 8) {
                            Image(systemName: job.isRunning ? "bolt.fill" : (job.isCompleted ? "checkmark.circle.fill" : "circle"))
                                .foregroundStyle(JobStatusColor.color(job.statusColorName))
                            Text(job.query).font(.subheadline).foregroundStyle(Tactical.ink)
                                .lineLimit(1)
                            Spacer()
                            Text(job.status.uppercased())
                                .font(.system(size: 9, weight: .bold, design: .monospaced))
                                .foregroundStyle(JobStatusColor.color(job.statusColorName))
                        }
                    }
                }
            }
        }
    }

    private func statBlock(_ v: String, _ label: String) -> some View {
        VStack(spacing: 2) {
            Text(v).font(.system(size: 24, weight: .bold, design: .rounded)).foregroundStyle(Tactical.accent)
            Text(label).font(.caption).foregroundStyle(Tactical.muted)
        }
        .frame(maxWidth: .infinity)
    }

    private func statSmall(_ label: String, _ v: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label).font(.caption).foregroundStyle(Tactical.muted)
            Text(v).font(.headline.monospaced()).foregroundStyle(Tactical.ink)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Compose sheet (dispatches a real job)
struct ComposeSheet: View {
    @Environment(\.dismiss) private var dismiss
    let onDispatch: (String) -> Void
    @State private var prompt = ""
    @State private var submitting = false

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 16) {
                MonoLabel(text: "AUTONOMOUS DISPATCH")
                TextEditor(text: $prompt)
                    .frame(height: 120)
                    .scrollContentBackground(.hidden)
                    .padding(10)
                    .background(RoundedRectangle(cornerRadius: 12).fill(Tactical.surface2))
                Button {
                    submitting = true
                    onDispatch(prompt)
                    dismiss()
                } label: {
                    Text(submitting ? "Dispatching…" : "Dispatch run")
                        .font(.headline).frame(maxWidth: .infinity).padding(.vertical, 12)
                }
                .buttonStyle(.borderedProminent).tint(Tactical.accent)
                .disabled(prompt.trimmingCharacters(in: .whitespaces).isEmpty || submitting)
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
