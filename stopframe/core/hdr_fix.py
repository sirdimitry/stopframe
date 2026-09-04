"""Approximate HLG -> Rec.709 correction for frames that decode "flat" —
the washed-out look you get when an HDR (HLG) clip's samples are read as
if they were already display-referred, without applying the HLG curve.

This is a tone-curve approximation (HLG EOTF -> linear -> Rec.709 OETF)
applied per channel via a 256-entry LUT, not a full BT.2020->709 gamut
remap — it fixes the dominant "flat/milky" symptom cheaply, on the
already-8-bit-decoded frame, with no re-decode of the source video.
"""

from __future__ import annotations

import cv2
import numpy as np

_HLG_A, _HLG_B, _HLG_C = 0.17883277, 0.28466892, 0.55991073


def _hlg_eotf(e_prime: np.ndarray) -> np.ndarray:
    low = e_prime <= 0.5
    linear = np.empty_like(e_prime)
    linear[low] = (e_prime[low] ** 2) / 3.0
    linear[~low] = (np.exp((e_prime[~low] - _HLG_C) / _HLG_A) + _HLG_B) / 12.0
    return linear


def _rec709_oetf(e: np.ndarray) -> np.ndarray:
    low = e < 0.018
    out = np.empty_like(e)
    out[low] = 4.5 * e[low]
    out[~low] = 1.099 * np.power(e[~low], 0.45) - 0.099
    return out


def _build_lut() -> np.ndarray:
    x = np.linspace(0.0, 1.0, 256, dtype=np.float64)
    linear = np.clip(_hlg_eotf(x), 0.0, 1.0)
    corrected = np.clip(_rec709_oetf(linear), 0.0, 1.0)
    return (corrected * 255.0).round().astype(np.uint8)


_LUT = _build_lut()


def apply_hdr_fix(frame_bgr: np.ndarray) -> np.ndarray:
    return cv2.LUT(frame_bgr, _LUT)
