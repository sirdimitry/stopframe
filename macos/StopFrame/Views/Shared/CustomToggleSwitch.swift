import SwiftUI

/// A bespoke physical switch — matching the original's one specialized
/// control, used only for the Screenshots tab's global "Logo" toggle, since
/// a physical on/off switch reads better there than a checkbox.
struct CustomToggleSwitch: View {
    @Binding var isOn: Bool

    private let width: CGFloat = 44
    private let height: CGFloat = 24
    private let thumbPadding: CGFloat = 2

    var body: some View {
        Button {
            withAnimation(.spring(response: 0.25, dampingFraction: 0.8)) {
                isOn.toggle()
            }
        } label: {
            ZStack(alignment: isOn ? .trailing : .leading) {
                Capsule()
                    .fill(isOn ? Palette.accent : Palette.border)
                Circle()
                    .fill(Palette.textPrimary)
                    .padding(thumbPadding)
            }
            .frame(width: width, height: height)
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Logo")
        .accessibilityValue(isOn ? "On" : "Off")
        .accessibilityAddTraits(.isButton)
    }
}

#Preview {
    @Previewable @State var isOn = true
    CustomToggleSwitch(isOn: $isOn)
        .padding()
        .background(Palette.bgApp)
}
