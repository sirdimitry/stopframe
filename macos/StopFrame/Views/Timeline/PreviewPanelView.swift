import SwiftUI

struct PreviewPanelView: View {
    @Bindable var viewModel: TimelineViewModel
    @State private var flashOpacity: Double = 0
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        VStack(spacing: 12) {
            Text(previewLabel)
                .font(.callout)
                .foregroundStyle(Palette.textSecondary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .lineLimit(1)

            ZStack {
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(Palette.bgSurfaceAlt)
                if let previewImage = viewModel.previewImage {
                    Image(decorative: previewImage, scale: 1)
                        .resizable()
                        .aspectRatio(contentMode: .fit)
                        .padding(8)
                } else {
                    Text("Выберите видео на временной шкале")
                        .foregroundStyle(Palette.textSecondary)
                }
                Color.white
                    .opacity(flashOpacity)
                    .allowsHitTesting(false)
            }
            .frame(maxWidth: .infinity, minHeight: 200)
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))

            Button("Захватить кадр (Space)") {
                viewModel.captureFrame()
                flashOpacity = reduceMotion ? 0 : 0.3
                withAnimation(.easeOut(duration: 0.3)) {
                    flashOpacity = 0
                }
            }
            .buttonStyle(.primary)
            .frame(maxWidth: .infinity, minHeight: 48)
            .disabled(viewModel.activeVideo == nil)
        }
        .padding()
    }

    private var previewLabel: String {
        if let video = viewModel.activeVideo {
            return "Просмотр: \(video.fileName)"
        }
        return "Просмотр: —"
    }
}
