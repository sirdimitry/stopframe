# Apple Silicon performance

The macOS build contains a native arm64 Apple Vision worker. On macOS 14+ it selects Neural Engine compute stages only when Vision lists that device as supported; on macOS 13 Vision schedules automatically. Initialization/inference failures fall back to the bundled MediaPipe worker. No model downloads or external Python installations are needed.

Analysis uses AVFoundation (with FFmpeg fallback) and aspect-preserving proxies of at most 960 pixels on the long edge. Changing analysis resolution and the landmark model can change selected timestamps; the count remains an upper limit. Face classification is approximate with both backends.

Card rendering uses 640-pixel proxies, scales logo offsets to those proxies, and runs at most two jobs. Queued edits of the same card collapse into the latest edit. Export retains original resolution and the original FFmpeg color pipeline, runs at most two jobs, and reserves output names atomically. FFmpeg decoder threads are bounded according to CPU count (up to four per decoder). Fitted logo overlays share a cache capped at 64 MiB. OpenCV's inner parallelism is disabled to avoid competing with independent decoder/render jobs; the Apple GCD backend cannot be capped to an intermediate queue width.

## Local measurements, 2026-10-02

Measured on the build Mac (Apple M3 Max), from source, using eight local 1920x1080 clips totaling 72.92 seconds and a target of two frames per clip. Reference and optimized analysis ran in separate fresh Python processes. Source files and saved settings were not changed.

| Workload | Reference | Optimized |
| --- | ---: | ---: |
| Analysis, eight clips | 13.23 s | 7.72 s |
| First clip, including initialization | 2.37 s | 1.09 s |
| PNG/JPEG preview rendering, 16 cards with overlays | 3.30 s, serial full-size reference | 2.41 s, bounded two-job proxy queue |
| JPEG export with overlays, 16 frames | 3.40 s, serial reference | 2.57 s, two jobs |

The final analysis result was approximately 1.7x faster; earlier repeated runs were approximately 1.9x faster. Both pipelines selected two frames for each sampled clip. The preview/export measurements used an earlier, tighter two-thread decoder limit; the release allows up to four on this Mac. Measurements are workload-specific and include file-cache and scheduler effects, not a guarantee for every video. Face detection on an individual warm no-face input took about 11–12 ms with Apple Vision; landmark-heavy frames may cost more. These timings do not prove GPU or Neural Engine utilization percentages; the worker reports the supported compute device it explicitly selected.

Reproduce the analysis comparison:

```bash
.venv/bin/python scripts/build_native.py
.venv/bin/python scripts/benchmark.py /path/to/videos --count 8
```

The release smoke test verifies the native helper's geometry, a real native inference and threaded Automatic Pick in the frozen application, as well as the MediaPipe fallback protocol. It prints the selected face backend.

Apple API references: [Vision face landmarks](https://developer.apple.com/documentation/vision/vndetectfacelandmarksrequest), [supported request compute devices](https://developer.apple.com/documentation/vision/vnrequest/computedevice%28for%3A%29), [Core ML compute units](https://developer.apple.com/documentation/coreml/mlcomputeunits).
