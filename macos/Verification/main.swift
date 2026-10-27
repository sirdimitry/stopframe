import Foundation
import AVFoundation
import CoreImage
import ImageIO
import UniformTypeIdentifiers

struct CheckFailed: Error { let message: String }
@main struct Verification {
    @MainActor static func main() async throws {
        setbuf(stdout,nil)
        let root = URL(fileURLWithPath: ProcessInfo.processInfo.environment["STOPFRAME_TEST_ROOT"]!)
        try FileManager.default.createDirectory(at: root,withIntermediateDirectories: true)
        let media = root.appendingPathComponent("media")
        try FileManager.default.createDirectory(at: media,withIntermediateDirectories: true)
        var checks = 0
        func check(_ value: Bool,_ message: String) throws {
            guard value else { throw CheckFailed(message: message) }; checks += 1; print("PASS \(message)")
        }
        func scene(_ seed: UInt64) -> CGImage {
            let ctx = CGContext(data: nil,width: 160,height: 96,bitsPerComponent: 8,bytesPerRow: 640,space: CGColorSpaceCreateDeviceRGB(),bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
            var state = seed+1
            for y in 0..<8 { for x in 0..<8 {
                func next() -> CGFloat { state = state &* 6364136223846793005 &+ 1; return CGFloat((state>>32)%256)/255 }
                ctx.setFillColor(CGColor(red: next(),green: next(),blue: next(),alpha: 1))
                ctx.fill(CGRect(x: x*20,y: y*12,width: 20,height: 12))
            } }
            return ctx.makeImage()!
        }
        func write(_ image: CGImage,_ url: URL,orientation: Int = 1) throws {
            let d = CGImageDestinationCreateWithURL(url as CFURL,UTType.png.identifier as CFString,1,nil)!
            CGImageDestinationAddImage(d,image,[kCGImagePropertyOrientation: orientation] as CFDictionary)
            guard CGImageDestinationFinalize(d) else { throw CheckFailed(message: "write fixture") }
        }
        let photo = media.appendingPathComponent("original.png")
        try write(scene(1),photo)
        let oriented = media.appendingPathComponent("oriented.png")
        try write(scene(2),oriented,orientation: 6)
        let image = try PhotoSource.read(url: oriented)
        try check(image.width == 96 && image.height == 160,"EXIF 90° photo orientation")
        let size = try PhotoSource.size(url: oriented)
        try check(size.width == 96 && size.height == 160,"EXIF metadata dimensions")
        let fp = FrameFingerprint(scene(1))
        try check(fp.isSimilar(to: FrameFingerprint(scene(1))),"static scene duplicate suppression")
        try check(!fp.isSimilar(to: FrameFingerprint(scene(2))),"different spatial scenes retained")
        let settings = Settings.empty
        var json = try JSONSerialization.jsonObject(with: JSONEncoder().encode(settings)) as! [String: Any]
        json.removeValue(forKey: "framesPerVideo")
        let legacy = try JSONDecoder().decode(Settings.self,from: JSONSerialization.data(withJSONObject: json))
        try check(legacy.exportFormat == settings.exportFormat,"legacy settings decode")
        let state = AppState()
        state.videos = []; state.frameCandidates = []
        await state.importFiles([photo,oriented,photo])
        try check(state.videos.count == 2 && state.frameCandidates.count == 2,"batch photo import, immediate frames, no duplicate source")
        try check(state.frameCandidates[0].logoPlacement.slotKey.aspect == .sixteenNine,"wide cropped photos use nearest 16:9 logo family")
        let model = ScreenshotsViewModel(appState: state)
        model.selectAll(); model.rotateSelected()
        try check(state.frameCandidates.allSatisfy { $0.turns == 1 },"rotation increments")
        // Verify actual export dimensions and atomic no-overwrite, not just model state.
        var exportSettings = settings
        exportSettings.exportIncludeLogo = false
        let candidate = state.frameCandidates[0], source = state.videos[0]
        let originalData = try Data(contentsOf: photo)
        let output1 = try await FrameExporter.export(candidate: candidate,video: source,settings: exportSettings,destinationFolder: root)
        let output2 = try await FrameExporter.export(candidate: candidate,video: source,settings: exportSettings,destinationFolder: root)
        let exported = try PhotoSource.read(url: output1)
        try check(exported.width == 96 && exported.height == 160,"export rotates source at full resolution")
        try check(output1 != output2 && output1.lastPathComponent == "logo-original.png","photo names and collision suffix")
        try check(try Data(contentsOf: photo) == originalData,"original never overwritten")
        for _ in 0..<3 { model.rotateSelected() }
        try check(state.frameCandidates.allSatisfy { $0.turns == 0 },"four rotations restore orientation")
        var legacyCandidate = try JSONSerialization.jsonObject(with: JSONEncoder().encode(state.frameCandidates[0])) as! [String: Any]
        legacyCandidate.removeValue(forKey: "rotationQuarterTurns")
        let decoded = try JSONDecoder().decode(FrameCandidate.self,from: JSONSerialization.data(withJSONObject: legacyCandidate))
        try check(decoded.turns == 0,"legacy frame projects decode")
        model.select(state.frameCandidates[0].id,extend: false,range: false)
        model.select(state.frameCandidates[1].id,extend: false,range: true)
        try check(model.selectedIDs.count == 2,"shift range selection")
        model.deleteSelected()
        try check(state.frameCandidates.allSatisfy { !$0.included },"batch exclusion")
        state.settingsStore.settings.exportPrefix = "preserve"
        let emptyFolder = root.appendingPathComponent("empty")
        try FileManager.default.createDirectory(at: emptyFolder,withIntermediateDirectories: true)
        await state.addVideoFolder(url: emptyFolder)
        try check(state.videos.isEmpty && state.frameCandidates.isEmpty && state.settingsStore.settings.exportPrefix == "preserve","opening folder resets session but preserves settings")
        for i in 0..<6 { try write(scene(UInt64(i+10)),media.appendingPathComponent(String(format: "scene-%02d.png",i))) }
        let tools = URL(fileURLWithPath: ProcessInfo.processInfo.environment["STOPFRAME_TOOLS"]!)
        func video(_ name: String,_ input: String,_ extra: [String] = []) async throws -> URL {
            let output = root.appendingPathComponent(name)
            let mp4Output = name.hasSuffix(".mkv") ? root.appendingPathComponent("mkv-fixture.mp4") : output
            let writer = try AVAssetWriter(outputURL: mp4Output,fileType: .mp4)
            let writerInput = AVAssetWriterInput(mediaType: .video,outputSettings: [AVVideoCodecKey: AVVideoCodecType.h264,AVVideoWidthKey: 160,AVVideoHeightKey: 96])
            let adaptor = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: writerInput,sourcePixelBufferAttributes: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32ARGB,kCVPixelBufferWidthKey as String: 160,kCVPixelBufferHeightKey as String: 96])
            writer.add(writerInput)
            guard writer.startWriting() else { throw writer.error ?? CheckFailed(message: "writer start") }
            writer.startSession(atSourceTime: .zero)
            for frame in 0..<60 {
                while !writerInput.isReadyForMoreMediaData {
                    if writer.status == .failed { throw writer.error ?? CheckFailed(message: "writer failed") }
                    try await Task.sleep(for: .milliseconds(1))
                }
                let file = extra.isEmpty ? input.replacingOccurrences(of: "%02d",with: String(format: "%02d",frame/10)) : input
                let image = try PhotoSource.read(url: URL(fileURLWithPath: file))
                var buffer: CVPixelBuffer?
                CVPixelBufferCreate(kCFAllocatorDefault,160,96,kCVPixelFormatType_32ARGB,[kCVPixelBufferCGImageCompatibilityKey: true,kCVPixelBufferCGBitmapContextCompatibilityKey: true] as CFDictionary,&buffer)
                guard let buffer else { throw CheckFailed(message: "pixel buffer") }
                CVPixelBufferLockBaseAddress(buffer,[])
                let ctx = CGContext(data: CVPixelBufferGetBaseAddress(buffer),width: 160,height: 96,bitsPerComponent: 8,bytesPerRow: CVPixelBufferGetBytesPerRow(buffer),space: CGColorSpaceCreateDeviceRGB(),bitmapInfo: CGImageAlphaInfo.noneSkipFirst.rawValue)!
                ctx.draw(image,in: CGRect(x: 0,y: 0,width: 160,height: 96))
                CVPixelBufferUnlockBaseAddress(buffer,[])
                guard adaptor.append(buffer,withPresentationTime: CMTime(value: Int64(frame),timescale: 10)) else { throw writer.error ?? CheckFailed(message: "append frame") }
            }
            writerInput.markAsFinished(); await writer.finishWriting()
            guard writer.status == .completed else { throw writer.error ?? CheckFailed(message: "writer finish") }
            if name.hasSuffix(".mkv") {
                let p = Process(); p.executableURL = tools.appendingPathComponent("ffmpeg")
                p.arguments = ["-v","error","-y","-i",mp4Output.path,"-map","0:v:0","-c","copy","-f","matroska",output.path]
                try p.run(); p.waitUntilExit()
                guard p.terminationStatus == 0 else { throw CheckFailed(message: "MKV remux") }
            }
            return output
        }
        let mp4 = try await video("scenes.mp4",media.appendingPathComponent("scene-%02d.png").path)
        let mkv = try await video("scenes.mkv",media.appendingPathComponent("scene-%02d.png").path)
        let still = try await video("static.mp4",photo.path,["static"])
        await state.importFiles([mp4,mkv,still])
        try check(state.videoSources.count == 3,"MP4 and MKV native/fallback import")
        let mkvSource = state.videos.first { $0.fileName == "scenes.mkv" }!
        let fallback = try await VideoReader.readFrame(url: mkv,at: CMTime(seconds: 2,preferredTimescale: 600))
        try check(fallback.width == 160 && fallback.height == 96,"MKV full-resolution fallback decoding")
        let key = LogoSlotKey.resolve(aspect: .other,orientation: .landscape,side: .left)
        let videoCandidate = FrameCandidate(videoID: mkvSource.id,frameIndex: 20,timestampSeconds: 2,origin: .manual,logoPlacement: LogoPlacement(slotKey: key))
        let videoOutput = try await FrameExporter.export(candidate: videoCandidate,video: mkvSource,settings: exportSettings,destinationFolder: root)
        try check(videoOutput.deletingLastPathComponent().lastPathComponent == "logo","video export into logo subfolder")
        func picks(_ source: VideoItem,_ count: Int) async -> [FrameCandidate] {
            var result: [FrameCandidate] = []
            let stream = await AutoPickEngine().run(videos: [source],targetCount: count)
            for await event in stream { if case .videoCompleted(_,let candidates) = event { result = candidates } }
            return result
        }
        let dynamicSource = state.videos.first { $0.fileName == "scenes.mp4" }!
        let staticSource = state.videos.first { $0.fileName == "static.mp4" }!
        let one = await picks(dynamicSource,1)
        try check(one.count == 1,"automatic count 1")
        let six = await picks(dynamicSource,6)
        try check(six.count == 6,"automatic count above five")
        let hundred = await picks(staticSource,100)
        try check(hundred.count == 1,"100 requested frames do not duplicate static scene")
        let huge = await picks(dynamicSource,Int(Int32.max))
        try check(huge.count == 6,"huge count bounded by actual samples")
        let badEyes = AutoPickEngine(faceAnalyzer: { _ in FaceQualityResult(faceFound: true,eyesOpen: false,mouthClosed: true) })
        var badEyesPicks: [FrameCandidate] = []
        for await event in await badEyes.run(videos: [staticSource],targetCount: 4) {
            if case .videoCompleted(_,let c) = event { badEyesPicks = c }
        }
        try check(badEyesPicks.isEmpty,"closed eyes never used to fill requested count")
        let badMouth = AutoPickEngine(faceAnalyzer: { _ in FaceQualityResult(faceFound: true,eyesOpen: true,mouthClosed: false) })
        var badMouthPicks: [FrameCandidate] = []
        for await event in await badMouth.run(videos: [staticSource],targetCount: 4) {
            if case .videoCompleted(_,let c) = event { badMouthPicks = c }
        }
        try check(badMouthPicks.isEmpty,"open mouth never used to fill requested count")
        let unavailable = AutoPickEngine(faceAnalyzer: { _ in nil })
        var warned = false, fallbackPicks = 0
        for await event in await unavailable.run(videos: [staticSource],targetCount: 4) {
            if case .warning = event { warned = true }
            if case .videoCompleted(_,let c) = event { fallbackPicks = c.count }
        }
        try check(warned && fallbackPicks == 1,"unavailable faces warn and continue with sharpness/diversity")
        // Preview/export placement arithmetic at non-default scale and offsets.
        let placement = LogoPlacement(slotKey: key,offsetX: 10,offsetY: 20,scale: 0.5)
        let rect = LogoPreviewGeometry.rect(placement: placement,containerSize: CGSize(width: 160,height: 96),imageSize: CGSize(width: 160,height: 96),fitScale: 1)
        try check(rect.minX == 10 && rect.minY == 20 && rect.width == 80,"top-left logo geometry at 50 percent scale")
        let base = CIImage(color: CIColor(red: 0,green: 0,blue: 0)).cropped(to: CGRect(x: 0,y: 0,width: 160,height: 96))
        let logo = CIImage(color: CIColor(red: 1,green: 0,blue: 0)).cropped(to: CGRect(x: 0,y: 0,width: 160,height: 96))
        let composite = LogoCompositor.compose(frame: base,logo: logo,placement: placement)
        try check(composite.extent == base.extent,"logo outside bounds cannot enlarge export")
        let context = CIContext(options: [.workingColorSpace: NSNull()])
        let swatch = CIImage(color: CIColor(red: 0.5,green: 0.5,blue: 0.5)).cropped(to: CGRect(x: 0,y: 0,width: 2,height: 2))
        let corrected = HLGToRec709Converter.apply(to: swatch)
        var rgba = [UInt8](repeating: 0,count: 16)
        context.render(corrected,toBitmap: &rgba,rowBytes: 8,bounds: swatch.extent,format: .RGBA8,colorSpace: CGColorSpaceCreateDeviceRGB())
        try check(rgba[0] < 115 && rgba[0] > 20,"HDR correction changes midtone pixels")
        exportSettings.exportFormat = .jpeg; exportSettings.jpegQuality = 90
        let jpeg = try await FrameExporter.export(candidate: candidate,video: source,settings: exportSettings,destinationFolder: root)
        try check(jpeg.pathExtension == "jpg" && (try PhotoSource.read(url: jpeg)).width == 96,"JPEG export at source resolution")
        let failedStream = await BatchExporter().run(candidates: [(candidate,VideoItem(bookmark: try SecureBookmark(url: root),fileName: "missing.mp4",width: 10,height: 10,durationSeconds: 1,fps: 1,aspect: .other))],settings: exportSettings,destinationFolder: root)
        var reportedFailure = false
        for await event in failedStream { if case .failure = event { reportedFailure = true } }
        try check(reportedFailure,"export errors surfaced instead of silent success")
        // Logo matching must distinguish explicit 4na3 templates, 16:9 and
        // approximately square photos independently of portrait rotation.
        for (w,h,family) in [(1920,1080,AspectClass.sixteenNine),(1080,1920,.sixteenNine),(6000,4000,.fourThree),(4000,6000,.fourThree),(1000,1000,.fourThree),(1600,1000,.sixteenNine)] {
            try check(AspectClass.logoFamily(width: w,height: h) == family,"logo family \(w)x\(h)")
        }
        let logos = root.appendingPathComponent("logo-fixtures")
        try FileManager.default.createDirectory(at: logos,withIntermediateDirectories: true)
        func overlay(_ width: Int,_ height: Int,_ red: Bool) -> CGImage {
            let ctx = CGContext(data: nil,width: width,height: height,bitsPerComponent: 8,bytesPerRow: width*4,space: CGColorSpaceCreateDeviceRGB(),bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
            ctx.clear(CGRect(x: 0,y: 0,width: width,height: height))
            ctx.setFillColor(CGColor(red: red ? 1 : 0,green: 0,blue: red ? 0 : 1,alpha: 1))
            ctx.fill(CGRect(x: 0,y: height*3/4,width: width/4,height: height/4))
            return ctx.makeImage()!
        }
        let wideLogo = logos.appendingPathComponent("ПРИОРИТЕТ - лого слева 16на9.png")
        let nearSquareLogo = logos.appendingPathComponent("ПРИОРИТЕТ - лого слева 4на3.png")
        let alternateLogo = logos.appendingPathComponent("замена - лого слева 16на9.png")
        try write(overlay(1920,1080,true),wideLogo)
        try write(overlay(600,400,false),nearSquareLogo)
        try write(overlay(192,108,false),alternateLogo)
        let matched = LogoMatcher.matchLogos(in: logos)
        let wideKey = LogoSlotKey(aspect: .sixteenNine,orientation: .landscape,side: .left)
        let squareKey = LogoSlotKey(aspect: .fourThree,orientation: .landscape,side: .left)
        try check(matched[wideKey]?.lastPathComponent == wideLogo.lastPathComponent && matched[squareKey]?.lastPathComponent == nearSquareLogo.lastPathComponent,"named 4na3 template with 3:2 pixels stays separate from 16:9")
        var logoSettings = Settings.empty
        logoSettings.logosFolder = try SecureBookmark(url: logos)
        logoSettings.logoSlots[wideKey.stringValue]?.imageBookmark = try SecureBookmark(url: wideLogo)
        logoSettings.logoSlots[squareKey.stringValue]?.imageBookmark = try SecureBookmark(url: nearSquareLogo)
        func pixels(_ image: CGImage) -> [UInt8] {
            var data = [UInt8](repeating: 0,count: image.width*image.height*4)
            data.withUnsafeMutableBytes { bytes in
                let ctx = CGContext(data: bytes.baseAddress,width: image.width,height: image.height,bitsPerComponent: 8,bytesPerRow: image.width*4,space: CGColorSpaceCreateDeviceRGB(),bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
                ctx.draw(image,in: CGRect(x: 0,y: 0,width: image.width,height: image.height))
            }
            return data
        }
        let background = LogoCompositor.sharedContext.createCGImage(CIImage(color: CIColor(red: 0.1,green: 0.1,blue: 0.1)).cropped(to: CGRect(x: 0,y: 0,width: 192,height: 108)),from: CGRect(x: 0,y: 0,width: 192,height: 108))!
        let widePlacement = LogoPlacement(slotKey: wideKey)
        let visible = try await ImagePostProcessor.shared.preview(base: background,imageSize: CGSize(width: 1920,height: 1080),placement: widePlacement,settings: logoSettings)
        try check(pixels(visible) != pixels(background),"logo visible in card preview")
        var hiddenSettings = logoSettings; hiddenSettings.exportIncludeLogo = false
        let hidden = try await ImagePostProcessor.shared.preview(base: background,imageSize: CGSize(width: 1920,height: 1080),placement: widePlacement,settings: hiddenSettings)
        try check(pixels(hidden) == pixels(background),"global logo switch produces clean card pixels")
        let visibleAgain = try await ImagePostProcessor.shared.preview(base: background,imageSize: CGSize(width: 1920,height: 1080),placement: widePlacement,settings: logoSettings)
        try check(pixels(visibleAgain) == pixels(visible),"logo returns after off/on without reimport")
        let oldIdentity = LogoLoadIdentity(slotKey: wideKey,settings: logoSettings)
        logoSettings.logoSlots[wideKey.stringValue]?.imageBookmark = try SecureBookmark(url: alternateLogo)
        let replacement = try await ImagePostProcessor.shared.preview(base: background,imageSize: CGSize(width: 1920,height: 1080),placement: widePlacement,settings: logoSettings)
        try check(oldIdentity != LogoLoadIdentity(slotKey: wideKey,settings: logoSettings) && pixels(replacement) != pixels(visible),"changing logo file invalidates preview and cached pixels")
        let logoCandidate = FrameCandidate(videoID: UUID(),frameIndex: 0,timestampSeconds: 0,origin: .photo,logoPlacement: widePlacement)
        let previewPhoto = root.appendingPathComponent("preview-source.png")
        try write(background,previewPhoto)
        let previewSource = VideoItem(id: logoCandidate.videoID,bookmark: try SecureBookmark(url: previewPhoto),fileName: previewPhoto.lastPathComponent,width: 192,height: 108,durationSeconds: 0,fps: 0,aspect: .sixteenNine)
        let previewBase = try await MediaRenderer.shared.read(url: previewPhoto,source: previewSource,candidate: logoCandidate,maxDimension: 640)
        let previewAtNativeSize = try await ImagePostProcessor.shared.preview(base: previewBase,imageSize: CGSize(width: 192,height: 108),placement: widePlacement,settings: logoSettings)
        let exportedLogo = try await FrameExporter.export(candidate: logoCandidate,video: previewSource,settings: logoSettings,destinationFolder: root)
        try check(pixels(try PhotoSource.read(url: exportedLogo)) == pixels(previewAtNativeSize),"preview and PNG export have identical logo pixels")
        var largeSettings = logoSettings
        largeSettings.logoSlots[wideKey.stringValue]?.imageBookmark = try SecureBookmark(url: wideLogo)
        let reduced = try await ImagePostProcessor.shared.logo(settings: largeSettings,slotKey: wideKey,maxDimension: 640)!
        try check(max(reduced.width,reduced.height) <= 640,"large transparent logos decoded at bounded preview size")
        print("VERIFIED \(checks) checks")
    }
}
