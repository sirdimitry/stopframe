import Foundation

/// One of the 8 fixed logo slots: {16:9, 4:3} x {landscape, portrait} x {left, right}.
/// Each slot holds a full-frame PNG overlay for that exact combination, not a
/// small movable sprite.
struct LogoSlotKey: Codable, Hashable {
    var aspect: AspectClass
    var orientation: Orientation
    var side: LogoSide

    var stringValue: String {
        "\(aspect.rawValue)-\(orientation.rawValue)-\(side.rawValue)"
    }

    static let all: [LogoSlotKey] = {
        var result: [LogoSlotKey] = []
        for aspect: AspectClass in [.sixteenNine, .fourThree] {
            for orientation: Orientation in [.landscape, .portrait] {
                for side: LogoSide in [.left, .right] {
                    result.append(LogoSlotKey(aspect: aspect, orientation: orientation, side: side))
                }
            }
        }
        return result
    }()

    /// `.other` has no dedicated slot family and falls back to 16:9 — mirrors
    /// the original's `pick_slot_key`.
    static func resolve(aspect: AspectClass, orientation: Orientation, side: LogoSide) -> LogoSlotKey {
        let normalizedAspect: AspectClass = aspect == .fourThree ? .fourThree : .sixteenNine
        return LogoSlotKey(aspect: normalizedAspect, orientation: orientation, side: side)
    }
}
