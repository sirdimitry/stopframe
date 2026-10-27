import Foundation

extension JSONEncoder {
    /// Human-inspectable output (pretty-printed, sorted keys) — settings/project
    /// files are small and infrequently written, so readability wins over size.
    static let stopFrame: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        return encoder
    }()
}
