import Foundation
import ImageIO

/// Rule-based, no ML/CV content recognition — matches PNG files in one
/// folder to the 8 fixed slots so a user only has to point at a folder once.
enum LogoMatcher {
    private static let leftKeywords = ["слева", "лево", "left"]
    private static let rightKeywords = ["справа", "право", "right"]

    /// First-alphabetical file wins any slot collision; the rest are
    /// silently skipped (no UI warning — just a log line, matching the original).
    static func matchLogos(in folder: URL) -> [LogoSlotKey: URL] {
        guard let enumerator = FileManager.default.enumerator(
            at: folder, includingPropertiesForKeys: [.isRegularFileKey], options: [.skipsHiddenFiles]
        ) else { return [:] }

        var pngURLs: [URL] = []
        for case let url as URL in enumerator where url.pathExtension.lowercased() == "png" {
            pngURLs.append(url)
        }
        pngURLs.sort { $0.path < $1.path }

        var result: [LogoSlotKey: URL] = [:]
        for url in pngURLs {
            guard let side = side(from: url.lastPathComponent) else { continue }
            guard let (width, height) = pixelSize(of: url) else { continue }

            let parentFolderName = url.deletingLastPathComponent().lastPathComponent
            let fileStem = url.deletingPathExtension().lastPathComponent
            let aspect = detectAspect(text: "\(parentFolderName) \(fileStem)", width: width, height: height)
            guard aspect != .other else { continue }

            let orientation: Orientation = height > width ? .portrait : .landscape
            let key = LogoSlotKey(aspect: aspect, orientation: orientation, side: side)
            if result[key] == nil {
                result[key] = url
            }
        }
        return result
    }

    /// Side comes only from filename keywords — it can't be read from pixels.
    private static func side(from fileName: String) -> LogoSide? {
        let lower = fileName.lowercased()
        let hasLeft = leftKeywords.contains { lower.contains($0) }
        let hasRight = rightKeywords.contains { lower.contains($0) }
        if hasLeft && !hasRight { return .left }
        if hasRight && !hasLeft { return .right }
        return nil
    }

    /// Aspect prefers text (filename/folder) over pixel dimensions — these
    /// overlay PNGs are often exported at an unrelated source resolution, so
    /// a text label like "...4na3.png" is more reliable than raw pixel ratio.
    private static func detectAspect(text: String, width: Int, height: Int) -> AspectClass {
        // Ratios are explicit tokens, not arbitrary occurrences of digits
        // in a date, camera filename or ancestor folder.
        let lower = text.lowercased()
        let sixteenNine = #"(?<![0-9])16\s*(?:[:x×/_-]|на|na)\s*9(?![0-9])"#
        let fourThree = #"(?<![0-9])4\s*(?:[:x×/_-]|на|na)\s*3(?![0-9])"#
        if lower.range(of: sixteenNine,options: .regularExpression) != nil { return .sixteenNine }
        if lower.range(of: fourThree,options: .regularExpression) != nil { return .fourThree }
        return AspectClass.logoFamily(width: width,height: height)
    }

    private static func pixelSize(of url: URL) -> (width: Int, height: Int)? {
        guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
              let properties = CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [CFString: Any],
              let width = properties[kCGImagePropertyPixelWidth] as? Int,
              let height = properties[kCGImagePropertyPixelHeight] as? Int
        else { return nil }
        return (width, height)
    }
}
