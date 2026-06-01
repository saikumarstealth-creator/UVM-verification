"""
Replicate API client for UVM generation.
Calls the saikumarstealth-creator/uvm-generator deployment
and returns generated files.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import zipfile
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("replicate_client")


class ReplicateClient:
    def __init__(self):
        self.api_token: Optional[str] = os.environ.get("REPLICATE_API_TOKEN")
        self.deployment: str = os.environ.get(
            "REPLICATE_DEPLOYMENT", "saikumarstealth-creator/uvm-generator"
        )
        self._client = None

    @property
    def available(self) -> bool:
        return bool(self.api_token)

    async def _get_client(self):
        if self._client is None:
            import replicate

            self._client = replicate.Client(api_token=self.api_token)
        return self._client

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
        """Call Replicate deployment and return generated files + metrics."""
        if not self.available:
            raise RuntimeError(
                "REPLICATE_API_TOKEN not set. "
                "Add it to your Hugging Face Space secrets or env."
            )

        client = await self._get_client()

        logger.info(
            "Calling Replicate deployment %s with protocol=%s model=%s",
            self.deployment, protocol, model_type,
        )

        prediction = await asyncio.to_thread(
            client.deployments.predictions.create,
            deployment=self.deployment,
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

        logger.info("Replicate prediction %s — status=%s", prediction.id, prediction.status)

        if prediction.status == "failed":
            error_detail = getattr(prediction, "error", "unknown error")
            raise RuntimeError(f"Replicate prediction failed: {error_detail}")

        output_url = getattr(prediction, "output", None)
        if not output_url:
            raise RuntimeError(
                f"Replicate returned no output (status={prediction.status})"
            )

        files, metrics = self._extract_zip(output_url)
        return {"files": files, "metrics": metrics}

    def _extract_zip(self, url: str) -> Tuple[Dict[str, str], Dict[str, Any]]:
        """Download and extract the .zip from Replicate output."""
        import httpx

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
        """Quick coverage prediction only (lightweight)."""
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


# Global singleton
replicate_client = ReplicateClient()
