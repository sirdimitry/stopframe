import CoreGraphics
import Vision

/// Chooses which third of a frame is "calmer" for logo placement, combining
/// Sobel edge density with a bonus weight for any detected face in a third.
/// The bonus is proportional to the frame's own edge-density scale (not a
/// fixed constant) so it stays meaningful regardless of content/resolution —
/// edge-density sums vary by orders of magnitude between a busy and a flat frame.
enum AdaptiveSideSelector {
    static let faceBonusFraction: Double = 0.5

    static func chooseSide(for cgImage: CGImage) -> LogoSide {
        guard let edges = EdgeDensityAnalyzer.analyze(cgImage) else { return .left }

        var leftScore = edges.left
        var rightScore = edges.right
        let bonus = max(leftScore, rightScore, 1) * faceBonusFraction

        let width = Double(cgImage.width)
        for box in faceBoundingBoxes(in: cgImage) {
            let centerX = box.midX * width
            if centerX < width / 3 {
                leftScore += bonus
            } else if centerX > width * 2 / 3 {
                rightScore += bonus
            }
            // A face centered in the middle third biases neither side.
        }

        return leftScore <= rightScore ? .left : .right
    }

    private static func faceBoundingBoxes(in cgImage: CGImage) -> [CGRect] {
        let request = VNDetectFaceRectanglesRequest()
        let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
        guard (try? handler.perform([request])) != nil else { return [] }
        return (request.results ?? []).map(\.boundingBox)
    }
}
