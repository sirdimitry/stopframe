import SwiftUI

private struct StopFrameThemeModifier: ViewModifier {
    func body(content: Content) -> some View {
        content
            .preferredColorScheme(.dark)
            .tint(Palette.accent)
    }
}

extension View {
    /// Pins the fixed dark theme + accent tint. Applied once at the root.
    func stopFrameTheme() -> some View {
        modifier(StopFrameThemeModifier())
    }
}
