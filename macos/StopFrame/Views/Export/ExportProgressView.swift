import SwiftUI

struct ExportProgressView: View {
    let done: Int
    let total: Int
    let onCancel: () -> Void

    var body: some View {
        VStack(spacing: 16) {
            Text("Экспорт изображений…")
                .font(.headline)
                .foregroundStyle(Palette.textPrimary)

            ProgressView(value: Double(done), total: Double(max(total, 1)))
                .frame(width: 280)

            Text("\(done) / \(total)")
                .font(.caption)
                .foregroundStyle(Palette.textSecondary)

            Button("Остановить") { onCancel() }
                .buttonStyle(.secondary)
        }
        .padding(24)
        .frame(width: 320)
        .background(Palette.bgApp)
    }
}
