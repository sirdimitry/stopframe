import CoreGraphics
import CryptoKit
import Foundation
import ImageIO
import UniformTypeIdentifiers

/// Disk cache for filmstrip thumbnails, stored under Caches (pure derived
/// data, safe to purge). One horizontal contact-sheet HEIC per video instead
/// of N loose files — cheap to write/read/invalidate as a single unit.
/// The fingerprint is embedded in the filename, so a stale cache is simply a
/// miss (no separate manifest needed) — mirrors the original's
/// SHA256(path+size+mtime+count) invalidation key.
enum FilmstripCache {
    static let thumbnailHeight = 64

    static func fingerprint(path: String, size: Int, mtime: Double, count: Int) -> String {
        let input = "\(path)|\(size)|\(mtime)|\(count)"
        let digest = SHA256.hash(data: Data(input.utf8))
        return digest.map { String(format: "%02x", $0) }.joined()
    }

    private static func cacheURL(forFingerprint fingerprint: String) -> URL {
        AppPaths.filmstripCacheDirectory.appendingPathComponent("\(fingerprint).heic")
    }

    static func load(fingerprint: String, count: Int) -> [CGImage]? {
        let url = cacheURL(forFingerprint: fingerprint)
        guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
              let contactSheet = CGImageSourceCreateImageAtIndex(source, 0, nil)
        else { return nil }

        let sheetWidth = contactSheet.width
        let sheetHeight = contactSheet.height
        guard count > 0, sheetHeight > 0 else { return nil }
        let tileWidth = sheetWidth / count
        guard tileWidth > 0 else { return nil }

        var thumbnails: [CGImage] = []
        for i in 0..<count {
            let rect = CGRect(x: i * tileWidth, y: 0, width: tileWidth, height: sheetHeight)
            guard let tile = contactSheet.cropping(to: rect) else { return nil }
            thumbnails.append(tile)
        }
        return thumbnails
    }

    static func save(fingerprint: String, thumbnails: [CGImage]) {
        guard let first = thumbnails.first else { return }
        let tileWidth = first.width
        let height = first.height
        let totalWidth = tileWidth * thumbnails.count
        guard totalWidth > 0, height > 0,
              let colorSpace = CGColorSpace(name: CGColorSpace.sRGB),
              let context = CGContext(
                data: nil,
                width: totalWidth,
                height: height,
                bitsPerComponent: 8,
                bytesPerRow: 0,
                space: colorSpace,
                bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue
              )
        else { return }

        for (index, thumbnail) in thumbnails.enumerated() {
            let rect = CGRect(x: index * tileWidth, y: 0, width: thumbnail.width, height: thumbnail.height)
            context.draw(thumbnail, in: rect)
        }

        guard let combined = context.makeImage() else { return }
        let url = cacheURL(forFingerprint: fingerprint)
        guard let destination = CGImageDestinationCreateWithURL(
            url as CFURL, UTType.heic.identifier as CFString, 1, nil
        ) else { return }
        CGImageDestinationAddImage(destination, combined, nil)
        CGImageDestinationFinalize(destination)
    }
}
