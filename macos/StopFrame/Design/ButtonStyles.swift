import SwiftUI

/// Solid orange primary action — one per screen, matching the original's rule
/// of exactly one primary button per view (Export, Run Automatic Pick, Capture Frame, ...).
struct PrimaryButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 13, weight: .semibold))
            // Dark text, not white — white-on-accent measures ~3:1, short of
            // the 4.5:1 WCAG minimum for this text size; dark text against
            // the same orange measures ~6.5:1.
            .foregroundStyle(Palette.bgApp)
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
            .frame(minHeight: 20)
            .background(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(configuration.isPressed ? Palette.accentPressed : Palette.accent)
            )
            .opacity(isEnabled ? (configuration.isPressed ? 0.85 : 1) : 0.4)
            .animation(reduceMotion ? nil : .easeOut(duration: 0.09), value: configuration.isPressed)
    }
}

/// Dark surface + border, orange only on hover/focus — the default button look.
struct SecondaryButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 13, weight: .medium))
            .foregroundStyle(Palette.textPrimary)
            .padding(.horizontal, 14)
            .padding(.vertical, 9)
            .background(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(configuration.isPressed ? Palette.bgPressed : Palette.bgSurfaceAlt)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .strokeBorder(Palette.border, lineWidth: 1)
            )
            .opacity(isEnabled ? (configuration.isPressed ? 0.85 : 1) : 0.4)
            .animation(reduceMotion ? nil : .easeOut(duration: 0.09), value: configuration.isPressed)
    }
}

/// Transparent, icon-only — used for things like the exclude "x" on a screenshot card.
struct IconButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .foregroundStyle(Palette.textSecondary)
            .frame(width: 24, height: 24)
            .background(Circle().fill(configuration.isPressed ? Palette.bgPressed : Color.clear))
            .opacity(isEnabled ? (configuration.isPressed ? 0.85 : 1) : 0.4)
            .animation(reduceMotion ? nil : .easeOut(duration: 0.09), value: configuration.isPressed)
    }
}

extension ButtonStyle where Self == PrimaryButtonStyle {
    static var primary: PrimaryButtonStyle { PrimaryButtonStyle() }
}

extension ButtonStyle where Self == SecondaryButtonStyle {
    static var secondary: SecondaryButtonStyle { SecondaryButtonStyle() }
}

extension ButtonStyle where Self == IconButtonStyle {
    static var icon: IconButtonStyle { IconButtonStyle() }
}
