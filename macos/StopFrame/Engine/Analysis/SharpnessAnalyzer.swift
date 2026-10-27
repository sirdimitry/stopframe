import Accelerate
import CoreGraphics

/// Laplacian-variance sharpness score, mirroring `cv2.Laplacian(gray, CV_64F).var()`:
/// grayscale -> 3x3 Laplacian convolution -> variance of the response. A sharp
/// frame has a wide spread of edge-response values; a blurred one, a narrow one.
/// Uses Accelerate/vImage (CPU, vectorized) rather than a GPU path — this runs
/// once per second across an entire video during Auto-Pick sampling, so raw
/// throughput without GPU round-trip latency matters more than convenience.
enum SharpnessAnalyzer {
    /// OpenCV's default `cv2.Laplacian` kernel.
    private static let kernel: [Float] = [0, 1, 0, 1, -4, 1, 0, 1, 0]

    static func score(of cgImage: CGImage) -> Double {
        guard let format = vImage_CGImageFormat(
            bitsPerComponent: 8, bitsPerPixel: 8,
            colorSpace: CGColorSpaceCreateDeviceGray(),
            bitmapInfo: CGBitmapInfo(rawValue: CGImageAlphaInfo.none.rawValue)
        ) else { return 0 }

        guard var grayBuffer = try? vImage_Buffer(cgImage: cgImage, format: format) else { return 0 }
        defer { grayBuffer.free() }

        // Convert to float before convolving so the Laplacian response isn't
        // clipped to 0...255 — the response can be negative, and OpenCV
        // computes this at higher precision before taking the variance.
        guard var floatBuffer = try? vImage_Buffer(
            width: Int(grayBuffer.width), height: Int(grayBuffer.height), bitsPerPixel: 32
        ) else { return 0 }
        defer { floatBuffer.free() }
        vImageConvert_Planar8toPlanarF(&grayBuffer, &floatBuffer, 255, 0, vImage_Flags(kvImageNoFlags))

        guard var responseBuffer = try? vImage_Buffer(
            width: Int(grayBuffer.width), height: Int(grayBuffer.height), bitsPerPixel: 32
        ) else { return 0 }
        defer { responseBuffer.free() }

        let convolveError = kernel.withUnsafeBufferPointer { kernelPointer in
            vImageConvolve_PlanarF(
                &floatBuffer, &responseBuffer, nil, 0, 0,
                kernelPointer.baseAddress, 3, 3, 0, vImage_Flags(kvImageEdgeExtend)
            )
        }
        guard convolveError == kvImageNoError else { return 0 }

        return variance(of: responseBuffer)
    }

    /// Row-wise reduction (rather than treating the buffer as one flat
    /// array) since `rowBytes` may include alignment padding beyond `width`.
    private static func variance(of buffer: vImage_Buffer) -> Double {
        let width = Int(buffer.width)
        let height = Int(buffer.height)
        guard width > 0, height > 0 else { return 0 }

        var sum: Float = 0
        var sumSquares: Float = 0
        for row in 0..<height {
            let rowPointer = buffer.data.advanced(by: row * buffer.rowBytes).assumingMemoryBound(to: Float.self)
            var rowSum: Float = 0
            var rowSumSquares: Float = 0
            vDSP_sve(rowPointer, 1, &rowSum, vDSP_Length(width))
            vDSP_svesq(rowPointer, 1, &rowSumSquares, vDSP_Length(width))
            sum += rowSum
            sumSquares += rowSumSquares
        }

        let count = Float(width * height)
        let mean = sum / count
        let meanSquare = sumSquares / count
        return Double(meanSquare - mean * mean)
    }
}
