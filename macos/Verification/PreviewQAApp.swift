import AppKit
import SwiftUI
import ImageIO
import UniformTypeIdentifiers

/// Isolated manual UI regression fixture. Not part of the shipping target.
@main struct PreviewQAApp: App {
    @State private var appState = AppState()
    @State private var ready = false
    var body: some Scene {
        WindowGroup {
            RootView().environment(appState).task {
                guard !ready else { return }; ready = true
                do { try await prepare() }
                catch { appState.message = "QA fixture: \(error.localizedDescription)" }
            }
        }.defaultSize(width: 1200,height: 800)
    }
    @MainActor private func prepare() async throws {
        let root = AppPaths.applicationSupportDirectory().appendingPathComponent("generated-media",isDirectory: true)
        try FileManager.default.createDirectory(at: root,withIntermediateDirectories: true)
        func write(_ image: CGImage,_ name: String) throws -> URL {
            let url = root.appendingPathComponent(name)
            let destination = CGImageDestinationCreateWithURL(url as CFURL,UTType.png.identifier as CFString,1,nil)!
            CGImageDestinationAddImage(destination,image,nil)
            guard CGImageDestinationFinalize(destination) else { throw FrameExportError.writeFailed }
            return url
        }
        func image(_ width: Int,_ height: Int,logo: (String,LogoSide)? = nil) -> CGImage {
            let context = CGContext(data: nil,width: width,height: height,bitsPerComponent: 8,bytesPerRow: width*4,space: CGColorSpaceCreateDeviceRGB(),bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
            if let (label,side) = logo {
                context.clear(CGRect(x: 0,y: 0,width: width,height: height))
                let color = label == "16:9" ? NSColor.systemRed : NSColor.systemBlue
                let rect = CGRect(x: side == .left ? 0 : width*2/3,y: height*3/4,width: width/3,height: height/4)
                context.setFillColor(color.cgColor);context.fill(rect)
                NSGraphicsContext.saveGraphicsState();NSGraphicsContext.current = NSGraphicsContext(cgContext: context,flipped: false)
                (label as NSString).draw(at: NSPoint(x: rect.minX+CGFloat(width)/40,y: rect.minY+CGFloat(height)/30),withAttributes: [.font:NSFont.boldSystemFont(ofSize: CGFloat(min(width,height))/9),.foregroundColor:NSColor.white])
                NSGraphicsContext.restoreGraphicsState()
            } else {
                context.setFillColor(NSColor(calibratedWhite: 0.35,alpha: 1).cgColor)
                context.fill(CGRect(x: 0,y: 0,width: width,height: height))
                for n in 0..<6 {
                    context.setFillColor(NSColor(calibratedWhite: 0.2+CGFloat(n)*0.08,alpha: 1).cgColor)
                    context.fill(CGRect(x: n*width/6,y: 0,width: width/6,height: height))
                }
            }
            return context.makeImage()!
        }
        appState.videos = [];appState.frameCandidates = []
        var settings = Settings.empty
        for key in LogoSlotKey.all {
            let landscape = key.orientation == .landscape
            let w = key.aspect == .sixteenNine ? (landscape ? 1920 : 1080) : (landscape ? 600 : 400)
            let h = key.aspect == .sixteenNine ? (landscape ? 1080 : 1920) : (landscape ? 400 : 600)
            let url = try write(image(w,h,logo: (key.aspect.rawValue,key.side)),"\(key.stringValue.replacingOccurrences(of: ":",with: "на")).png")
            settings.logoSlots[key.stringValue]?.imageBookmark = try SecureBookmark(url: url)
        }
        settings.logosFolder = try SecureBookmark(url: root)
        settings.logoLibraryRevision = UUID()
        appState.settingsStore.settings = settings
        let photos = try [("Wide-16x9.png",1920,1080),("Photo-3x2.png",600,400),("Square-1x1.png",600,600)].map { try write(image($0.1,$0.2),$0.0) }
        await appState.importFiles(photos)
    }
}
