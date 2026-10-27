import Foundation
import CoreGraphics
import ImageIO

/// Used only when AVFoundation cannot decode an original container/codec.
/// Bundled tools have no Homebrew dependencies; no shell interpolation.
actor FFmpegBridge {
    static let shared = FFmpegBridge()
    private func executable(_ name: String) throws -> URL {
        if let root = ProcessInfo.processInfo.environment["STOPFRAME_TOOLS"] {
            return URL(fileURLWithPath: root).appendingPathComponent(name)
        }
        let choices = [Bundle.main.url(forResource: name,withExtension: nil,subdirectory: "Tools"),
                       Bundle.main.url(forResource: name,withExtension: nil)]
        guard let url = choices.compactMap({ $0 }).first else { throw VideoReaderError.noFrame }
        return url
    }
    private func execute(_ name: String,args: [String]) async throws -> Data {
        try Task.checkCancellation()
        let url = try executable(name)
        let process = Process()
        process.executableURL = url; process.arguments = args
        let output = Pipe()
        process.standardOutput = output; process.standardError = FileHandle.nullDevice
        return try await withTaskCancellationHandler {
            try process.run()
            let data = output.fileHandleForReading.readDataToEndOfFile()
            process.waitUntilExit()
            try Task.checkCancellation()
            guard process.terminationStatus == 0 else { throw VideoReaderError.noFrame }
            return data
        } onCancel: { if process.isRunning { process.terminate() } }
    }
    func probe(_ url: URL) async throws -> VideoProbeResult {
        let data = try await execute("ffprobe",args: ["-v","error","-select_streams","v:0","-show_entries","stream=width,height,avg_frame_rate:stream_side_data=rotation:format=duration","-of","json",url.path])
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let streams = json["streams"] as? [[String: Any]],let stream = streams.first,
              var width = stream["width"] as? Int,var height = stream["height"] as? Int else { throw VideoProbeError.noVideoTrack }
        let rate = (stream["avg_frame_rate"] as? String ?? "0/1").split(separator: "/").compactMap { Double($0) }
        let fps = rate.count == 2 && rate[1] > 0 ? rate[0]/rate[1] : 0
        let sideData = stream["side_data_list"] as? [[String: Any]] ?? []
        if let rotation = sideData.first?["rotation"] as? Int, abs(rotation)%180 == 90 { swap(&width,&height) }
        let format = json["format"] as? [String: Any]
        let duration = Double(format?["duration"] as? String ?? "0") ?? 0
        guard width > 0,height > 0,duration > 0 else { throw VideoProbeError.invalidDimensions }
        return VideoProbeResult(width: width,height: height,durationSeconds: duration,fps: fps)
    }
    func frame(_ url: URL,seconds: Double,maxDimension: Int? = nil) async throws -> CGImage {
        var args = ["-v","error","-threads","2","-ss",String(format: "%.6f",locale: Locale(identifier: "en_US_POSIX"),max(0,seconds)),"-i",url.path,"-frames:v","1"]
        if let maxDimension { args += ["-vf","scale=\(maxDimension):\(maxDimension):force_original_aspect_ratio=decrease"] }
        args += ["-f","image2pipe","-c:v","png","-threads","1","pipe:1"]
        let data = try await execute("ffmpeg",args: args)
        guard let source = CGImageSourceCreateWithData(data as CFData,nil),let image = CGImageSourceCreateImageAtIndex(source,0,nil) else { throw VideoReaderError.noFrame }
        return image
    }
}
