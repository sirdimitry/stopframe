import Foundation
import Observation

/// Loads Settings once at launch; saves synchronously on every mutation
/// (assigning through `settings.someField = ...` triggers `didSet` below),
/// matching the original's "no explicit Save button, every edit persists
/// immediately" behavior.
@Observable
@MainActor
final class SettingsStore {
    var settings: Settings {
        didSet {
            guard settings != oldValue else { return }
            save()
        }
    }

    init() {
        settings = Self.load()
    }

    private static func load() -> Settings {
        guard let data = try? Data(contentsOf: AppPaths.settingsFile),
              let decoded = try? JSONDecoder().decode(Settings.self, from: data)
        else {
            return .empty
        }
        return decoded
    }

    private func save() {
        do {
            let data = try JSONEncoder.stopFrame.encode(settings)
            try data.write(to: AppPaths.settingsFile, options: .atomic)
        } catch {
            Task { await StopFrameLogger.shared.error("settings", "failed to save: \(error.localizedDescription)") }
        }
    }
}
