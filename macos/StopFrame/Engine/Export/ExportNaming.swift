import Foundation

/// Capture-time-based naming (not the video timestamp) with millisecond
/// precision, mirroring the original — names are inherently unique per
/// export moment and don't depend on the (possibly long/awkward) source
/// video's file name.
enum ExportNaming {
    static func fileName(
        captureDate: Date = Date(),
        frameIndex: Int,
        prefix: String,
        prefixBeforeName: Bool,
        extension ext: String
    ) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd-HH'h'mm'm'ss's'"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        let stamped = formatter.string(from: captureDate)

        let milliseconds = Int((captureDate.timeIntervalSince1970 * 1000).truncatingRemainder(dividingBy: 1000))
        let msString = String(format: "%03d", max(0, milliseconds))
        let base = "\(stamped)\(msString)_frame\(frameIndex)"

        let trimmedPrefix = prefix.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedPrefix.isEmpty else { return "\(base).\(ext)" }
        return prefixBeforeName ? "\(trimmedPrefix)-\(base).\(ext)" : "\(base)-\(trimmedPrefix).\(ext)"
    }

    /// Names are unique by construction (millisecond precision), but a fast
    /// batch could theoretically collide — append a numeric suffix if so.
    static func uniqueURL(for baseURL: URL) -> URL {
        guard FileManager.default.fileExists(atPath: baseURL.path) else { return baseURL }
        let ext = baseURL.pathExtension
        let stem = baseURL.deletingPathExtension().lastPathComponent
        let directory = baseURL.deletingLastPathComponent()

        var counter = 2
        while true {
            let candidate = directory.appendingPathComponent("\(stem)_\(counter).\(ext)")
            if !FileManager.default.fileExists(atPath: candidate.path) { return candidate }
            counter += 1
        }
    }
}
