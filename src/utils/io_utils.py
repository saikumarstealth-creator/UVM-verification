# src/utils/io_utils.py — I/O helpers

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import yaml


def read_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def read_json(path: str) -> Dict[str, Any]:
    return json.loads(Path(path).read_text())


def write_json(path: str, data: Any, indent: int = 2) -> None:
    Path(path).write_text(json.dumps(data, indent=indent))


def ensure_dir(path: str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
