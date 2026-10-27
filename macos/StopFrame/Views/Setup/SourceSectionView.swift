import SwiftUI
import UniformTypeIdentifiers

struct SourceSectionView: View {
    @Environment(AppState.self) private var appState
    @State private var selection = Set<VideoItem.ID>()
    @State private var isPickingFolder = false
    @State private var isPickingFile = false
    @State private var isConfirmingClearAll = false

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Button("Открыть папку…") { isPickingFolder = true }
                    .buttonStyle(.secondary)
                Button("Добавить файлы…") { isPickingFile = true }
                    .buttonStyle(.secondary)
                Spacer()
                Button("Очистить список", role: .destructive) { isConfirmingClearAll = true }
                    .buttonStyle(.secondary)
                    .disabled(appState.videos.isEmpty)
            }

            if appState.isImporting { ProgressView("Чтение файлов…") }
            Table(appState.videos, selection: $selection) {
                TableColumn("Файл") { video in
                    Text(video.fileName)
                        .foregroundStyle(Palette.textPrimary)
                        .help(video.fileName)
                }
                TableColumn("Размер") { video in
                    Text("\(video.width)×\(video.height)")
                        .foregroundStyle(Palette.textSecondary)
                }
                TableColumn("Пропорции") { video in
                    Text(video.aspect.rawValue)
                        .foregroundStyle(Palette.textSecondary)
                }
                TableColumn("Длительность") { video in
                    Text(video.isPhoto ? "Фото" : Self.formatDuration(video.durationSeconds))
                        .foregroundStyle(Palette.textSecondary)
                }
            }
            .frame(minHeight: 180,maxHeight: .infinity)
            .overlay {
                if appState.videos.isEmpty {
                    ContentUnavailableView("Добавьте материалы",systemImage: "square.and.arrow.down",description: Text("Видео: MP4, MOV, M4V, AVI, MKV. Фото: JPEG, PNG, WebP, TIFF, BMP, HEIC."))
                        .allowsHitTesting(false)
                }
            }
            .onDeleteCommand { removeSelected() }

            Text("Перетащите сюда файлы из Finder. Новая папка заменяет список и кадры; «Добавить файлы» дополняет сессию.")
                .font(.caption)
                .foregroundStyle(Palette.textSecondary)
        }
        .disabled(appState.isImporting)
        .fileImporter(isPresented: $isPickingFolder, allowedContentTypes: [.folder]) { result in
            handleFolderPick(result)
        }
        .fileImporter(
            isPresented: $isPickingFile,
            allowedContentTypes: VideoFileType.allowedContentTypes + [.image],
            allowsMultipleSelection: true
        ) { result in
            handleFilePick(result)
        }
        .confirmationDialog(
            "Очистить список файлов и кадров?",
            isPresented: $isConfirmingClearAll,
            titleVisibility: .visible
        ) {
            Button("Очистить", role: .destructive) { clearAll() }
        } message: {
            Text("Исходники и экспортированные изображения останутся на диске. Настройки и логотипы сохранятся.")
        }
    }

    private func removeSelected() {
        appState.removeVideos(ids: selection)
        selection.removeAll()
    }

    private func clearAll() {
        appState.removeVideos(ids: Set(appState.videos.map(\.id)))
        selection.removeAll()
    }

    private func handleFolderPick(_ result: Result<URL, Error>) {
        guard case .success(let url) = result else { return }
        appState.importTask?.cancel()
        appState.importTask = Task { await appState.addVideoFolder(url: url) }
    }

    private func handleFilePick(_ result: Result<[URL], Error>) {
        guard case .success(let urls) = result else { return }
        appState.importTask = Task { await appState.importFiles(urls) }
    }

    private static func formatDuration(_ seconds: Double) -> String {
        guard seconds.isFinite, seconds >= 0 else { return "0:00" }
        let total = Int(seconds.rounded())
        return String(format: "%d:%02d", total / 60, total % 60)
    }
}

#Preview {
    SourceSectionView()
        .environment(AppState())
        .stopFrameTheme()
        .padding()
}
