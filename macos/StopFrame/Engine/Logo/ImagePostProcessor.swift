import CoreImage
import ImageIO

actor ImagePostProcessor {
    static let shared = ImagePostProcessor()
    private let context = CIContext()
    private var cache: [String: CGImage] = [:]
    private var order: [String] = []
    private var bytes = 0
    private let limit = 64 * 1024 * 1024
    func applyHDRFix(to image: CGImage) -> CGImage {
        let fixed = HLGToRec709Converter.apply(to: CIImage(cgImage: image))
        return context.createCGImage(fixed,from: fixed.extent) ?? image
    }
    func decodeLogo(url: URL) -> CGImage? {
        let values = try? url.resourceValues(forKeys: [.contentModificationDateKey,.fileSizeKey])
        let key = "\(url.path)|\(values?.contentModificationDate?.timeIntervalSince1970 ?? 0)|\(values?.fileSize ?? 0)"
        if let image = cache[key] {
            order.removeAll { $0 == key }; order.append(key); return image
        }
        guard let source = CGImageSourceCreateWithURL(url as CFURL,nil),let image = CGImageSourceCreateImageAtIndex(source,0,nil) else { return nil }
        let cost = image.bytesPerRow*image.height
        while bytes+cost > limit, let oldest = order.first {
            if let evicted = cache.removeValue(forKey: oldest) { bytes -= evicted.bytesPerRow*evicted.height }
            order.removeFirst()
        }
        if cost <= limit { cache[key] = image; order.append(key); bytes += cost }
        return image
    }
}
