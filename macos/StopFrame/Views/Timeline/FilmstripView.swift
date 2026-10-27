import SwiftUI

/// Shows as many of the cached thumbnails as fit at their natural aspect
/// ratio (like a DaVinci/Premiere/Final Cut filmstrip) rather than squeezing
/// all of them into whatever width is available — cramming e.g. 60 thumbnails
/// into a narrow strip turns each into an unrecognizable 1-pixel-wide sliver.
/// `thumbnails == nil` means "not requested/still loading yet"; `thumbnails == []`
/// means a request was made and came back empty ("could not read video") —
/// the original distinguishes these two states the same way.
struct FilmstripView: View {
    let thumbnails: [CGImage]?
    let markers: [FrameCandidate]
    let duration: Double
    let playheadFraction: Double
    let onScrub: (Double) -> Void

    var body: some View {
        GeometryReader { proxy in
            Canvas { context, size in
                draw(context: context, size: size)
            }
            .background(Palette.bgSurfaceAlt)
            .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { value in
                        guard proxy.size.width > 0 else { return }
                        onScrub(max(0, min(1, value.location.x / proxy.size.width)))
                    }
            )
        }
    }

    private func draw(context: GraphicsContext, size: CGSize) {
        guard let thumbnails, !thumbnails.isEmpty else {
            let message = thumbnails == nil ? "Loading…" : "Could not read video"
            let color: Color = thumbnails == nil ? Palette.textSecondary : Palette.danger
            context.draw(
                Text(message).font(.caption).foregroundStyle(color),
                at: CGPoint(x: size.width / 2, y: size.height / 2)
            )
            return
        }

        let trackHeight = size.height - 6
        for (rect, cgImage) in visibleTiles(thumbnails: thumbnails, size: size, trackHeight: trackHeight) {
            context.draw(Image(decorative: cgImage, scale: 1), in: rect)
        }

        if duration > 0 {
            for marker in markers {
                let fraction = marker.timestampSeconds / duration
                let x = CGFloat(fraction) * size.width
                let color = marker.origin == .auto ? Palette.autoMarker : Palette.manualMarker
                context.fill(Path(CGRect(x: x - 2, y: trackHeight, width: 4, height: 6)), with: .color(color))
            }
        }

        let playheadX = CGFloat(playheadFraction) * size.width
        context.fill(Path(CGRect(x: playheadX - 1, y: 0, width: 2, height: size.height)), with: .color(Palette.playhead))
    }

    /// Picks evenly-spaced thumbnails from the cached set so each tile is
    /// drawn close to its natural aspect ratio, then stretches that count to
    /// exactly fill the width (a few percent of stretch is imperceptible;
    /// squeezing 60 tiles into a narrow strip is not).
    private func visibleTiles(thumbnails: [CGImage], size: CGSize, trackHeight: CGFloat) -> [(CGRect, CGImage)] {
        guard let first = thumbnails.first, first.height > 0, trackHeight > 0, size.width > 0 else { return [] }

        let naturalAspect = CGFloat(first.width) / CGFloat(first.height)
        let naturalTileWidth = trackHeight * naturalAspect
        let visibleCount = max(1, min(thumbnails.count, Int(size.width / naturalTileWidth)))

        let indices: [Int] = (0..<visibleCount).map { i in
            visibleCount > 1
                ? Int((Double(i) * Double(thumbnails.count - 1) / Double(visibleCount - 1)).rounded())
                : 0
        }

        let tileWidth = size.width / CGFloat(visibleCount)
        return indices.enumerated().map { position, thumbnailIndex in
            let rect = CGRect(x: CGFloat(position) * tileWidth, y: 0, width: tileWidth, height: trackHeight)
            return (rect, thumbnails[thumbnailIndex])
        }
    }
}
