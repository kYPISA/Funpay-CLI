from __future__ import annotations
import os
from datetime import datetime
from .settings import load_settings, get_base_dir


def get_log_path() -> str:
    return os.path.join(get_base_dir(), "kypisa.log")


def log(message: str) -> None:
    cfg = load_settings()
    if not cfg.get("log_enabled", True):
        return
    path = get_log_path()
    try:
        with open(path, "a", encoding="utf-8") as f:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{ts}] {message}\n")
    except Exception:
        pass
