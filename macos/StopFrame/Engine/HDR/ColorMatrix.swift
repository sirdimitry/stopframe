import simd

/// BT.2020 -> BT.709 RGB conversion matrix, built programmatically from each
/// gamut's primaries + the shared D65 white point via the Bruce Lindbloom
/// method — deliberately not a hardcoded literal, to avoid silently
/// carrying a slightly-wrong constant. Both gamuts share the D65 white
/// point, so no chromatic adaptation step is needed between them.
enum ColorMatrix {
    static let bt2020ToBt709: simd_float3x3 = {
        let rgbToXYZ2020 = rgbToXYZMatrix(
            red: SIMD2(0.708, 0.292), green: SIMD2(0.170, 0.797), blue: SIMD2(0.131, 0.046),
            white: SIMD2(0.3127, 0.3290)
        )
        let rgbToXYZ709 = rgbToXYZMatrix(
            red: SIMD2(0.640, 0.330), green: SIMD2(0.300, 0.600), blue: SIMD2(0.150, 0.060),
            white: SIMD2(0.3127, 0.3290)
        )
        let result = rgbToXYZ709.inverse * rgbToXYZ2020
        return simd_float3x3(
            SIMD3(Float(result.columns.0.x), Float(result.columns.0.y), Float(result.columns.0.z)),
            SIMD3(Float(result.columns.1.x), Float(result.columns.1.y), Float(result.columns.1.z)),
            SIMD3(Float(result.columns.2.x), Float(result.columns.2.y), Float(result.columns.2.z))
        )
    }()

    /// Standard RGB-to-XYZ construction: primaries + white point (as xy
    /// chromaticity coordinates) -> XYZ tristimulus values (Y=1) -> solve
    /// for the per-primary scale factors that reproduce the white point.
    private static func rgbToXYZMatrix(
        red: SIMD2<Double>, green: SIMD2<Double>, blue: SIMD2<Double>, white: SIMD2<Double>
    ) -> simd_double3x3 {
        func xyz(_ chromaticity: SIMD2<Double>) -> SIMD3<Double> {
            SIMD3(chromaticity.x / chromaticity.y, 1, (1 - chromaticity.x - chromaticity.y) / chromaticity.y)
        }

        let xr = xyz(red)
        let xg = xyz(green)
        let xb = xyz(blue)
        let primaries = simd_double3x3(columns: (xr, xg, xb))
        let whiteXYZ = xyz(white)
        let scale = primaries.inverse * whiteXYZ

        return simd_double3x3(columns: (xr * scale.x, xg * scale.y, xb * scale.z))
    }
}
