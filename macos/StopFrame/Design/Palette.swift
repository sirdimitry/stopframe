import SwiftUI

extension Color {
    init(hex: UInt32, opacity: Double = 1) {
        let red = Double((hex & 0xFF0000) >> 16) / 255
        let green = Double((hex & 0x00FF00) >> 8) / 255
        let blue = Double(hex & 0x0000FF) / 255
        self.init(.sRGB, red: red, green: green, blue: blue, opacity: opacity)
    }
}

/// Fixed dark palette, ported 1:1 from the original app's QSS theme tokens.
/// The app does not follow system light/dark — it always renders dark.
enum Palette {
    static let bgApp = Color(hex: 0x0b0b0d)
    static let bgSurface = Color(hex: 0x141416)
    static let bgSurfaceAlt = Color(hex: 0x1b1b1e)
    static let bgElevated = Color(hex: 0x202024)
    static let bgPressed = Color(hex: 0x262629)

    static let border = Color(hex: 0x2a2a2e)
    static let borderStrong = Color(hex: 0x38383d)

    static let textPrimary = Color(hex: 0xf2f1ee)
    static let textSecondary = Color(hex: 0x9d9ca3)
    static let textDisabled = Color(hex: 0x5a5a60)

    static let accent = Color(hex: 0xe8734a)
    static let accentHover = Color(hex: 0xf0916e)
    // Slightly lighter than a strict "pressed" darkening would suggest —
    // dark button-label text needs this to clear 4.5:1 against it.
    static let accentPressed = Color(hex: 0xcf5820)
    static let accentSubtle = Color(hex: 0xe8734a, opacity: 0.14)

    static let success = Color(hex: 0x7fc697)
    static let danger = Color(hex: 0xff5c5c)
    static let dangerSubtle = Color(hex: 0xff5c5c, opacity: 0.14)

    /// Manual-capture filmstrip marker — deliberately outside the orange accent
    /// family so it never reads as "clickable" like the rest of the UI's accents.
    static let manualMarker = Color(hex: 0xffd65a)
    static let autoMarker = Color(hex: 0x5aa0ff)
    static let playhead = Color(hex: 0xff3c3c)
}
