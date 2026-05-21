# src/generation/renderer.py — Low-level template renderer (engine delegates to this via model)

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader, TemplateNotFound


class TemplateRenderer:
    """Low-level Jinja2 rendering utility used by TemplateModel."""

    def __init__(self, templates_dir: str):
        self.templates_dir = Path(templates_dir)
        if not self.templates_dir.exists():
            raise FileNotFoundError(f"Templates directory not found: {templates_dir}")
        self.env = Environment(loader=FileSystemLoader(str(self.templates_dir)))

    def render(self, template_name: str, context: Dict[str, Any]) -> str:
        try:
            tmpl = self.env.get_template(template_name)
            return tmpl.render(**context)
        except TemplateNotFound:
            raise FileNotFoundError(f"Template not found: {template_name}")
