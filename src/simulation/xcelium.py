from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from src.simulation.base import CoverageBin, SimResult, Simulator


class XceliumSimulator(Simulator):
    """Cadence Xcelium simulation backend.

    Uses xrun for compile+elaborate+simulate in one step.
    Detects xrun at runtime; falls back gracefully if not installed.
    """

    def __init__(
        self,
        work_dir: str = "sim_output",
        xrun_path: str = "xrun",
        compile_flags: Optional[List[str]] = None,
        run_flags: Optional[List[str]] = None,
    ):
        super().__init__(work_dir)
        self.xrun_path = xrun_path
        self.compile_flags = compile_flags or [
            "-64bit",
            "-sv",
            "-access",
            "+rwc",
            "-coverage",
            "all",
            "-nowarn",
            "NONPORTTOPCONN",
        ]
        self.run_flags = run_flags or [
            "-coverage",
            "all",
            "-exit",
        ]

    def run(
        self,
        files: List[str],
        top: str = "testbench",
        plusargs: Optional[List[str]] = None,
    ) -> SimResult:
        work_dir = Path(self.work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)

        # Check if xrun is available
        try:
            subprocess.run(
                [self.xrun_path, "-version"],
                capture_output=True,
                timeout=10,
                check=True,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
            return SimResult(
                passed=False,
                errors=[f"Xcelium ({self.xrun_path}) not found or not executable"],
            )

        # Write file list
        flist_path = work_dir / "xrun_files.f"
        flist_path.write_text("\n".join(str(f) for f in files), encoding="utf-8")

        plusargs = plusargs or []
        seed = None
        for pa in plusargs:
            if "+seed=" in pa:
                seed = pa.split("=")[1]
                break

        xrun_cmd = [
            self.xrun_path,
            *self.compile_flags,
            "-f",
            str(flist_path),
            "-top",
            top,
            "-l",
            str(work_dir / "xrun_sim.log"),
        ]
        if seed:
            xrun_cmd += [f"+ntb_random_seed={seed}"]
        xrun_cmd += self.run_flags

        try:
            result = subprocess.run(
                xrun_cmd,
                cwd=str(work_dir),
                capture_output=True,
                timeout=600,
            )
            log = result.stdout + "\n" + result.stderr
            log_file = work_dir / "xrun_sim.log"
            if log_file.exists():
                log = log_file.read_text(encoding="utf-8", errors="replace")

            if result.returncode != 0:
                errors = self._parse_errors(log)
                return SimResult(
                    passed=False,
                    errors=errors or ["Xcelium simulation failed"],
                    log_output=log[:5000],
                )

            return self.parse_coverage(log)

        except subprocess.TimeoutExpired:
            return SimResult(
                passed=False,
                errors=["Xcelium simulation timed out (>600s)"],
            )
        except Exception as e:
            return SimResult(
                passed=False,
                errors=[f"Xcelium simulation error: {e}"],
            )

    def parse_coverage(self, log: str) -> SimResult:
        bins: List[CoverageBin] = []
        passed = True
        errors: List[str] = []

        xrun_cov = re.compile(
            r"COVERAGE:\s+(\S+)\s+(\d+)/(\d+)\s+\[(HIT|MISS)\]"
        )
        for match in xrun_cov.finditer(log):
            name = match.group(1)
            hit = int(match.group(2))
            goal = int(match.group(3))
            bins.append(CoverageBin(name=name, hit_count=hit, goal=goal))
            if hit < goal:
                passed = False

        # Xcelium coverage summary
        total_cov = re.compile(
            r"(Line|Toggle|Functional|Assertion)\s+Coverage:\s+([\d.]+)%"
        )
        for match in total_cov.finditer(log):
            cov_type = match.group(1)
            pct = float(match.group(2))
            bins.append(CoverageBin(
                name=f"xrun_{cov_type.lower()}_total",
                hit_count=int(pct),
                goal=100,
            ))
            if pct < 100:
                passed = False

        # Error extraction
        err_patterns = re.compile(
            r"\*[WE]|(Error|Warning|Fatal):\s*(.*)", re.IGNORECASE
        )
        for match in err_patterns.finditer(log):
            err_text = match.group(0).strip()
            if len(err_text) > 20:
                errors.append(err_text[:200])

        if not bins:
            # No structured coverage; check for pass/fail
            if re.search(r"TEST.*PASSED|UVM.*PASSED", log, re.IGNORECASE):
                passed = True
            elif re.search(r"TEST.*FAILED|UVM.*FAILED|#\s*FAIL", log, re.IGNORECASE):
                passed = False
                errors.append("Simulation FAILED (no structured coverage found)")

        return SimResult(
            passed=passed,
            total_bins=len(bins),
            covered_bins=sum(1 for b in bins if b.covered),
            bins=bins,
            errors=errors[:20],
            log_output=log[:5000],
        )

    def _parse_errors(self, log: str) -> List[str]:
        errors = []
        for line in log.split("\n"):
            if any(kw in line for kw in ["*E", "*W", "Error:", "Fatal:", "FAIL"]):
                errors.append(line.strip()[:200])
        return errors[:20]
