import Foundation
import CoreGraphics

/// A captured frame ("screenshot"). Soft-deletable via `included` — excluding
/// a frame in the UI never removes it from the store, it just stops appearing.
struct FrameCandidate: Codable, Identifiable, Equatable {
    var id: UUID = UUID()
    var videoID: UUID
    var frameIndex: Int
    var timestampSeconds: Double
    var origin: FrameOrigin
    var logoPlacement: LogoPlacement
    var included: Bool = true
    var sharpnessScore: Double = 0
    var hdrFix: Bool = false
    // Optional preserves projects written before rotation was introduced.
    var rotationQuarterTurns: Int? = nil
    var turns: Int { ((rotationQuarterTurns ?? 0) % 4 + 4) % 4 }
    func imageSize(for source: VideoItem) -> CGSize {
        turns % 2 == 0 ? CGSize(width: source.width, height: source.height)
                       : CGSize(width: source.height, height: source.width)
    }
}
