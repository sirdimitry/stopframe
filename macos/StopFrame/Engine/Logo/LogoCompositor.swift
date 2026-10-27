import CoreImage
import CoreImage.CIFilterBuiltins

/// Shared pixel composition for review thumbnails and full-resolution export.
/// Detail uses an eagerly decoded overlay with the same top-left geometry.
enum LogoCompositor {
    /// Shared across all call sites — CIContext creation is comparatively
    /// expensive, so it's created once rather than per render.
    static let sharedContext = CIContext()

    /// If `logo` is nil, returns `frame` unchanged. `frame` is never mutated.
    static func compose(frame: CIImage, logo: CIImage?, placement: LogoPlacement,offsetScale: CGSize = CGSize(width: 1,height: 1)) -> CIImage {
        guard let logo, logo.extent.width > 0, logo.extent.height > 0 else { return frame }

        // scale=1.0 means "the overlay exactly covers the frame", independent
        // of the source PNG's native pixel resolution.
        let scale = max(placement.scale, 0.01)
        let targetWidth = frame.extent.width * scale
        let targetHeight = frame.extent.height * scale
        let scaleTransform = CGAffineTransform(
            scaleX: targetWidth / logo.extent.width,
            y: targetHeight / logo.extent.height
        )

        // Core Image's Y axis increases upward; the offset convention here
        // (positive Y = move down) matches the original's top-left, Y-down
        // image space, so the Y translation is negated.
        let positioned = logo
            .transformed(by: scaleTransform)
            .transformed(by: CGAffineTransform(
                translationX: frame.extent.minX + CGFloat(placement.offsetX)*offsetScale.width,
                y: frame.extent.maxY - targetHeight - CGFloat(placement.offsetY)*offsetScale.height
            ))

        let filter = CIFilter.sourceOverCompositing()
        filter.inputImage = positioned
        filter.backgroundImage = frame
        return (filter.outputImage ?? frame).cropped(to: frame.extent)
    }
}
