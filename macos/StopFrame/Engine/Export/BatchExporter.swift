import Foundation

enum ExportEvent: Sendable {
    case progress(done: Int,total: Int)
    case failure(String)
    case finished(destinationFolder: URL)
}
actor BatchExporter {
    func run(candidates: [(candidate: FrameCandidate,video: VideoItem)],settings: Settings,destinationFolder: URL) -> AsyncStream<ExportEvent> {
        AsyncStream { continuation in
            let task = Task {
                var done = 0
                for (candidate,video) in candidates {
                    if Task.isCancelled { break }
                    do {
                        _ = try await FrameExporter.export(candidate: candidate,video: video,settings: settings,destinationFolder: destinationFolder)
                    } catch is CancellationError { break }
                    catch { continuation.yield(.failure("\(video.fileName): \(error.localizedDescription)")) }
                    done += 1
                    continuation.yield(.progress(done: done,total: candidates.count))
                }
                if !Task.isCancelled { continuation.yield(.finished(destinationFolder: destinationFolder)) }
                continuation.finish()
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }
}
