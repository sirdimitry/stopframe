import AVFoundation
import CoreImage

enum VideoReaderError: Error {
    case noVideoTrack
    case noFrame
}

/// Transient, single-use, full-resolution frame read — the direct analog of
/// the original's `cv2.VideoCapture` + `.set(CAP_PROP_POS_MSEC)` + `.read()`.
/// Used only for export, unlike `FrameGeneratorProvider` (persistent,
/// tolerant, for live scrubbing/thumbnails) — export needs a precise,
/// uncompressed, full-size sample, not a cached generator.
enum VideoReader {
    static func readFrame(url: URL, at time: CMTime) async throws -> CGImage {
        do { return try await nativeFrame(url: url,at: time) }
        catch { return try await FFmpegBridge.shared.frame(url,seconds: time.seconds) }
    }
    private static func nativeFrame(url: URL,at time: CMTime) async throws -> CGImage {
        let asset = AVURLAsset(url: url)
        guard let track = try await asset.loadTracks(withMediaType: .video).first else {
            throw VideoReaderError.noVideoTrack
        }
        let transform = try await track.load(.preferredTransform)

        let reader = try AVAssetReader(asset: asset)
        reader.timeRange = CMTimeRange(start: time, duration: .positiveInfinity)
        let output = AVAssetReaderTrackOutput(
            track: track,
            outputSettings: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA]
        )
        output.alwaysCopiesSampleData = false
        reader.add(output)
        reader.startReading()

        guard let sampleBuffer = output.copyNextSampleBuffer(),
              let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer)
        else { throw VideoReaderError.noFrame }

        var ciImage = CIImage(cvPixelBuffer: pixelBuffer).transformed(by: transform)
        ciImage = ciImage.transformed(by: CGAffineTransform(
            translationX: -ciImage.extent.origin.x, y: -ciImage.extent.origin.y
        ))
        guard let cgImage = LogoCompositor.sharedContext.createCGImage(ciImage, from: ciImage.extent) else {
            throw VideoReaderError.noFrame
        }
        return cgImage
    }
}
