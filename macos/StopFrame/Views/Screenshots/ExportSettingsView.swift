import SwiftUI

struct ExportSettingsView: View {
    @Environment(AppState.self) private var appState
    var body: some View {
        @Bindable var store = appState.settingsStore
        Form {
            Section("Имя файла") {
                TextField("Префикс",text: $store.settings.exportPrefix)
                Picker("Положение",selection: $store.settings.prefixBeforeName) {
                    Text("Перед именем").tag(true); Text("После имени").tag(false)
                }
            }
            Section("Изображение") {
                Picker("Формат",selection: $store.settings.exportFormat) {
                    ForEach(ExportFormat.allCases,id: \.self) { Text($0.rawValue).tag($0) }
                }.pickerStyle(.segmented)
                if store.settings.exportFormat == .jpeg {
                    Stepper("Качество JPEG: \(store.settings.jpegQuality)",value: $store.settings.jpegQuality,in: 1...100)
                }
            }
            Text("Видео → подпапка logo выбранной папки. Фото → рядом с оригиналом; пустой префикс заменяется на logo. Существующие файлы сохраняются.")
                .font(.caption).foregroundStyle(Palette.textSecondary)
        }.formStyle(.grouped).frame(width: 370,height: 330)
    }
}
