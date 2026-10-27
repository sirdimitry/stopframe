import Foundation

/// All paths are resolved inside the sandbox container automatically by
/// `FileManager` — no special-casing needed for App Sandbox here.
enum AppPaths {
    static let appName = "StopFrame"

    static func applicationSupportDirectory() -> URL {
        if let testRoot = ProcessInfo.processInfo.environment["STOPFRAME_TEST_ROOT"] {
            let url = URL(fileURLWithPath: testRoot,isDirectory: true)
            try? FileManager.default.createDirectory(at: url,withIntermediateDirectories: true)
            return url
        }
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        let dir = base.appendingPathComponent(appName, isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    static func cachesDirectory() -> URL {
        let base = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
        let dir = base.appendingPathComponent(appName, isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    static var settingsFile: URL { applicationSupportDirectory().appendingPathComponent("settings.json") }
    static var projectFile: URL { applicationSupportDirectory().appendingPathComponent("project.json") }
    static var logFile: URL { applicationSupportDirectory().appendingPathComponent("stopframe.log") }

    static var filmstripCacheDirectory: URL {
        let dir = cachesDirectory().appendingPathComponent("Filmstrips", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }
}
