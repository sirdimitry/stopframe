import AVFoundation
import AppKit
import SwiftUI

struct FrameCardView: View {
    let candidate: FrameCandidate
    let video: VideoItem
    let isSelected: Bool
    let viewModel: ScreenshotsViewModel
    let onOpenDetail: () -> Void

    @Environment(AppState.self) private var appState
    @State private var image: CGImage?
    // Raw decoded logo asset (no compositing) — kept separate from `image`
    // so an open Frame Detail dialog's live drag/HDR edits on this same
    // candidate don't force a full decode + Core Image re-render of this
    // background card on every pixel of the drag.
    @State private var logoImage: CGImage?
    @State private var loadFailed = false

    var body: some View {
        VStack(spacing: 6) {
            ZStack(alignment: .topLeading) {
                thumbnail

                Text(candidate.origin == .photo ? "ФОТО" : candidate.origin == .auto ? "АВТО" : "ВРУЧНУЮ")
                    .font(.caption2.bold())
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(candidate.origin == .auto ? Palette.autoMarker : Palette.bgElevated)
                    // White text measures ~2.7:1 on the mid-brightness blue
                    // autoMarker fill — well short of 4.5:1; dark text there
                    // measures ~7.4:1. The dark bgElevated fill still needs
                    // white text (dark-on-dark would fail badly).
                    .foregroundStyle(candidate.origin == .auto ? Palette.bgApp : Color.white)
                    .clipShape(Capsule())
                    .padding(4)

                Button {
                    viewModel.toggleExclude(candidate.id)
                } label: {
                    Image(systemName: "xmark")
                        .font(.system(size: 10, weight: .bold))
                }
                .buttonStyle(.icon)
                .padding(4)
                .frame(maxWidth: .infinity, alignment: .trailing)
                .help("Исключить из экспорта")
                .accessibilityLabel("Исключить из экспорта")
                // Exposed as a custom action on the whole card below instead,
                // since the card combines its children into one VoiceOver element.
                .accessibilityHidden(true)
            }

            Text("\(video.fileName) · \(String(format: "%.1f", candidate.timestampSeconds))s")
                .font(.caption2)
                .foregroundStyle(Palette.textSecondary)
                .lineLimit(1)
        }
        .padding(8)
        .frame(width: 200)
        .background(Palette.bgSurface)
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .strokeBorder(isSelected ? Palette.accent : Color.clear, lineWidth: 2)
        )
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .contentShape(Rectangle())
        .gesture(
            TapGesture(count: 2).onEnded { onOpenDetail() }
                .exclusively(before: TapGesture(count: 1).onEnded { handleSingleClick() })
        )
        .focusable()
        .onKeyPress(.space) { handleSingleClick(); return .handled }
        .onKeyPress(.return) { onOpenDetail(); return .handled }
        .task(id: renderKey) { await render() }
        .task(id: logoRenderKey) { await renderLogo() }
        // The raw TapGesture combinator above isn't wired into VoiceOver's
        // activate gesture, so the card needs explicit accessibility: one
        // combined element, a default action matching single-click-to-select,
        // and custom actions for the mouse-only double-click/exclude affordances.
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibilityDescription)
        .accessibilityAddTraits(.isButton)
        .accessibilityAction(.default) { handleSingleClick() }
        .accessibilityAction(named: "Открыть кадр") { onOpenDetail() }
        .accessibilityAction(named: "Исключить из экспорта") { viewModel.toggleExclude(candidate.id) }
    }

    private var accessibilityDescription: String {
        let origin = candidate.origin == .photo ? "фотография" : candidate.origin == .auto ? "автоотбор" : "вручную"
        let timestamp = String(format: "%.1f", candidate.timestampSeconds)
        let selection = isSelected ? ", selected" : ""
        return "\(video.fileName), \(origin) capture at \(timestamp) seconds\(selection)"
    }

    private var thumbnail: some View {
        GeometryReader { proxy in
            ZStack {
                if let image {
                    Image(decorative: image, scale: 1)
                        .resizable()
                        .aspectRatio(contentMode: .fit)
                        .frame(width: proxy.size.width, height: proxy.size.height)

                    if appState.settingsStore.settings.exportIncludeLogo, let logoImage {
                        logoOverlay(logoImage: logoImage, containerSize: proxy.size)
                    }
                } else if loadFailed {
                    Text("Не удалось прочитать кадр")
                        .font(.caption2)
                        .foregroundStyle(Palette.danger)
                } else {
                    Text("Загрузка…")
                        .font(.caption2)
                        .foregroundStyle(Palette.textSecondary)
                }
            }
        }
        .frame(width: 184, height: 104)
        .background(Palette.bgSurfaceAlt)
        .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
    }

    /// Positions the (already-decoded, uncomposited) logo asset with the same
    /// arithmetic `LogoDetailDialog` uses, so the card preview stays a
    /// faithful — but cheap, no Core Image involved — match for what export
    /// will bake in. Uses the *video's* native width/height, not `image`'s
    /// (this thumbnail is decoded downscaled to 400px wide) — offsets are
    /// defined in native-resolution units, so using the downscaled image's
    /// own pixel size here would place the logo wrong for any non-zero
    /// offset (same fix as `FrameDetailDialog`'s preview).
    private func logoOverlay(logoImage: CGImage, containerSize: CGSize) -> some View {
        let imageSize = candidate.imageSize(for: video)
        let scale = LogoPreviewGeometry.fitScale(containerSize: containerSize, imageSize: imageSize)
        let rect = LogoPreviewGeometry.rect(
            placement: candidate.logoPlacement, containerSize: containerSize, imageSize: imageSize, fitScale: scale
        )
        return Image(decorative: logoImage, scale: 1)
            .resizable()
            .frame(width: rect.width, height: rect.height)
            .position(x: rect.midX, y: rect.midY)
    }

    private func handleSingleClick() {
        let flags = NSEvent.modifierFlags
        if flags.contains(.shift) {
            viewModel.select(candidate.id, extend: false, range: true)
        } else if flags.contains(.command) {
            viewModel.select(candidate.id, extend: true, range: false)
        } else {
            viewModel.select(candidate.id, extend: false, range: false)
        }
    }

    /// Only the video frame + HDR fix — never the placement, so an open
    /// Frame Detail dialog dragging this same candidate's logo doesn't
    /// re-trigger a decode here on every pixel of the drag.
    private var renderKey: String {
        "\(candidate.id)|\(candidate.hdrFix)|\(candidate.turns)"
    }

    /// Only the slot + export toggle — never the offset/scale, for the same
    /// reason.
    private var logoRenderKey: String {
        "\(candidate.logoPlacement.slotKey.stringValue)|\(appState.settingsStore.settings.exportIncludeLogo)|\(appState.settingsStore.settings.logoSlots)"
    }

    private func render() async {
        loadFailed = false
        image = nil

        var mutableVideo = video
        guard let url = try? mutableVideo.bookmark.resolve() else {
            loadFailed = true
            return
        }
        let granted = url.startAccessingSecurityScopedResource()
        defer { if granted { url.stopAccessingSecurityScopedResource() } }

        do {
            let rendered = try await MediaRenderer.shared.read(url: url,source: video,candidate: candidate,maxDimension: 640)
            guard !Task.isCancelled else { return }
            image = rendered
        } catch { if !Task.isCancelled { loadFailed = true } }
    }

    /// Decodes the raw logo asset only (no compositing) — `logoOverlay`
    /// positions it directly, so moving/scaling it in the open detail
    /// dialog never touches this decode again.
    private func renderLogo() async {
        guard appState.settingsStore.settings.exportIncludeLogo,
              var bookmark = appState.settingsStore.settings.logoSlots[candidate.logoPlacement.slotKey.stringValue]?.imageBookmark,
              let logoURL = try? bookmark.resolve()
        else {
            logoImage = nil
            return
        }
        let granted = logoURL.startAccessingSecurityScopedResource()
        defer { if granted { logoURL.stopAccessingSecurityScopedResource() } }
        // Off the main actor — see `ImagePostProcessor`.
        logoImage = await ImagePostProcessor.shared.decodeLogo(url: logoURL)
    }
}
