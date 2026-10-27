import SwiftUI

@main
struct StopFrameApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @State private var appState = AppState()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(appState)
                .onAppear { appDelegate.appState = appState }
        }
        .defaultSize(width: 1200, height: 800)
        .commands {
            CommandGroup(after: .saveItem) {
                Button("Сохранить проект") { appState.saveProject() }
                    .keyboardShortcut("s", modifiers: .command)
            }
        }
        SwiftUI.Settings {
            VStack(alignment: .leading,spacing: 20) {
                Text("Библиотека логотипов").font(.title2.bold())
                LogosSectionView()
            }.padding(24).frame(width: 620).environment(appState).stopFrameTheme()
        }

    }
}
