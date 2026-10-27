import AVFoundation
import Vision

enum AutoPickEvent: Sendable {
    case progress(done: Int, total: Int)
    case status(String)
    case warning(String)
    case videoCompleted(video: VideoItem, candidates: [FrameCandidate])
}

actor AutoPickEngine {
    private let faceAnalyzer: @Sendable (CGImage) -> FaceQualityResult?
    init(faceAnalyzer: @escaping @Sendable (CGImage) -> FaceQualityResult? = { FaceQualityAnalyzer.analyze($0) }) {
        self.faceAnalyzer = faceAnalyzer
    }
    static let minPicks = 1
    static let maxPicks = Int(Int32.max)
    struct Sample {
        let timestamp: Double
        let sharpness: Double
        let fingerprint: FrameFingerprint
    }
    func run(videos: [VideoItem], targetCount: Int, settings: Settings = .empty) -> AsyncStream<AutoPickEvent> {
        AsyncStream { continuation in
            let task = Task {
                for (index, video) in videos.enumerated() {
                    if Task.isCancelled { break }
                    let candidates = await pickFrames(for: video, targetCount: max(1,targetCount), settings: settings, emit: { continuation.yield($0) })
                    if Task.isCancelled { break }
                    continuation.yield(.videoCompleted(video: video, candidates: candidates))
                    continuation.yield(.progress(done: index+1, total: videos.count))
                }
                continuation.finish()
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }
    private func pickFrames(for video: VideoItem, targetCount: Int, settings: Settings, emit: (AutoPickEvent) -> Void) async -> [FrameCandidate] {
        guard !video.isPhoto, video.durationSeconds > 0 else { return [] }
        var bookmark = video.bookmark
        guard let url = try? bookmark.resolve() else { emit(.status("Нет доступа к \(video.fileName). Добавьте файл заново.")); return [] }
        let granted = url.startAccessingSecurityScopedResource()
        defer { if granted { url.stopAccessingSecurityScopedResource() } }
        // A private exact generator avoids sharing mutable tolerances with timeline requests.
        let generator = AVAssetImageGenerator(asset: AVURLAsset(url: url))
        generator.appliesPreferredTrackTransform = true
        generator.maximumSize = CGSize(width: 960,height: 960)
        generator.requestedTimeToleranceBefore = .zero
        generator.requestedTimeToleranceAfter = .zero
        func read(_ t: Double) async -> CGImage? {
            guard !Task.isCancelled else { return nil }
            do { return try await generator.image(at: CMTime(seconds: t,preferredTimescale: 60000)).image }
            catch { return try? await FFmpegBridge.shared.frame(url,seconds: t,maxDimension: 960) }
        }
        var samples: [Sample] = []
        var timestamp = 0.0
        while timestamp < video.durationSeconds {
            guard !Task.isCancelled else { return [] }
            if let image = await read(timestamp) {
                samples.append(Sample(timestamp: timestamp,sharpness: SharpnessAnalyzer.score(of: image),fingerprint: FrameFingerprint(image)))
            }
            timestamp += 1
            emit(.status("\(video.fileName) · резкость \(Int(timestamp)) / \(Int(ceil(video.durationSeconds))) с"))
        }
        let floor = (samples.map(\.sharpness).max() ?? 0) * 0.35
        let ranked = samples.filter { $0.sharpness >= floor }.sorted {
            $0.sharpness == $1.sharpness ? $0.timestamp < $1.timestamp : $0.sharpness > $1.sharpness
        }
        guard !ranked.isEmpty else { return [] }
        var checked: [Double: Sample] = [:], rejected = Set<Double>()
        var faceUnavailable = false
        func validate(_ sample: Sample) async -> Sample? {
            if let cached = checked[sample.timestamp] { return cached }
            if rejected.contains(sample.timestamp) { return nil }
            rejected.insert(sample.timestamp)
            guard !Task.isCancelled, let image = await read(sample.timestamp) else { return nil }
            let quality = faceAnalyzer(image)
            if quality == nil { faceUnavailable = true }
            if quality == nil || quality!.eyesOpen && quality!.mouthClosed {
                checked[sample.timestamp] = sample
                return sample
            }
            var best: Sample?
            for offset in [-0.3,-0.15,0.15,0.3] {
                let t = sample.timestamp + offset
                guard t >= 0, t < video.durationSeconds, !Task.isCancelled else { continue }
                guard let neighbor = await read(t) else { continue }
                let score = SharpnessAnalyzer.score(of: neighbor)
                guard score >= floor, let face = faceAnalyzer(neighbor), face.faceFound, face.eyesOpen, face.mouthClosed else { continue }
                if best == nil || score > best!.sharpness { best = Sample(timestamp: t,sharpness: score,fingerprint: FrameFingerprint(neighbor)) }
            }
            if let best { checked[sample.timestamp] = best }
            return best
        }
        let count = min(targetCount,ranked.count)
        var buckets = [Sample?](repeating: nil,count: count)
        for sample in ranked {
            guard !Task.isCancelled else { return [] }
            let bucket = min(count-1,Int(sample.timestamp/video.durationSeconds*Double(count)))
            if buckets[bucket] == nil { buckets[bucket] = await validate(sample) }
            emit(.status("\(video.fileName) · проверка лиц и разнообразия"))
            if buckets.allSatisfy({ $0 != nil }) { break }
        }
        var selected: [Sample] = []
        for winner in buckets.compactMap({ $0 }).sorted(by: { $0.sharpness > $1.sharpness }) {
            if !selected.contains(where: { winner.fingerprint.isSimilar(to: $0.fingerprint) }) { selected.append(winner) }
        }
        for sample in ranked {
            guard selected.count < targetCount else { break }
            guard !Task.isCancelled else { return [] }
            if selected.contains(where: { sample.fingerprint.isSimilar(to: $0.fingerprint) }) { continue }
            if let valid = await validate(sample), !selected.contains(where: { valid.fingerprint.isSimilar(to: $0.fingerprint) }) { selected.append(valid) }
        }
        guard !Task.isCancelled else { return [] }
        if faceUnavailable { emit(.warning("Проверка лиц недоступна для части кадров: отбор по резкости и разнообразию.")) }
        let key = LogoSlotKey.resolve(aspect: video.aspect, orientation: video.orientation, side: .left)
        let slot = settings.logoSlots[key.stringValue] ?? LogoSlot()
        return selected.sorted { $0.timestamp < $1.timestamp }.map {
            FrameCandidate(videoID: video.id,frameIndex: Int(($0.timestamp*video.fps).rounded()),timestampSeconds: $0.timestamp,origin: .auto,
                logoPlacement: LogoPlacement(slotKey: key,offsetX: slot.offsetX,offsetY: slot.offsetY,scale: slot.scale),sharpnessScore: $0.sharpness)
        }
    }
}
