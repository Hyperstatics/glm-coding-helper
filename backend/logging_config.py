"""
Tee-stdout logging for backend + workers.

Call ``setup_logging()`` early in every process (main server, YOLO worker,
OCR worker, and GUI). All ``print()`` calls are automatically written to both
the console *and* ``logs/backend-<timestamp>.log``.

Multiprocessing-safe: each process opens the log file in line-buffered append
mode, so writes are atomic at the line level.
"""

import sys
import threading
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_LOG_DIR = _ROOT / "logs"
_MAX_BYTES = 2 * 1024 * 1024       # 2 MB per log file
_KEEP_FILES = 5                    # keep last 5 rotated backups


class _TeeStdout:
    """Forwards every write to the *original* stdout AND a log file."""

    def __init__(self, log_path: Path) -> None:
        self.stdout = sys.__stdout__          # grab the real stdout *before* we replace it
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        self._file = open(str(log_path), "a", encoding="utf-8", buffering=1)
        self._closed = False
        self._lock = threading.Lock()         # thread-safety within one process

    def write(self, data: str) -> None:
        if self._closed:
            return
        with self._lock:
            try:
                self.stdout.write(data)
            except Exception:
                pass
            try:
                self._file.write(data)
            except Exception:
                pass

    def flush(self) -> None:
        if self._closed:
            return
        with self._lock:
            try:
                self.stdout.flush()
            except Exception:
                pass
            try:
                self._file.flush()
            except Exception:
                pass

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                try:
                    self._file.close()
                except Exception:
                    pass
                self._closed = True

    # -- delegate attrs that the runtime may inspect --------------------
    @property
    def encoding(self):
        return self.stdout.encoding

    def fileno(self):
        return self.stdout.fileno()

    def isatty(self):
        return self.stdout.isatty()


def _rotate_logs() -> None:
    """Remove oldest logs when we have more than _KEEP_FILES."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    existing = sorted(
        [p for p in _LOG_DIR.glob("backend-*.log") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
    )
    while len(existing) > _KEEP_FILES:
        oldest = existing.pop(0)
        try:
            oldest.unlink()
        except Exception:
            pass


def _stamp_log_path(log_path: Path) -> None:
    """Write a one-line header so the log always starts with a timestamp."""
    try:
        with open(str(log_path), "a", encoding="utf-8") as fh:
            fh.write(f"# session {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                     f"  pid={__import__('os').getpid()}\n")
    except Exception:
        pass


def setup_logging(suffix: str = "") -> str:
    """Install tee-stdout and return the absolute path to the log file.

    ``suffix`` is optional (e.g. ``"yolo0"``, ``"ocr3"``) so workers can
    write to their own small sidecar logs for debugging.  When empty the
    main process log is used.

    After calling this, **all** ``print()`` output is automatically mirrored
    to the log file — no other code changes required.
    """
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    _rotate_logs()

    tag = suffix or "main"
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = _LOG_DIR / f"backend-{tag}-{ts}.log"

    _stamp_log_path(log_path)
    sys.stdout = _TeeStdout(log_path)
    print(f"[log] session started → {log_path.name}")
    return str(log_path)
