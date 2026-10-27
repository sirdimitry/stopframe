import SwiftUI

/// Equal-width choices fill their allocated space rather than relying on
/// NSSegmentedControl's intrinsic width. Native buttons retain keyboard access.
struct ChoiceStrip<Option: Hashable>: View {
    let title: String
    let options: [(String,Option)]
    @Binding var selection: Option
    var body: some View {
        HStack(spacing: 2) {
            ForEach(options.indices,id: \.self) { index in
                let option = options[index]
                Button { selection = option.1 } label: {
                    Text(option.0).font(.system(size: 13,weight: .semibold)).lineLimit(1)
                        .frame(maxWidth: .infinity,minHeight: 30)
                        .foregroundStyle(selection == option.1 ? Palette.bgApp : Palette.textPrimary)
                        .background(selection == option.1 ? Palette.accent : .clear,in: RoundedRectangle(cornerRadius: 6))
                        .contentShape(Rectangle())
                }.buttonStyle(.plain)
                    .accessibilityLabel("\(title): \(option.0)")
                    .accessibilityAddTraits(selection == option.1 ? [.isSelected] : [])
            }
        }.padding(3).background(Palette.bgElevated,in: RoundedRectangle(cornerRadius: 8))
    }
}
