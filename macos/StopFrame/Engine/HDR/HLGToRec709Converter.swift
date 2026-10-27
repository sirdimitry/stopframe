import CoreImage
import simd

/// Approximate HDR fix for HLG (Hybrid Log-Gamma) footage decoded "as is"
/// (as if already display-referred), which looks flat/washed-out. The full
/// pipeline runs in linear light between two curves:
///
/// 1. HLG EOTF (per channel) — HLG signal -> linear light, BT.2020.
/// 2. BT.2020 -> BT.709 gamut matrix (`ColorMatrix`, cross-channel) — the
///    critical step; skipping it leaves a visible green cast, since
///    BT.2020's green primary is far more saturated than BT.709's.
/// 3. Rec.709 OETF (per channel) — back to a display signal.
///
/// Known limitation, inherited by design: out-of-gamut colors are hard-clipped,
/// not perceptually remapped, and there's no local tone mapping — this fixes
/// the dominant "flat and green" symptom, not a full ACES-like pipeline.
enum HLGToRec709Converter {
    private static let kernel: CIColorKernel? = {
        let source = """
        kernel vec4 hlgToRec709(__sample s, vec3 col0, vec3 col1, vec3 col2) {
            vec3 e = s.rgb;
            float a = 0.17883277;
            float b = 0.28466892;
            float c = 0.55991073;

            vec3 lin;
            lin.r = e.r <= 0.5 ? (e.r * e.r) / 3.0 : (exp((e.r - c) / a) + b) / 12.0;
            lin.g = e.g <= 0.5 ? (e.g * e.g) / 3.0 : (exp((e.g - c) / a) + b) / 12.0;
            lin.b = e.b <= 0.5 ? (e.b * e.b) / 3.0 : (exp((e.b - c) / a) + b) / 12.0;

            mat3 m = mat3(col0, col1, col2);
            vec3 converted = clamp(m * lin, 0.0, 1.0);

            vec3 outColor;
            outColor.r = converted.r < 0.018 ? 4.5 * converted.r : 1.099 * pow(converted.r, 0.45) - 0.099;
            outColor.g = converted.g < 0.018 ? 4.5 * converted.g : 1.099 * pow(converted.g, 0.45) - 0.099;
            outColor.b = converted.b < 0.018 ? 4.5 * converted.b : 1.099 * pow(converted.b, 0.45) - 0.099;

            return vec4(outColor, s.a);
        }
        """
        return try? CIColorKernel(source: source)
    }()

    static func apply(to image: CIImage) -> CIImage {
        guard let kernel else { return image }
        let m = ColorMatrix.bt2020ToBt709
        let col0 = CIVector(x: CGFloat(m.columns.0.x), y: CGFloat(m.columns.0.y), z: CGFloat(m.columns.0.z))
        let col1 = CIVector(x: CGFloat(m.columns.1.x), y: CGFloat(m.columns.1.y), z: CGFloat(m.columns.1.z))
        let col2 = CIVector(x: CGFloat(m.columns.2.x), y: CGFloat(m.columns.2.y), z: CGFloat(m.columns.2.z))
        return kernel.apply(extent: image.extent, arguments: [image, col0, col1, col2]) ?? image
    }
}
