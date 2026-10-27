import CoreGraphics
import ImageIO
import Foundation

enum PhotoSource {
    static let extensions: Set<String> = ["jpg", "jpeg", "png", "webp", "tif", "tiff", "bmp", "heic", "heif"]

    static func read(url: URL, maxDimension: Int? = nil) throws -> CGImage {
        guard let source = CGImageSourceCreateWithURL(url as CFURL, nil) else { throw VideoReaderError.noFrame }
        let properties = CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [CFString: Any]
        let width = properties?[kCGImagePropertyPixelWidth] as? Int ?? 1
        let height = properties?[kCGImagePropertyPixelHeight] as? Int ?? 1
        // ImageIO applies all eight EXIF orientations, including mirrors.
        let options: [CFString: Any] = [
            kCGImageSourceCreateThumbnailFromImageAlways: true,
            kCGImageSourceCreateThumbnailWithTransform: true,
            kCGImageSourceThumbnailMaxPixelSize: maxDimension ?? max(width, height),
            kCGImageSourceShouldCacheImmediately: true
        ]
        guard let image = CGImageSourceCreateThumbnailAtIndex(source, 0, options as CFDictionary) else {
            throw VideoReaderError.noFrame
        }
        return image
    }

    static func size(url: URL) throws -> CGSize {
        guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
              let props = CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [CFString: Any],
              let width = props[kCGImagePropertyPixelWidth] as? Int,
              let height = props[kCGImagePropertyPixelHeight] as? Int else { throw VideoReaderError.noFrame }
        let orientation = props[kCGImagePropertyOrientation] as? Int ?? 1
        return (5...8).contains(orientation) ? CGSize(width: height, height: width) : CGSize(width: width, height: height)
    }
}
