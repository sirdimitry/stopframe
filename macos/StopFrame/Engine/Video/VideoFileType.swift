import UniformTypeIdentifiers
import Foundation

/// Matches the original's `VIDEO_EXTENSIONS`. Filtering is extension-based
/// (not purely UTType-based) because some of these — .avi, .mkv — don't
/// always have a system-registered UTType, and AVFoundation may not be able
/// to decode every container even when the extension matches; that's a
/// runtime probe failure (logged, skipped), not an import-time filter concern.
enum VideoFileType {
    static let extensions: Set<String> = ["mp4", "mov", "m4v", "avi", "mkv", "mts", "m2ts", "webm", "mpg", "mpeg"]

    static var allowedContentTypes: [UTType] {
        extensions.compactMap { UTType(filenameExtension: $0) }
    }

    static func isVideoFile(_ url: URL) -> Bool {
        extensions.contains(url.pathExtension.lowercased())
    }

    /// Recursive folder scan, sorted for a deterministic result regardless of
    /// filesystem enumeration order — mirrors `find_videos_in_folder`.
    static func findVideos(in folder: URL) -> [URL] {
        guard let enumerator = FileManager.default.enumerator(
            at: folder,
            includingPropertiesForKeys: [.isRegularFileKey],
            options: [.skipsHiddenFiles]
        ) else { return [] }

        var results: [URL] = []
        for case let url as URL in enumerator where isVideoFile(url) {
            results.append(url)
        }
        return results.sorted { $0.path < $1.path }
    }
}
