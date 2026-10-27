import Foundation

/// Typed identities compare the actual bookmark bytes. Data's text description
/// contains only its length and must never identify a selected logo file.
struct LogoAssetIdentity: Hashable {
    let slotKey: LogoSlotKey
    let imageBookmark: Data?
    let folderBookmark: Data?
    let libraryRevision: UUID?
    init(slotKey: LogoSlotKey,settings: Settings) {
        self.slotKey = slotKey
        imageBookmark = settings.logoSlots[slotKey.stringValue]?.imageBookmark?.bookmarkData
        folderBookmark = settings.logosFolder?.bookmarkData
        libraryRevision = settings.logoLibraryRevision
    }
}
struct LogoLoadIdentity: Hashable {
    let asset: LogoAssetIdentity
    let enabled: Bool
    init(slotKey: LogoSlotKey,settings: Settings) {
        asset = LogoAssetIdentity(slotKey: slotKey,settings: settings)
        enabled = settings.exportIncludeLogo
    }
}
struct CardPreviewIdentity: Hashable {
    let baseRevision: UUID
    let logo: LogoLoadIdentity
    let placement: LogoPlacement
}
