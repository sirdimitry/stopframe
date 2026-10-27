import Foundation

/// Classified by long-side/short-side ratio, independent of rotation — a
/// portrait 1080x1920 clip is still "16:9 family", just rotated. Matches the
/// original's ±0.05 tolerance.
enum AspectClass: String, Codable, CaseIterable {
    case sixteenNine = "16:9"
    case fourThree = "4:3"
    case other

    private static let tolerance = 0.05

    static func classify(width: Int, height: Int) -> AspectClass {
        guard width > 0, height > 0 else { return .other }
        let long = Double(max(width, height))
        let short = Double(min(width, height))
        let ratio = long / short
        if abs(ratio - 16.0 / 9.0) <= tolerance { return .sixteenNine }
        if abs(ratio - 4.0 / 3.0) <= tolerance { return .fourThree }
        return .other
    }
}
