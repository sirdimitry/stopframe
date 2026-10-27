import AVFoundation
import CoreImage

/// Exact ±1 native-frame stepping.
///
/// `AVAssetImageGenerator`, even at zero tolerance, was measured to
/// occasionally return a duplicate/skipped frame across a run of sequential
/// frame requests on real footage (its seek-then-decode model isn't
/// guaranteed frame-exact for every codec/timing). This instead sequentially
/// decodes with `AVAssetReader`, which delivers samples in true presentation
/// order — the only way to guarantee distinct, monotonically increasing
/// frames matching `frameIndex/fps` exactly.
///
/// A "cursor" (an open reader positioned at the next frame it will deliver)
/// is kept per URL so the common case — repeated arrow-key stepping forward
/// by one frame at a time — is O(1) per step instead of rescanning from zero.
actor FrameStepper {
    static let shared = FrameStepper()

    private struct Cursor {
        var url: URL
        var reader: AVAssetReader
        var output: AVAssetReaderTrackOutput
        var transform: CGAffineTransform
        /// Index of the frame `output.copyNextSampleBuffer()` will return next.
        var nextFrameIndex: Int
    }

    private var cursor: Cursor?
    private let ciContext = CIContext()

    func image(url: URL, frameIndex: Int, fps: Double) async throws -> CGImage {
        let target = max(0, frameIndex)

        // Fast path: the cursor is already positioned at or before the target
        // for this file — step forward without restarting the reader.
        if var active = cursor, active.url == url, active.nextFrameIndex <= target {
            while active.nextFrameIndex < target, active.reader.status == .reading,
                  active.output.copyNextSampleBuffer() != nil {
                active.nextFrameIndex += 1
            }
            if active.nextFrameIndex == target, active.reader.status == .reading,
               let sampleBuffer = active.output.copyNextSampleBuffer(),
               let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) {
                active.nextFrameIndex += 1
                cursor = active
                return try render(pixelBuffer: pixelBuffer, transform: active.transform)
            }
        }

        // Slow path: backward seek, jump, or first request for this file —
        // start a fresh reader from the beginning and scan forward.
        let asset = AVURLAsset(url: url)
        guard let track = try await asset.loadTracks(withMediaType: .video).first else {
            throw VideoProbeError.noVideoTrack
        }
        let transform = try await track.load(.preferredTransform)

        let reader = try AVAssetReader(asset: asset)
        let output = AVAssetReaderTrackOutput(
            track: track,
            outputSettings: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA]
        )
        output.alwaysCopiesSampleData = false
        reader.add(output)
        reader.startReading()

        var index = 0
        var lastPixelBuffer: CVPixelBuffer?
        while index <= target, reader.status == .reading, let sampleBuffer = output.copyNextSampleBuffer() {
            if let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) {
                lastPixelBuffer = pixelBuffer
            }
            index += 1
        }

        guard let pixelBuffer = lastPixelBuffer else {
            throw VideoProbeError.invalidDimensions
        }

        cursor = Cursor(url: url, reader: reader, output: output, transform: transform, nextFrameIndex: index)
        return try render(pixelBuffer: pixelBuffer, transform: transform)
    }

    private func render(pixelBuffer: CVPixelBuffer, transform: CGAffineTransform) throws -> CGImage {
        var ciImage = CIImage(cvPixelBuffer: pixelBuffer).transformed(by: transform)
        ciImage = ciImage.transformed(by: CGAffineTransform(
            translationX: -ciImage.extent.origin.x, y: -ciImage.extent.origin.y
        ))
        guard let cgImage = ciContext.createCGImage(ciImage, from: ciImage.extent) else {
            throw VideoProbeError.invalidDimensions
        }
        return cgImage
    }

    func evict(url: URL) {
        if cursor?.url == url { cursor = nil }
    }
}
