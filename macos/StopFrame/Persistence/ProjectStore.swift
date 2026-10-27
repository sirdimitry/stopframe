import Foundation

/// Disk I/O for the session-persistence document. `AppState` remains the
/// single runtime source of truth for `videos`/`frameCandidates`; this type
/// only knows how to load/save that state's `ProjectDocument` snapshot.
enum ProjectStore {
    static func load() -> ProjectDocument? {
        guard let data = try? Data(contentsOf: AppPaths.projectFile) else { return nil }
        return try? JSONDecoder().decode(ProjectDocument.self, from: data)
    }

    static func save(_ document: ProjectDocument) {
        guard let data = try? JSONEncoder.stopFrame.encode(document) else { return }
        try? data.write(to: AppPaths.projectFile, options: .atomic)
    }
}
