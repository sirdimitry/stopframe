import Foundation

/// The session-persistence payload — new relative to the original, which
/// kept the video list and all captured frames in memory only (lost on
/// quit; only `Settings` persisted). `VideoItem.id` is a stable UUID
/// (not derived from path), so `FrameCandidate.videoID` references survive
/// across relaunches as long as the underlying bookmark still resolves.
struct ProjectDocument: Codable {
    var schemaVersion: Int = 1
    var videos: [VideoItem]
    var frameCandidates: [FrameCandidate]
}
