import Accelerate
import CoreGraphics

struct EdgeDensityResult {
    var left: Double
    var right: Double
}

/// Sobel-based edge density for the left and right thirds of a frame — the
/// core signal for adaptive logo-side placement: the calmer (lower-density)
/// third is where the logo goes.
enum EdgeDensityAnalyzer {
    private static let sobelX: [Float] = [-1, 0, 1, -2, 0, 2, -1, 0, 1]
    private static let sobelY: [Float] = [-1, -2, -1, 0, 0, 0, 1, 2, 1]

    static func analyze(_ cgImage: CGImage) -> EdgeDensityResult? {
        guard let format = vImage_CGImageFormat(
            bitsPerComponent: 8, bitsPerPixel: 8,
            colorSpace: CGColorSpaceCreateDeviceGray(),
            bitmapInfo: CGBitmapInfo(rawValue: CGImageAlphaInfo.none.rawValue)
        ) else { return nil }

        guard var grayBuffer = try? vImage_Buffer(cgImage: cgImage, format: format) else { return nil }
        defer { grayBuffer.free() }

        guard var floatBuffer = try? vImage_Buffer(
            width: Int(grayBuffer.width), height: Int(grayBuffer.height), bitsPerPixel: 32
        ) else { return nil }
        defer { floatBuffer.free() }
        vImageConvert_Planar8toPlanarF(&grayBuffer, &floatBuffer, 255, 0, vImage_Flags(kvImageNoFlags))

        guard var gxBuffer = try? vImage_Buffer(
            width: Int(grayBuffer.width), height: Int(grayBuffer.height), bitsPerPixel: 32
        ), var gyBuffer = try? vImage_Buffer(
            width: Int(grayBuffer.width), height: Int(grayBuffer.height), bitsPerPixel: 32
        ) else { return nil }
        defer { gxBuffer.free(); gyBuffer.free() }

        let gxError = sobelX.withUnsafeBufferPointer { kernelPointer in
            vImageConvolve_PlanarF(
                &floatBuffer, &gxBuffer, nil, 0, 0, kernelPointer.baseAddress, 3, 3, 0, vImage_Flags(kvImageEdgeExtend)
            )
        }
        let gyError = sobelY.withUnsafeBufferPointer { kernelPointer in
            vImageConvolve_PlanarF(
                &floatBuffer, &gyBuffer, nil, 0, 0, kernelPointer.baseAddress, 3, 3, 0, vImage_Flags(kvImageEdgeExtend)
            )
        }
        guard gxError == kvImageNoError, gyError == kvImageNoError else { return nil }

        return magnitudeSums(gx: gxBuffer, gy: gyBuffer)
    }

    /// Sums Sobel gradient magnitude (`sqrt(gx^2 + gy^2)`) over the left-third
    /// and right-third column ranges, row by row (respecting `rowBytes`,
    /// which may include alignment padding beyond `width`).
    private static func magnitudeSums(gx: vImage_Buffer, gy: vImage_Buffer) -> EdgeDensityResult {
        let width = Int(gx.width)
        let height = Int(gx.height)
        let thirdWidth = max(1, width / 3)
        let rightStart = width - thirdWidth

        var leftSum: Double = 0
        var rightSum: Double = 0

        var gxSquared = [Float](repeating: 0, count: width)
        var gySquared = [Float](repeating: 0, count: width)
        var sumSquares = [Float](repeating: 0, count: width)
        var magnitude = [Float](repeating: 0, count: width)
        var sampleCount = Int32(width)

        for row in 0..<height {
            let gxRow = gx.data.advanced(by: row * gx.rowBytes).assumingMemoryBound(to: Float.self)
            let gyRow = gy.data.advanced(by: row * gy.rowBytes).assumingMemoryBound(to: Float.self)

            vDSP_vsq(gxRow, 1, &gxSquared, 1, vDSP_Length(width))
            vDSP_vsq(gyRow, 1, &gySquared, 1, vDSP_Length(width))
            vDSP_vadd(gxSquared, 1, gySquared, 1, &sumSquares, 1, vDSP_Length(width))
            vvsqrtf(&magnitude, sumSquares, &sampleCount)

            var leftRowSum: Float = 0
            var rightRowSum: Float = 0
            vDSP_sve(magnitude, 1, &leftRowSum, vDSP_Length(thirdWidth))
            magnitude.withUnsafeBufferPointer { pointer in
                vDSP_sve(pointer.baseAddress! + rightStart, 1, &rightRowSum, vDSP_Length(thirdWidth))
            }

            leftSum += Double(leftRowSum)
            rightSum += Double(rightRowSum)
        }

        return EdgeDensityResult(left: leftSum, right: rightSum)
    }
}
