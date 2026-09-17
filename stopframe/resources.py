"""Read-only assets, resolved identically from source and a PyInstaller bundle."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    return ROOT.joinpath(*parts)
