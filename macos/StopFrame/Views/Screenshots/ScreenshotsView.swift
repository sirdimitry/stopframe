import SwiftUI

struct ScreenshotsView: View {
    @Environment(AppState.self) private var appState
    @State private var viewModel: ScreenshotsViewModel?

    var body: some View {
        Group {
            if let viewModel {
                ScreenshotsContentView(viewModel: viewModel)
            } else {
                Color.clear
            }
        }
        .onAppear {
            if viewModel == nil {
                viewModel = ScreenshotsViewModel(appState: appState)
            }
        }
        .background(Palette.bgApp)
    }
}

private struct ScreenshotsContentView: View {
    @Environment(AppState.self) private var appState
    @Bindable var viewModel: ScreenshotsViewModel
    @State private var detailCandidateID: FrameCandidate.ID?

    var body: some View {
        VStack(spacing: 0) {
            ScreenshotsToolbarView(viewModel: viewModel)
            Divider()

            if viewModel.groupedCandidates.isEmpty {
                ContentUnavailableView("Пока нет кадров",systemImage: "photo.on.rectangle.angled",description: Text("Запустите автоматический отбор, захватите кадр на временной шкале или добавьте фотографии."))
            }
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    ForEach(viewModel.groupedCandidates, id: \.video.id) { group in
                        VStack(alignment: .leading, spacing: 8) {
                            Text(group.video.fileName)
                                .font(.headline)
                                .foregroundStyle(Palette.textPrimary)
                                .accessibilityAddTraits(.isHeader)

                            FlowLayout(spacing: 14) {
                                ForEach(group.candidates) { candidate in
                                    FrameCardView(
                                        candidate: candidate,
                                        video: group.video,
                                        isSelected: viewModel.isSelected(candidate.id),
                                        viewModel: viewModel,
                                        onOpenDetail: {
                                            detailCandidateID = candidate.id
                                            viewModel.selectOnly(candidate.id)
                                        }
                                    )
                                }
                            }
                        }
                    }
                }
                .padding()
            }
        }
        .onDeleteCommand { viewModel.deleteSelected() }
        .onChange(of: appState.sessionID) { _, _ in viewModel.selectedIDs.removeAll(); detailCandidateID = nil }
        .sheet(isPresented: Binding(
            get: { detailCandidateID != nil },
            set: { if !$0 { detailCandidateID = nil } }
        )) {
            if let id = detailCandidateID,
               let candidate = appState.frameCandidates.first(where: { $0.id == id }),
               let video = appState.videos.first(where: { $0.id == candidate.videoID }) {
                FrameDetailDialog(candidateID: id, video: video)
            }
        }
    }
}

#Preview {
    let state = AppState()
    let containerData = URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent("PreviewAssets")
    let videoURL = containerData.appendingPathComponent("sample.mp4")
    let logoFolder = containerData.appendingPathComponent("logos_16x9")

    let video = VideoItem(
        bookmark: try! SecureBookmark(url: videoURL),
        fileName: "sample.mp4", width: 1920, height: 1080, durationSeconds: 10.1, fps: 60, aspect: .sixteenNine
    )
    state.videos = [video]

    let matches = LogoMatcher.matchLogos(in: logoFolder)
    var settings = state.settingsStore.settings
    for key in LogoSlotKey.all {
        settings.logoSlots[key.stringValue]?.imageBookmark = matches[key].flatMap { try? SecureBookmark(url: $0) }
    }
    state.settingsStore.settings = settings

    let leftKey = LogoSlotKey.resolve(aspect: .sixteenNine, orientation: .landscape, side: .left)
    let rightKey = LogoSlotKey.resolve(aspect: .sixteenNine, orientation: .landscape, side: .right)
    state.frameCandidates = [
        FrameCandidate(videoID: video.id, frameIndex: 60, timestampSeconds: 1, origin: .manual, logoPlacement: LogoPlacement(slotKey: leftKey)),
        FrameCandidate(videoID: video.id, frameIndex: 180, timestampSeconds: 3, origin: .auto, logoPlacement: LogoPlacement(slotKey: rightKey), sharpnessScore: 42),
        FrameCandidate(videoID: video.id, frameIndex: 300, timestampSeconds: 5, origin: .auto, logoPlacement: LogoPlacement(slotKey: leftKey), sharpnessScore: 38),
    ]

    return ScreenshotsView()
        .environment(state)
        .stopFrameTheme()
}
