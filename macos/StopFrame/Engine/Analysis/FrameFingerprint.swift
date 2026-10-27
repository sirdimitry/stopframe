import CoreGraphics

/// Compact spatial signature; stores ~20KB per sampled second, never full frames.
struct FrameFingerprint {
    let gray: [Double]
    let color: [Double]
    let hash: [Bool]
    init(_ image: CGImage) {
        var pixels = [UInt8](repeating: 0, count: 64 * 64 * 4)
        pixels.withUnsafeMutableBytes { buffer in
            let ctx = CGContext(data: buffer.baseAddress, width: 64, height: 64, bitsPerComponent: 8, bytesPerRow: 256,
                                space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
            ctx.interpolationQuality = .high
            ctx.draw(image, in: CGRect(x: 0, y: 0, width: 64, height: 64))
        }
        let raw = (0..<4096).map { i in 0.299 * Double(pixels[i*4]) + 0.587 * Double(pixels[i*4+1]) + 0.114 * Double(pixels[i*4+2]) }
        gray = Self.blur(raw, kernel: [0.25, 0.5, 0.25])
        var c: [Double] = []
        for y in 0..<16 { for x in 0..<16 { for channel in 0..<3 {
            var sum = 0.0
            for dy in 0..<4 { for dx in 0..<4 { sum += Double(pixels[((y*4+dy)*64+x*4+dx)*4+channel]) } }
            c.append(sum/16)
        } } }
        color = c
        var reduced = [Double](repeating: 0, count: 1024)
        for y in 0..<32 { for x in 0..<32 {
            reduced[y*32+x] = (gray[(y*2)*64+x*2] + gray[(y*2)*64+x*2+1] + gray[(y*2+1)*64+x*2] + gray[(y*2+1)*64+x*2+1])/4
        } }
        var dct: [Double] = []
        for v in 0..<8 { for u in 0..<8 where u != 0 || v != 0 {
            var coefficient = 0.0
            for y in 0..<32 { for x in 0..<32 {
                coefficient += reduced[y*32+x] * cos(Double(2*x+1)*Double(u)*Double.pi/64) * cos(Double(2*y+1)*Double(v)*Double.pi/64)
            } }
            dct.append(coefficient)
        } }
        let median = dct.sorted()[dct.count/2]
        hash = dct.map { $0 > median }
    }
    static func blur(_ input: [Double], kernel: [Double]) -> [Double] {
        let r = kernel.count/2
        var horizontal = input, output = input
        for y in 0..<64 { for x in 0..<64 {
            var sum = 0.0
            for k in kernel.indices { sum += input[y*64 + min(63, max(0,x+k-r))] * kernel[k] }
            horizontal[y*64+x] = sum
        } }
        for y in 0..<64 { for x in 0..<64 {
            var sum = 0.0
            for k in kernel.indices { sum += horizontal[min(63,max(0,y+k-r))*64+x] * kernel[k] }
            output[y*64+x] = sum
        } }
        return output
    }
    func isSimilar(to other: Self) -> Bool {
        let colorDelta = zip(color, other.color).reduce(0) { $0 + abs($1.0-$1.1) } / Double(color.count) / 255
        guard colorDelta <= 0.08 else { return false }
        let meanX = gray.reduce(0,+)/4096, meanY = other.gray.reduce(0,+)/4096
        let centered = zip(gray,other.gray).reduce(0) { $0 + abs(($1.0-meanX)-($1.1-meanY)) }/4096/255
        let distance = zip(hash,other.hash).filter { $0 != $1 }.count
        if distance <= 6 && centered <= 0.04 { return true }
        let weights = (-3...3).map { exp(-Double($0*$0)/4.5) }
        let sum = weights.reduce(0,+), kernel = weights.map { $0/sum }
        let mx = Self.blur(gray,kernel: kernel), my = Self.blur(other.gray,kernel: kernel)
        let xx = Self.blur(gray.map { $0*$0 },kernel: kernel)
        let yy = Self.blur(other.gray.map { $0*$0 },kernel: kernel)
        let xy = Self.blur(zip(gray,other.gray).map(*),kernel: kernel)
        var ssim = 0.0
        for i in gray.indices {
            let numerator = (2*mx[i]*my[i]+6.5025) * (2*(xy[i]-mx[i]*my[i])+58.5225)
            let denominator = (mx[i]*mx[i]+my[i]*my[i]+6.5025) * (xx[i]-mx[i]*mx[i]+yy[i]-my[i]*my[i]+58.5225)
            ssim += numerator/denominator
        }
        return ssim/4096 >= 0.94
    }
}
