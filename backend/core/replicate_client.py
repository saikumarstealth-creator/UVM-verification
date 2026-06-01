"""
Replicate API client for UVM generation.
Calls the saikumarstealth-creator/uvmgenerator model via
replicate.run() and returns generated files.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import zipfile
from typing import Any, Dict, Optional, Tuple

import httpx
import replicate

logger = logging.getLogger("replicate_client")


class ReplicateClient:
    def __init__(self):
        self.api_token: Optional[str] = os.environ.get("REPLICATE_API_TOKEN")
        self.model: str = os.environ.get(
            "REPLICATE_MODEL", "saikumarstealth-creator/uvmgenerator"
        )

    @property
    def available(self) -> bool:
        return bool(self.api_token)

    async def generate(
        self,
        spec_yaml: str,
        design_name: str = "uart_top",
        protocol: str = "uart",
        model_type: str = "v2",
        rl_strategy: str = "ucb",
        enable_learning: bool = True,
        strict_uvm: bool = True,
        max_iterations: int = 1,
        coverage_target: float = 90.0,
        optimize_parameters: bool = True,
    ) -> Dict[str, Any]:
        if not self.available:
            raise RuntimeError(
                "REPLICATE_API_TOKEN not set. "
                "Add it to your Hugging Face Space secrets or env."
            )

        os.environ["REPLICATE_API_TOKEN"] = self.api_token

        logger.info("Calling replicate.run(%s) ...", self.model)

        try:
            output = await asyncio.to_thread(
                replicate.run,
                self.model,
                input={
                    "spec_yaml": spec_yaml,
                    "design_name": design_name,
                    "protocol": protocol,
                    "model_type": model_type,
                    "rl_strategy": rl_strategy,
                    "enable_learning": enable_learning,
                    "strict_uvm": strict_uvm,
                    "max_iterations": max_iterations,
                    "coverage_target": coverage_target,
                    "optimize_parameters": optimize_parameters,
                },
            )
        except replicate.exceptions.ModelNotFound as e:
            raise RuntimeError(
                f"Model '{self.model}' not found on Replicate. "
                "Make sure you pushed the model with: cog push r8.im/{self.model}"
            ) from e

        logger.info("Replicate run completed — output type=%s", type(output).__name__)

        if not output:
            raise RuntimeError("Replicate returned no output")

        files, metrics = self._extract_zip(output)
        return {"files": files, "metrics": metrics}

    def _extract_zip(self, url: str) -> Tuple[Dict[str, str], Dict[str, Any]]:
        logger.info("Downloading output from %s", url)
        resp = httpx.get(url, follow_redirects=True, timeout=120)
        resp.raise_for_status()

        files: Dict[str, str] = {}
        metrics: Dict[str, Any] = {}

        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            for name in zf.namelist():
                if name.endswith("/"):
                    continue
                content = zf.read(name).decode("utf-8", errors="replace")
                if name == "generation_report.json":
                    try:
                        metrics = json.loads(content)
                    except json.JSONDecodeError as e:
                        logger.warning("Failed to parse report: %s", e)
                elif name == "summary.txt":
                    pass
                else:
                    files[name] = content

        return files, metrics

    async def get_coverage_prediction(
        self,
        spec_yaml: str,
        design_name: str = "uart_top",
        protocol: str = "uart",
    ) -> Dict[str, Any]:
        try:
            result = await self.generate(
                spec_yaml=spec_yaml,
                design_name=design_name,
                protocol=protocol,
                model_type="v2",
                max_iterations=1,
                optimize_parameters=True,
            )
            report = result.get("metrics", {})
            cov = report.get("coverage_prediction", report.get("coverage", {}))
            if isinstance(cov, dict):
                return cov
            return {"expected": 0, "gaps": []}
        except Exception as e:
            logger.warning("Coverage prediction failed: %s", e)
            return {"expected": 0, "gaps": [], "error": str(e)}


replicate_client = ReplicateClient()
