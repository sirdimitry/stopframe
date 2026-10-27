import SwiftUI

struct AutoPickSectionView: View {
    @Environment(AppState.self) private var appState
    @State private var confirmLong = false
    private var count: Binding<Int> {
        Binding(get: { appState.settingsStore.settings.framesPerVideo ?? 4 },set: { appState.settingsStore.settings.framesPerVideo = min(Int(Int32.max),max(1,$0)) })
    }
    var body: some View {
        VStack(alignment: .leading,spacing: 12) {
            HStack(spacing: 16) {
                Label("Автоматический отбор",systemImage: "sparkles").font(.headline)
                Spacer()
                Text("Максимум кадров на видео").foregroundStyle(Palette.textSecondary)
                TextField("Количество",value: count,format: .number.grouping(.never))
                    .textFieldStyle(.roundedBorder).frame(width: 85).disabled(appState.isAnalyzing)
                Stepper("Количество",value: count,in: 1...Int(Int32.max)).labelsHidden().disabled(appState.isAnalyzing)
                Button(appState.isAnalyzing ? "Идёт отбор…" : "Отобрать кадры") {
                    if count.wrappedValue > 99 { confirmLong = true } else { appState.startAnalysis(count: count.wrappedValue) }
                }.buttonStyle(.primary).disabled(appState.isAnalyzing || appState.isImporting || appState.videoSources.isEmpty)
                if appState.isAnalyzing {
                    Button("Остановить") { appState.stopAnalysis(); appState.analysisStatus = "Отбор остановлен. Уже найденные кадры сохранены." }.buttonStyle(.secondary)
                }
            }
            Text("Резкость, открытые глаза, закрытый рот и разные сцены. Указанное число — максимум: статичная сцена может дать один кадр.")
                .font(.caption).foregroundStyle(Palette.textSecondary)
            if appState.isAnalyzing { ProgressView(value: Double(appState.analysisDone),total: Double(max(1,appState.analysisTotal))) }
            if !appState.analysisStatus.isEmpty { Text(appState.analysisStatus).font(.caption).foregroundStyle(Palette.textSecondary) }
        }
        .alert("Поиск может занять много времени",isPresented: $confirmLong) {
            Button("Нет",role: .cancel) { }.keyboardShortcut(.defaultAction)
            Button("Да") { appState.startAnalysis(count: count.wrappedValue) }
        } message: { Text("Вы запросили \(count.wrappedValue) кадров на видео. Начать поиск?") }
    }
}
