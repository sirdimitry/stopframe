import CoreGraphics

/// Pure geometry mapping a `LogoPlacement` (source-image pixel space, same
/// Y-up offset convention as `LogoCompositor`) onto on-screen points for an
/// aspect-fit image displayed inside `containerSize`. Shared by the
/// Screenshots card thumbnail and the Frame Detail preview so that dragging,
/// zooming, or nudging the logo is pure arithmetic — no Core Image re-render
/// needed just to reposition the on-screen overlay. `LogoCompositor` (via
/// this same math, kept in sync by hand) still owns the one real pixel
/// composite, run only for the card/preview's base image and for export.
enum LogoPreviewGeometry {
    static func fitScale(containerSize: CGSize, imageSize: CGSize) -> CGFloat {
        guard imageSize.width > 0, imageSize.height > 0 else { return 1 }
        return min(containerSize.width / imageSize.width, containerSize.height / imageSize.height)
    }

    static func rect(placement: LogoPlacement, containerSize: CGSize, imageSize: CGSize, fitScale: CGFloat) -> CGRect {
        guard imageSize.width > 0, imageSize.height > 0 else { return .zero }

        let displayedSize = CGSize(width: imageSize.width * fitScale, height: imageSize.height * fitScale)
        let baseOrigin = CGPoint(x: (containerSize.width - displayedSize.width) / 2, y: (containerSize.height - displayedSize.height) / 2)

        let logoScale = max(placement.scale, 0.01)
        let logoWidthInImage = imageSize.width * logoScale
        let logoHeightInImage = imageSize.height * logoScale
        // Offsets are measured from the image's top-left, matching export.
        let logoXInImage = Double(placement.offsetX)
        let logoYInImage = Double(placement.offsetY)

        return CGRect(
            x: baseOrigin.x + CGFloat(logoXInImage) * fitScale,
            y: baseOrigin.y + CGFloat(logoYInImage) * fitScale,
            width: logoWidthInImage * fitScale,
            height: logoHeightInImage * fitScale
        )
    }
}
