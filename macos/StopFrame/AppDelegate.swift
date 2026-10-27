import AppKit

/// Gates app termination on graceful shutdown of any long-running work
/// (Auto-Pick, export) and persists the session (project) before quitting —
/// the structured-concurrency analog of the original's "QThread.wait()
/// before close, else crash" rule, plus the new session-persistence feature.
@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    var appState: AppState?

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        appState?.saveProject()
        return .terminateNow
    }
}
