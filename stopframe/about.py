"""What the About dialog shows. Keep this in sync with requirements.txt
and reality as the build changes: add an entry when something new is
actually wired in, remove one the moment it stops being used (this
project has already carried genuinely-dead dependencies before —
imageio-ffmpeg sat in requirements.txt unused for a while).
"""

from __future__ import annotations

from stopframe import __version__

CREDIT = "навайбкодил- @sirdimitry"

TECH_STACK = [
    "PySide6 (Qt for Python) — the user interface",
    "OpenCV (opencv-contrib-python) — video decoding/seeking, sharpness "
    "scoring, edge detection, and the HDR color-space math",
    "Pillow — logo compositing",
    "NumPy — image and color math",
    "MediaPipe (legacy solutions.face_mesh API) — optional eyes-open/"
    "mouth-closed check during automatic pick; the app works fine "
    "without it, that check is just skipped",
]


def about_text() -> str:
    lines = [
        f"StopFrame {__version__}",
        CREDIT,
        "",
        "Runs fully local. Nothing is uploaded or sent anywhere.",
        "",
        "Built with:",
    ]
    lines += [f"  • {item}" for item in TECH_STACK]
    return "\n".join(lines)
