"""
Replicate API client for UVM generation.
Calls the saikumarstealth-creator/uvmgenerator model via
the Replicate models predictions API.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import time
import zipfile
from typing import Any, Dict, Optional, Tuple

import httpx

logger = logging.getLogger("replicate_client")

API_BASE = "https://api.replicate.com/v1"
POLL_INTERVAL = 2.0
MAX_POLL_TIME = 600.0


class ReplicateClient:
    def __init__(self):
        self.api_token: Optional[str] = os.environ.get("REPLICATE_API_TOKEN")
        self.model: str = os.environ.get(
            "REPLICATE_MODEL", "saikumarstealth-creator/uvmgenerator"
        )
        self._headers: Optional[Dict[str, str]] = None

    @property
    def available(self) -> bool:
        return bool(self.api_token)

    @property
    def headers(self) -> Dict[str, str]:
        if self._headers is None:
            self._headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            }
        return self._headers

    def _build_payload(self, **kwargs) -> Dict:
        payload = {
            "input": {
                "spec_yaml": kwargs.get("spec_yaml", ""),
                "design_name": kwargs.get("design_name", "uart_top"),
                "protocol": kwargs.get("protocol", "uart"),
                "model_type": kwargs.get("model_type", "v2"),
                "rl_strategy": kwargs.get("rl_strategy", "ucb"),
                "enable_learning": kwargs.get("enable_learning", True),
                "strict_uvm": kwargs.get("strict_uvm", True),
                "max_iterations": kwargs.get("max_iterations", 1),
                "coverage_target": kwargs.get("coverage_target", 90.0),
                "optimize_parameters": kwargs.get("optimize_parameters", True),
            },
        }
        return payload

    async def generate(
        self,
        spec_yaml: str = "",
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

        body = self._build_payload(
            spec_yaml=spec_yaml,
            design_name=design_name,
            protocol=protocol,
            model_type=model_type,
            rl_strategy=rl_strategy,
            enable_learning=enable_learning,
            strict_uvm=strict_uvm,
            max_iterations=max_iterations,
            coverage_target=coverage_target,
            optimize_parameters=optimize_parameters,
        )

        prediction = await self._create_prediction(body)
        prediction = await self._poll_until_done(prediction["id"])

        if prediction["status"] == "failed":
            error = prediction.get("error", "unknown error")
            raise RuntimeError(f"Replicate prediction failed: {error}")

        output = prediction.get("output")
        if not output:
            raise RuntimeError(f"Replicate returned no output (status={prediction['status']})")

        files, metrics = self._extract_zip(output)
        return {"files": files, "metrics": metrics}

    async def _create_prediction(self, body: Dict) -> Dict:
        url = f"{API_BASE}/models/{self.model}/predictions"
        logger.info("Creating prediction: POST %s", url)

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=self.headers, json=body, timeout=30)
            if resp.status_code == 404:
                raise RuntimeError(
                    f"Model '{self.model}' not found on Replicate. "
                    "Make sure you pushed the model with: cog push r8.im/{self.model}"
                )
            resp.raise_for_status()
            return resp.json()

    async def _poll_until_done(self, pred_id: str) -> Dict:
        url = f"{API_BASE}/predictions/{pred_id}"
        start = time.monotonic()

        while True:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=self.headers, timeout=30)
                resp.raise_for_status()
                prediction = resp.json()

            status = prediction["status"]
            logger.info("Prediction %s — status=%s", pred_id, status)

            if status in ("succeeded", "failed", "canceled"):
                return prediction

            if time.monotonic() - start > MAX_POLL_TIME:
                raise RuntimeError(f"Prediction {pred_id} timed out after {MAX_POLL_TIME}s")

            await asyncio.sleep(POLL_INTERVAL)

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
