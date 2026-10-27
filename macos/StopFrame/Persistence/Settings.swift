import Foundation

/// Persistent user settings — small, written synchronously on every UI
/// change (matching the original), unlike the much larger project/session
/// document which benefits from debounced saves instead.
struct Settings: Codable, Equatable {
    var logoSlots: [String: LogoSlot]
    var exportPrefix: String = ""
    var prefixBeforeName: Bool = true
    var lastVideoFolder: SecureBookmark?
    var logosFolder: SecureBookmark?
    var exportFormat: ExportFormat = .png
    var jpegQuality: Int = 95
    var exportIncludeLogo: Bool = true
    var framesPerVideo: Int? = 4

    static var empty: Settings {
        var slots: [String: LogoSlot] = [:]
        for key in LogoSlotKey.all {
            slots[key.stringValue] = LogoSlot()
        }
        return Settings(logoSlots: slots)
    }
}
