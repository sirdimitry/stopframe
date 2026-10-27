import SwiftUI

struct ScreenshotsToolbarView: View {
    @Environment(AppState.self) private var appState
    @Bindable var viewModel: ScreenshotsViewModel
    @State private var showSettings = false
    @State private var showLibrary = false
    var body: some View {
        @Bindable var store = appState.settingsStore
        VStack(spacing: 10) {
            HStack {
                Text("Кадры и экспорт").font(.title2.bold())
                Text("Выбрано: \(viewModel.selectedIDs.count)").font(.caption).foregroundStyle(Palette.textSecondary)
                Spacer()
                Button { showLibrary = true } label: {
                    Label("Логотипы: \(store.settings.logoSlots.values.filter { $0.imageBookmark != nil }.count)/8",systemImage: "photo.stack")
                }.help("Открыть библиотеку логотипов")
                Toggle("Логотип",isOn: $store.settings.exportIncludeLogo).toggleStyle(.switch)
                Button { showSettings.toggle() } label: { Label("Параметры",systemImage: "slider.horizontal.3") }
                    .popover(isPresented: $showSettings,arrowEdge: .bottom) { ExportSettingsView() }
            }
            HStack(spacing: 8) {
                Group {
                    Button("Слева") { viewModel.applySide(.left) }
                    Button("Справа") { viewModel.applySide(.right) }
                    Button("4:3") { viewModel.applyAspect(.fourThree) }
                    Button("16:9") { viewModel.applyAspect(.sixteenNine) }
                    Divider().frame(height: 20)
                    Button { viewModel.rotateSelected() } label: { Label("90°",systemImage: "rotate.right") }.help("Повернуть выбранные кадры по часовой стрелке")
                    Button(viewModel.allSelectedHaveHDRFix ? "HDR включён" : "Коррекция HDR") { viewModel.toggleHDRFix() }
                    Button(role: .destructive) { viewModel.deleteSelected() } label: { Label("Удалить",systemImage: "trash") }
                }.disabled(viewModel.selectedIDs.isEmpty)
                Spacer()
                Button("Выбрать все") { viewModel.selectAll() }.keyboardShortcut("a",modifiers: .command)
            }.buttonStyle(.secondary)
        }.padding(16).background(Palette.bgSurface)
        .sheet(isPresented: $showLibrary) {
            VStack(alignment: .leading,spacing: 20) {
                Text("Библиотека логотипов").font(.title2.bold())
                LogosSectionView()
                Button("Готово") { showLibrary = false }.buttonStyle(.primary)
            }.padding(24).frame(width: 620)
        }
    }
}
