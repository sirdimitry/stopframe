import CoreGraphics
import Vision

struct FaceQualityResult {
    var faceFound: Bool = false
    var eyesOpen: Bool
    var mouthClosed: Bool
}

/// Vision-based face-quality check: eyes-open / mouth-closed, the analog of
/// the original's MediaPipe FaceMesh EAR/mouth-ratio check. Vision exposes
/// named landmark regions rather than MediaPipe's flat 468-point mesh, so
/// the original's literal point indices don't transfer — this reads
/// `leftEye`/`rightEye`/`innerLips` region bounding-box ratios instead.
/// Thresholds start at the original's 0.15 and are expected to need
/// recalibration against real footage, since the topology differs.
///
/// No face found, or any failure, means "no penalty" — this must never
/// block sharpness-only picking. Vision runs in-process; unlike MediaPipe,
/// it has no history of crashing on Metal/GPU init, so no subprocess
/// isolation is needed here.
enum FaceQualityAnalyzer {
    static let eyeOpenRatioThreshold: CGFloat = 0.15
    static let mouthClosedRatioThreshold: CGFloat = 0.15

    static func analyze(_ cgImage: CGImage) -> FaceQualityResult? {
        let request = VNDetectFaceLandmarksRequest()
        let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
        guard (try? handler.perform([request])) != nil else { return nil }
        let faces = request.results ?? []
        if faces.isEmpty { return FaceQualityResult(faceFound: false, eyesOpen: true, mouthClosed: true) }
        var eyes = true, mouth = true
        for face in faces {
            guard let landmarks = face.landmarks else { return nil }
            let box = face.boundingBox
            let pixelAspect = box.height * CGFloat(cgImage.height) / max(0.001,box.width * CGFloat(cgImage.width))
            eyes = eyes && eyesOpen(landmarks,pixelAspect: pixelAspect)
            mouth = mouth && mouthClosed(landmarks,pixelAspect: pixelAspect)
        }
        return FaceQualityResult(faceFound: true, eyesOpen: eyes, mouthClosed: mouth)
    }

    private static func eyesOpen(_ landmarks: VNFaceLandmarks2D,pixelAspect: CGFloat) -> Bool {
        let ratios = [openRatio(of: landmarks.leftEye), openRatio(of: landmarks.rightEye)].compactMap { $0 }
        guard !ratios.isEmpty else { return true }
        return ratios.allSatisfy { $0 * pixelAspect > eyeOpenRatioThreshold }
    }

    private static func mouthClosed(_ landmarks: VNFaceLandmarks2D,pixelAspect: CGFloat) -> Bool {
        guard let ratio = openRatio(of: landmarks.innerLips) else { return true }
        return ratio * pixelAspect < mouthClosedRatioThreshold
    }

    /// height/width of a landmark region's own normalized bounding box —
    /// scale-invariant, so no pixel-space conversion is needed.
    private static func openRatio(of region: VNFaceLandmarkRegion2D?) -> CGFloat? {
        guard let region, region.pointCount > 0 else { return nil }
        let points = region.normalizedPoints
        guard let minX = points.map(\.x).min(), let maxX = points.map(\.x).max(),
              let minY = points.map(\.y).min(), let maxY = points.map(\.y).max(),
              maxX - minX > 0
        else { return nil }
        return (maxY - minY) / (maxX - minX)
    }
}
