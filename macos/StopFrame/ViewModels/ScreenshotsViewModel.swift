import Foundation
import Observation

@Observable
@MainActor
final class ScreenshotsViewModel {
    private let appState: AppState

    var selectedIDs: Set<FrameCandidate.ID> = []
    private var anchorID: FrameCandidate.ID?

    /// First-appearance video order for grouping — deliberately stateful
    /// (not re-derived from current capture order each time), so a group's
    /// position stays put once established even as more captures arrive
    /// interleaved across videos. Read via the `groupedCandidates` getter
    /// below, which lazily extends it — safe to call repeatedly since it
    /// only appends video IDs it hasn't seen yet.
    private var groupOrder: [VideoItem.ID] = []

    init(appState: AppState) {
        self.appState = appState
    }

    var groupedCandidates: [(video: VideoItem, candidates: [FrameCandidate])] {
        let included = appState.frameCandidates.filter { $0.included }
        var byVideo: [VideoItem.ID: [FrameCandidate]] = [:]
        for candidate in included {
            byVideo[candidate.videoID, default: []].append(candidate)
        }

        for candidate in included where !groupOrder.contains(candidate.videoID) {
            groupOrder.append(candidate.videoID)
        }

        return groupOrder.compactMap { videoID in
            guard let video = appState.videos.first(where: { $0.id == videoID }),
                  let candidates = byVideo[videoID], !candidates.isEmpty
            else { return nil }
            return (video, candidates)
        }
    }

    /// Flattened order used for Shift-click ranges — all of one video's
    /// cards stay contiguous, so a range never jumps into another video's
    /// cards regardless of the actual interleaved capture order.
    private var flattenedOrder: [FrameCandidate.ID] {
        groupedCandidates.flatMap { $0.candidates.map(\.id) }
    }

    func isSelected(_ id: FrameCandidate.ID) -> Bool {
        selectedIDs.contains(id)
    }

    /// Unconditionally makes `id` the sole selection — used when opening
    /// Frame Detail, so the toolbar's Assign Logo/HDR buttons (which act on
    /// `selectedIDs`, not on whatever the detail sheet happens to show) stay
    /// in sync with the frame actually on screen instead of silently no-oping
    /// or editing an unrelated, hidden card.
    func selectOnly(_ id: FrameCandidate.ID) {
        selectedIDs = [id]
        anchorID = id
    }

    /// Mirrors Finder-style multi-select: plain click replaces the
    /// selection (and toggles off if it was the sole selected item);
    /// Cmd-click adds/removes one item; Shift-click selects the range from
    /// the last anchor.
    func select(_ id: FrameCandidate.ID, extend: Bool, range: Bool) {
        if range, let anchorID {
            let order = flattenedOrder
            guard let anchorIndex = order.firstIndex(of: anchorID), let targetIndex = order.firstIndex(of: id) else {
                selectedIDs = [id]
                self.anchorID = id
                return
            }
            selectedIDs = Set(order[min(anchorIndex, targetIndex)...max(anchorIndex, targetIndex)])
            return
        }

        if extend {
            if selectedIDs.contains(id) {
                selectedIDs.remove(id)
            } else {
                selectedIDs.insert(id)
            }
            anchorID = id
            return
        }

        if selectedIDs == [id] {
            selectedIDs = []
            anchorID = nil
        } else {
            selectedIDs = [id]
            anchorID = id
        }
    }

    /// Soft-delete: the candidate stays in the store, just stops appearing.
    func toggleExclude(_ id: FrameCandidate.ID) {
        guard let index = appState.frameCandidates.firstIndex(where: { $0.id == id }) else { return }
        appState.frameCandidates[index].included = false
        selectedIDs.remove(id)
    }

    /// "On" only when every selected candidate already has the flag set —
    /// drives the toolbar button's label/state.
    var allSelectedHaveHDRFix: Bool {
        let selected = appState.frameCandidates.filter { selectedIDs.contains($0.id) }
        guard !selected.isEmpty else { return false }
        return selected.allSatisfy { $0.hdrFix }
    }

    /// Binary toggle: if any selected candidate is off, turn them all on;
    /// only turns them all off once every selected candidate is already on.
    func toggleHDRFix() {
        let shouldEnable = !allSelectedHaveHDRFix
        for id in selectedIDs {
            guard let index = appState.frameCandidates.firstIndex(where: { $0.id == id }) else { continue }
            appState.frameCandidates[index].hdrFix = shouldEnable
        }
    }

    func rotateSelected() {
        for index in appState.frameCandidates.indices where selectedIDs.contains(appState.frameCandidates[index].id) {
            var candidate = appState.frameCandidates[index]
            candidate.rotationQuarterTurns = (candidate.turns + 1) % 4
            guard let source = appState.videos.first(where: { $0.id == candidate.videoID }) else { continue }
            let size = candidate.imageSize(for: source)
            let key = candidate.logoPlacement.slotKey
            candidate.logoPlacement.slotKey = LogoSlotKey(aspect: key.aspect, orientation: size.height > size.width ? .portrait : .landscape, side: key.side)
            appState.frameCandidates[index] = candidate
        }
    }
    func deleteSelected() {
        for index in appState.frameCandidates.indices where selectedIDs.contains(appState.frameCandidates[index].id) {
            appState.frameCandidates[index].included = false
        }
        selectedIDs.removeAll()
    }
    func selectAll() { selectedIDs = Set(flattenedOrder) }

    func applySide(_ side: LogoSide) {
        applySlotChange { LogoSlotKey(aspect: $0.aspect, orientation: $0.orientation, side: side) }
    }

    func applyAspect(_ aspect: AspectClass) {
        applySlotChange { LogoSlotKey(aspect: aspect, orientation: $0.orientation, side: $0.side) }
    }

    /// Switching slots re-seeds offset/scale from the new slot's own
    /// default — the old per-frame nudge doesn't carry over.
    private func applySlotChange(_ transform: (LogoSlotKey) -> LogoSlotKey) {
        for id in selectedIDs {
            guard let index = appState.frameCandidates.firstIndex(where: { $0.id == id }) else { continue }
            let newKey = transform(appState.frameCandidates[index].logoPlacement.slotKey)
            guard let defaultSlot = appState.settingsStore.settings.logoSlots[newKey.stringValue] else { continue }
            appState.frameCandidates[index].logoPlacement = LogoPlacement(
                slotKey: newKey,
                offsetX: defaultSlot.offsetX,
                offsetY: defaultSlot.offsetY,
                scale: defaultSlot.scale
            )
        }
    }
}
