from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import List, Optional

from src.simulation.base import CoverageBin, SimResult, Simulator


class QuestaSimulator(Simulator):
    """Siemens EDA (Mentor) Questa simulation backend.

    Uses vlib + vlog + vsim pipeline.
    Falls back gracefully if Questa is not installed.
    """

    def __init__(
        self,
        work_dir: str = "sim_output",
        vlog_path: str = "vlog",
        vsim_path: str = "vsim",
        vlib_path: str = "vlib",
        compile_flags: Optional[List[str]] = None,
        run_flags: Optional[List[str]] = None,
    ):
        super().__init__(work_dir)
        self.vlog_path = vlog_path
        self.vsim_path = vsim_path
        self.vlib_path = vlib_path
        self.compile_flags = compile_flags or [
            "-sv",
            "-nocovercells",
            "-timescale",
            "1ns/1ps",
            "+define+UVM_NO_DPI",
            "+define+UVM_NO_RELNOTES",
        ]
        self.run_flags = run_flags or [
            "-c",
            "-do",
            "run -all; quit",
            "-coverage",
            "-voptargs=+acc",
        ]

    def _check_available(self) -> bool:
        try:
            subprocess.run([self.vlog_path, "-version"], capture_output=True, timeout=10)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def run(
        self,
        files: List[str],
        top: str = "testbench",
        plusargs: Optional[List[str]] = None,
    ) -> SimResult:
        available = self._check_available()
        if not available:
            return SimResult(
                passed=False,
                errors=[
                    "vlog not found — install Siemens Questa or use stub simulator"
                ],
                log_output="",
            )

        Path(self.work_dir).mkdir(parents=True, exist_ok=True)
        work_dir = Path(self.work_dir).resolve()
        lib_dir = work_dir / "work"

        plusargs_list = plusargs or []
        plusargs_str = " ".join(f"+{a.removeprefix('+')}" for a in plusargs_list)

        try:
            # Step 1: Create work library
            vlib_result = subprocess.run(
                [self.vlib_path, str(lib_dir)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(work_dir),
            )
            if vlib_result.returncode != 0:
                # Library may already exist — ignore
                pass

            # Step 2: Compile with vlog
            compile_cmd = (
                [self.vlog_path]
                + self.compile_flags
                + ["-work", str(lib_dir)]
                + [str(Path(f).resolve()) for f in files if Path(f).exists()]
            )
            vlog_result = subprocess.run(
                compile_cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(work_dir),
            )
            if vlog_result.returncode != 0:
                # Check for compilation errors vs warnings
                stderr = vlog_result.stderr
                has_errors = bool(
                    re.search(r"\*\*(Error|Fatal)", stderr, re.IGNORECASE)
                )
                if has_errors:
                    return SimResult(
                        passed=False,
                        errors=[
                            f"vlog compilation failed:\n{stderr[:2000]}"
                        ],
                        log_output=vlog_result.stdout + "\n" + stderr,
                    )

            # Step 3: Run with vsim
            run_cmd = [
                self.vsim_path,
                "-c",
                "-coverage",
                "-voptargs=+acc",
                "-do",
                f"run -all; quit",
                "-l",
                "questa_sim.log",
                "-sv_lib",
                "uvm_dpi",
                f"+UVM_NO_RELNOTES",
                f"{plusargs_str}",
                "-work",
                str(lib_dir),
                top,
            ]
            # Filter empty args
            run_cmd = [a for a in run_cmd if a.strip()]

            sim_result = subprocess.run(
                run_cmd,
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(work_dir),
            )
            log = sim_result.stdout + "\n" + sim_result.stderr

            # Also read log file for full output
            log_file = work_dir / "questa_sim.log"
            if log_file.exists():
                log += "\n" + log_file.read_text(encoding="utf-8", errors="replace")

            return self.parse_coverage(log)

        except subprocess.TimeoutExpired:
            return SimResult(
                passed=False,
                errors=["Questa simulation timed out (>600s)"],
                log_output="",
            )
        except Exception as e:
            return SimResult(
                passed=False,
                errors=[f"Questa simulation error: {e}"],
                log_output="",
            )

    def parse_coverage(self, log: str) -> SimResult:
        bins = []
        errors = []
        passed = True

        # Parse Questa coverage: "# COVERAGE: <name> <hit>/<goal>"
        cov_pattern = re.compile(
            r"COVERAGE:\s+(\S+)\s+(\d+)/(\d+)", re.MULTILINE
        )
        for match in cov_pattern.finditer(log):
            name, hits, goal = (
                match.group(1),
                int(match.group(2)),
                int(match.group(3)),
            )
            bins.append(CoverageBin(name=name, hit_count=hits, goal=goal))

        # Parse Questa-style coverage lines from -coverage output
        # Format: "NAME hit_count goal %covered"
        questa_cov = re.compile(
            r"^\s*(\S+)\s+(\d+)\s+(\d+)\s+\d+\.\d+%\s*$", re.MULTILINE
        )
        for match in questa_cov.finditer(log):
            name = match.group(1)
            hits = int(match.group(2))
            goal = int(match.group(3))
            # Deduplicate
            if not any(b.name == name for b in bins):
                bins.append(CoverageBin(name=name, hit_count=hits, goal=goal))

        # Parse UVM errors
        err_pattern = re.compile(r"UVM_(ERROR|FATAL)\s*:\s*(.*)")
        for match in err_pattern.finditer(log):
            errors.append(match.group(2).strip())
            passed = False

        # Scoreboard
        if "SCOREBOARD: FAIL" in log:
            passed = False
            errors.append("Scoreboard mismatch detected")

        # Questa error summary
        for pattern in [
            r"Errors:\s*(\d+)",
            r"# \*\* Error: (\d+)",
        ]:
            fm = re.search(pattern, log)
            if fm and int(fm.group(1)) > 0:
                passed = False

        # UVM summary
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
            log_output=log,
        )
