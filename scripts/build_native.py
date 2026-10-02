#!/usr/bin/env python3
"""Build and check the local Apple Vision helper for Apple Silicon."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def build():
    target = ROOT / 'build/StopFrameFaceWorker'
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['xcrun', 'swiftc', '-O', '-target', 'arm64-apple-macosx13.0',
                    str(ROOT / 'native/FaceWorker.swift'), '-o', str(target)], check=True)
    subprocess.run([str(target), '--self-test'], check=True)
    return target


if __name__ == '__main__':
    print(build())
