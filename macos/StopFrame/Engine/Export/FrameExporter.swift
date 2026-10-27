import AVFoundation
import CoreImage
import UniformTypeIdentifiers
import Darwin

enum FrameExportError: LocalizedError {
    case couldNotReadFrame, encodingFailed, writeFailed, missingLogo
    var errorDescription: String? {
        switch self {
        case .couldNotReadFrame: "Не удалось прочитать исходный кадр."
        case .encodingFailed: "Не удалось создать изображение."
        case .writeFailed: "Не удалось записать изображение в выбранную папку."
        case .missingLogo: "Файл логотипа недоступен. Проверьте библиотеку или отключите логотип."
        }
    }
}

enum FrameExporter {
    static func export(candidate: FrameCandidate, video: VideoItem, settings: Settings, destinationFolder: URL) async throws -> URL {
        var bookmark = video.bookmark
        let sourceURL = try bookmark.resolve()
        let granted = sourceURL.startAccessingSecurityScopedResource()
        defer { if granted { sourceURL.stopAccessingSecurityScopedResource() } }
        let image = try await MediaRenderer.shared.read(url: sourceURL, source: video, candidate: candidate)
        var logo: CIImage?
        var logoAccess: URL?
        defer { logoAccess?.stopAccessingSecurityScopedResource() }
        if settings.exportIncludeLogo, var logoBookmark = settings.logoSlots[candidate.logoPlacement.slotKey.stringValue]?.imageBookmark {
            let url = try logoBookmark.resolve()
            if url.startAccessingSecurityScopedResource() { logoAccess = url }
            guard let decoded = CIImage(contentsOf: url) else { throw FrameExportError.missingLogo }
            logo = decoded
        }
        let composed = LogoCompositor.compose(frame: CIImage(cgImage: image),logo: logo,placement: candidate.logoPlacement)
        guard let output = LogoCompositor.sharedContext.createCGImage(composed,from: composed.extent) else { throw FrameExportError.encodingFailed }
        let ext = settings.exportFormat == .png ? "png" : "jpg"
        let prefix = settings.exportPrefix.trimmingCharacters(in: .whitespacesAndNewlines).replacingOccurrences(of: "/",with: "_").replacingOccurrences(of: "\\",with: "_")
        let fileName: String
        let folder: URL
        if video.isPhoto {
            let p = prefix.isEmpty ? "logo" : prefix
            let stem = sourceURL.deletingPathExtension().lastPathComponent
            fileName = (settings.prefixBeforeName ? "\(p)-\(stem)" : "\(stem)-\(p)") + ".\(ext)"
            folder = sourceURL.deletingLastPathComponent()
        } else {
            fileName = ExportNaming.fileName(frameIndex: candidate.frameIndex,prefix: prefix,prefixBeforeName: settings.prefixBeforeName,extension: ext)
            folder = destinationFolder.appendingPathComponent("logo",isDirectory: true)
        }
        try FileManager.default.createDirectory(at: folder,withIntermediateDirectories: true)
        let encoded = NSMutableData()
        let type: UTType = settings.exportFormat == .png ? .png : .jpeg
        guard let destination = CGImageDestinationCreateWithData(encoded,type.identifier as CFString,1,nil) else { throw FrameExportError.encodingFailed }
        let options: [CFString: Any] = settings.exportFormat == .jpeg ? [kCGImageDestinationLossyCompressionQuality: Double(min(100,max(1,settings.jpegQuality)))/100] : [:]
        CGImageDestinationAddImage(destination,output,options as CFDictionary)
        guard CGImageDestinationFinalize(destination) else { throw FrameExportError.encodingFailed }
        // O_EXCL reserves names atomically. Existing exports and originals are never replaced.
        while true {
            try Task.checkCancellation()
            let target = ExportNaming.uniqueURL(for: folder.appendingPathComponent(fileName))
            let fd = open(target.path,O_WRONLY | O_CREAT | O_EXCL,0o644)
            if fd < 0 { if errno == EEXIST { continue }; throw FrameExportError.writeFailed }
            do {
                let handle = FileHandle(fileDescriptor: fd,closeOnDealloc: true)
                try handle.write(contentsOf: encoded as Data)
                try handle.close()
                return target
            } catch {
                try? FileManager.default.removeItem(at: target)
                throw error
            }
        }
    }
}
