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
    @State private var imageRevision = UUID()
    @State private var compositedImage: CGImage?
    @State private var completedPreview: CardPreviewIdentity?
    @State private var loadFailed = false
    @State private var logoFailed = false

    var body: some View {
        VStack(spacing: 6) {
            ZStack(alignment: .bottomLeading) {
                thumbnail
                Text(candidate.origin == .photo ? "ФОТО" : candidate.origin == .auto ? "АВТО" : "ВРУЧНУЮ")
                    .font(.caption2.bold()).padding(.horizontal,6).padding(.vertical,2)
                    .background(candidate.origin == .auto ? Palette.autoMarker : Palette.bgElevated)
                    .foregroundStyle(candidate.origin == .auto ? Palette.bgApp : .white)
                    .clipShape(Capsule()).padding(badgeInsets).allowsHitTesting(false)
                if logoFailed, appState.settingsStore.settings.exportIncludeLogo {
                    Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(Palette.danger).padding(5)
                        .frame(maxWidth: .infinity,maxHeight: .infinity,alignment: .topLeading)
                        .help("Не удалось прочитать логотип. Проверьте библиотеку логотипов.").allowsHitTesting(false)
                }
            }
            // The selection gesture belongs only to the preview. The close
            // button is a sibling overlay, so this gesture cannot swallow it.
            .contentShape(Rectangle())
            .gesture(TapGesture(count: 2).onEnded { onOpenDetail() }
                .exclusively(before: TapGesture(count: 1).onEnded { handleSingleClick() }))
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(accessibilityDescription)
            .accessibilityAddTraits(.isButton)
            .accessibilityAction(.default) { handleSingleClick() }
            .accessibilityAction(named: "Открыть кадр") { onOpenDetail() }

            Text(video.isPhoto ? video.fileName : "\(video.fileName) · \(String(format: "%.1f",candidate.timestampSeconds))s")
                .font(.caption2).foregroundStyle(Palette.textSecondary).lineLimit(1)
                .onTapGesture { handleSingleClick() }.accessibilityHidden(true)
        }
        .padding(8).frame(width: 200).background(Palette.bgSurface)
        .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(isSelected ? Palette.accent : .clear,lineWidth: 2))
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay(alignment: .topTrailing) {
            Button { viewModel.toggleExclude(candidate.id) } label: {
                Image(systemName: "xmark").font(.system(size: 11,weight: .bold))
                    .foregroundStyle(.white).shadow(color: .black.opacity(0.8),radius: 1)
                    .frame(width: 24,height: 24)
                    .contentShape(Rectangle())
            }.buttonStyle(.plain).padding(2)
                .help("Убрать кадр из списка и экспорта")
                .accessibilityLabel("Убрать кадр")
                .accessibilityIdentifier("exclude-\(candidate.id)")
        }
        .focusable()
        .onKeyPress(.space) { handleSingleClick(); return .handled }
        .onKeyPress(.return) { onOpenDetail(); return .handled }
        .task(id: renderKey) { await render() }
        .task(id: previewIdentity) { await composePreview() }
        .accessibilityElement(children: .contain)
    }
    private var badgeInsets: EdgeInsets {
        let size = candidate.imageSize(for: video)
        let fit = LogoPreviewGeometry.fitScale(containerSize: CGSize(width: 184,height: 104),imageSize: size)
        return EdgeInsets(top: 0,leading: max(4,(184-size.width*fit)/2+4),bottom: max(4,(104-size.height*fit)/2+4),trailing: 0)
    }
    private var previewIdentity: CardPreviewIdentity {
        CardPreviewIdentity(baseRevision: imageRevision,
            logo: LogoLoadIdentity(slotKey: candidate.logoPlacement.slotKey,settings: appState.settingsStore.settings),
            placement: candidate.logoPlacement)
    }
    private var displayImage: CGImage? {
        // Hide on every card immediately, without waiting for queued decoding.
        guard appState.settingsStore.settings.exportIncludeLogo else { return image }
        return completedPreview == previewIdentity ? (compositedImage ?? image) : image
    }
    private var thumbnail: some View {
        ZStack {
            Palette.bgSurfaceAlt
            if let displayImage {
                Image(decorative: displayImage,scale: 1).resizable().aspectRatio(contentMode: .fit)
                    .frame(width: 184,height: 104)
            } else if loadFailed {
                Text("Не удалось прочитать кадр").font(.caption2).foregroundStyle(Palette.danger)
            } else {
                ProgressView().controlSize(.small).accessibilityLabel("Загрузка кадра")
            }
        }.frame(width: 184,height: 104).clipShape(RoundedRectangle(cornerRadius: 6))
    }
    private var accessibilityDescription: String {
        let origin = candidate.origin == .photo ? "фотография" : candidate.origin == .auto ? "автоотбор" : "вручную"
        return "\(video.fileName), \(origin)\(isSelected ? ", выбран" : "")"
    }
    private func handleSingleClick() {
        let flags = NSEvent.modifierFlags
        viewModel.select(candidate.id,extend: flags.contains(.command),range: flags.contains(.shift))
    }
    private var renderKey: String { "\(candidate.id)|\(candidate.hdrFix)|\(candidate.turns)" }
    private func render() async {
        loadFailed = false; image = nil; imageRevision = UUID()
        var bookmark = video.bookmark
        do {
            let url = try bookmark.resolve()
            let granted = url.startAccessingSecurityScopedResource()
            defer { if granted { url.stopAccessingSecurityScopedResource() } }
            let result = try await MediaRenderer.shared.read(url: url,source: video,candidate: candidate,maxDimension: 640)
            guard !Task.isCancelled else { return }
            image = result; imageRevision = UUID()
        } catch { if !Task.isCancelled { loadFailed = true } }
    }
    private func composePreview() async {
        guard let image else { return }
        let identity = previewIdentity
        let settings = appState.settingsStore.settings
        do {
            let result = try await ImagePostProcessor.shared.preview(base: image,imageSize: candidate.imageSize(for: video),placement: candidate.logoPlacement,settings: settings)
            guard !Task.isCancelled,identity == previewIdentity else { return }
            compositedImage = result; completedPreview = identity; logoFailed = false
        } catch {
            if !Task.isCancelled,identity == previewIdentity { completedPreview = nil; compositedImage = nil; logoFailed = true }
        }
    }
}
