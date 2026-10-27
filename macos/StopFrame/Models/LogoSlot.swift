import Foundation

/// A full-frame PNG overlay for one slot, plus a fine nudge (offset/scale) on
/// top of it — the nudge is a minor adjustment, not the main placement mechanism.
struct LogoSlot: Codable, Equatable {
    var imageBookmark: SecureBookmark?
    var offsetX: Int = 0
    var offsetY: Int = 0
    var scale: Double = 1.0
}
