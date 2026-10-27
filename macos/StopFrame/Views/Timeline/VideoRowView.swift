import SwiftUI

struct VideoRowView: View {
    let video: VideoItem
    @Bindable var viewModel: TimelineViewModel

    private var isActive: Bool { viewModel.activeVideoID == video.id }

    var body: some View {
        HStack(spacing: 10) {
            Text(video.fileName)
                .lineLimit(1)
                .truncationMode(.middle)
                .frame(width: 170, alignment: .leading)
                .foregroundStyle(Palette.textPrimary)
                .help(video.fileName)
                .contentShape(Rectangle())
                .onTapGesture { viewModel.activate(video) }

            FilmstripView(
                thumbnails: viewModel.thumbnailsByVideoID[video.id],
                markers: viewModel.markers(for: video.id),
                duration: video.durationSeconds,
                playheadFraction: viewModel.playheadFraction(for: video.id),
                onScrub: { fraction in
                    if !isActive { viewModel.activate(video) }
                    viewModel.setPlayhead(fraction: fraction, for: video)
                }
            )
            .frame(height: 70)
        }
        .padding(8)
        .background(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .fill(isActive ? Palette.accentSubtle : Color.clear)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .strokeBorder(isActive ? Palette.accent : Color.clear, lineWidth: 1)
        )
        .onAppear { viewModel.loadThumbnailsIfNeeded(for: video) }
    }
}
