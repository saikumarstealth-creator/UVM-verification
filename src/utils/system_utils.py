# src/utils/system_utils.py — System-level utilities

from __future__ import annotations

import os
import platform
import subprocess
from typing import List, Optional


def detect_simulator() -> Optional[str]:
    """Detect available UVM simulator on PATH."""
    sims = ["vcs", "xrun", "xsim", "vsim", "vlogan"]
    for sim in sims:
        if _which(sim):
            return sim
    return None


def _which(name: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["where", name] if platform.system() == "Windows" else ["which", name],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None
