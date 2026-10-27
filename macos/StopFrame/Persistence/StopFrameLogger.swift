import Foundation

/// Mirrors the original's privacy-safe logger: a single file under
/// Application Support, capped at 10 MB by trimming to the last 100 lines
/// (not rotated into separate files). Callers must only log short
/// identifiers — file names, indices — never full user paths or images.
/// The app makes no network calls anywhere, ever.
actor StopFrameLogger {
    static let shared = StopFrameLogger()

    private let maxBytes = 10 * 1024 * 1024
    private let keepLines = 100
    private let fileURL = AppPaths.logFile

    func info(_ category: String, _ message: String) {
        write(level: "INFO", category: category, message: message)
    }

    func error(_ category: String, _ message: String) {
        write(level: "ERROR", category: category, message: message)
    }

    private func write(level: String, category: String, message: String) {
        let timestamp = ISO8601DateFormatter().string(from: Date())
        let line = "\(timestamp) [\(level)] \(category): \(message)\n"
        #if DEBUG
        print(line, terminator: "")
        #endif
        do {
            if FileManager.default.fileExists(atPath: fileURL.path) {
                let handle = try FileHandle(forWritingTo: fileURL)
                defer { try? handle.close() }
                try handle.seekToEnd()
                try handle.write(contentsOf: Data(line.utf8))
            } else {
                try Data(line.utf8).write(to: fileURL)
            }
            try trimIfNeeded()
        } catch {
            // Logging must never crash the app; silently drop on failure.
        }
    }

    private func trimIfNeeded() throws {
        let attributes = try FileManager.default.attributesOfItem(atPath: fileURL.path)
        guard let size = attributes[.size] as? Int, size > maxBytes else { return }
        let content = try String(contentsOf: fileURL, encoding: .utf8)
        let lines = content.split(separator: "\n", omittingEmptySubsequences: false)
        let tail = lines.suffix(keepLines).joined(separator: "\n")
        try tail.write(to: fileURL, atomically: true, encoding: .utf8)
    }
}
