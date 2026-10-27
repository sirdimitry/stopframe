import Foundation

enum SecureBookmarkError: Error {
    case accessDenied
}

/// Codable wrapper around a security-scoped bookmark so sandboxed access to a
/// user-picked file/folder (video, logo PNG, "last folder" convenience paths)
/// survives relaunch. A plain `Codable URL` would only round-trip the path
/// string and lose sandbox access entirely.
struct SecureBookmark: Codable, Equatable {
    private(set) var bookmarkData: Data

    init(url: URL) throws {
        bookmarkData = try url.bookmarkData(
            options: [.withSecurityScope],
            includingResourceValuesForKeys: nil,
            relativeTo: nil
        )
    }

    /// Resolves to a URL. If the bookmark is stale, self-heals by re-deriving
    /// fresh bookmark data in place so staleness doesn't recur on next launch.
    mutating func resolve() throws -> URL {
        var isStale = false
        let url = try URL(
            resolvingBookmarkData: bookmarkData,
            options: [.withSecurityScope],
            relativeTo: nil,
            bookmarkDataIsStale: &isStale
        )
        if isStale, let refreshed = try? url.bookmarkData(
            options: [.withSecurityScope],
            includingResourceValuesForKeys: nil,
            relativeTo: nil
        ) {
            bookmarkData = refreshed
        }
        return url
    }

    /// Resolves and brackets security-scoped access around `body`, stopping
    /// access afterward even if `body` throws.
    mutating func withSecurityScopedAccess<T>(_ body: (URL) throws -> T) throws -> T {
        let url = try resolve()
        guard url.startAccessingSecurityScopedResource() else {
            throw SecureBookmarkError.accessDenied
        }
        defer { url.stopAccessingSecurityScopedResource() }
        return try body(url)
    }
}
