import CoreGraphics
import Vision

/// On-device content embedding via Vision — used to measure how visually
/// different two frames are (framing/content/shot-scale), not just how far
/// apart in time they are. No network call, no bundled model: Vision's
/// feature print is built into the OS.
enum FeaturePrintAnalyzer {
    static func featurePrint(for cgImage: CGImage) -> VNFeaturePrintObservation? {
        let request = VNGenerateImageFeaturePrintRequest()
        let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
        guard (try? handler.perform([request])) != nil else { return nil }
        return request.results?.first as? VNFeaturePrintObservation
    }

    /// Higher = more visually different. Returns nil if the two prints
    /// aren't comparable (shouldn't normally happen for same-size requests).
    static func distance(_ a: VNFeaturePrintObservation, _ b: VNFeaturePrintObservation) -> Float? {
        var distance: Float = 0
        guard (try? a.computeDistance(&distance, to: b)) != nil else { return nil }
        return distance
    }
}
