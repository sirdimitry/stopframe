import AVFoundation
import CoreGraphics

/// Owns one AVAssetImageGenerator per active video, used for scrubbing and
/// thumbnail generation. Generous seek tolerance lets the generator snap to
/// the nearest available frame instead of decoding exactly, which is what
/// keeps scrubbing responsive. Exact-frame needs (±1 step, export) go through
/// `FrameStepper`/`VideoReader` instead, which use zero tolerance / a reader.
actor FrameGeneratorProvider {
    static let shared = FrameGeneratorProvider()

    private var generators: [URL: AVAssetImageGenerator] = [:]

    // Caps concurrent hardware-decode work across every video. Without this,
    // opening the Screenshots tab with dozens of videos fires one
    // AVAssetImageGenerator request per card simultaneously; macOS's shared
    // video-decode sessions serialize/starve under that many concurrent
    // requests, so some cards were observed stuck on "Loading…" indefinitely
    // rather than merely slow. Queuing keeps every request eventually
    // completing instead of some being starved. Kept low (rather than e.g.
    // 4) because the Frame Detail sheet's own read (below) runs alongside
    // this queue, not through it, and high-resolution source footage (4K/8K
    // drone/action-cam clips) makes each decode session heavy enough that
    // even a handful running together can saturate a laptop's GPU/decoder
    // and drag down the whole system, not just this app.
    private let maxConcurrentRequests = 2
    private var activeRequests = 0
    private var waiters: [CheckedContinuation<Void, Never>] = []

    private func acquireSlot() async {
        if activeRequests < maxConcurrentRequests {
            activeRequests += 1
            return
        }
        await withCheckedContinuation { continuation in
            waiters.append(continuation)
        }
    }

    private func releaseSlot() {
        if let next = waiters.first {
            waiters.removeFirst()
            next.resume()
        } else {
            activeRequests -= 1
        }
    }

    private func generator(for url: URL) -> AVAssetImageGenerator {

        let asset = AVURLAsset(url: url)
        let generator = AVAssetImageGenerator(asset: asset)
        generator.appliesPreferredTrackTransform = true
        generator.requestedTimeToleranceBefore = .zero
        generator.requestedTimeToleranceAfter = .zero

        return generator
    }

    func image(url: URL, at time: CMTime, maximumSize: CGSize) async throws -> CGImage {
        await acquireSlot()
        defer { releaseSlot() }
        let generator = generator(for: url)
        generator.maximumSize = maximumSize
        do { return try await generator.image(at: time).image }
        catch {
            let edge = Int(max(maximumSize.width,maximumSize.height))
            return try await FFmpegBridge.shared.frame(url,seconds: time.seconds,maxDimension: edge > 0 ? edge : nil)
        }
    }

    /// Used only by the single-at-a-time Frame Detail sheet's interactive
    /// read. Deliberately bypasses the queue above (that queue exists to
    /// stop dozens of background thumbnail loads from piling up simultaneous
    /// decode sessions; only one Frame Detail sheet can be open at a time,
    /// so this alone can't cause that pile-up).
    ///
    /// Capped to `maxDimension` rather than the source's native resolution
    /// (previously `.zero`, i.e. full native size): on 4K/8K source footage
    /// that meant decoding tens of millions of pixels just to display them
    /// shrunk into a ~700-point-wide preview box, which is exactly the
    /// decode cost that was making opening/editing this dialog slow and, at
    /// high enough resolutions, heavy enough to visibly load the whole
    /// system. `LogoPreviewGeometry` is fed the *video's* native
    /// width/height (from `VideoItem`), never this decoded image's actual
    /// pixel size, so downscaling here can't shift where the logo overlay
    /// lands — offsets stay defined in native-resolution units, matching
    /// what export (which reads full-resolution separately, via
    /// `VideoReader`) actually bakes in.
    func detailImage(url: URL, at time: CMTime, maxDimension: CGFloat = 1600) async throws -> CGImage {
        try await image(url: url,at: time,maximumSize: CGSize(width: maxDimension,height: maxDimension))
    }

    /// Batched fetch for filmstrip thumbnails — one call for all N times.
    /// Some requested times may fail to produce an image; those are dropped.
    func images(url: URL, at times: [CMTime], maximumSize: CGSize) async -> [(time: CMTime, image: CGImage)] {
        await acquireSlot()
        defer { releaseSlot() }
        let generator = generator(for: url)
        generator.maximumSize = maximumSize
        var results: [(time: CMTime, image: CGImage)] = []
        for await outcome in generator.images(for: times) {
            switch outcome {
            case .success(requestedTime: let requested, image: let image, actualTime: _):
                results.append((requested, image))
            case .failure:
                continue
            }
        }
        if results.isEmpty {
            for time in times {
                guard !Task.isCancelled else { break }
                if let image = try? await FFmpegBridge.shared.frame(url,seconds: time.seconds,maxDimension: 320) { results.append((time,image)) }
            }
        }
        return results
    }

    func evict(url: URL) {
        generators.removeValue(forKey: url)
    }
}
