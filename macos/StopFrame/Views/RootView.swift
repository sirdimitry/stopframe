import AppKit
import SwiftUI
import UniformTypeIdentifiers

enum AppTab: Hashable { case setup,timeline,screenshots }

struct RootView: View {
    @Environment(AppState.self) private var appState
    @State private var selectedTab: AppTab = .setup
    @State private var isExporting = false
    @State private var exportDone = 0
    @State private var exportTotal = 0
    @State private var exportTask: Task<Void,Never>?
    @State private var dropTarget = false
    @State private var exportErrors: [String] = []
    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 14) {
                Image(systemName: "viewfinder").font(.title2).foregroundStyle(Palette.accent)
                Text("StopFrame").font(.title3.bold())
                Text("\(Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "0.1.0") · Native").font(.caption).foregroundStyle(Palette.textSecondary)
                Spacer()
                Text("\(appState.videos.count) файлов · \(appState.frameCandidates.filter(\.included).count) кадров")
                    .font(.caption).foregroundStyle(Palette.textSecondary)
            }.padding(.horizontal,24).padding(.vertical,14).background(Palette.bgSurface)
            TabView(selection: $selectedTab) {
                SetupView().tabItem { Label("1. Файлы и отбор",systemImage: "folder") }.tag(AppTab.setup)
                TimelineView(isActive: selectedTab == .timeline).tabItem { Label("2. Временная шкала",systemImage: "film") }.tag(AppTab.timeline)
                ScreenshotsView().tabItem { Label("3. Кадры и экспорт",systemImage: "photo.on.rectangle") }.tag(AppTab.screenshots)
            }
            if !appState.message.isEmpty {
                HStack(alignment: .top) {
                    Image(systemName: "info.circle")
                    Text(appState.message).font(.callout).textSelection(.enabled)
                    Spacer()
                    Button { appState.message = "" } label: { Image(systemName: "xmark") }.accessibilityLabel("Скрыть сообщение")
                }.padding(12).background(Palette.bgElevated)
            }
            if selectedTab == .screenshots {
                Divider()
                HStack {
                    Text("PNG / JPEG · исходное разрешение · оригиналы сохраняются").font(.caption).foregroundStyle(Palette.textSecondary)
                    Spacer()
                    Button("Экспортировать \(appState.frameCandidates.filter(\.included).count) кадров…") { startExport() }
                        .buttonStyle(.primary).disabled(isExporting || appState.frameCandidates.filter(\.included).isEmpty)
                }.padding(16).background(Palette.bgSurface)
            }
        }
        .frame(minWidth: 1100,minHeight: 720).background(Palette.bgApp).stopFrameTheme()
        .overlay { if dropTarget { RoundedRectangle(cornerRadius: 10).strokeBorder(Palette.accent,lineWidth: 3).allowsHitTesting(false) } }
        .onDrop(of: [UTType.fileURL.identifier],isTargeted: $dropTarget) { providers in
            guard !isExporting, !appState.isImporting else { return false }
            appState.importTask = Task {
                var urls: [URL] = []
                for provider in providers {
                    let url: URL? = await withCheckedContinuation { continuation in
                        _ = provider.loadDataRepresentation(forTypeIdentifier: UTType.fileURL.identifier) { data,_ in
                            continuation.resume(returning: data.flatMap { URL(dataRepresentation: $0,relativeTo: nil) })
                        }
                    }
                    if let url { urls.append(url) }
                }
                await appState.importFiles(urls)
            }
            return true
        }
        .sheet(isPresented: $isExporting) { ExportProgressView(done: exportDone,total: exportTotal,onCancel: { exportTask?.cancel() }) }
        .onChange(of: appState.isImporting) { _, importing in
            if !importing, !appState.videos.isEmpty, appState.videoSources.isEmpty { selectedTab = .screenshots }
        }
    }
    private func chooseFolder(title: String,at url: URL?) -> URL? {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false; panel.canChooseDirectories = true; panel.canCreateDirectories = true
        panel.prompt = "Выбрать"; panel.message = title; panel.directoryURL = url
        return panel.runModal() == .OK ? panel.url : nil
    }
    private func startExport() {
        guard !isExporting else { return }
        let pairs = appState.frameCandidates.filter(\.included).compactMap { c in appState.videos.first { $0.id == c.videoID }.map { (candidate: c,video: $0) } }
        guard !pairs.isEmpty else { return }
        var folder = URL(fileURLWithPath: NSTemporaryDirectory())
        if pairs.contains(where: { !$0.video.isPhoto }) {
            var bookmark = appState.settingsStore.settings.lastVideoFolder
            guard let chosen = chooseFolder(title: "Кадры из видео будут сохранены в подпапку logo.",at: try? bookmark?.resolve()) else { return }
            folder = chosen
        }
        // The sandbox requires folder grants to create siblings of photo originals.
        var photoFolders: [URL] = []
        for pair in pairs where pair.video.isPhoto {
            var bookmark = pair.video.bookmark
            guard let url = try? bookmark.resolve() else { continue }
            let parent = url.deletingLastPathComponent()
            if !photoFolders.contains(parent) { photoFolders.append(parent) }
        }
        var grants = [folder]
        for parent in photoFolders {
            guard let chosen = chooseFolder(title: "Разрешите сохранение фотографий рядом с оригиналами: выберите папку «\(parent.lastPathComponent)».",at: parent) else { return }
            guard chosen.standardizedFileURL == parent.standardizedFileURL else {
                appState.message = "Для сохранения рядом с фотографиями выберите их исходную папку. Экспорт не начат."; return
            }
            grants.append(chosen)
        }
        isExporting = true; exportDone = 0; exportTotal = pairs.count; exportErrors = []
        let settings = appState.settingsStore.settings
        exportTask = Task {
            let active = grants.filter { $0.startAccessingSecurityScopedResource() }
            defer { for url in active { url.stopAccessingSecurityScopedResource() } }
            let exporter = BatchExporter()
            let stream = await exporter.run(candidates: pairs,settings: settings,destinationFolder: folder)
            for await event in stream {
                if Task.isCancelled { break }
                switch event {
                case .progress(let done,let total): exportDone = done; exportTotal = total
                case .failure(let error): exportErrors.append(error)
                case .finished: break
                }
            }
            isExporting = false
            appState.message = Task.isCancelled ? "Экспорт остановлен. Уже сохранённые файлы остались на диске." : "Экспорт завершён: \(exportDone-exportErrors.count) из \(exportTotal)." + (exportErrors.isEmpty ? "" : " Ошибки: " + exportErrors.joined(separator: "; "))
            if !Task.isCancelled, exportErrors.isEmpty {
                NSWorkspace.shared.open(photoFolders.first ?? folder.appendingPathComponent("logo"))
            }
        }
    }
}
