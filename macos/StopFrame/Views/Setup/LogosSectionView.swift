import SwiftUI
import UniformTypeIdentifiers

struct LogosSectionView: View {
    @Environment(AppState.self) private var appState
    @State private var isPickingFolder = false
    @State private var didInitialRescan = false

    var body: some View {
        @Bindable var settingsStore = appState.settingsStore

        VStack(alignment: .leading,spacing: 12) {
            Button("Выбрать папку логотипов…") { isPickingFolder = true }
                .buttonStyle(.primary)

            Text(statusText(settingsStore.settings))
                .font(.caption)
                .foregroundStyle(isComplete(settingsStore.settings) ? Palette.success : Palette.textSecondary)
                .help(missingSlotsDescription(settingsStore.settings))
            Text(missingSlotsDescription(settingsStore.settings)).font(.caption).foregroundStyle(Palette.textSecondary)
            Button("Проверить файлы заново") {
                guard var bookmark = settingsStore.settings.logosFolder,let url = try? bookmark.resolve() else { return }
                rescan(folder: url,persistFolder: false)
            }.disabled(settingsStore.settings.logosFolder == nil)
        }
        .fileImporter(isPresented: $isPickingFolder, allowedContentTypes: [.folder]) { result in
            guard case .success(let url) = result else { return }
            rescan(folder: url, persistFolder: true)
        }
        .task {
            guard !didInitialRescan else { return }
            didInitialRescan = true
            guard var bookmark = settingsStore.settings.logosFolder, let url = try? bookmark.resolve() else { return }
            rescan(folder: url, persistFolder: false)
        }
    }

    private func filledCount(_ settings: Settings) -> Int {
        settings.logoSlots.values.filter { $0.imageBookmark != nil }.count
    }

    private func isComplete(_ settings: Settings) -> Bool {
        filledCount(settings) == LogoSlotKey.all.count
    }

    private func statusText(_ settings: Settings) -> String {
        let count = filledCount(settings)
        guard count > 0 else { return "Логотипы не загружены" }
        return "Найдено шаблонов: \(count) из \(LogoSlotKey.all.count)"
    }

    private func missingSlotsDescription(_ settings: Settings) -> String {
        let missing = LogoSlotKey.all.filter { settings.logoSlots[$0.stringValue]?.imageBookmark == nil }
        guard !missing.isEmpty else { return "Все шаблоны найдены" }
        return "Не найдены: " + missing.map(\.stringValue).joined(separator: ", ")
    }

    private func rescan(folder: URL, persistFolder: Bool) {
        // Needed for both a fresh picker URL (recursing into subfolders
        // needs the scope explicitly held) and a resolved bookmark from a
        // previous launch (which never has implicit access at all).
        let granted = folder.startAccessingSecurityScopedResource()
        defer { if granted { folder.stopAccessingSecurityScopedResource() } }

        let matches = LogoMatcher.matchLogos(in: folder)
        var updated = appState.settingsStore.settings
        for key in LogoSlotKey.all {
            if let matchedURL = matches[key] {
                updated.logoSlots[key.stringValue]?.imageBookmark = try? SecureBookmark(url: matchedURL)
            } else {
                updated.logoSlots[key.stringValue]?.imageBookmark = nil
            }
        }
        if persistFolder {
            updated.logosFolder = try? SecureBookmark(url: folder)
        }
        updated.logoLibraryRevision = UUID()
        appState.settingsStore.settings = updated
    }
}

#Preview {
    LogosSectionView()
        .environment(AppState())
        .stopFrameTheme()
        .padding()
}
