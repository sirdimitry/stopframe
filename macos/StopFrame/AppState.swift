import Foundation
import Observation

@Observable @MainActor
final class AppState {
    let settingsStore = SettingsStore()
    var videos: [VideoItem] = []
    var frameCandidates: [FrameCandidate] = []
    var sessionID = UUID()
    var message = ""
    var isImporting = false
    var importTask: Task<Void, Never>?
    var autoPickTask: Task<Void, Never>?
    var isAnalyzing = false
    var analysisDone = 0
    var analysisTotal = 0
    var analysisStatus = ""

    init() {
        if let project = ProjectStore.load() {
            videos = project.videos
            frameCandidates = project.frameCandidates
        }
    }
    var videoSources: [VideoItem] { videos.filter { !$0.isPhoto } }
    func saveProject() { ProjectStore.save(ProjectDocument(videos: videos, frameCandidates: frameCandidates)) }
    func markers(for videoID: UUID) -> [FrameCandidate] { frameCandidates.filter { $0.videoID == videoID && $0.included } }

    func placement(for source: VideoItem, side: LogoSide = .left) -> LogoPlacement {
        let aspect = source.logoAspect
        let key = LogoSlotKey.resolve(aspect: aspect, orientation: source.orientation, side: side)
        let slot = settingsStore.settings.logoSlots[key.stringValue] ?? LogoSlot()
        return LogoPlacement(slotKey: key, offsetX: slot.offsetX, offsetY: slot.offsetY, scale: slot.scale)
    }
    func captureManualFrame(video: VideoItem, timestampSeconds: Double, frameIndex: Int) {
        guard !frameCandidates.contains(where: { $0.videoID == video.id && $0.frameIndex == frameIndex && $0.included }) else { return }
        frameCandidates.append(FrameCandidate(videoID: video.id, frameIndex: frameIndex,
            timestampSeconds: timestampSeconds, origin: .manual, logoPlacement: placement(for: video)))
    }
    func addVideoFile(url: URL) async { await importFiles([url]) }
    func addVideoFolder(url: URL) async {
        stopAnalysis()
        sessionID = UUID()
        videos.removeAll()
        frameCandidates.removeAll()
        settingsStore.settings.lastVideoFolder = try? SecureBookmark(url: url)
        let granted = url.startAccessingSecurityScopedResource()
        defer { if granted { url.stopAccessingSecurityScopedResource() } }
        let files = FileManager.default.enumerator(at: url, includingPropertiesForKeys: [.isRegularFileKey], options: [.skipsHiddenFiles, .skipsPackageDescendants])?
            .allObjects.compactMap { $0 as? URL }.filter { Self.supports($0) }.sorted { $0.path < $1.path } ?? []
        await importFiles(files)
    }
    static func supports(_ url: URL) -> Bool { VideoFileType.isVideoFile(url) || PhotoSource.extensions.contains(url.pathExtension.lowercased()) }
    func importFiles(_ urls: [URL]) async {
        let generation = sessionID
        isImporting = true
        defer { if sessionID == generation { isImporting = false } }
        for url in urls {
            guard !Task.isCancelled, generation == sessionID else { break }
            if (try? url.resourceValues(forKeys: [.isDirectoryKey]))?.isDirectory == true {
                let granted = url.startAccessingSecurityScopedResource()
                let found = FileManager.default.enumerator(at: url, includingPropertiesForKeys: nil, options: [.skipsHiddenFiles, .skipsPackageDescendants])?.allObjects.compactMap { $0 as? URL }.filter { Self.supports($0) }.sorted { $0.path < $1.path } ?? []
                await importFiles(found)
                if granted { url.stopAccessingSecurityScopedResource() }
                continue
            }
            guard Self.supports(url), !isAlreadyAdded(url) else { continue }
            let granted = url.startAccessingSecurityScopedResource()
            defer { if granted { url.stopAccessingSecurityScopedResource() } }
            do {
                let bookmark = try SecureBookmark(url: url)
                let item: VideoItem
                if PhotoSource.extensions.contains(url.pathExtension.lowercased()) {
                    let size = try await Task.detached { try PhotoSource.size(url: url) }.value
                    item = VideoItem(bookmark: bookmark, fileName: url.lastPathComponent, width: Int(size.width), height: Int(size.height), durationSeconds: 0, fps: 0, aspect: AspectClass.classify(width: Int(size.width), height: Int(size.height)))
                } else {
                    let p = try await VideoProbe.probe(url: url)
                    item = VideoItem(bookmark: bookmark, fileName: url.lastPathComponent, width: p.width, height: p.height, durationSeconds: p.durationSeconds, fps: p.fps, aspect: AspectClass.classify(width: p.width, height: p.height))
                }
                guard generation == sessionID, !Task.isCancelled else { break }
                videos.append(item)
                if item.isPhoto {
                    frameCandidates.append(FrameCandidate(videoID: item.id, frameIndex: 0, timestampSeconds: 0, origin: .photo, logoPlacement: placement(for: item)))
                }
            } catch {
                message = "Не удалось открыть «\(url.lastPathComponent)»: \(error.localizedDescription). Проверьте файл или выберите другой формат."
                await StopFrameLogger.shared.error("import", message)
            }
        }
    }
    func removeVideos(ids: Set<UUID>) {
        stopAnalysis()
        videos.removeAll { ids.contains($0.id) }
        frameCandidates.removeAll { ids.contains($0.videoID) }
    }
    func stopAnalysis() { autoPickTask?.cancel(); autoPickTask = nil; isAnalyzing = false }
    func startAnalysis(count: Int) {
        guard !isAnalyzing, !videoSources.isEmpty else { return }
        let sources = videoSources
        let generation = sessionID
        isAnalyzing = true
        analysisDone = 0; analysisTotal = sources.count
        analysisStatus = "Подготовка анализа…"
        let settings = settingsStore.settings
        autoPickTask = Task {
            let engine = AutoPickEngine()
            let stream = await engine.run(videos: sources, targetCount: count, settings: settings)
            for await event in stream {
                guard !Task.isCancelled, generation == sessionID else { break }
                switch event {
                case .progress(let done, let total): analysisDone = done; analysisTotal = total
                case .status(let text): analysisStatus = text
                case .warning(let text): message = text
                case .videoCompleted(let video, let candidates):
                    guard videos.contains(where: { $0.id == video.id }) else { continue }
                    frameCandidates.removeAll { $0.videoID == video.id && $0.origin == .auto }
                    frameCandidates.append(contentsOf: candidates)
                }
            }
            if generation == sessionID, !Task.isCancelled {
                isAnalyzing = false
                analysisStatus = "Готово: обработано \(analysisDone) из \(analysisTotal). Результат доступен в разделе «Кадры и экспорт»."
            }
        }
    }
    private func isAlreadyAdded(_ url: URL) -> Bool {
        videos.contains { video in
            var bookmark = video.bookmark
            return (try? bookmark.resolve().standardizedFileURL) == url.standardizedFileURL
        }
    }
}
