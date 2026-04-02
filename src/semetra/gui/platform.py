"""Platform-specific utilities for GUI operations."""
from __future__ import annotations

import subprocess as _subprocess
from typing import Optional


# ── WSL-aware URL opener ───────────────────────────────────────────────────
# On WSL, QDesktopServices.openUrl() calls xdg-open which fails when no
# Linux browser is installed.  Detect WSL once at import time and use
# cmd.exe /c start as a fallback so links open in the Windows browser.
def _is_running_on_wsl() -> bool:
    try:
        with open("/proc/version") as _f:
            return "microsoft" in _f.read().lower()
    except Exception:
        return False


_ON_WSL: bool = _is_running_on_wsl()


def _open_url_safe(url: str) -> None:
    """Open *url* in the system browser.

    On WSL the standard QDesktopServices path goes through xdg-open which
    usually fails because no Linux browser is configured.  We detect WSL and
    delegate to ``cmd.exe /c start`` instead, which opens the URL in whatever
    Windows browser the user has set as default.
    """
    from PySide6.QtGui import QDesktopServices  # local import — gui module only
    from PySide6.QtCore import QUrl as _QUrl
    if _ON_WSL:
        try:
            # cmd.exe expects an empty first arg when the target contains query strings
            _subprocess.Popen(["cmd.exe", "/c", "start", "", url])
            return
        except Exception:
            pass  # fall through to Qt default
    QDesktopServices.openUrl(_QUrl(url))


# Alias for convenience
_open_url = _open_url_safe
