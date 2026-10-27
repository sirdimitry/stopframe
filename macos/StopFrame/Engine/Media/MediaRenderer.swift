import AVFoundation
import CoreImage
import ImageIO

/// One transform pipeline for cards, detail and export. Logo is applied after rotation.
actor MediaRenderer {
    static let shared = MediaRenderer()
    private let context = CIContext()

    func read(url: URL, source: VideoItem, candidate: FrameCandidate, maxDimension: Int? = nil) async throws -> CGImage {
        let raw: CGImage
        if source.isPhoto {
            raw = try PhotoSource.read(url: url, maxDimension: maxDimension)
        } else if let maxDimension {
            raw = try await FrameGeneratorProvider.shared.image(
                url: url, at: CMTime(seconds: candidate.timestampSeconds, preferredTimescale: 600),
                maximumSize: CGSize(width: maxDimension, height: maxDimension))
        } else {
            raw = try await VideoReader.readFrame(url: url, at: CMTime(seconds: candidate.timestampSeconds, preferredTimescale: 600))
        }
        return process(raw, turns: candidate.turns, hdrFix: candidate.hdrFix)
    }

    func process(_ raw: CGImage, turns: Int, hdrFix: Bool) -> CGImage {
        var image = CIImage(cgImage: raw)
        let orientation: Int32 = [1, 6, 3, 8][((turns % 4) + 4) % 4]
        image = image.oriented(forExifOrientation: orientation)
        image = image.transformed(by: CGAffineTransform(translationX: -image.extent.minX, y: -image.extent.minY))
        if hdrFix { image = HLGToRec709Converter.apply(to: image) }
        return context.createCGImage(image, from: image.extent) ?? raw
    }
}
