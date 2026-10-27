import SwiftUI

struct SetupView: View {
    var body: some View {
        VStack(alignment: .leading,spacing: 20) {
            VStack(alignment: .leading,spacing: 6) {
                Text("Найдите кадр, который стоит сохранить").font(.title2.bold())
                Text("Откройте папку или добавьте видео и фотографии. Фотографии сразу доступны для обработки.")
                    .foregroundStyle(Palette.textSecondary)
            }
            SourceSectionView().frame(maxHeight: .infinity)
            Divider()
            AutoPickSectionView()
        }.padding(24).background(Palette.bgApp)
    }
}
