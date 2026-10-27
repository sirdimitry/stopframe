import AVFoundation
import CoreGraphics
import Foundation

/// 60 evenly-spaced thumbnails per video — the highest-volume decode
/// operation in the app, so results are cached to disk (`FilmstripCache`).
enum FilmstripGenerator {
    static let thumbnailCount = 60

    static func thumbnails(duration: Double, url: URL) async -> [CGImage] {
        let attributes = try? FileManager.default.attributesOfItem(atPath: url.path)
        let size = (attributes?[.size] as? Int) ?? 0
        let mtime = (attributes?[.modificationDate] as? Date)?.timeIntervalSince1970 ?? 0
        let fingerprint = FilmstripCache.fingerprint(path: url.path, size: size, mtime: mtime, count: thumbnailCount)

        if let cached = FilmstripCache.load(fingerprint: fingerprint, count: thumbnailCount) {
            return cached
        }

        guard duration > 0 else { return [] }
        let times: [CMTime] = (0..<thumbnailCount).map { index in
            let fraction = thumbnailCount > 1 ? Double(index) / Double(thumbnailCount - 1) : 0
            return CMTime(seconds: fraction * max(0,duration-0.001), preferredTimescale: 600)
        }

        let maximumSize = CGSize(width: 0, height: Double(FilmstripCache.thumbnailHeight))
        let results = await FrameGeneratorProvider.shared.images(url: url, at: times, maximumSize: maximumSize)
        let ordered = results.sorted { $0.time.seconds < $1.time.seconds }.map(\.image)

        if !ordered.isEmpty {
            FilmstripCache.save(fingerprint: fingerprint, thumbnails: ordered)
        }
        return ordered
    }
}
