"""App-wide logging.

Everything stays on disk, locally — this module never sends anything over
the network. The log file lives at paths.log_file() and is capped at
MAX_LOG_BYTES: once it would grow past that, we keep the last KEEP_LINES
lines and drop the rest, instead of growing forever or rotating into
multiple numbered files.

Log content itself must stay privacy-safe: log button presses, which engine
ran, and results/errors — never full filesystem paths to the user's videos
or photos of people. Use short identifiers (file name only, frame index,
etc.) when logging about user media.
"""

import logging
from logging import Logger

from stopframe.paths import log_file

MAX_LOG_BYTES = 10 * 1024 * 1024  # 10 MB
KEEP_LINES = 100

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


class _TrimmingFileHandler(logging.FileHandler):
    """A FileHandler that trims itself to the last KEEP_LINES lines
    whenever it would otherwise grow past MAX_LOG_BYTES."""

    def emit(self, record: logging.LogRecord) -> None:
        self._trim_if_needed()
        super().emit(record)

    def _trim_if_needed(self) -> None:
        try:
            path = self.baseFilename
            if self.stream is None:
                return
            self.stream.flush()
            import os

            if os.path.getsize(path) <= MAX_LOG_BYTES:
                return
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            kept = lines[-KEEP_LINES:]
            self.stream.close()
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(kept)
            self.stream = self._open()
        except OSError:
            pass


_configured = False


def configure_logging(level: int = logging.INFO) -> None:
    global _configured
    if _configured:
        return
    root = logging.getLogger("stopframe")
    root.setLevel(level)

    handler = _TrimmingFileHandler(log_file(), encoding="utf-8")
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    root.addHandler(handler)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(_LOG_FORMAT))
    root.addHandler(console)

    _configured = True


def get_logger(name: str) -> Logger:
    configure_logging()
    return logging.getLogger(f"stopframe.{name}")


def log_ui_action(logger: Logger, control: str, detail: str = "") -> None:
    """Log a user-initiated UI action, e.g. a button press."""
    msg = f"UI action: {control}"
    if detail:
        msg += f" ({detail})"
    logger.info(msg)


def log_engine_start(logger: Logger, engine: str, detail: str = "") -> None:
    msg = f"Engine start: {engine}"
    if detail:
        msg += f" ({detail})"
    logger.info(msg)


def log_engine_result(logger: Logger, engine: str, result: str, detail: str = "") -> None:
    msg = f"Engine result: {engine} -> {result}"
    if detail:
        msg += f" ({detail})"
    logger.info(msg)


def log_error(logger: Logger, where: str, error: BaseException) -> None:
    logger.error(f"Error in {where}: {error!r}", exc_info=True)
