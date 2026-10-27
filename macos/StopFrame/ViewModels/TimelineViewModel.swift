import AVFoundation
import CoreGraphics
import Observation

@Observable
@MainActor
final class TimelineViewModel {
    private let appState: AppState

    var activeVideoID: VideoItem.ID?
    var previewImage: CGImage?
    var thumbnailsByVideoID: [VideoItem.ID: [CGImage]] = [:]
    var playheadFractionByVideoID: [VideoItem.ID: Double] = [:]
    var shortcutsEnabled = false

    init(appState: AppState) {
        self.appState = appState
    }

    var activeVideo: VideoItem? {
        guard let id = activeVideoID else { return nil }
        return appState.videos.first { $0.id == id }
    }

    func playheadFraction(for videoID: VideoItem.ID) -> Double {
        playheadFractionByVideoID[videoID] ?? 0
    }

    func markers(for videoID: VideoItem.ID) -> [FrameCandidate] {
        appState.markers(for: videoID)
    }

    private var previewTask: Task<Void, Never>?
    private var previewRevision = 0
    func reset() {
        previewTask?.cancel()
        previewRevision += 1
        activeVideoID = nil; previewImage = nil
        thumbnailsByVideoID.removeAll(); playheadFractionByVideoID.removeAll()
    }
    func activate(_ video: VideoItem) {
        activeVideoID = video.id
        previewTask?.cancel()
        previewTask = Task { await renderPreview(for: video) }
    }

    func loadThumbnailsIfNeeded(for video: VideoItem) {
        guard thumbnailsByVideoID[video.id] == nil else { return }
        Task {
            let thumbnails = await resolvedURL(for: video) { url in
                await FilmstripGenerator.thumbnails(duration: video.durationSeconds, url: url)
            }
            thumbnailsByVideoID[video.id] = thumbnails ?? []
        }
    }

    func setPlayhead(fraction: Double, for video: VideoItem) {
        let clamped = min(max(fraction, 0), video.durationSeconds > 0 ? max(0,1-1/max(1,video.durationSeconds*max(1,video.fps))) : 0)
        playheadFractionByVideoID[video.id] = clamped
        if activeVideoID == video.id {
            previewTask?.cancel()
        previewTask = Task { await renderPreview(for: video) }
        }
    }

    func step(by delta: Int) {
        guard let video = activeVideo, video.fps > 0, video.durationSeconds > 0 else { return }
        let currentFraction = playheadFraction(for: video.id)
        let currentFrame = Int((currentFraction * video.durationSeconds * video.fps).rounded())
        let nextFrame = min(max(0,Int((video.durationSeconds * video.fps).rounded(.down))-1),max(0,currentFrame+delta))
        let nextFraction = min(1, (Double(nextFrame) / video.fps) / video.durationSeconds)
        playheadFractionByVideoID[video.id] = nextFraction

        Task {
            let image = await resolvedURL(for: video) { url in
                try? await FrameStepper.shared.image(url: url, frameIndex: nextFrame, fps: video.fps)
            }
            if let image, activeVideoID == video.id {
                previewImage = image
            }
        }
    }

    func captureFrame() {
        guard let video = activeVideo, video.durationSeconds > 0 else { return }
        let fraction = playheadFraction(for: video.id)
        let timestamp = fraction * video.durationSeconds
        let frameIndex = video.fps > 0 ? Int((timestamp * video.fps).rounded()) : 0
        appState.captureManualFrame(video: video, timestampSeconds: timestamp, frameIndex: frameIndex)
    }

    private func renderPreview(for video: VideoItem) async {
        previewRevision += 1
        let revision = previewRevision
        let fraction = playheadFraction(for: video.id)
        let image = await resolvedURL(for: video) { url in
            let time = CMTime(seconds: fraction * video.durationSeconds, preferredTimescale: 600)
            return try? await FrameGeneratorProvider.shared.image(
                url: url, at: time, maximumSize: CGSize(width: 800, height: 0)
            )
        }
        if !Task.isCancelled, revision == previewRevision, activeVideoID == video.id {
            previewImage = image ?? nil
        }
    }

    /// Resolves the video's bookmark, brackets security-scoped access around
    /// `body`, and returns its result (or nil on resolution failure).
    private func resolvedURL<T>(for video: VideoItem, access body: (URL) async -> T) async -> T? {
        var mutableVideo = video
        guard let url = try? mutableVideo.bookmark.resolve() else { return nil }
        let granted = url.startAccessingSecurityScopedResource()
        defer { if granted { url.stopAccessingSecurityScopedResource() } }
        return await body(url)
    }
}
