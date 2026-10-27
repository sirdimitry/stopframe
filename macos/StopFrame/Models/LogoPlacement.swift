import Foundation

/// Per-frame logo placement: which slot, plus this specific frame's own
/// offset/scale nudge (seeded from the slot's default when first assigned).
struct LogoPlacement: Codable, Hashable {
    var slotKey: LogoSlotKey
    var offsetX: Int = 0
    var offsetY: Int = 0
    var scale: Double = 1.0
}
