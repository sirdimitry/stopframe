"""Approximate HLG -> Rec.709 correction for frames that decode "flat" —
the washed-out look you get when an HDR (HLG) clip's samples are read as
if they were already display-referred, without applying the HLG curve.

Full pipeline, all in linear light between the two curves:
  HLG EOTF (per channel) -> BT.2020->BT.709 gamut matrix (cross-channel)
  -> Rec.709 OETF (per channel)

The first version of this only did the two curves and skipped the gamut
matrix — visually that left a green cast, because BT.2020's green primary
is far more saturated than BT.709's; converting only the transfer function
without also remapping the primaries pushes everything toward it. The
matrix below is derived from each color space's standard primaries/white
point (not hand-copied from memory, which is exactly the kind of constant
that's easy to get subtly wrong) via the standard RGB->XYZ construction,
then BT2020->BT709 = inverse(RGB2XYZ_709) @ RGB2XYZ_2020.

Still an approximation — out-of-709-gamut colors are hard-clipped rather
than perceptually remapped, and there's no local tone mapping — but the
dominant "flat and green" symptom is what this fixes.
"""

from __future__ import annotations

import numpy as np

_HLG_A, _HLG_B, _HLG_C = 0.17883277, 0.28466892, 0.55991073

_D65_WHITE_XY = (0.3127, 0.3290)
_BT2020_PRIMARIES_XY = ((0.708, 0.292), (0.170, 0.797), (0.131, 0.046))
_BT709_PRIMARIES_XY = ((0.640, 0.330), (0.300, 0.600), (0.150, 0.060))


def _rgb_to_xyz_matrix(primaries_xy, white_xy) -> np.ndarray:
    """Standard construction: given each primary's chromaticity and the
    white point, find the RGB->XYZ matrix that maps (1,1,1) to the white
    point's XYZ. See e.g. Bruce Lindbloom's "RGB/XYZ Matrices" derivation."""
    primary_xyz = np.array(
        [[x / y, 1.0, (1.0 - x - y) / y] for x, y in primaries_xy]
    ).T  # columns = XYZ of each primary at unit luminance
    xw, yw = white_xy
    white_xyz = np.array([xw / yw, 1.0, (1.0 - xw - yw) / yw])
    scale = np.linalg.solve(primary_xyz, white_xyz)
    return primary_xyz * scale


def _bt2020_to_bt709_matrix() -> np.ndarray:
    to_xyz_2020 = _rgb_to_xyz_matrix(_BT2020_PRIMARIES_XY, _D65_WHITE_XY)
    to_xyz_709 = _rgb_to_xyz_matrix(_BT709_PRIMARIES_XY, _D65_WHITE_XY)
    return np.linalg.inv(to_xyz_709) @ to_xyz_2020


_BT2020_TO_BT709 = _bt2020_to_bt709_matrix()


def _hlg_eotf(e_prime: np.ndarray) -> np.ndarray:
    low = e_prime <= 0.5
    linear = np.empty_like(e_prime)
    linear[low] = (e_prime[low] ** 2) / 3.0
    linear[~low] = (np.exp((e_prime[~low] - _HLG_C) / _HLG_A) + _HLG_B) / 12.0
    return linear


def _rec709_oetf(e: np.ndarray) -> np.ndarray:
    e = np.clip(e, 0.0, None)
    low = e < 0.018
    out = np.empty_like(e)
    out[low] = 4.5 * e[low]
    out[~low] = 1.099 * np.power(e[~low], 0.45) - 0.099
    return out


def apply_hdr_fix(frame_bgr: np.ndarray) -> np.ndarray:
    bgr = frame_bgr.astype(np.float64) / 255.0
    rgb = bgr[:, :, ::-1]

    linear_2020 = _hlg_eotf(rgb)
    linear_709 = np.clip(linear_2020 @ _BT2020_TO_BT709.T, 0.0, 1.0)
    corrected = np.clip(_rec709_oetf(linear_709), 0.0, 1.0)

    result_rgb = (corrected * 255.0).round().astype(np.uint8)
    return result_rgb[:, :, ::-1]
