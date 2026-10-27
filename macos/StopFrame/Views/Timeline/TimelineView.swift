import SwiftUI

struct TimelineView: View {
    let isActive: Bool

    @Environment(AppState.self) private var appState
    @State private var viewModel: TimelineViewModel?

    var body: some View {
        Group {
            if let viewModel {
                TimelineContentView(viewModel: viewModel, isActive: isActive)
            } else {
                Color.clear
            }
        }
        .onAppear {
            if viewModel == nil {
                viewModel = TimelineViewModel(appState: appState)
            }
        }
        .background(Palette.bgApp)
    }
}

private struct TimelineContentView: View {
    @Environment(AppState.self) private var appState
    @Bindable var viewModel: TimelineViewModel
    let isActive: Bool

    @FocusState private var isFocused: Bool

    var body: some View {
        HStack(spacing: 0) {
            PreviewPanelView(viewModel: viewModel)
                .frame(width: 420)
                .background(Palette.bgSurface)

            Divider()

            ScrollView {
                LazyVStack(alignment: .leading, spacing: 8) {
                    if appState.videoSources.isEmpty {
                        ContentUnavailableView("Нет видео",systemImage: "film",description: Text("Добавьте видео в разделе «Файлы и отбор». Фотографии доступны сразу в разделе «Кадры и экспорт»."))
                    }
                    ForEach(appState.videoSources) { video in
                        VideoRowView(video: video, viewModel: viewModel)
                    }
                }
                .padding(8)
            }
            .background(Palette.bgApp)
        }
        .onChange(of: appState.sessionID) { _, _ in viewModel.reset() }
        .focusable()
        .focused($isFocused)
        .onKeyPress(.space) {
            guard viewModel.shortcutsEnabled else { return .ignored }
            viewModel.captureFrame()
            return .handled
        }
        .onKeyPress(.leftArrow) {
            guard viewModel.shortcutsEnabled else { return .ignored }
            viewModel.step(by: -1)
            return .handled
        }
        .onKeyPress(.rightArrow) {
            guard viewModel.shortcutsEnabled else { return .ignored }
            viewModel.step(by: 1)
            return .handled
        }
        .onChange(of: isActive, initial: true) { _, newValue in
            viewModel.shortcutsEnabled = newValue
            if newValue { isFocused = true }
        }
    }
}

#Preview {
    let state = AppState()
    let videoURL = URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent("PreviewAssets/sample.mp4")
    let video = VideoItem(
        bookmark: try! SecureBookmark(url: videoURL),
        fileName: "sample.mp4", width: 1920, height: 1080, durationSeconds: 10.1, fps: 60, aspect: .sixteenNine
    )
    state.videos = [video]

    return TimelineView(isActive: true)
        .environment(state)
        .stopFrameTheme()
        .frame(width: 950, height: 500)
}
