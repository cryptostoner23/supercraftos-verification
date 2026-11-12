import SwiftUI

@MainActor
struct LearningView: View {
    @ObservedObject var store: BackendStore
    @State private var memory: AgentMemory?
    @State private var error: String?
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("Execution memory").font(.title2.bold())
                Text("See the approach, action explanations, test evidence and uncertainty in each task’s activity. Verified results can contribute reusable lessons.").foregroundStyle(.secondary)
                if let error { Text(error).foregroundStyle(.orange) }
                if let memory {
                    Text(memory.description).font(.body).foregroundStyle(.secondary)
                    ForEach(memory.playbooks) { playbook in
                        GroupBox {
                            VStack(alignment: .leading, spacing: 8) {
                                Text(playbook.title).font(.headline)
                                Text(playbook.when).font(.body).foregroundStyle(.secondary)
                                ForEach(Array(playbook.steps.enumerated()), id: \.offset) { index, step in Text("\(index + 1). \(step)") }
                                Text("Source: " + playbook.evidence.joined(separator: ", ")).font(.subheadline).foregroundStyle(.secondary)
                            }.frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                    Text("Learned from completed tasks").font(.headline)
                    if memory.lessons.isEmpty { Text("Lessons appear after a task passes its checks and acceptance review.").foregroundStyle(.secondary) }
                    ForEach(memory.lessons) { lesson in
                        GroupBox {
                            VStack(alignment: .leading, spacing: 8) {
                                Text(lesson.lesson)
                                Text("\(lesson.checksPassed) passing checks · \(lesson.accepted ? "review accepted" : "review unavailable")").font(.body).foregroundStyle(.secondary)
                                Text("Task " + lesson.jobID).font(.subheadline.monospaced()).textSelection(.enabled)
                                Button("Forget lesson", role: .destructive) {
                                    Task { do { try await store.forgetLesson(lesson.id); await reload() } catch { self.error = error.localizedDescription } }
                                }.disabled(store.busy)
                            }.frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                } else if error == nil { ProgressView() }
            }.padding()
        }.task(id: store.backend) { await reload() }
    }
    private func reload() async {
        memory = nil; error = nil
        do { memory = try await store.executionMemory() } catch { self.error = error.localizedDescription }
    }
}
