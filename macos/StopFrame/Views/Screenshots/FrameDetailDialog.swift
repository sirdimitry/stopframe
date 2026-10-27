import SwiftUI

struct FrameDetailDialog: View {
    let candidateID: FrameCandidate.ID
    let video: VideoItem
    @Environment(AppState.self) private var appState
    @Environment(\.dismiss) private var dismiss
    @State private var activeID: UUID?
    @State private var baseImage: CGImage?
    @State private var logoImage: CGImage?
    @State private var zoom = 1.0
    @State private var pan = CGSize.zero
    @State private var panStart = CGSize.zero
    @State private var dragStart: CGPoint?
    @State private var errorText = ""
    @FocusState private var logoFocused: Bool

    private var currentID: UUID { activeID ?? candidateID }
    private var index: Int? { appState.frameCandidates.firstIndex { $0.id == currentID && $0.included } }
    private var candidate: FrameCandidate? { index.map { appState.frameCandidates[$0] } }
    private var source: VideoItem? { candidate.flatMap { c in appState.videos.first { $0.id == c.videoID } } }
    private var order: [UUID] {
        let included = appState.frameCandidates.filter(\.included)
        var groups: [UUID] = []
        for c in included where !groups.contains(c.videoID) { groups.append(c.videoID) }
        return groups.flatMap { id in included.filter { $0.videoID == id }.map(\.id) }
    }
    private var position: Int { order.firstIndex(of: currentID) ?? 0 }
    private var renderKey: String { "\(currentID)|\(candidate?.hdrFix ?? false)|\(candidate?.turns ?? 0)" }
    private var logoKey: LogoLoadIdentity? {
        candidate.map { LogoLoadIdentity(slotKey: $0.logoPlacement.slotKey,settings: appState.settingsStore.settings) }
    }

    var body: some View {
        VStack(spacing: 12) {
            HStack {
                VStack(alignment: .leading,spacing: 4) {
                    Text(source?.fileName ?? "Просмотр кадра").font(.headline).lineLimit(1)
                    Text("\(position+1) из \(order.count) · изменения сохраняются сразу").font(.caption).foregroundStyle(Palette.textSecondary)
                }
                Spacer()
                Button { navigate(-1) } label: { Label("Предыдущий",systemImage: "chevron.left") }
                    .disabled(position == 0).keyboardShortcut(.leftArrow,modifiers: .option)
                Button { navigate(1) } label: {
                    HStack(spacing: 8) { Text("Следующий"); Image(systemName: "chevron.right") }
                }.accessibilityLabel("Следующий")
                    .disabled(position >= order.count-1).keyboardShortcut(.rightArrow,modifiers: .option)
                Button("Готово") { dismiss() }.buttonStyle(.primary).keyboardShortcut(.defaultAction)
            }
            preview.frame(minHeight: 240,maxHeight: .infinity)
            if !errorText.isEmpty { Text(errorText).foregroundStyle(Palette.danger).textSelection(.enabled) }
            HStack(spacing: 12) {
                Button { rotate() } label: { Label("Повернуть 90°",systemImage: "rotate.right") }
                Toggle("Коррекция HDR",isOn: binding(\.hdrFix,default: false)).toggleStyle(.switch)
                Spacer()
                Button("−") { zoom = max(1,zoom-0.5) }.accessibilityLabel("Уменьшить")
                Text("\(Int(zoom*100)) %").monospacedDigit().frame(width: 60)
                Button("+") { zoom = min(8,zoom+0.5) }.accessibilityLabel("Увеличить")
                Button("Вписать") { zoom = 1; pan = .zero; panStart = .zero }
            }
            HStack(spacing: 20) {
                Text("Шаблон логотипа").foregroundStyle(Palette.textSecondary).fixedSize()
                HStack(spacing: 10) {
                    Text("Сторона").fixedSize()
                    ChoiceStrip(title: "Сторона",options: [("Слева",LogoSide.left),("Справа",LogoSide.right)],selection: slotBinding(\.side,default: .left))
                        .frame(maxWidth: .infinity)
                }.frame(maxWidth: .infinity)
                HStack(spacing: 10) {
                    Text("Пропорции").fixedSize()
                    ChoiceStrip(title: "Пропорции",options: [("4:3",AspectClass.fourThree),("16:9",AspectClass.sixteenNine)],selection: slotBinding(\.aspect,default: .sixteenNine))
                        .frame(maxWidth: .infinity)
                }.frame(maxWidth: .infinity)
            }.lineLimit(1)
            adjustment("Смещение X",value: placementBinding(\.offsetX),range: -8000...8000,step: 1,reset: 0)
            adjustment("Смещение Y",value: placementBinding(\.offsetY),range: -8000...8000,step: 1,reset: 0)
            adjustment("Масштаб",value: scaleBinding,range: 0.05...5,step: 0.01,reset: 1)
            Text("Перетащите логотип или задайте точные значения. При увеличении перетаскивайте изображение. Alt + ← / → — соседний кадр.")
                .font(.caption).foregroundStyle(Palette.textSecondary)
        }
        .padding(20).frame(minWidth: 820,idealWidth: 960,minHeight: 650,idealHeight: 760)
        .background(Palette.bgApp).foregroundStyle(Palette.textPrimary)
        .task(id: renderKey) { await render() }
        .task(id: logoKey) { await renderLogo() }
    }
    private var preview: some View {
        GeometryReader { proxy in
            ZStack {
                Palette.bgSurfaceAlt
                if let baseImage, let candidate, let source {
                    Image(decorative: baseImage,scale: 1).resizable().aspectRatio(contentMode: .fit)
                        .frame(width: proxy.size.width,height: proxy.size.height).scaleEffect(zoom).offset(pan)
                    if appState.settingsStore.settings.exportIncludeLogo, let logoImage {
                        let size = candidate.imageSize(for: source)
                        let fit = LogoPreviewGeometry.fitScale(containerSize: proxy.size,imageSize: size)
                        let r = LogoPreviewGeometry.rect(placement: candidate.logoPlacement,containerSize: proxy.size,imageSize: size,fitScale: fit)
                        let center = CGPoint(x: proxy.size.width/2,y: proxy.size.height/2)
                        Image(decorative: logoImage,scale: 1).resizable()
                            .frame(width: r.width*zoom,height: r.height*zoom)
                            .overlay(Rectangle().stroke(logoFocused ? Palette.accent : .clear,lineWidth: 2))
                            .position(x: center.x+(r.midX-center.x)*zoom+pan.width,y: center.y+(r.midY-center.y)*zoom+pan.height)
                            .contentShape(Rectangle()).focusable().focused($logoFocused)
                            .gesture(DragGesture().onChanged { drag in
                                if dragStart == nil { dragStart = CGPoint(x: candidate.logoPlacement.offsetX,y: candidate.logoPlacement.offsetY) }
                                if let start = dragStart {
                                    update { $0.logoPlacement.offsetX = Int(start.x+drag.translation.width/(fit*zoom)); $0.logoPlacement.offsetY = Int(start.y+drag.translation.height/(fit*zoom)) }
                                }
                            }.onEnded { _ in dragStart = nil })
                            .onKeyPress { key in
                                switch key.key {
                                case .leftArrow: update { $0.logoPlacement.offsetX -= 1 }
                                case .rightArrow: update { $0.logoPlacement.offsetX += 1 }
                                case .upArrow: update { $0.logoPlacement.offsetY -= 1 }
                                case .downArrow: update { $0.logoPlacement.offsetY += 1 }
                                default: return .ignored
                                }
                                return .handled
                            }
                            .accessibilityLabel("Положение логотипа").accessibilityHint("Перемещайте стрелками или настройками ниже")
                    }
                } else if errorText.isEmpty { ProgressView("Загрузка…") }
            }
            .contentShape(Rectangle())
            .gesture(DragGesture().onChanged { value in
                guard zoom > 1 else { return }
                pan = CGSize(width: panStart.width+value.translation.width,height: panStart.height+value.translation.height)
            }.onEnded { _ in panStart = pan })
            .simultaneousGesture(MagnifyGesture().onChanged { zoom = min(8,max(1,$0.magnification)) })
            .onTapGesture(count: 2) { zoom = 1; pan = .zero; panStart = .zero }
            .clipped()
        }.clipShape(RoundedRectangle(cornerRadius: 8))
    }
    private func adjustment(_ title: String,value: Binding<Double>,range: ClosedRange<Double>,step: Double,reset: Double) -> some View {
        HStack {
            Text(title).frame(width: 100,alignment: .leading).foregroundStyle(Palette.textSecondary)
            Slider(value: value,in: range,step: step).accessibilityLabel(title)
            TextField(title,value: value,format: .number.precision(.fractionLength(step < 1 ? 2 : 0)))
                .textFieldStyle(.roundedBorder).frame(width: 78).accessibilityLabel("\(title): точное значение")
            Button { value.wrappedValue = reset } label: { Image(systemName: "arrow.counterclockwise") }.help("Сбросить \(title)")
        }
    }
    private func update(_ body: (inout FrameCandidate) -> Void) {
        guard let index else { return }; body(&appState.frameCandidates[index])
    }
    private func binding<T>(_ key: WritableKeyPath<FrameCandidate,T>,default fallback: T) -> Binding<T> {
        Binding(get: { candidate?[keyPath: key] ?? fallback },set: { value in update { $0[keyPath: key] = value } })
    }
    private func slotBinding<T>(_ key: WritableKeyPath<LogoSlotKey,T>,default fallback: T) -> Binding<T> {
        Binding(get: { candidate?.logoPlacement.slotKey[keyPath: key] ?? fallback },set: { value in update { $0.logoPlacement.slotKey[keyPath: key] = value } })
    }
    private func placementBinding(_ key: WritableKeyPath<LogoPlacement,Int>) -> Binding<Double> {
        Binding(get: { Double(candidate?.logoPlacement[keyPath: key] ?? 0) },set: { value in update { $0.logoPlacement[keyPath: key] = Int(min(8000,max(-8000,value))) } })
    }
    private var scaleBinding: Binding<Double> {
        Binding(get: { candidate?.logoPlacement.scale ?? 1 },set: { value in update { $0.logoPlacement.scale = min(5,max(0.05,value)) } })
    }
    private func rotate() {
        guard let source else { return }
        update { c in
            c.rotationQuarterTurns = (c.turns+1)%4
            let size = c.imageSize(for: source)
            c.logoPlacement.slotKey.orientation = size.height > size.width ? .portrait : .landscape
        }
    }
    private func navigate(_ delta: Int) {
        guard order.indices.contains(position+delta) else { return }
        activeID = order[position+delta]; zoom = 1; pan = .zero; panStart = .zero
    }
    private func render() async {
        baseImage = nil; errorText = ""
        guard let candidate, let source else { return }
        var bookmark = source.bookmark
        do {
            let url = try bookmark.resolve()
            let granted = url.startAccessingSecurityScopedResource()
            defer { if granted { url.stopAccessingSecurityScopedResource() } }
            let image = try await MediaRenderer.shared.read(url: url,source: source,candidate: candidate,maxDimension: 1600)
            guard !Task.isCancelled else { return }; baseImage = image
        } catch { if !Task.isCancelled { errorText = "Не удалось открыть кадр: \(error.localizedDescription)" } }
    }
    private func renderLogo() async {
        logoImage = nil
        guard let candidate else { return }
        do {
            let image = try await ImagePostProcessor.shared.logo(settings: appState.settingsStore.settings,slotKey: candidate.logoPlacement.slotKey,maxDimension: 1600)
            if !Task.isCancelled { logoImage = image }
        } catch {
            if !Task.isCancelled { errorText = "Логотип недоступен. Проверьте библиотеку логотипов." }
        }
    }
}
