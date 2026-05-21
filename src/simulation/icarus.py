from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from src.simulation.base import CoverageBin, SimResult, Simulator


class IcarusSimulator(Simulator):
    def __init__(self, work_dir: str = "sim_output", iverilog_path: str = "iverilog",
                 vvp_path: str = "vvp"):
        super().__init__(work_dir)
        self.iverilog_path = iverilog_path
        self.vvp_path = vvp_path

    def _check_available(self) -> bool:
        try:
            subprocess.run([self.iverilog_path, "-V"], capture_output=True, timeout=5)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def run(self, files: List[str], top: str = "testbench",
            plusargs: Optional[List[str]] = None) -> SimResult:
        available = self._check_available()
        if not available:
            return SimResult(
                passed=False,
                errors=["iverilog not found — install Icarus Verilog or use stub simulator"],
                log_output=""
            )

        Path(self.work_dir).mkdir(parents=True, exist_ok=True)
        vvp_out = os.path.join(self.work_dir, "sim.vvp")

        plusargs_list = plusargs or []
        plusargs_str = " ".join(f"-P{top}.{a}" for a in plusargs_list)

        compile_cmd = (
            f"{self.iverilog_path} -g2012 -o {vvp_out} "
            f"{' '.join(files)} "
            f"{plusargs_str}"
        )
        try:
            result = subprocess.run(compile_cmd, shell=True, capture_output=True,
                                    text=True, timeout=120)
            if result.returncode != 0:
                return SimResult(
                    passed=False,
                    errors=[f"iverilog compilation failed:\n{result.stderr}"],
                    log_output=result.stdout + "\n" + result.stderr
                )

            run_cmd = f"{self.vvp_path} {vvp_out} +UVM_NO_RELNOTES"
            sim_result = subprocess.run(run_cmd, shell=True, capture_output=True,
                                         text=True, timeout=300)
            log = sim_result.stdout + "\n" + sim_result.stderr
            return self.parse_coverage(log)

        except subprocess.TimeoutExpired:
            return SimResult(
                passed=False,
                errors=["Simulation timed out (>300s)"],
                log_output=""
            )
        except Exception as e:
            return SimResult(
                passed=False,
                errors=[f"Simulation error: {e}"],
                log_output=""
            )

    def parse_coverage(self, log: str) -> SimResult:
        bins = []
        errors = []
        passed = True

        # Parse UVM coverage output: "COVERAGE: <name> <hit_count>/<goal>"
        cov_pattern = re.compile(
            r"COVERAGE:\s+(\S+)\s+(\d+)/(\d+)", re.MULTILINE
        )
        for match in cov_pattern.finditer(log):
            name, hits, goal = match.group(1), int(match.group(2)), int(match.group(3))
            bins.append(CoverageBin(name=name, hit_count=hits, goal=goal))

        # Parse UVM errors
        err_pattern = re.compile(r"UVM_(ERROR|FATAL)\s*:\s*(.*)")
        for match in err_pattern.finditer(log):
            errors.append(match.group(2).strip())
            passed = False

        # Parse scoreboard result
        if "SCOREBOARD: PASS" in log:
            pass
        elif "SCOREBOARD: FAIL" in log:
            passed = False
            errors.append("Scoreboard mismatch detected")

        # Test pass/fail from UVM summary
        if "UVM Report Summary" in log or "--- UVM Summary ---" in log:
            fail_match = re.search(r"Errors\s*:\s*(\d+)", log)
            if fail_match and int(fail_match.group(1)) > 0:
                passed = False

        covered = sum(1 for b in bins if b.covered)
        return SimResult(
            passed=passed,
            total_bins=len(bins),
            covered_bins=covered,
            bins=bins,
            errors=errors,
            log_output=log
        )
