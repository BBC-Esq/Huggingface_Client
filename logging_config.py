from __future__ import annotations
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_DIR = Path(__file__).resolve().parent / "logs"
_MAX_LOG_FILES = 10
_MAX_BYTES = 2 * 1024 * 1024


def setup_logging() -> None:
    _LOG_DIR.mkdir(exist_ok=True)
    _cleanup_old_logs()

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = _LOG_DIR / f"hfhub_{timestamp}.log"

    handler = RotatingFileHandler(
        log_file, maxBytes=_MAX_BYTES, backupCount=1, encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)

    logging.getLogger("hf_backend").setLevel(logging.DEBUG)
    logging.getLogger("ui").setLevel(logging.DEBUG)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("huggingface_hub").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def _cleanup_old_logs() -> None:
    logs = sorted(_LOG_DIR.glob("hfhub_*.log"), key=lambda p: p.name)
    while len(logs) > _MAX_LOG_FILES:
        oldest = logs.pop(0)
        try:
            oldest.unlink()
        except OSError:
            pass
