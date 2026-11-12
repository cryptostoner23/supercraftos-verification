import SwiftUI
import AppIntents

enum AppDestination: String, AppEnum {
    case mission
    case tasks, memory, quests, shortcuts
    case products
    case platforms
    case grants
    case workflows
    case integrations
    case tools
    case registrations

    static let typeDisplayRepresentation = TypeDisplayRepresentation(name: "SuperCraftOS destination")
    static let caseDisplayRepresentations: [Self: DisplayRepresentation] = [
        .mission: "Mission Control",
        .tasks: "Tasks", .memory: "Memory", .quests: "Quests", .shortcuts: "Shortcuts",
        .products: "Product Lab",
        .platforms: "Engine",
        .grants: "Grant Operations",
        .workflows: "Workflows",
        .integrations: "Integrations",
        .tools: "Tools",
        .registrations: "Accounts",
    ]
}

@MainActor
final class AppNavigationModel: ObservableObject {
    static let shared = AppNavigationModel()
    @Published var destination: AppDestination?
    private init() {}

    func open(_ destination: AppDestination) {
        self.destination = destination
    }
}

struct OpenControlSurfaceIntent: AppIntent {
    static let title: LocalizedStringResource = "Open SuperCraftOS"
    static let description = IntentDescription("Open a selected SuperCraftOS control surface.")
    static let openAppWhenRun = true

    @Parameter(title: "Destination", default: .mission)
    var destination: AppDestination

    @Dependency
    private var navigationModel: AppNavigationModel

    @MainActor
    func perform() async throws -> some IntentResult {
        navigationModel.open(destination)
        return .result()
    }
}

@main
@MainActor
struct SuperCraftOSApp: App {
    @StateObject private var navigationModel: AppNavigationModel

    init() {
        let model = AppNavigationModel.shared
        _navigationModel = StateObject(wrappedValue: model)
        AppDependencyManager.shared.add(dependency: model)
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(navigationModel)
        }
    }
}
