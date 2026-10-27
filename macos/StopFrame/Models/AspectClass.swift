import Foundation

/// Classified by long-side/short-side ratio, independent of rotation — a
/// portrait 1080x1920 clip is still "16:9 family", just rotated. Matches the
/// original's ±0.05 tolerance.
enum AspectClass: String, Codable, CaseIterable {
    case sixteenNine = "16:9"
    case fourThree = "4:3"
    case other

    /// Logo templates have two families. Square/3:2/5:4 media use 4:3;
    /// wide media use 16:9. Classification is independent of orientation.
    static func logoFamily(width: Int,height: Int) -> AspectClass {
        guard width > 0,height > 0 else { return .fourThree }
        let ratio = Double(max(width,height))/Double(min(width,height))
        return ratio >= (16.0/9.0 + 4.0/3.0)/2 ? .sixteenNine : .fourThree
    }
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
