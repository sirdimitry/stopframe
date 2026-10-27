import CoreImage
import ImageIO

/// Eager, pixel-backed logo decoding and the same Core Image composition as
/// export. Encoded file providers are never retained after scoped access ends.
actor ImagePostProcessor {
    static let shared = ImagePostProcessor()
    private let context = LogoCompositor.sharedContext
    private var cache: [String: CGImage] = [:]
    private var order: [String] = []
    private var bytes = 0
    private let limit = 64 * 1024 * 1024

    func applyHDRFix(to image: CGImage) -> CGImage {
        let fixed = HLGToRec709Converter.apply(to: CIImage(cgImage: image))
        return context.createCGImage(fixed,from: fixed.extent) ?? image
    }
    func decodeLogo(url: URL,maxDimension: Int? = nil) -> CGImage? {
        let values = try? url.resourceValues(forKeys: [.contentModificationDateKey,.fileSizeKey])
        let key = "\(url.standardizedFileURL.path)|\(values?.contentModificationDate?.timeIntervalSince1970 ?? 0)|\(values?.fileSize ?? 0)|\(maxDimension ?? 0)"
        if let image = cache[key] {
            order.removeAll { $0 == key }; order.append(key); return image
        }
        guard let data = try? Data(contentsOf: url),
              let source = CGImageSourceCreateWithData(data as CFData,nil) else { return nil }
        let decoded: CGImage?
        if let maxDimension {
            let options: [CFString: Any] = [
                kCGImageSourceCreateThumbnailFromImageAlways: true,
                kCGImageSourceCreateThumbnailWithTransform: true,
                kCGImageSourceThumbnailMaxPixelSize: maxDimension,
                kCGImageSourceShouldCacheImmediately: true
            ]
            decoded = CGImageSourceCreateThumbnailAtIndex(source,0,options as CFDictionary)
        } else {
            decoded = CGImageSourceCreateImageAtIndex(source,0,[kCGImageSourceShouldCacheImmediately: true] as CFDictionary)
        }
        guard let decoded,
              let image = context.createCGImage(CIImage(cgImage: decoded),from: CGRect(x: 0,y: 0,width: decoded.width,height: decoded.height),format: .RGBA8,colorSpace: CGColorSpace(name: CGColorSpace.sRGB)) else { return nil }
        let cost = image.bytesPerRow*image.height
        while bytes+cost > limit,let oldest = order.first {
            if let evicted = cache.removeValue(forKey: oldest) { bytes -= evicted.bytesPerRow*evicted.height }
            order.removeFirst()
        }
        if cost <= limit { cache[key] = image; order.append(key); bytes += cost }
        return image
    }
    func logo(settings: Settings,slotKey: LogoSlotKey,maxDimension: Int? = nil) throws -> CGImage? {
        guard settings.exportIncludeLogo, var bookmark = settings.logoSlots[slotKey.stringValue]?.imageBookmark else { return nil }
        var accessed: [URL] = []
        defer { for url in accessed { url.stopAccessingSecurityScopedResource() } }
        if var folderBookmark = settings.logosFolder,let folder = try? folderBookmark.resolve(),folder.startAccessingSecurityScopedResource() { accessed.append(folder) }
        let url = try bookmark.resolve()
        if url.startAccessingSecurityScopedResource() { accessed.append(url) }
        guard let image = decodeLogo(url: url,maxDimension: maxDimension) else { throw FrameExportError.missingLogo }
        return image
    }
    func preview(base: CGImage,imageSize: CGSize,placement: LogoPlacement,settings: Settings) throws -> CGImage {
        guard settings.exportIncludeLogo else { return base }
        guard let logo = try logo(settings: settings,slotKey: placement.slotKey,maxDimension: max(base.width,base.height)) else { return base }
        let scale = CGSize(width: CGFloat(base.width)/max(1,imageSize.width),height: CGFloat(base.height)/max(1,imageSize.height))
        let result = LogoCompositor.compose(frame: CIImage(cgImage: base),logo: CIImage(cgImage: logo),placement: placement,offsetScale: scale)
        guard let image = context.createCGImage(result,from: result.extent) else { throw FrameExportError.encodingFailed }
        return image
    }
}
