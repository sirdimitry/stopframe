import AVFoundation

enum VideoProbeError: Error {
    case noVideoTrack
    case invalidDimensions
}

struct VideoProbeResult {
    var width: Int
    var height: Int
    var durationSeconds: Double
    var fps: Double
}

/// Cheap, metadata-only read (no frame decode) — the direct analog of the
/// original's `probe_video`, which is fast enough to call synchronously from
/// the UI as files are added.
enum VideoProbe {
    static func probe(url: URL) async throws -> VideoProbeResult {
        do { return try await nativeProbe(url: url) }
        catch { return try await FFmpegBridge.shared.probe(url) }
    }
    private static func nativeProbe(url: URL) async throws -> VideoProbeResult {
        let asset = AVURLAsset(url: url)
        guard let track = try await asset.loadTracks(withMediaType: .video).first else {
            throw VideoProbeError.noVideoTrack
        }

        // `naturalSize` alone ignores rotation metadata (e.g. a portrait phone
        // clip stored with landscape naturalSize + a 90° preferredTransform);
        // applying the transform gives the actual displayed width/height.
        let naturalSize = try await track.load(.naturalSize)
        let transform = try await track.load(.preferredTransform)
        let displaySize = naturalSize.applying(transform)
        let width = Int(abs(displaySize.width).rounded())
        let height = Int(abs(displaySize.height).rounded())
        guard width > 0, height > 0 else { throw VideoProbeError.invalidDimensions }

        let fps = try await track.load(.nominalFrameRate)
        let duration = try await asset.load(.duration)
        let durationSeconds = duration.isNumeric ? CMTimeGetSeconds(duration) : 0

        return VideoProbeResult(
            width: width,
            height: height,
            durationSeconds: max(0, durationSeconds),
            fps: Double(fps)
        )
    }
}
