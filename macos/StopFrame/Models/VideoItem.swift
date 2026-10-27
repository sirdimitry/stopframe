import Foundation

/// An imported source video. `id` is a stable UUID independent of the file
/// path so `FrameCandidate.videoID` references survive file moves as long as
/// the bookmark still resolves. `fileName` is cached at import time so the UI
/// can display/log it without needing to resolve the bookmark (and per the
/// original's privacy rule, only the file name is ever logged, never the full path).
struct VideoItem: Codable, Identifiable, Equatable {
    var id: UUID = UUID()
    var bookmark: SecureBookmark
    var fileName: String
    var width: Int
    var height: Int
    var durationSeconds: Double
    var fps: Double
    var aspect: AspectClass

    var isPhoto: Bool { PhotoSource.extensions.contains(URL(fileURLWithPath: fileName).pathExtension.lowercased()) }

    var orientation: Orientation {
        height > width ? .portrait : .landscape
    }
}
