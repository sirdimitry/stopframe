"""Still-image decoding shared by review and export; respects EXIF orientation."""
from contextlib import contextmanager
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageOps

PHOTO_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.tif', '.tiff', '.bmp', '.heic', '.heif'}


def is_photo_path(path: str) -> bool:
    return Path(path).suffix.lower() in PHOTO_EXTENSIONS


@contextmanager
def open_photo(path: str):
    if Path(path).suffix.lower() in {'.heic', '.heif'} and sys.platform == 'darwin':
        # macOS ships the HEIF decoder; no extra Python plugin is needed.
        with tempfile.TemporaryDirectory(prefix='stopframe-photo-') as folder:
            converted = Path(folder) / 'photo.png'
            subprocess.run(['/usr/bin/sips', '-s', 'format', 'png', path, '--out', str(converted)],
                           check=True, capture_output=True, timeout=60)
            with Image.open(converted) as image:
                yield image
    else:
        with Image.open(path) as image:
            yield image


def photo_size(path: str) -> tuple[int, int]:
    with open_photo(path) as image:
        width, height = image.size
        if image.getexif().get(274) in (5, 6, 7, 8):
            width, height = height, width
        return width, height


def read_photo(path: str) -> np.ndarray:
    with open_photo(path) as image:
        rgb = np.asarray(ImageOps.exif_transpose(image).convert('RGB'))
        return np.ascontiguousarray(rgb[:, :, ::-1])
