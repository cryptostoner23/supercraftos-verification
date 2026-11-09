import SwiftUI
import Charts
import SceneKit
import UIKit

// iOS 17+. Present ContentView() in the app target's WindowGroup.
enum ConsoleStyle {
    static let background = Color(red: 0.035, green: 0.055, blue: 0.086)
    static let panel = Color(red: 0.067, green: 0.106, blue: 0.161)
    static let pink = Color(red: 0.52, green: 0.93, blue: 0.81)
    static let cyan = Color(red: 0.22, green: 0.82, blue: 0.77)
    static let purple = Color(red: 0.64, green: 0.43, blue: 1)
    static let line = Color.white.opacity(0.10)
}

enum ConsoleScreen: String, CaseIterable, Identifiable {
    case mission = "Mission", tasks = "Tasks", memory = "Memory", digital_me = "Digital Me", quests = "Quests", products = "Product Lab", platforms = "Engine", grants = "Grant Ops", workflows = "Workflows", integrations = "Integrations", tools = "Tools", registrations = "Accounts", shortcuts = "Shortcuts", notes = "Notes"
    var id: String { rawValue }
    var icon: String {
        switch self {
        case .mission: return "point.3.connected.trianglepath.dotted"
        case .tasks: return "checklist"
        case .memory: return "brain"
        case .digital_me: return "laptop.compute"
        case .quests: return "map"
        case .products: return "cube.transparent"
        case .platforms: return "square.grid.3x3"
        case .grants: return "banknote"
        case .workflows: return "arrow.triangle.branch"
        case .integrations: return "network"
        case .tools: return "terminal"
        case .registrations: return "person.crop.rectangle.stack"
        case .shortcuts: return "arrow.triangle.branch"
        case .notes: return "note.text"
        }
    }

    init(destination: AppDestination) {
        switch destination {
        case .mission: self = .mission
        case .tasks: self = .tasks
        case .memory: self = .memory
        case .quests: self = .quests
        case .shortcuts: self = .shortcuts
        case .products: self = .products
        case .platforms: self = .platforms
        case .grants: self = .grants
        case .workflows: self = .workflows
        case .integrations: self = .integrations
        case .tools: self = .tools
        case .registrations: self = .registrations
        }
    }
}

private enum VisualMode: String, CaseIterable, Identifiable {
    case wiring = "Wiring", constellation = "Constellation", vortex = "Vortex", lattice = "Lattice"
    var id: String { rawValue }
}

private enum ConsoleSheet: String, Identifiable {
    case connection, compose
    var id: String { rawValue }
}

@MainActor
struct ContentView: View {
    @EnvironmentObject private var navigationModel: AppNavigationModel
    @StateObject private var store = BackendStore()
    @State private var selection: ConsoleScreen = .mission
    @State private var mode: VisualMode = .wiring
    @State private var sheet: ConsoleSheet?
    @State private var query = ""
    @State private var quickRequest = ""
    @State private var quickRequestKey = UUID().uuidString
    @State private var search = ""
    @State private var workflowFilter = "All"
    @State private var selectedWorkflow: AgentWorkflow?
    @State private var selectedMission: AutonomousJob?
    @State private var animate = true
    @State private var autoRefresh = true
    @Environment(\.horizontalSizeClass) private var sizeClass
    @Environment(\.scenePhase) private var scenePhase
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        Group {
            if sizeClass == .regular {
                HStack(spacing: 0) {
                    sidebar.frame(width: 230)
                    workspace
                }
            } else { workspace }
        }
        .background(ConsoleStyle.background).preferredColorScheme(.dark).tint(ConsoleStyle.pink)
        .task {
            if !store.backend.isEmpty { await store.refresh() }
        }
        .onReceive(navigationModel.$destination.compactMap { $0 }) { destination in
            selection = ConsoleScreen(destination: destination)
            search = ""
        }
        .task(id: autoRefresh && scenePhase == .active) {
            guard autoRefresh && scenePhase == .active else { return }
            while !Task.isCancelled {
                do { try await Task.sleep(for: .seconds(5)) } catch { return }
                if !store.backend.isEmpty { await store.refresh() }
            }
        }
        .sheet(item: $sheet) { item in
            switch item {
            case .connection: ConnectionSheet(store: store)
            case .compose: ComposeSheet(store: store)
            }
        }
        .sheet(item: $selectedMission) { job in AutonomousTaskDetail(store: store, initialJob: job) }
        .sheet(item: $selectedWorkflow) { workflow in WorkflowDetail(store: store, workflowID: workflow.id) }
    }

    private var sidebar: some View {
        VStack(alignment: .leading, spacing: 24) {
            brand.padding(.top, 24)
            Text("CONTROL SURFACE / 01").font(.system(size: 13, design: .monospaced)).foregroundStyle(.secondary)
            ScrollView {
                VStack(spacing: 8) {
                ForEach(ConsoleScreen.allCases) { screen in
                    Button { selection = screen; search = "" } label: {
                        Label(screen.rawValue, systemImage: screen.icon)
                            .font(.system(size: 17, weight: .medium, design: .monospaced))
                            .frame(maxWidth: .infinity, alignment: .leading).padding(12)
                            .foregroundStyle(selection == screen ? ConsoleStyle.pink : .gray)
                            .background(selection == screen ? ConsoleStyle.pink.opacity(0.09) : .clear)
                            .overlay(alignment: .leading) { if selection == screen { Rectangle().fill(ConsoleStyle.pink).frame(width: 2) } }
                    }.buttonStyle(.plain).accessibilityIdentifier("navigation-\(screen.rawValue)")
                }
            }
            }.accessibilityIdentifier("sidebar-navigation")
            Spacer(minLength: 0)
            Text("PYTHON / LANGGRAPH\nMCP / LARK / NOTION").font(.system(size: 14, design: .monospaced)).foregroundStyle(.secondary).lineSpacing(6)
            Button { sheet = .connection } label: { Label("Connection", systemImage: "slider.horizontal.3") }
                .font(.system(size: 16, design: .monospaced)).foregroundStyle(.white)
        }.padding(16).background(ConsoleStyle.panel).overlay(alignment: .trailing) { Rectangle().fill(ConsoleStyle.line).frame(width: 1) }
    }

    private var brand: some View {
        HStack(spacing: 8) {
            Text("S").font(.system(size: 25, weight: .black, design: .monospaced)).padding(7).background(ConsoleStyle.pink).foregroundStyle(.black)
            VStack(alignment: .leading, spacing: 0) {
                Text("SUPERCRAFT").font(.system(size: 16, weight: .heavy, design: .monospaced))
                Text("OPERATING SYSTEM").font(.system(size: 12, design: .monospaced)).foregroundStyle(.secondary)
            }
        }
    }

    private var workspace: some View {
        VStack(spacing: 0) {
            header
            if let error = store.error {
                HStack {
                    Image(systemName: "exclamationmark.triangle")
                    Text(error).lineLimit(2)
                    Spacer()
                    Button("Connect") { sheet = .connection }
                }.font(.system(size: 15, design: .monospaced)).foregroundStyle(.orange).padding(10).background(.orange.opacity(0.07))
            }
            if selection == .mission { mobileMission }
            else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 20) {
                        sectionHeading
                        if [.workflows, .integrations, .tools, .registrations].contains(selection) {
                            Label {
                                TextField("Search \(selection.rawValue.lowercased())", text: $search)
                                    .font(.body)
                            } icon: {
                                Image(systemName: "magnifyingglass").foregroundStyle(ConsoleStyle.cyan)
                            }
                            .padding(16)
                            .background(ConsoleStyle.panel, in: RoundedRectangle(cornerRadius: 16))
                            .overlay(RoundedRectangle(cornerRadius: 16).stroke(ConsoleStyle.line))
                        }
                        switch selection {
                        case .tasks: AutonomousTasksView(store: store, onCreate: { sheet = .compose })
                        case .memory: LearningView(store: store)
                        case .digital_me: DigitalMeView(store: store)
                        case .quests: QuestOperationsView(store: store)
                        case .workflows: workflows
                        case .integrations: integrations
                        case .tools: tools
                        case .registrations: AccountOperationsView(store: store)
                        case .shortcuts: ShortcutsHubView()
                        case .products: ProductLab(store: store)
                        case .platforms: PlatformHub(store: store)
                        case .grants: GrantOperations(store: store)
                        case .mission: EmptyView()
                        case .notes: AppleNotesView(store: store)
                        }
                    }.padding(18).frame(maxWidth: 1200, alignment: .leading).frame(maxWidth: .infinity)
                }.accessibilityIdentifier("workspace-scroll").refreshable { await store.refresh() }
            }
            if sizeClass != .regular { compactNavigation }
        }
    }

    private var sectionHeading: some View {
        VStack(alignment: .leading, spacing: 9) {
            HStack(spacing: 10) {
                Image(systemName: selection.icon)
                    .font(.title2.weight(.semibold))
                    .foregroundStyle(ConsoleStyle.cyan)
                    .frame(width: 44, height: 44)
                    .background(ConsoleStyle.cyan.opacity(0.12), in: RoundedRectangle(cornerRadius: 13))
                Text(selection.rawValue)
                    .font(.system(size: 31, weight: .bold, design: .rounded))
                    .foregroundStyle(.white)
            }
            Text(sectionDescription)
                .font(.system(size: 18))
                .foregroundStyle(.white.opacity(0.72))
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(.bottom, 6)
    }

    private var sectionDescription: String {
        switch selection {
        case .tasks: return "Run autonomous work and inspect its actual steps and files."
        case .grants: return "Screen funding programmes against a real project and prepare applications."
        case .products: return "Turn dimensions into a validated 3D solid and export manufacturing files."
        case .tools: return "Run installed capabilities and inspect their live responses."
        case .quests: return "Discover and execute supported reward actions."
        case .memory: return "Review the decisions and evidence the system has retained."
        case .digital_me: return "Manage your identity, memories, reasoning and plans."
        case .workflows: return "Open durable plans, checkpoints and completed artifacts."
        case .integrations: return "Inspect recorded provider health and connection evidence."
        case .registrations: return "Track account setup and verification outcomes."
        case .platforms: return "See the capabilities the runtime can actually route and measure."
        case .shortcuts: return "Launch frequently used actions from your device."
        case .mission: return ""
        case .notes: return "Import notes from Apple Notes on this device and review them."
        }
    }

    private var header: some View {
        HStack(spacing: 12) {
            if sizeClass != .regular { Text("SC / OS").font(.system(size: 17, weight: .black, design: .monospaced)).foregroundStyle(ConsoleStyle.pink) }
            Circle().fill(store.error == nil && store.status != nil ? ConsoleStyle.cyan : .orange).frame(width: 5, height: 5)
            Text((store.agentStatus?.workers ?? 0) > 0 ? "\(store.agentStatus!.workers) WORKERS ONLINE" : (store.status != nil ? "CONNECTED" : "OFFLINE")).font(.system(size: 14, design: .monospaced))
            if sizeClass == .regular {
                Text("\(store.status?.tools ?? 0) TOOLS   /   \(store.status?.awaitingApproval ?? 0) GATES").font(.system(size: 14, design: .monospaced)).foregroundStyle(.secondary)
            }
            Spacer(minLength: 0)
            if store.busy { ProgressView().controlSize(.small) }
            Button { sheet = .compose } label: { Image(systemName: "plus") }.accessibilityLabel("New autonomous task")
            Button { Task { await store.refresh() } } label: { Image(systemName: "arrow.clockwise") }.disabled(store.busy).accessibilityLabel("Refresh backend")
            Button { sheet = .connection } label: { Image(systemName: "gearshape") }.accessibilityLabel("Connection settings")
        }.foregroundStyle(.white).padding(.horizontal, 16).frame(height: 60)
            .background(ConsoleStyle.panel).overlay(alignment: .bottom) { Rectangle().fill(ConsoleStyle.line).frame(height: 1) }
    }

    private var compactNavigation: some View {
        HStack(spacing: 0) {
            compactTab(.mission, title: "Home", icon: "bubble.left.and.bubble.right")
            compactTab(.tasks, title: "Tasks", icon: "checklist")
            compactTab(.grants, title: "Funding", icon: "banknote")
            compactTab(.products, title: "Build", icon: "cube.transparent")
            Menu {
                ForEach(ConsoleScreen.allCases.filter { ![.mission, .tasks, .grants, .products].contains($0) }) { screen in
                    Button { selection = screen; search = "" } label: {
                        Label(screen.rawValue, systemImage: screen.icon)
                    }
                }
            } label: {
                VStack(spacing: 4) {
                    Image(systemName: "square.grid.2x2").font(.title3)
                    Text("More").font(.subheadline)
                }.frame(maxWidth: .infinity).foregroundStyle([ConsoleScreen.mission, .tasks, .grants, .products].contains(selection) ? Color.gray : ConsoleStyle.pink)
            }.accessibilityIdentifier("navigation-more")
        }
        .padding(.vertical, 8)
        .accessibilityIdentifier("compact-navigation")
        .background(ConsoleStyle.panel)
        .overlay(alignment: .top) { Rectangle().fill(ConsoleStyle.line).frame(height: 1) }
    }

    private func compactTab(_ screen: ConsoleScreen, title: String, icon: String) -> some View {
        Button { selection = screen; search = "" } label: {
            VStack(spacing: 4) {
                Image(systemName: icon).font(.title3)
                Text(title).font(.subheadline)
            }.frame(maxWidth: .infinity).foregroundStyle(selection == screen ? ConsoleStyle.pink : .gray)
        }.buttonStyle(.plain).accessibilityIdentifier("navigation-\(screen.rawValue)")
    }

    private var mobileMission: some View {
        MissionConversation(store: store, connect: { sheet = .connection }, details: { selectedMission = $0 })
            .safeAreaInset(edge: .bottom, spacing: 0) { quickComposer }
            .accessibilityIdentifier("mobile-mission")
    }

    private var mobileHero: some View {
        ZStack(alignment: .topLeading) {
            RoundedRectangle(cornerRadius: 28)
                .fill(LinearGradient(colors: [ConsoleStyle.purple.opacity(0.32), ConsoleStyle.pink.opacity(0.16), ConsoleStyle.panel],
                                     startPoint: .topLeading, endPoint: .bottomTrailing))
            Circle()
                .fill(RadialGradient(colors: [ConsoleStyle.pink.opacity(0.33), .clear], center: .center, startRadius: 0, endRadius: 150))
                .frame(width: 300, height: 300)
                .offset(x: 170, y: -125)
                .accessibilityHidden(true)
            Circle().stroke(ConsoleStyle.cyan.opacity(0.18), lineWidth: 1)
                .frame(width: 240, height: 240).offset(x: 220, y: -110).accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 8) {
                    Circle().fill(store.status == nil ? Color.orange : ConsoleStyle.cyan).frame(width: 8, height: 8)
                    Text(store.status == nil ? "AWAITING CONNECTION" : "SYSTEM ONLINE")
                        .font(.subheadline.weight(.bold)).tracking(1.5)
                    Spacer()
                    Image(systemName: "sparkle").font(.title3).foregroundStyle(ConsoleStyle.cyan)
                }.foregroundStyle(ConsoleStyle.cyan)
                Text("Make the next\nthing real.")
                    .font(.system(.largeTitle, design: .rounded, weight: .bold))
                    .foregroundStyle(.white)
                    .fixedSize(horizontal: false, vertical: true)
                Text("Start a mission. Track every step. Keep the result.")
                    .font(.body).foregroundStyle(.white.opacity(0.78))
                HStack(spacing: 8) {
                    heroMetric("\(store.jobs.count)", caption: "TASKS")
                    heroMetric("\(store.agentStatus?.workers ?? 0)", caption: "WORKERS")
                    heroMetric("\(store.status?.tools ?? 0)", caption: "TOOLS")
                }.padding(.top, 4)
            }.padding(22)
        }
        .frame(maxWidth: .infinity, minHeight: 250, alignment: .topLeading)
        .clipShape(RoundedRectangle(cornerRadius: 28))
        .overlay(RoundedRectangle(cornerRadius: 28).stroke(.white.opacity(0.12), lineWidth: 1))
        .accessibilityElement(children: .contain)
    }

    private func heroMetric(_ value: String, caption: String) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(value).font(.title2.bold()).monospacedDigit()
            Text(caption).font(.caption.weight(.semibold)).tracking(1).foregroundStyle(.white.opacity(0.65))
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(10)
        .background(.white.opacity(0.08), in: RoundedRectangle(cornerRadius: 12))
    }

    private var mobileActions: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Launch a workflow")
                .font(.title2.bold())
                .foregroundStyle(.white)
            LazyVGrid(columns: [GridItem(.flexible(), spacing: 12), GridItem(.flexible(), spacing: 12)], spacing: 12) {
                actionCard("Build a product", subtitle: "3D CAD + exports", icon: "cube.transparent", tint: ConsoleStyle.cyan, destination: .products)
                actionCard("Find funding", subtitle: "Screen + draft", icon: "banknote", tint: ConsoleStyle.purple, destination: .grants)
                actionCard("Run a tool", subtitle: "Live MCP actions", icon: "terminal", tint: ConsoleStyle.pink, destination: .tools)
                actionCard("Track tasks", subtitle: "Steps + files", icon: "checklist", tint: ConsoleStyle.cyan, destination: .tasks)
            }
        }
    }

    private func actionCard(_ title: String, subtitle: String, icon: String, tint: Color, destination: ConsoleScreen) -> some View {
        Button { selection = destination; search = "" } label: {
            VStack(alignment: .leading, spacing: 10) {
                Image(systemName: icon)
                    .font(.title2.weight(.medium))
                    .foregroundStyle(tint)
                    .frame(width: 45, height: 45)
                    .background(tint.opacity(0.13), in: RoundedRectangle(cornerRadius: 13))
                Spacer(minLength: 2)
                Text(title).font(.system(size: 19, weight: .semibold, design: .rounded)).foregroundStyle(.white)
                Text(subtitle).font(.system(size: 15)).foregroundStyle(.white.opacity(0.7))
                Image(systemName: "arrow.up.right").font(.caption.bold()).foregroundStyle(tint)
                    .frame(maxWidth: .infinity, alignment: .trailing)
            }
            .frame(maxWidth: .infinity, minHeight: 146, alignment: .leading)
            .padding(16)
            .background(ConsoleStyle.panel, in: RoundedRectangle(cornerRadius: 20))
            .overlay(RoundedRectangle(cornerRadius: 20).stroke(tint.opacity(0.28)))
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("mission-action-\(destination.rawValue)")
    }

    private var quickComposer: some View {
        HStack(alignment: .bottom, spacing: 10) {
            TextField("Ask SuperCraftOS to build or research…", text: $quickRequest, axis: .vertical)
                .font(.body).lineLimit(2...5).padding(12)
                .background(ConsoleStyle.background, in: RoundedRectangle(cornerRadius: 16))
                .onChange(of: quickRequest) { _, _ in quickRequestKey = UUID().uuidString }
                .accessibilityIdentifier("quick-task-request")
            Button {
                let request = quickRequest.trimmingCharacters(in: .whitespacesAndNewlines)
                let key = quickRequestKey
                Task {
                    if await store.submitTask(query: request, maxSteps: 24, runAt: nil, idempotencyKey: key) != nil {
                        quickRequest = ""
                    }
                }
            } label: {
                Image(systemName: "arrow.up").font(.title3.bold())
                    .frame(width: 46, height: 46)
                    .background(ConsoleStyle.pink, in: Circle()).foregroundStyle(.black)
            }
            .disabled(store.mutating || store.backend.isEmpty || !(3...12000).contains(quickRequest.trimmingCharacters(in: .whitespacesAndNewlines).count))
            .accessibilityLabel("Send task")
        }
        .padding(12)
        .background(ConsoleStyle.panel)
        .overlay(alignment: .top) { Rectangle().fill(ConsoleStyle.line).frame(height: 1) }
    }

    private var mission: some View {
        GeometryReader { geometry in
            let wide = geometry.size.width > 850
            VStack(spacing: 0) {
                HStack {
                    VStack(alignment: .leading, spacing: 3) {
                        Text("THE EXECUTION FIELD").font(.system(size: wide ? 27 : 22, weight: .black, design: .monospaced))
                        Text("Topology + observed state · no inferred execution traces")
                            .font(.system(size: 13, design: .monospaced)).foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button { animate.toggle() } label: { Image(systemName: animate ? "pause.fill" : "play.fill") }
                        .accessibilityLabel(animate ? "Pause visual motion" : "Resume visual motion")
                }.padding(14)
                HStack(spacing: 0) {
                    ForEach(VisualMode.allCases) { visual in
                        Button { withAnimation(.easeInOut(duration: 0.25)) { mode = visual } } label: {
                            Text(visual.rawValue.uppercased()).font(.system(size: 14, weight: .bold, design: .monospaced))
                                .frame(maxWidth: .infinity).padding(.vertical, 10)
                                .foregroundStyle(mode == visual ? ConsoleStyle.pink : .gray)
                                .overlay(alignment: .bottom) { Rectangle().fill(mode == visual ? ConsoleStyle.pink : ConsoleStyle.line).frame(height: 2) }
                        }.buttonStyle(.plain)
                    }
                }
                HStack(spacing: 0) {
                    if wide { operatorRail.frame(width: 155) }
                    ExecutionField(store: store, mode: mode, animated: animate && !reduceMotion && scenePhase == .active)
                }
                HStack(spacing: 10) {
                    Button(store.status?.runtime == "running" ? "STOP RUNTIME" : "START RUNTIME") {
                        Task { await store.perform(store.status?.runtime == "running" ? "/api/runtime/stop" : "/api/runtime/start") }
                    }.buttonStyle(.bordered).disabled(store.busy || store.status == nil)
                    Button("NEW TASK") { sheet = .compose }.buttonStyle(.borderedProminent)
                    Spacer(minLength: 0)
                    Text("\(store.workflows.count) RUNS").foregroundStyle(.secondary)
                }.font(.system(size: 14, weight: .bold, design: .monospaced)).padding(10).background(ConsoleStyle.panel)
                telemetry.frame(height: wide ? 215 : 185)
            }
        }
    }

    private var operatorRail: some View {
        VStack(alignment: .leading, spacing: 18) {
            microTitle("OPERATORS / STATE")
            ForEach(Array(operatorStates.enumerated()), id: \.offset) { index, item in
                VStack(alignment: .leading, spacing: 7) {
                    HStack { Text(item.0); Spacer(); Text(String(format: "%02ld", index + 1)).foregroundStyle(.secondary) }
                    Text(item.1.uppercased()).foregroundStyle(index % 2 == 0 ? ConsoleStyle.pink : ConsoleStyle.cyan)
                    Rectangle().fill(ConsoleStyle.line).frame(height: 2)
                }.font(.system(size: 14, design: .monospaced))
            }
            Spacer()
            Text("STATE IS POLLED\nEVERY 5 SECONDS\nWHILE ACTIVE").font(.system(size: 13, design: .monospaced)).foregroundStyle(.secondary).lineSpacing(4)
        }.padding(12).background(ConsoleStyle.panel.opacity(0.6))
    }

    private var operatorStates: [(String, String)] {
        [("RUNTIME", store.status?.runtime ?? "unknown"),
         ("PLANNER / BUILDER", store.status?.runtimeSnapshot?.mode ?? "unknown"),
         ("APPROVAL", "\(store.status?.awaitingApproval ?? 0) pending"),
         ("LARK", store.status?.runtimeSnapshot?.lark ?? "unknown"),
         ("SANDBOX", store.status?.runtimeSnapshot?.sandbox ?? "unknown")]
    }

    private var telemetry: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(alignment: .top, spacing: 1) {
                terminalPanel("PROCESS / MEMORY", width: 220) {
                    if store.samples.count > 1 {
                        Chart(store.samples) { sample in
                            LineMark(x: .value("Time", sample.date), y: .value("MB", sample.memoryMB)).foregroundStyle(ConsoleStyle.pink)
                        }.chartXAxis(.hidden).chartYAxis(.hidden).frame(height: 60)
                    } else { Text("Awaiting live samples").font(.system(size: 15, design: .monospaced)).foregroundStyle(.secondary).frame(height: 60) }
                    Text(store.status.map { String(format: "%.1f / %.0f MB", $0.memoryMB, $0.memoryLimitMB) } ?? "NO SAMPLE")
                        .font(.system(size: 16, design: .monospaced)).foregroundStyle(ConsoleStyle.cyan)
                }
                terminalPanel("TOKEN ECONOMY", width: 195) {
                    telemetryRow("INPUT", "\(store.status?.usage?.inputTokens ?? 0)")
                    telemetryRow("OUTPUT", "\(store.status?.usage?.outputTokens ?? 0)")
                    telemetryRow("REQUESTS", "\(store.status?.usage?.requests ?? 0)")
                    Text((store.status?.usage?.unpricedRequests ?? 0) > 0 ? "COST INCOMPLETE / UNPRICED" : String(format: "EST. $%.4f", store.status?.usage?.costUSD ?? 0))
                        .font(.system(size: 13, design: .monospaced)).foregroundStyle(ConsoleStyle.pink)
                }
                terminalPanel("AGENT STATES", width: 170) {
                    telemetryRow("RUNTIME", store.status?.runtime ?? "unknown")
                    telemetryRow("MODE", store.status?.runtimeSnapshot?.mode ?? "unknown")
                    telemetryRow("GATES", "\(store.status?.awaitingApproval ?? 0) pending")
                    telemetryRow("LARK", store.status?.runtimeSnapshot?.lark ?? "unknown")
                    telemetryRow("SANDBOX", store.status?.runtimeSnapshot?.sandbox ?? "unknown")
                }
                terminalPanel("INTEGRATION MATRIX", width: 225) {
                    LazyVGrid(columns: Array(repeating: GridItem(.fixed(16), spacing: 4), count: 9), spacing: 4) {
                        ForEach(store.integrations) { integration in
                            Rectangle().fill(healthy(integration.status) ? ConsoleStyle.cyan.opacity(0.7) : ConsoleStyle.pink.opacity(0.55))
                                .frame(height: 14).accessibilityLabel("\(integration.name): \(integration.status)")
                        }
                    }
                    Text("\(store.status?.healthyIntegrations ?? 0) / \(store.integrations.count) HEALTHY")
                        .font(.system(size: 14, design: .monospaced)).foregroundStyle(.secondary)
                }
                terminalPanel("RUN LOG / LIVE", width: 320) {
                    if store.log.isEmpty {
                        Text("Awaiting first backend sync").font(.system(size: 14, design: .monospaced)).foregroundStyle(.secondary)
                    }
                    ForEach(store.log.prefix(9)) { entry in
                        HStack(spacing: 6) {
                            Circle().fill(logTint(entry.level)).frame(width: 4, height: 4)
                            Text(entry.message).lineLimit(1).foregroundStyle(logTint(entry.level))
                            Spacer(minLength: 0)
                        }.font(.system(size: 13, design: .monospaced))
                    }
                }
                terminalPanel("CHECKPOINTS / RECENT", width: 290) {
                    if store.workflows.isEmpty { Text("No recorded workflows").foregroundStyle(.secondary).font(.system(size: 15, design: .monospaced)) }
                    ForEach(store.workflows.prefix(4)) { workflow in
                        Button { selectedWorkflow = workflow } label: {
                            HStack { Text(String(workflow.id.prefix(8))).foregroundStyle(ConsoleStyle.purple); Text(workflow.status ?? "unknown").lineLimit(1) }
                                .font(.system(size: 14, design: .monospaced))
                        }.buttonStyle(.plain)
                    }
                }
            }
        }.background(ConsoleStyle.line)
    }

    private var workflows: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Picker("Status", selection: $workflowFilter) {
                    ForEach(["All", "Approval", "Completed", "Failed"], id: \.self) { Text($0).tag($0) }
                }.pickerStyle(.menu)
                Spacer()
                Button { sheet = .compose } label: { Label("New autonomous task", systemImage: "plus") }.buttonStyle(.borderedProminent)
            }
            ForEach(store.workflows.filter { workflow in
                let matchesSearch = search.isEmpty || ((workflow.query ?? "") + workflow.id).localizedCaseInsensitiveContains(search)
                let matchesStatus = workflowFilter == "All" || (workflowFilter == "Approval" && workflow.status == "awaiting_approval") || (workflowFilter == "Completed" && workflow.status == "completed") || (workflowFilter == "Failed" && workflow.status == "failed")
                return matchesSearch && matchesStatus
            }) { workflow in
                Button { selectedWorkflow = workflow } label: {
                    VStack(alignment: .leading, spacing: 10) {
                        HStack { Text(String(workflow.id.prefix(8))).foregroundStyle(ConsoleStyle.purple); Spacer(); StatusTag(status: workflow.status ?? "unknown") }
                        Text(workflow.query ?? "Workflow").font(.system(size: 20, weight: .semibold)).foregroundStyle(.white)
                        Text((workflow.artifact ?? workflow.plan ?? workflow.error ?? "Open checkpoint").prefix(160)).font(.system(size: 16, design: .monospaced)).foregroundStyle(.secondary).lineLimit(3)
                    }.consolePanel()
                }.buttonStyle(.plain).accessibilityIdentifier("workflow-row")
            }
            if store.workflows.isEmpty { emptyState("NO CHECKPOINTS", detail: "Submit a task to run the planner and builder.") }
        }
    }

    private var integrations: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 280))], spacing: 12) {
            ForEach(store.integrations.filter { search.isEmpty || ($0.name + $0.status).localizedCaseInsensitiveContains(search) }) { integration in
                VStack(alignment: .leading, spacing: 12) {
                    HStack { Image(systemName: "network").foregroundStyle(ConsoleStyle.cyan); Text(integration.name).fontWeight(.bold); Spacer() }
                    StatusTag(status: integration.status)
                    if let latency = integration.latencyMS { Text(String(format: "%.0f ms / recorded check", latency)).font(.system(size: 16, design: .monospaced)).foregroundStyle(.secondary) }
                    Text(integration.detail ?? "").font(.body).foregroundStyle(.secondary).textSelection(.enabled)
                    Text("SAVED HEALTH EVIDENCE").font(.system(size: 13, design: .monospaced)).foregroundStyle(.secondary)
                }.consolePanel()
            }
            if store.integrations.isEmpty { emptyState("NO HEALTH EVIDENCE", detail: "Connect to the backend to retrieve recorded checks.") }
        }
    }

    private var tools: some View {
        VStack(spacing: 12) {
            LocalUtilityPanel()
            ForEach(store.tools.filter { search.isEmpty || ($0.name + ($0.description ?? "")).localizedCaseInsensitiveContains(search) }) { tool in
                ToolExecutionPanel(store: store, tool: tool)
            }
            if store.tools.isEmpty { emptyState("NO TOOL CATALOG", detail: "Connect to discover the backend's MCP tools.") }
        }
    }

    private var registrations: some View {
        VStack(spacing: 12) {
            ForEach(store.registrations.filter { search.isEmpty || ($0.name + $0.status).localizedCaseInsensitiveContains(search) }) { registration in
                VStack(alignment: .leading, spacing: 12) {
                    HStack { Text(registration.name.uppercased()).font(.system(size: 19, weight: .bold, design: .monospaced)); Spacer(); StatusTag(status: registration.status) }
                    Text(registration.detail ?? "Recorded locally").font(.system(size: 17)).foregroundStyle(.secondary)
                }.frame(maxWidth: .infinity, alignment: .leading).consolePanel()
            }
            if store.registrations.isEmpty { emptyState("NO ACCOUNT EVIDENCE", detail: "Registration outcomes will appear after backend synchronization.") }
            Text("Credentials remain in the server environment and encrypted vault.").font(.body).foregroundStyle(.secondary)
        }
    }

    private func emptyState(_ title: String, detail: String) -> some View {
        VStack(alignment: .leading, spacing: 8) { Text(title).foregroundStyle(ConsoleStyle.pink); Text(detail).foregroundStyle(.secondary) }
            .font(.system(size: 17, design: .monospaced)).frame(maxWidth: .infinity, alignment: .leading).consolePanel()
    }

    private func microTitle(_ title: String) -> some View { Text(title).font(.system(size: 13, weight: .bold, design: .monospaced)).foregroundStyle(.secondary) }
    private func telemetryRow(_ key: String, _ value: String) -> some View {
        HStack { Text(key).foregroundStyle(.secondary); Spacer(); Text(value).foregroundStyle(ConsoleStyle.cyan) }.font(.system(size: 15, design: .monospaced))
    }
    private func terminalPanel<Content: View>(_ title: String, width: CGFloat, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 10) { microTitle(title); content(); Spacer(minLength: 0) }
            .padding(12).frame(width: width, alignment: .leading).frame(maxHeight: .infinity).background(ConsoleStyle.panel)
    }
}

private func healthy(_ status: String) -> Bool {
    ["active", "authenticated", "reachable", "verified", "passed", "ready", "completed", "credential_present"].contains(status)
}

private func logTint(_ level: String) -> Color {
    switch level {
    case "error": return .orange
    case "warn": return ConsoleStyle.pink
    case "task": return ConsoleStyle.purple
    case "ok", "state": return ConsoleStyle.cyan
    default: return .gray
    }
}

private struct StatusTag: View {
    let status: String
    var body: some View {
        Text(status.replacingOccurrences(of: "_", with: " ").uppercased())
            .font(.system(size: 13, weight: .bold, design: .monospaced)).lineLimit(2)
            .padding(.horizontal, 7).padding(.vertical, 5)
            .foregroundStyle(healthy(status) ? ConsoleStyle.cyan : ConsoleStyle.pink)
            .background((healthy(status) ? ConsoleStyle.cyan : ConsoleStyle.pink).opacity(0.1))
    }
}

private extension View {
    func consolePanel() -> some View {
        padding(18)
            .background(ConsoleStyle.panel, in: RoundedRectangle(cornerRadius: 18))
            .overlay(RoundedRectangle(cornerRadius: 18).stroke(ConsoleStyle.line, lineWidth: 1))
    }
}

private struct FieldNode: Identifiable {
    let id: String
    let title: String
    let subtitle: String
    let position: CGPoint
    let tint: Color
}

@MainActor
private struct ExecutionField: View {
    @ObservedObject var store: BackendStore
    let mode: VisualMode
    let animated: Bool
    @State private var zoom: CGFloat = 1
    @State private var offset: CGSize = .zero
    @GestureState private var drag: CGSize = .zero
    @GestureState private var pinch: CGFloat = 1
    @State private var selectedID: String?
    private let world = CGSize(width: 1100, height: 650)

    private var nodes: [FieldNode] {
        var result = [
            FieldNode(id: "input", title: "REQUEST", subtitle: "\(store.workflows.count) checkpoints", position: CGPoint(x: 60, y: 285), tint: ConsoleStyle.pink),
            FieldNode(id: "planner", title: "PLANNER", subtitle: store.status?.runtimeSnapshot?.mode ?? "unknown", position: CGPoint(x: 300, y: 150), tint: ConsoleStyle.purple),
            FieldNode(id: "builder", title: "BUILDER", subtitle: "artifact synthesis", position: CGPoint(x: 535, y: 285), tint: ConsoleStyle.pink),
            FieldNode(id: "approval", title: "APPROVAL GATE", subtitle: "\(store.status?.awaitingApproval ?? 0) pending", position: CGPoint(x: 770, y: 150), tint: .orange),
            FieldNode(id: "checkpoint", title: "CHECKPOINT", subtitle: "durable state", position: CGPoint(x: 770, y: 465), tint: ConsoleStyle.cyan),
            FieldNode(id: "mcp", title: "MCP CATALOG", subtitle: "\(store.tools.count) tools", position: CGPoint(x: 300, y: 465), tint: ConsoleStyle.cyan)
        ]
        for (index, tool) in store.tools.prefix(5).enumerated() {
            result.append(FieldNode(id: "tool-" + tool.id, title: tool.name, subtitle: "registered tool", position: CGPoint(x: 55 + Double(index % 3) * 240, y: index < 3 ? 35 : 575), tint: ConsoleStyle.cyan))
        }
        return result
    }

    private var modeTitle: String {
        switch mode {
        case .wiring: return "LANGGRAPH / TOPOLOGY"
        case .constellation: return "CAPABILITY / CLUSTERS"
        case .vortex: return "EXECUTION / FIELD"
        case .lattice: return "NEURAL / LATTICE"
        }
    }

    private var modeHint: String {
        switch mode {
        case .wiring: return "Tap a node · drag to pan · pinch to zoom"
        case .constellation: return "Ambient motion · not execution throughput"
        case .vortex: return "Ambient motion · not execution throughput"
        case .lattice: return "Rotating projection · drag to pan · pinch to zoom"
        }
    }

    var body: some View {
        GeometryReader { geometry in
            let scale = min(geometry.size.width / world.width, geometry.size.height / world.height) * zoom * pinch
            ZStack(alignment: .topLeading) {
                TimelineView(.animation(minimumInterval: 1.0 / 20, paused: !animated || mode == .wiring)) { timeline in
                    Canvas { context, size in
                        let time = animated ? timeline.date.timeIntervalSinceReferenceDate : 0
                        drawGrid(context: &context, size: size)
                        let translation = CGSize(width: (size.width - world.width * scale) / 2 + offset.width + drag.width,
                                                 height: (size.height - world.height * scale) / 2 + offset.height + drag.height)
                        context.translateBy(x: translation.width, y: translation.height)
                        context.scaleBy(x: scale, y: scale)
                        switch mode {
                        case .wiring: drawWiring(context: &context, time: time)
                        case .constellation: drawConstellation(context: &context, time: time)
                        case .vortex: drawVortex(context: &context, time: time)
                        case .lattice: drawLattice(context: &context, time: time)
                        }
                    }
                }
                .accessibilityLabel("\(mode.rawValue) visualization of runtime topology. Use the inspector for node details.")
                if mode == .wiring {
                    ForEach(nodes) { node in
                        Button { selectedID = selectedID == node.id ? nil : node.id } label: {
                            VStack(alignment: .leading, spacing: 5) {
                                Text(node.title).font(.system(size: 16, weight: .bold, design: .monospaced)).lineLimit(1)
                                    .frame(maxWidth: .infinity, alignment: .leading).padding(5).background(node.tint.opacity(0.30))
                                Text(node.subtitle).font(.system(size: 14, design: .monospaced)).lineLimit(1).foregroundStyle(.gray).padding(.horizontal, 6)
                                HStack(spacing: 4) { Circle().fill(node.tint).frame(width: 4, height: 4); Text("STATE / INSPECT").font(.system(size: 12, design: .monospaced)).foregroundStyle(.secondary) }.padding(6)
                            }.frame(width: 165, height: 76, alignment: .topLeading)
                                .background(ConsoleStyle.panel.opacity(0.96)).overlay(Rectangle().stroke(node.tint.opacity(selectedID == node.id ? 1 : 0.5)))
                        }.buttonStyle(.plain)
                            .scaleEffect(scale, anchor: .topLeading)
                            .frame(width: 165 * scale, height: 76 * scale, alignment: .topLeading)
                            .position(x: (node.position.x + 82.5) * scale + (geometry.size.width - world.width * scale) / 2 + offset.width + drag.width,
                                      y: (node.position.y + 38) * scale + (geometry.size.height - world.height * scale) / 2 + offset.height + drag.height)
                    }
                }
                VStack(alignment: .leading, spacing: 5) {
                    Text(modeTitle)
                    Text(modeHint).foregroundStyle(.secondary)
                }.font(.system(size: 13, design: .monospaced)).padding(10).allowsHitTesting(false)
                VStack {
                    Spacer()
                    HStack(alignment: .bottom) {
                        if let node = nodes.first(where: { $0.id == selectedID }) {
                            VStack(alignment: .leading, spacing: 5) {
                                Text(node.title).foregroundStyle(node.tint)
                                Text(node.subtitle)
                                Text("Architecture node / latest polled state").foregroundStyle(.secondary)
                            }.font(.system(size: 14, design: .monospaced)).padding(10).background(ConsoleStyle.panel)
                        }
                        Spacer()
                        HStack(spacing: 16) {
                            Button { zoom = max(0.6, zoom - 0.25) } label: { Image(systemName: "minus.magnifyingglass") }.accessibilityLabel("Zoom out")
                            Button { zoom = 1; offset = .zero; selectedID = nil } label: { Image(systemName: "arrow.up.left.and.arrow.down.right") }.accessibilityLabel("Reset canvas")
                            Button { zoom = min(4, zoom + 0.25) } label: { Image(systemName: "plus.magnifyingglass") }.accessibilityLabel("Zoom in")
                        }.font(.system(size: 17)).padding(10).background(ConsoleStyle.panel)
                    }.padding(10)
                }
            }.clipped().contentShape(Rectangle())
                .simultaneousGesture(DragGesture(minimumDistance: 8).updating($drag) { value, state, _ in state = value.translation }.onEnded { value in offset.width += value.translation.width; offset.height += value.translation.height })
                .simultaneousGesture(MagnifyGesture().updating($pinch) { value, state, _ in state = value.magnification }.onEnded { value in zoom = min(4, max(0.6, zoom * value.magnification)) })
        }.background(ConsoleStyle.background)
    }

    private func drawGrid(context: inout GraphicsContext, size: CGSize) {
        var path = Path()
        for x in stride(from: 0.0, through: size.width, by: 24) { path.move(to: CGPoint(x: x, y: 0)); path.addLine(to: CGPoint(x: x, y: size.height)) }
        for y in stride(from: 0.0, through: size.height, by: 24) { path.move(to: CGPoint(x: 0, y: y)); path.addLine(to: CGPoint(x: size.width, y: y)) }
        context.stroke(path, with: .color(.white.opacity(0.025)), lineWidth: 0.5)
    }

    private func drawWiring(context: inout GraphicsContext, time: Double) {
        let edges = [("input", "planner"), ("planner", "builder"), ("builder", "approval"), ("approval", "checkpoint"), ("checkpoint", "planner"), ("mcp", "builder")]
        for (index, edge) in edges.enumerated() {
            guard let a = nodes.first(where: { $0.id == edge.0 }), let b = nodes.first(where: { $0.id == edge.1 }) else { continue }
            for strand in 0..<12 {
                let yOffset = Double(strand) * 3
                let start = CGPoint(x: a.position.x + 165, y: a.position.y + 25 + yOffset)
                let end = CGPoint(x: b.position.x, y: b.position.y + 20 + yOffset)
                var path = Path(); path.move(to: start)
                path.addCurve(to: end, control1: CGPoint(x: start.x + 120, y: start.y), control2: CGPoint(x: end.x - 120, y: end.y))
                context.stroke(path, with: .color((index % 2 == 0 ? ConsoleStyle.purple : ConsoleStyle.cyan).opacity(strand % 3 == 0 ? 0.42 : 0.13)), lineWidth: strand % 3 == 0 ? 0.9 : 0.5)
            }
        }
        for tool in nodes where tool.id.hasPrefix("tool-") {
            var path = Path(); path.move(to: CGPoint(x: tool.position.x + 80, y: tool.position.y + 76)); path.addQuadCurve(to: CGPoint(x: 380, y: 465), control: CGPoint(x: tool.position.x + 200, y: 350))
            context.stroke(path, with: .color(ConsoleStyle.cyan.opacity(0.2)), lineWidth: 0.7)
        }
    }

    private func drawConstellation(context: inout GraphicsContext, time: Double) {
        let groups: [(String, Int, CGPoint, Color)] = [
            ("RUNTIME", store.status == nil ? 0 : 1, CGPoint(x: 230, y: 180), ConsoleStyle.pink),
            ("TOOLS", store.tools.count, CGPoint(x: 550, y: 120), ConsoleStyle.cyan),
            ("INTEGRATIONS", store.integrations.count, CGPoint(x: 850, y: 235), ConsoleStyle.purple),
            ("WORKFLOWS", store.workflows.count, CGPoint(x: 360, y: 440), ConsoleStyle.purple),
            ("ACCOUNTS", store.registrations.count, CGPoint(x: 730, y: 490), ConsoleStyle.pink)]
        for (groupIndex, group) in groups.enumerated() {
            for index in 0..<220 {
                let seed = Double(index)
                let angle = seed * 2.399963 + time * 0.025 * (groupIndex % 2 == 0 ? 1 : -1)
                let radius = sqrt(seed / 220) * 135
                let point = CGPoint(x: group.2.x + cos(angle) * radius, y: group.2.y + sin(angle) * radius * 0.68)
                let dot = CGRect(x: point.x, y: point.y, width: index % 13 == 0 ? 2 : 0.9, height: index % 13 == 0 ? 2 : 0.9)
                context.fill(Path(ellipseIn: dot), with: .color(group.3.opacity(index % 13 == 0 ? 0.8 : 0.25)))
            }
            context.draw(Text(group.0).font(.system(size: 18, weight: .bold, design: .monospaced)).foregroundStyle(.white), at: CGPoint(x: group.2.x, y: group.2.y - 110))
            context.draw(Text("\(group.1) observed records").font(.system(size: 10, design: .monospaced)).foregroundStyle(group.3), at: CGPoint(x: group.2.x, y: group.2.y - 88))
        }
    }

    private func drawVortex(context: inout GraphicsContext, time: Double) {
        for index in 0..<1900 {
            let value = Double(index)
            let height = value / 1900
            let angle = value * 2.399963 + time * 0.22 + height * 18
            let radius = 30 + pow(height, 1.4) * 390
            let x = 550 + cos(angle) * radius
            let y = 605 - height * 565 + sin(angle) * radius * 0.22
            let diameter = index % 11 == 0 ? 2.5 : 1.2
            context.fill(Path(ellipseIn: CGRect(x: x, y: y, width: diameter, height: diameter)), with: .color((index % 7 == 0 ? ConsoleStyle.purple : ConsoleStyle.pink).opacity(0.25 + (sin(angle) + 1) * 0.3)))
        }
        context.draw(Text("SUPERCRAFT / EXECUTION FIELD").font(.system(size: 17, weight: .black, design: .monospaced)).foregroundStyle(.white), at: CGPoint(x: 550, y: 38))
        context.draw(Text("\(store.status?.awaitingApproval ?? 0) APPROVAL GATES  ·  \(store.status?.tools ?? 0) MCP TOOLS").font(.system(size: 11, design: .monospaced)).foregroundStyle(ConsoleStyle.cyan), at: CGPoint(x: 550, y: 625))
    }

    private func project(_ point: (x: Double, y: Double, z: Double), spin: Double, tilt: Double, center: CGPoint) -> (position: CGPoint, depth: Double) {
        let cosSpin = cos(spin); let sinSpin = sin(spin)
        let x1 = point.x * cosSpin + point.z * sinSpin
        let z1 = -point.x * sinSpin + point.z * cosSpin
        let cosTilt = cos(tilt); let sinTilt = sin(tilt)
        let y2 = point.y * cosTilt - z1 * sinTilt
        let z2 = point.y * sinTilt + z1 * cosTilt
        let scale = 820 / (820 + z2)
        return (position: CGPoint(x: center.x + x1 * scale, y: center.y + y2 * scale), depth: z2)
    }

    private func drawLattice(context: inout GraphicsContext, time: Double) {
        let center = CGPoint(x: 550, y: 335)
        let radius = 235.0
        let spin = time * 0.35
        let tilt = 0.42 + sin(time * 0.08) * 0.1
        for latitude in stride(from: -75.0, through: 75.0, by: 15.0) {
            let phi = latitude * .pi / 180
            let ringRadius = radius * cos(phi)
            let height = radius * sin(phi)
            var path = Path(); var started = false
            for step in 0...90 {
                let theta = Double(step) / 90 * 2 * .pi
                let point = project((x: ringRadius * cos(theta), y: height, z: ringRadius * sin(theta)), spin: spin, tilt: tilt, center: center)
                if started { path.addLine(to: point.position) } else { path.move(to: point.position); started = true }
            }
            let equator = abs(latitude) < 1
            context.stroke(path, with: .color((equator ? ConsoleStyle.cyan : ConsoleStyle.purple).opacity(equator ? 0.4 : 0.14)), lineWidth: equator ? 1.0 : 0.6)
        }
        for longitude in stride(from: 0.0, to: 360.0, by: 30.0) {
            let lambda = longitude * .pi / 180
            var path = Path(); var started = false
            for step in 0...72 {
                let theta = -Double(step) / 72 * .pi
                let ringRadius = radius * cos(theta)
                let point = project((x: ringRadius * cos(lambda), y: radius * sin(theta), z: ringRadius * sin(lambda)), spin: spin, tilt: tilt, center: center)
                if started { path.addLine(to: point.position) } else { path.move(to: point.position); started = true }
            }
            context.stroke(path, with: .color(ConsoleStyle.pink.opacity(0.12)), lineWidth: 0.6)
        }
        for index in 0..<640 {
            let value = Double(index) + 0.5
            let normalized = 1 - 2 * value / 640
            let ringRadius = sqrt(max(0, 1 - normalized * normalized))
            let angle = Double(index) * 2.399963
            let point = project((x: radius * ringRadius * cos(angle), y: radius * normalized, z: radius * ringRadius * sin(angle)), spin: spin, tilt: tilt, center: center)
            let shade = min(max(1 - (point.depth + radius) / (2 * radius), 0), 1)
            let size = index % 11 == 0 ? 2.4 : 1.1
            context.fill(Path(ellipseIn: CGRect(x: point.position.x - size / 2, y: point.position.y - size / 2, width: size, height: size)),
                         with: .color((index % 7 == 0 ? ConsoleStyle.cyan : index % 3 == 0 ? ConsoleStyle.purple : ConsoleStyle.pink).opacity(0.1 + shade * 0.72)))
        }
        for index in 0..<220 {
            let phi = Double(index) / 220 * 2 * .pi + time * 0.05
            let point = project((x: 330 * cos(phi), y: sin(phi * 2) * 7, z: 330 * sin(phi)), spin: spin, tilt: tilt, center: center)
            let bright = index % 9 == 0
            let size = bright ? 2.2 : 0.9
            context.fill(Path(ellipseIn: CGRect(x: point.position.x - size / 2, y: point.position.y - size / 2, width: size, height: size)),
                         with: .color((bright ? ConsoleStyle.cyan : ConsoleStyle.purple).opacity(bright ? 0.85 : 0.22)))
        }
        let orbiters = Array(store.integrations.prefix(8))
        for (index, integration) in orbiters.enumerated() {
            let phi = Double(index) / Double(max(orbiters.count, 1)) * 2 * .pi - spin * 0.5
            let point = project((x: 335 * cos(phi), y: 0, z: 335 * sin(phi)), spin: spin, tilt: tilt, center: center)
            context.draw(Text(integration.name).font(.system(size: 10, weight: .bold, design: .monospaced)).foregroundStyle(healthy(integration.status) ? ConsoleStyle.cyan : ConsoleStyle.pink), at: point.position)
        }
        context.draw(Text("SUPERCRAFT / NEURAL LATTICE").font(.system(size: 17, weight: .black, design: .monospaced)).foregroundStyle(.white), at: CGPoint(x: 550, y: 38))
        context.draw(Text("\(store.status?.tools ?? 0) MCP TOOLS · \(store.integrations.count) INTEGRATIONS · \(store.workflows.count) CHECKPOINTS").font(.system(size: 11, design: .monospaced)).foregroundStyle(ConsoleStyle.cyan), at: CGPoint(x: 550, y: 625))
    }
}

@MainActor
private struct ComposeSheet: View {
    @ObservedObject var store: BackendStore
    @State private var query = ""
    @State private var requestKey = UUID().uuidString
    @State private var maxSteps = 24
    @State private var scheduled = false
    @State private var startTime = Date()
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 20) {
                Text("DIRECT THE SYSTEM").font(.system(size: 27, weight: .black, design: .monospaced))
                Text("Plan → Build → Test → Repair → Verify → Deliver").font(.system(size: 16, design: .monospaced)).foregroundStyle(ConsoleStyle.pink)
                TextEditor(text: $query).padding(10).frame(minHeight: 160).scrollContentBackground(.hidden).background(ConsoleStyle.panel).accessibilityLabel("Autonomous task request")
                HStack { Text("\(query.count) / 12000").font(.body.monospaced()); Spacer(); if store.busy { ProgressView() } }
                if let error = store.error { Text(error).font(.body).foregroundStyle(.orange) }
                Stepper("Step budget: \(maxSteps)", value: $maxSteps, in: 2...80)
                Toggle("Schedule start", isOn: $scheduled)
                if scheduled { DatePicker("Start", selection: $startTime, in: Date()...) }
                Button("START AUTONOMOUS TASK") {
                    Task {
                        let job = await store.submitTask(query: query.trimmingCharacters(in: .whitespacesAndNewlines), maxSteps: maxSteps,
                                                         runAt: scheduled ? startTime : nil, idempotencyKey: requestKey)
                        if job != nil { dismiss() }
                    }
                }.buttonStyle(.borderedProminent).disabled(store.mutating || !(3...12000).contains(query.trimmingCharacters(in: .whitespacesAndNewlines).count))
            }.padding(20).background(ConsoleStyle.background)
                .onChange(of: query) { _, _ in requestKey = UUID().uuidString }
                .onChange(of: maxSteps) { _, _ in requestKey = UUID().uuidString }
                .onChange(of: scheduled) { _, _ in requestKey = UUID().uuidString }
                .onChange(of: startTime) { _, _ in requestKey = UUID().uuidString }
                .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Close") { dismiss() } } }
        }.tint(ConsoleStyle.pink).preferredColorScheme(.dark).interactiveDismissDisabled(store.mutating)
    }
}

@MainActor
private struct WorkflowDetail: View {
    @ObservedObject var store: BackendStore
    let workflowID: String
    @Environment(\.dismiss) private var dismiss
    private var workflow: AgentWorkflow? { store.workflows.first { $0.id == workflowID } }
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    if let workflow {
                        Text(workflow.query ?? "Workflow").font(.title2.bold()).accessibilityIdentifier("workflow-detail-query")
                        Text(workflow.id).font(.body.monospaced()).foregroundStyle(.secondary).textSelection(.enabled)
                        StatusTag(status: workflow.status ?? "unknown")
                        if let plan = workflow.plan { Text("PLAN").font(.body.monospaced()).foregroundStyle(ConsoleStyle.purple); Text(plan).textSelection(.enabled) }
                        if let artifact = workflow.artifact {
                            Text("ARTIFACT").font(.body.monospaced()).foregroundStyle(ConsoleStyle.pink)
                            Text(artifact).font(.system(size: 18, design: .monospaced)).textSelection(.enabled)
                            ShareLink(item: artifact) { Label("Export artifact", systemImage: "square.and.arrow.up") }.buttonStyle(.bordered)
                        }
                        if let error = workflow.error { Text(error).foregroundStyle(.orange) }
                        if workflow.status == "awaiting_approval" {
                            HStack {
                                Button("Approve") { decide("approve") }.buttonStyle(.borderedProminent)
                                Button("Deny", role: .destructive) { decide("deny") }.buttonStyle(.bordered)
                            }.disabled(store.busy)
                        }
                        if store.busy { ProgressView() }
                        if let error = store.error { Text(error).foregroundStyle(.orange).font(.body) }
                    } else { Text("Checkpoint no longer available.") }
                }.padding(20).frame(maxWidth: .infinity, alignment: .leading)
            }.background(ConsoleStyle.background).navigationTitle("Checkpoint").navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
        }.tint(ConsoleStyle.pink).preferredColorScheme(.dark)
    }
    private func decide(_ action: String) { Task { await store.perform("/api/workflows/\(workflowID)/\(action)") } }
}

@MainActor
private struct GrantOperations: View {
    @ObservedObject var store: BackendStore
    @State private var fundingFilter = "All"
    @State private var projectName = ""
    @State private var summary = ""
    @State private var topics = ""
    @State private var chains = ""
    @State private var budgetUSD = 0.0
    @State private var repositoryURL = ""
    @State private var team = ""
    @State private var milestones = ""
    @State private var problem = ""
    @State private var solution = ""
    @State private var publicGoodsCase = ""
    @State private var useOfFunds = ""
    @State private var contactEmail = ""
    @State private var successMetrics = ""
    @State private var showApplicationDetails = false
    @State private var showAllMatches = false
    @State private var browseCatalog = false

    @State private var budgetBreakdown = ""
    private var parsedBudgetBreakdown: [String: Double]? {
        var result: [String: Double] = [:]
        let lines = budgetBreakdown.split(separator: "\n").map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
        guard lines.count <= 30 else { return nil }
        for line in lines {
            let parts = line.split(separator: ":", maxSplits: 1).map { $0.trimmingCharacters(in: .whitespaces) }
            guard parts.count == 2, !parts[0].isEmpty, result[parts[0]] == nil,
                  let amount = Double(parts[1]), amount.isFinite, amount >= 0 else { return nil }
            result[parts[0]] = amount
        }
        return result
    }

    private var profile: GrantProfile {
        GrantProfile(projectName: projectName.trimmingCharacters(in: .whitespacesAndNewlines),
                     summary: summary.trimmingCharacters(in: .whitespacesAndNewlines),
                     topics: topics.split(separator: ",").map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }.filter { !$0.isEmpty },
                     chains: chains.split(separator: ",").map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }.filter { !$0.isEmpty },
                     budgetUSD: max(0, budgetUSD), repositoryURL: repositoryURL.trimmingCharacters(in: .whitespacesAndNewlines),
                     team: team.trimmingCharacters(in: .whitespacesAndNewlines),
                     milestones: milestones.split(separator: "\n").map { String($0).trimmingCharacters(in: .whitespacesAndNewlines) }.filter { !$0.isEmpty },
                     problem: problem.trimmingCharacters(in: .whitespacesAndNewlines),
                     solution: solution.trimmingCharacters(in: .whitespacesAndNewlines),
                     publicGoodsCase: publicGoodsCase.trimmingCharacters(in: .whitespacesAndNewlines),
                     useOfFunds: useOfFunds.trimmingCharacters(in: .whitespacesAndNewlines),
                     contactEmail: contactEmail.trimmingCharacters(in: .whitespacesAndNewlines),
                     successMetrics: successMetrics.split(separator: "\n").map { String($0).trimmingCharacters(in: .whitespacesAndNewlines) }.filter { !$0.isEmpty },
                     budgetBreakdownUSD: parsedBudgetBreakdown ?? [:])
    }

    private var canScreen: Bool { !profile.projectName.isEmpty && !profile.summary.isEmpty && !store.backend.isEmpty && parsedBudgetBreakdown != nil }

    private var fundingTypes: [String] {
        ["All"] + Array(Set(store.grants.map { $0.fundingType ?? "grant" })).sorted()
    }

    private var visibleGrants: [GrantOpportunity] {
        fundingFilter == "All" ? store.grants : store.grants.filter { ($0.fundingType ?? "grant") == fundingFilter }
    }

    private func label(_ value: String) -> String {
        value.replacingOccurrences(of: "_", with: " ").capitalized
    }

    private func httpsURL(_ value: String) -> URL? {
        guard let url = URL(string: value), url.scheme == "https", url.host != nil else { return nil }
        return url
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text("FUNDING RADAR").font(.system(size: 22, weight: .black, design: .monospaced)).foregroundStyle(.white)
                    Text("\(store.grants.count) official programme routes").font(.system(size: 15, design: .monospaced)).foregroundStyle(ConsoleStyle.cyan)
                }
                Spacer()
                Text("DISCOVERY")
                    .font(.subheadline.bold()).foregroundStyle(ConsoleStyle.cyan)
            }
            Text("Discover official funding routes and inspect current terms. A listed route is not an application or submission.")
                .font(.system(size: 16)).foregroundStyle(.secondary)
            VStack(alignment: .leading, spacing: 10) {
                Text("SCREEN YOUR PROJECT").font(.system(size: 18, weight: .heavy, design: .monospaced)).foregroundStyle(ConsoleStyle.cyan)
                TextField("Project name", text: $projectName).textFieldStyle(.roundedBorder)
                TextField("What is built and what will be delivered?", text: $summary, axis: .vertical)
                    .lineLimit(3...6).textFieldStyle(.roundedBorder)
                TextField("Topics, comma separated", text: $topics).textFieldStyle(.roundedBorder)
                TextField("Chains, comma separated", text: $chains).textFieldStyle(.roundedBorder)
                DisclosureGroup("Application details", isExpanded: $showApplicationDetails) {
                    VStack(alignment: .leading, spacing: 12) {
                        TextField("Requested budget in USD", value: $budgetUSD, format: .number)
                            .keyboardType(.decimalPad).textFieldStyle(.roundedBorder)
                        TextField("Itemized budget: label: amount, one per line", text: $budgetBreakdown, axis: .vertical)
                            .lineLimit(3...8).textFieldStyle(.roundedBorder)
                        if parsedBudgetBreakdown == nil {
                            Text("Use one unique label and a nonnegative amount per line, for example Documentation: 500.")
                                .font(.body).foregroundStyle(.orange)
                        }
                        TextField("Repository URL", text: $repositoryURL).textContentType(.URL).textInputAutocapitalization(.never).textFieldStyle(.roundedBorder)
                        TextField("Team and relevant delivery experience", text: $team, axis: .vertical).lineLimit(2...4).textFieldStyle(.roundedBorder)
                        TextField("Delivery milestones, one per line", text: $milestones, axis: .vertical).lineLimit(3...8).textFieldStyle(.roundedBorder)
                        TextField("Applicant contact email", text: $contactEmail).textContentType(.emailAddress).keyboardType(.emailAddress).textInputAutocapitalization(.never).textFieldStyle(.roundedBorder)
                        TextField("Problem and evidence", text: $problem, axis: .vertical).lineLimit(2...5).textFieldStyle(.roundedBorder)
                        TextField("Proposed solution and deliverables", text: $solution, axis: .vertical).lineLimit(2...5).textFieldStyle(.roundedBorder)
                        TextField("Public benefit and who can reproduce it", text: $publicGoodsCase, axis: .vertical).lineLimit(2...5).textFieldStyle(.roundedBorder)
                        TextField("Use of requested funds", text: $useOfFunds, axis: .vertical).lineLimit(2...5).textFieldStyle(.roundedBorder)
                        TextField("Measurable success metrics, one per line", text: $successMetrics, axis: .vertical).lineLimit(2...5).textFieldStyle(.roundedBorder)
                    }.padding(.top, 10)
                }.font(.body.weight(.semibold))
                Button("Screen funding fit", systemImage: "scope") { Task { await store.screenGrants(profile) } }
                    .buttonStyle(.borderedProminent).disabled(!canScreen || store.busy)
                Text("Fit is ranked against programme topics and chain. It does not verify an open intake or predict an award.")
                    .font(.system(size: 15)).foregroundStyle(.secondary)
            }.consolePanel()
            if !store.grantScreens.isEmpty {
                Text("SCREEN RESULTS · \(store.grantScreens.count)")
                    .font(.system(size: 18, weight: .heavy, design: .monospaced)).foregroundStyle(ConsoleStyle.pink)
                ForEach(showAllMatches ? store.grantScreens : Array(store.grantScreens.prefix(5))) { row in screenResult(row) }
                if store.grantScreens.count > 5 {
                    Button(showAllMatches ? "Show top matches" : "Show all \(store.grantScreens.count) matches") { showAllMatches.toggle() }
                        .buttonStyle(.bordered)
                }
            }
            DisclosureGroup("Browse official programmes (\(store.grants.count))", isExpanded: $browseCatalog) {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 7) {
                    ForEach(fundingTypes, id: \.self) { type in
                        Button { fundingFilter = type } label: {
                            Text(type == "All" ? "All" : label(type))
                                .font(.system(size: 15, weight: .bold, design: .monospaced))
                                .padding(.horizontal, 11).padding(.vertical, 7)
                                .background(fundingFilter == type ? ConsoleStyle.purple.opacity(0.35) : ConsoleStyle.panel)
                                .clipShape(Capsule())
                        }.buttonStyle(.plain)
                    }
                }
            }
            ForEach(visibleGrants) { grant in
                VStack(alignment: .leading, spacing: 8) {
                    HStack(alignment: .top) {
                        Text(grant.name).font(.system(size: 19, weight: .bold)).foregroundStyle(.white)
                        Spacer()
                        Text(grant.chain.uppercased()).font(.system(size: 14, design: .monospaced)).foregroundStyle(ConsoleStyle.cyan)
                    }
                    HStack(spacing: 8) {
                        Text(label(grant.fundingType ?? "grant")).foregroundStyle(ConsoleStyle.pink)
                        Text("·")
                        Text("Intake: " + label(grant.status ?? "unverified")).foregroundStyle(ConsoleStyle.cyan)
                        if let surface = grant.submissionSurface {
                            Text("·")
                            Text(label(surface))
                        }
                    }.font(.system(size: 14, weight: .semibold, design: .monospaced))
                    Text(grant.topics.joined(separator: "  ·  ")).font(.system(size: 15, design: .monospaced)).foregroundStyle(.secondary)
                    Text("TERMS  \(grant.payment)").font(.system(size: 15, design: .monospaced)).foregroundStyle(.white)
                    Text("WINDOW  \(grant.cadence)").font(.system(size: 15, design: .monospaced)).foregroundStyle(.secondary)
                    HStack(spacing: 16) {
                        if let url = httpsURL(grant.officialURL) { Link("Official programme ↗", destination: url) }
                        if let url = httpsURL(grant.applicationURL) { Link("Application route ↗", destination: url) }
                    }.font(.system(size: 15, weight: .bold, design: .monospaced))
                }.consolePanel()
            }
            }.font(.system(size: 18, weight: .semibold))
                .padding(16).background(ConsoleStyle.panel, in: RoundedRectangle(cornerRadius: 18))
            if store.grants.isEmpty { emptyGrantState }
            VStack(alignment: .leading, spacing: 14) {
                Text("Saved applications & provider receipts").font(.title2.bold())
                if store.savedGrantApplications.isEmpty {
                    Text("No saved applications on this server.").font(.body).foregroundStyle(.secondary)
                }
                ForEach(store.savedGrantApplications) { application in
                    VStack(alignment: .leading, spacing: 12) {
                        Text(application.title).font(.headline)
                        Text(application.programme).font(.body).foregroundStyle(.secondary)
                        Text("Requested: USD \(application.budgetUSD, specifier: "%.0f")").font(.body)
                        Label(label(application.submission.status), systemImage: application.submission.status == "submitted" ? "checkmark.seal" : "doc.text")
                            .font(.headline).foregroundStyle(application.submission.status == "submitted" ? ConsoleStyle.cyan : ConsoleStyle.pink)
                        if let reason = application.submission.reason { Text(reason).font(.body) }
                        if let receipt = application.submission.receipt {
                            DisclosureGroup("Provider confirmation") {
                                Text(receipt.formatted).font(.body.monospaced()).textSelection(.enabled)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                            }.accessibilityIdentifier("grant-provider-confirmation")
                        }
                        ShareLink(item: application.recordJSON) { Label("Export application record", systemImage: "square.and.arrow.up") }
                        Text("Submission does not establish approval or an award.").font(.body).foregroundStyle(.secondary)
                    }.consolePanel().accessibilityIdentifier("saved-grant-\(application.id)")
                }
            }

        }
    }
    private func screenResult(_ row: GrantScreenRow) -> some View {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack { Text(row.program.name).font(.headline); Spacer(); Text("\(row.score) / 100 · \(row.fit.uppercased())").foregroundStyle(ConsoleStyle.cyan) }
                        Text("Matched: " + (row.matchedTopics.isEmpty ? "No topic matches" : row.matchedTopics.joined(separator: ", ")))
                        Text("Chain match: " + (row.chainMatch ? "yes" : "no"))
                        Text(row.nextAction).foregroundStyle(.secondary)
                        ForEach(row.evidence, id: \.url) { item in
                            if let url = httpsURL(item.url) { Link(item.kind.replacingOccurrences(of: "_", with: " ").capitalized + " ↗", destination: url) }
                        }
                        Button("Create application draft", systemImage: "doc.text") { Task { await store.draftGrant(row.id, profile: profile) } }
                            .buttonStyle(.bordered).disabled(store.busy || !canScreen)
                        if let draft = store.grantDrafts.first(where: { $0.programID == row.id }) {
                            Text("Saved draft · \(draft.status) · ID \(draft.id)")
                                .font(.system(size: 15, design: .monospaced)).foregroundStyle(ConsoleStyle.cyan).textSelection(.enabled)
                            if let missing = draft.missingInformation, !missing.isEmpty {
                                Text("Application details needed: " + missing.map(label).joined(separator: ", "))
                                    .font(.system(size: 15)).foregroundStyle(ConsoleStyle.pink)
                            }
                            Text("\(draft.draft.title) · $\(draft.draft.budgetUSD, specifier: "%.0f") requested")
                            ForEach(Array(draft.draft.deliveryPlan.enumerated()), id: \.offset) { index, milestone in
                                Text("\(index + 1). \(milestone)").font(.body)
                            }
                            Button("Attempt official submission", systemImage: "paperplane") { Task { await store.submitGrant(draft.id) } }
                                .buttonStyle(.borderedProminent).disabled(store.busy)
                            if let submission = draft.submission {
                                Text("Provider status: " + label(submission.status) + ". " + (submission.reason ?? "Receipt recorded."))
                                    .font(.system(size: 15)).foregroundStyle(submission.status == "submitted" ? ConsoleStyle.cyan : ConsoleStyle.pink)
                            }
                            ShareLink(item: "\(draft.draft.title)\n\(draft.draft.programme)\nRequested USD: \(draft.draft.budgetUSD)\n" + draft.draft.deliveryPlan.joined(separator: "\n")) {
                                Label("Share application plan", systemImage: "square.and.arrow.up")
                            }
                        }
                    }.consolePanel()
    }
    private var emptyGrantState: some View { Text("NO OFFICIAL SOURCES LOADED · CONNECT TO REFRESH").font(.system(size: 16, design: .monospaced)).foregroundStyle(ConsoleStyle.pink).consolePanel() }
}

private struct PlatformHub: View {
    @ObservedObject var store: BackendStore
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("AUTONOMOUS CAPABILITY ENGINE").font(.system(size: 23, weight: .black, design: .monospaced))
            Text("Tasks automatically use installed tools when supported. Verified outcomes update routing scores immediately. Durable memory and checkpoints preserve work across sessions.")
                .font(.body).foregroundStyle(.secondary)
            ForEach(store.capabilities) { capability in
                VStack(alignment: .leading, spacing: 10) {
                    HStack { Text(capability.name).font(.headline); Spacer(); StatusTag(status: capability.enabled ? "ready" : "unavailable") }
                    Text(capability.features).font(.body)
                    Text("\(capability.successes) successful / \(capability.runs) measured runs")
                        .font(.system(size: 16, design: .monospaced)).foregroundStyle(ConsoleStyle.cyan)
                    ProgressView(value: capability.routingScore)
                    Text("Applied routing score: \(capability.routingScore, specifier: "%.2f")")
                        .font(.subheadline).foregroundStyle(.secondary)
                }.frame(maxWidth: .infinity, alignment: .leading).consolePanel()
            }
            if store.capabilities.isEmpty { Text("Connect to load the engine's applied policy and execution evidence.").font(.body).foregroundStyle(.secondary) }
            Text("Product generation and JSON transformations execute automatically. General planner/builder artifacts retain their review gate. Scores reflect this installation's outcomes, not vendor marketing ratings.")
                .font(.body).foregroundStyle(.secondary)
        }
    }
}

@MainActor
private struct ProductLab: View {
    @ObservedObject var store: BackendStore
    private var spec: ProductSpec {
        get { store.productSpec }
        nonmutating set { store.productSpec = newValue }
    }
    @State private var wireframe = false
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(alignment: .top, spacing: 16) {
                Image(systemName: "cube.transparent")
                    .font(.system(size: 32, weight: .medium))
                    .foregroundStyle(ConsoleStyle.cyan)
                    .frame(width: 62, height: 62)
                    .background(ConsoleStyle.cyan.opacity(0.14), in: RoundedRectangle(cornerRadius: 18))
                VStack(alignment: .leading, spacing: 7) {
                    Text("Idea to prototype")
                        .font(.system(size: 25, weight: .bold, design: .rounded))
                    Text("Set dimensions, generate a solid, then inspect the manufacturing evidence.")
                        .font(.system(size: 17)).foregroundStyle(.white.opacity(0.76))
                }
            }
            .padding(20)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                LinearGradient(colors: [ConsoleStyle.cyan.opacity(0.20), ConsoleStyle.panel], startPoint: .topLeading, endPoint: .bottomTrailing),
                in: RoundedRectangle(cornerRadius: 22)
            )
            .overlay(RoundedRectangle(cornerRadius: 22).stroke(ConsoleStyle.cyan.opacity(0.25)))
            TextField("Product name", text: $store.productSpec.name).textFieldStyle(.roundedBorder)
            TextField("What should this product do?", text: $store.productSpec.idea, axis: .vertical).lineLimit(3...6).textFieldStyle(.roundedBorder)
            Button("Suggest parameters from idea", systemImage: "sparkles") {
                Task { if let proposed = await store.interpretProduct(spec.idea) { spec = proposed } }
            }.buttonStyle(.bordered).disabled(store.busy || store.backend.isEmpty || !(5...3000).contains(spec.idea.count))
            Text("AI parameter suggestions use your configured server model. Review dimensions before generation.").font(.subheadline).foregroundStyle(.secondary)
            Text("Choose a parametric starting point. Your description is kept in the design brief; it is not treated as executable CAD code.").font(.body).foregroundStyle(.secondary)
            Picker("Template", selection: $store.productSpec.template) { Text("Enclosure").tag("enclosure"); Text("Plate").tag("plate"); Text("L bracket").tag("bracket") }.pickerStyle(.segmented)
                .onChange(of: spec.template) { _, template in if template == "enclosure" { spec.holeMM = 0 } }
            ProductScene(spec: spec, mesh: store.productMesh, wireframe: wireframe)
                .frame(height: 330)
                .clipShape(RoundedRectangle(cornerRadius: 20))
                .overlay(RoundedRectangle(cornerRadius: 20).stroke(ConsoleStyle.cyan.opacity(0.32)))
                .accessibilityLabel(store.productMesh == nil ? "Parametric product preview" : "Generated product mesh")
            HStack { Toggle("Wireframe", isOn: $wireframe); Spacer(); Text("ORBIT / PINCH").font(.system(size: 14, design: .monospaced)).foregroundStyle(ConsoleStyle.cyan) }.font(.body)
            Text(store.productMesh == nil ? "Live parametric preview in mm; holes appear in the authoritative exported mesh after generation." : "Displaying the generated STL mesh. Edit parameters and regenerate to update this mesh.")
                .font(.subheadline).foregroundStyle(.secondary)
            Text("Effective solid: \(spec.widthMM, specifier: "%.1f") × \(spec.depthMM, specifier: "%.1f") × \(spec.effectiveHeightMM, specifier: "%.1f") mm")
                .font(.body.monospaced()).foregroundStyle(ConsoleStyle.cyan)
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 240))], alignment: .leading, spacing: 14) {
                dimension("Width", value: $store.productSpec.widthMM, range: 10...300)
                dimension("Depth", value: $store.productSpec.depthMM, range: 10...300)
                if spec.template != "plate" { dimension("Height", value: $store.productSpec.heightMM, range: 5...200) }
                dimension("Wall / plate thickness", value: $store.productSpec.wallMM, range: 0.4...30)
                dimension("Hole diameter", value: $store.productSpec.holeMM, range: 0...20).disabled(spec.template == "enclosure")
                VStack(alignment: .leading) {
                    Text("Load case / N").font(.body)
                    TextField("Force in newtons", value: $store.productSpec.loadN, format: .number).keyboardType(.decimalPad).textFieldStyle(.roundedBorder)
                }
            }.disabled(store.busy)
            Picker("Material", selection: $store.productSpec.material) { ForEach(["PLA", "PETG", "Aluminum 6061-T6"], id: \.self) { Text($0) } }.pickerStyle(.menu)
            Picker("Process", selection: $store.productSpec.process) { Text("FDM printing").tag("FDM"); Text("CNC machining").tag("CNC") }.pickerStyle(.segmented)
            Text("LIVE CONSTRAINT SCREEN").font(.system(size: 16, design: .monospaced)).foregroundStyle(ConsoleStyle.cyan)
            if spec.localChecks.isEmpty { Text("No basic dimensional conflict detected. Geometry, manufacturing and performance remain to be validated.").font(.body).foregroundStyle(.secondary) }
            ForEach(spec.localChecks, id: \.self) { Text($0).font(.body).foregroundStyle(.orange) }
            Button { Task { await store.generateProduct(spec) } } label: {
                Label(store.busy ? "Generating CAD…" : "Generate STEP + STL + DXF", systemImage: "cube.box")
            }.buttonStyle(.borderedProminent).disabled(store.busy || store.backend.isEmpty || !spec.localChecks.isEmpty)
            if store.backend.isEmpty { Text("The preview and local screening work offline. Connect to the installed VPS CAD engine for validated solid exports.").font(.body).foregroundStyle(.secondary) }
            if let error = store.error { Text(error).font(.body).foregroundStyle(.orange) }
            if let report = store.productReport {
                Text("Build evidence").font(.title2.bold()).foregroundStyle(ConsoleStyle.cyan)
                StatusTag(status: report.readiness)
                if let mass = report.massEstimateG { Text("Nominal fully dense mass: \(mass, specifier: "%.2f") g").font(.system(size: 18, design: .monospaced)) }
                if let geometry = report.geometry {
                    Text("Solid valid: \(geometry.validSolid ? "yes" : "no") · STEP re-import: \(geometry.stepRoundtripValid ? "passed" : "failed")\nVolume: \(geometry.volumeMM3, specifier: "%.2f") mm³")
                        .font(.system(size: 16, design: .monospaced)).foregroundStyle(ConsoleStyle.cyan)
                }
                if let beam = report.beamScreen {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("IDEALIZED BEAM SCREEN").font(.system(size: 16, design: .monospaced)).foregroundStyle(ConsoleStyle.purple)
                        Text("Bending: \(beam.bendingStressMPa, specifier: "%.2f") MPa\nTip deflection: \(beam.tipDeflectionMM, specifier: "%.2f") mm\nAssumed allowable: \(beam.assumedAllowableMPa, specifier: "%.1f") MPa")
                            .font(.system(size: 17, design: .monospaced))
                        Text(beam.model + " Not FEA or a load rating.").font(.subheadline).foregroundStyle(.secondary)
                    }.consolePanel()
                }
                ForEach(report.checks) { check in
                    VStack(alignment: .leading, spacing: 7) {
                        HStack { Text(check.code.replacingOccurrences(of: "_", with: " ").uppercased()).font(.system(size: 15, design: .monospaced)); Spacer(); StatusTag(status: check.status) }
                        Text(check.detail).font(.body).foregroundStyle(.secondary)
                    }.consolePanel()
                }
                ForEach(store.productExports, id: \.self) { file in ShareLink(item: file) { Label("Export " + file.lastPathComponent, systemImage: "square.and.arrow.up") }.buttonStyle(.bordered) }
                ForEach(report.nextSteps ?? [], id: \.self) { step in Label(step, systemImage: "circle").font(.body).foregroundStyle(.secondary) }
                Text(report.scope).font(.body).foregroundStyle(.secondary)
            }
        }.disabled(store.busy)
            .onChange(of: spec) { _, _ in store.invalidateProductDraft() }
    }

    private func dimension(_ label: String, value: Binding<Double>, range: ClosedRange<Double>) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack { Text(label); Spacer(); Text("\(value.wrappedValue, specifier: "%.1f") mm").foregroundStyle(ConsoleStyle.cyan) }.font(.system(size: 15, design: .monospaced))
            Slider(value: value, in: range, step: 0.1)
        }
    }
}

@MainActor
private struct ProductScene: UIViewRepresentable {
    let spec: ProductSpec
    let mesh: URL?
    let wireframe: Bool

    final class Coordinator { var signature = "" }
    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeUIView(context: Context) -> SCNView {
        let view = SCNView(); view.allowsCameraControl = true; view.autoenablesDefaultLighting = true
        view.backgroundColor = UIColor(red: 0.025, green: 0.025, blue: 0.04, alpha: 1)
        view.preferredFramesPerSecond = 30
        view.isPlaying = false
        return view
    }

    func updateUIView(_ view: SCNView, context: Context) {
        let signature = (try? String(data: JSONEncoder().encode(spec), encoding: .utf8)) ?? ""
        let key = signature + (mesh?.absoluteString ?? "") + String(wireframe)
        guard context.coordinator.signature != key else { return }
        context.coordinator.signature = key
        let scene = SCNScene()
        let material = SCNMaterial(); material.diffuse.contents = UIColor(red: 0.84, green: 0.22, blue: 0.52, alpha: 1)
        material.lightingModel = .physicallyBased; material.metalness.contents = 0.35; material.roughness.contents = 0.45
        material.fillMode = wireframe ? .lines : .fill
        let model = SCNNode()
        if let mesh, let loaded = try? SCNScene(url: mesh, options: nil) {
            for node in loaded.rootNode.childNodes { model.addChildNode(node) }
            model.scale = SCNVector3(0.001, 0.001, 0.001)
        } else {
            let w = spec.widthMM / 1000, d = spec.depthMM / 1000, h = spec.heightMM / 1000, t = spec.wallMM / 1000
            func part(_ width: Double, _ depth: Double, _ height: Double, x: Double = 0, y: Double = 0, z: Double) {
                let box = SCNBox(width: CGFloat(width), height: CGFloat(depth), length: CGFloat(height), chamferRadius: 0)
                let node = SCNNode(geometry: box); node.position = SCNVector3(Float(x), Float(y), Float(z)); model.addChildNode(node)
            }
            part(w, d, t, z: t/2)
            if spec.template == "bracket" { part(w, t, h, y: -(d-t)/2, z: h/2) }
            if spec.template == "enclosure" && t * 2 < min(w, d) && t < h {
                part(w, t, h-t, y: -(d-t)/2, z: (h+t)/2)
                part(w, t, h-t, y: (d-t)/2, z: (h+t)/2)
                part(t, d-2*t, h-t, x: -(w-t)/2, z: (h+t)/2)
                part(t, d-2*t, h-t, x: (w-t)/2, z: (h+t)/2)
            }
        }
        model.enumerateChildNodes { node, _ in node.geometry?.materials = [material] }
        model.eulerAngles.x = -.pi / 2
        scene.rootNode.addChildNode(model)
        let camera = SCNNode(); camera.camera = SCNCamera(); camera.camera?.zNear = 0.001; camera.camera?.zFar = 10
        let productHeight = spec.effectiveHeightMM
        let extent = max(spec.widthMM, max(spec.depthMM, productHeight)) / 1000
        camera.position = SCNVector3(Float(extent * 1.6), Float(extent * 1.3), Float(extent * 1.7))
        camera.look(at: SCNVector3(0, Float(productHeight / 2000), 0))
        scene.rootNode.addChildNode(camera)
        view.scene = scene; view.pointOfView = camera
    }
}

private struct LocalUtilityPanel: View {
    @State private var input = ""
    @State private var output = ""
    @State private var failure: String?
    @AppStorage("supercraftos.localNotebook") private var notebook = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("ON-DEVICE WORKBENCH", systemImage: "cpu").font(.system(size: 18, weight: .bold, design: .monospaced)).foregroundStyle(ConsoleStyle.pink)
            Text("Runs locally. No server, model, account or network required.").font(.body).foregroundStyle(.secondary)
            TextEditor(text: $input).font(.system(size: 17, design: .monospaced)).frame(height: 120).accessibilityLabel("Utility input")
                .onChange(of: input) { _, value in if value.utf8.count > 262144 { input = String(value.prefix(32768)) } }
            ViewThatFits(in: .horizontal) {
                HStack { utilityButtons }
                VStack(alignment: .leading) { utilityButtons }
            }
            if let failure { Text(failure).font(.body).foregroundStyle(.orange) }
            if !output.isEmpty {
                Text(output).font(.system(size: 16, design: .monospaced)).textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading)
                ShareLink(item: output) { Label("Export result", systemImage: "square.and.arrow.up") }.font(.body)
            }
            Divider()
            Text("LOCAL NOTEBOOK").font(.system(size: 15, design: .monospaced)).foregroundStyle(ConsoleStyle.cyan)
            TextEditor(text: $notebook).frame(height: 100).accessibilityLabel("Local notebook")
                .onChange(of: notebook) { _, value in if value.count > 16000 { notebook = String(value.prefix(16000)) } }
            ShareLink(item: notebook) { Label("Export notes", systemImage: "square.and.arrow.up") }.font(.body)
            Text("Notes stay on this device. Do not store credentials here.").font(.subheadline).foregroundStyle(.secondary)
        }.consolePanel()
    }

    @ViewBuilder private var utilityButtons: some View {
        Button("Format JSON") { run { try LocalUtilities.formatJSON(input) } }.buttonStyle(.bordered)
        Button("Base64 encode") { run { LocalUtilities.encodeBase64(input) } }.buttonStyle(.bordered)
        Button("Decode") { run { try LocalUtilities.decodeBase64(input) } }.buttonStyle(.bordered)
    }

    private func run(_ operation: () throws -> String) {
        do { output = try operation(); failure = nil }
        catch { output = ""; failure = error.localizedDescription }
    }
}

@MainActor
private struct ConnectionSheet: View {
    @ObservedObject var store: BackendStore
    @State private var address: String
    @State private var accessKey = ""
    @Environment(\.dismiss) private var dismiss
    init(store: BackendStore) { self.store = store; _address = State(initialValue: store.backend) }

    private var addressProblem: String? {
        do { _ = try BackendConnection(address: address, accessKey: accessKey); return nil }
        catch { return error.localizedDescription }
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("BACKEND SWITCHBOARD") {
                    TextField("Private access link or HTTPS address", text: $address).textInputAutocapitalization(.never).autocorrectionDisabled().keyboardType(.URL).disabled(store.busy)
                    if let problem = addressProblem, !address.isEmpty {
                        Text(problem).font(.body).foregroundStyle(.orange)
                    }
                    SecureField("Access key (if not included in the link)", text: $accessKey).textInputAutocapitalization(.never).autocorrectionDisabled().disabled(store.busy)
                    Text("Paste the complete private access link, including its # fragment. The app saves only the server address in settings and keeps its access key in the device Keychain. Leave the key blank to reuse a saved connection.").font(.body).foregroundStyle(.secondary)
                }
                if !store.bookmarks.isEmpty {
                    Section("SAVED ENDPOINTS") {
                        ForEach(store.bookmarks, id: \.self) { endpoint in
                            Button {
                                address = endpoint; accessKey = ""
                                Task {
                                    await store.connect(address: endpoint, accessKey: "")
                                    if store.error == nil { dismiss() }
                                }
                            } label: {
                                Label(endpoint, systemImage: endpoint == store.backend ? "checkmark.circle.fill" : "bookmark")
                            }.disabled(store.busy)
                                .swipeActions {
                                    Button("Delete", role: .destructive) { store.removeBookmark(endpoint) }
                                }
                        }
                    }
                }
                Section("SERVER SECRETS") { Text("Model and service credentials stay on the server. The app uses its own gateway access key; control-session tokens remain in memory.").font(.body) }
                Section {
                    Button("Save and connect") {
                        Task {
                            await store.connect(address: address, accessKey: accessKey)
                            if store.error == nil { accessKey = ""; dismiss() }
                        }
                    }.disabled(store.busy || address.isEmpty || addressProblem != nil)
                    Button("Forget saved connection", role: .destructive) {
                        store.disconnect(); address = ""; accessKey = ""
                    }.disabled(store.busy || store.backend.isEmpty)
                    if store.busy { ProgressView() }
                    if let error = store.error { Text(error).foregroundStyle(.orange).font(.body) }
                }
            }.navigationTitle("Connection").toolbar { ToolbarItem(placement: .cancellationAction) { Button("Close") { dismiss() } } }
        }.tint(ConsoleStyle.pink).preferredColorScheme(.dark)
    }
}

@MainActor
private struct ToolExecutionPanel: View {
    @ObservedObject var store: BackendStore
    let tool: AgentTool
    @State private var arguments = "{}"
    @State private var result: String?
    @State private var failure: String?
    @State private var running = false
    @State private var expanded = false
    var body: some View {
        DisclosureGroup(isExpanded: $expanded) {
            VStack(alignment: .leading, spacing: 14) {
            DisclosureGroup("Input schema") {
                Text(tool.inputSchema?.formatted ?? "No input schema provided by the server.")
                    .font(.body.monospaced()).textSelection(.enabled)
            }
            Text("JSON arguments").font(.body.bold())
            TextEditor(text: $arguments).font(.body.monospaced()).frame(minHeight: 120)
                .autocorrectionDisabled().textInputAutocapitalization(.never).accessibilityLabel("Arguments for " + tool.name)
            Button(running ? "Running tool…" : "Run tool", systemImage: "play.fill") {
                running = true; failure = nil; result = nil
                Task {
                    defer { running = false }
                    do { result = try await store.executeTool(tool.name, arguments: arguments).formatted }
                    catch { failure = error.localizedDescription }
                }
            }.buttonStyle(.borderedProminent).disabled(running || store.backend.isEmpty)
            if let failure { Text(failure).foregroundStyle(.orange).textSelection(.enabled) }
            if let result {
                Text("Execution response").font(.headline)
                Text(result).font(.body.monospaced()).textSelection(.enabled)
                ShareLink(item: result) { Label("Share result", systemImage: "square.and.arrow.up") }
            }
            }.padding(.top, 16)
        } label: {
            VStack(alignment: .leading, spacing: 7) {
                HStack(spacing: 10) {
                    Image(systemName: "terminal.fill")
                        .font(.title3).foregroundStyle(ConsoleStyle.cyan)
                        .frame(width: 42, height: 42)
                        .background(ConsoleStyle.cyan.opacity(0.12), in: RoundedRectangle(cornerRadius: 12))
                    Text(tool.name.replacingOccurrences(of: "_", with: " "))
                        .font(.system(size: 19, weight: .semibold, design: .rounded))
                        .foregroundStyle(.white)
                }
                Text(tool.description ?? "Open to inspect inputs and run this tool.")
                    .font(.system(size: 16)).foregroundStyle(.white.opacity(0.7))
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(18)
        .background(ConsoleStyle.panel, in: RoundedRectangle(cornerRadius: 18))
        .overlay(RoundedRectangle(cornerRadius: 18).stroke(ConsoleStyle.line))
    }
}
