from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import List, Optional

from src.simulation.base import CoverageBin, SimResult, Simulator


class VcsSimulator(Simulator):
    """Synopsys VCS simulation backend.

    Uses vlogan + vcs + ./simv pipeline.
    Detects VCS at runtime; falls back gracefully if not installed.
    """

    def __init__(
        self,
        work_dir: str = "sim_output",
        vcs_path: str = "vcs",
        vlogan_path: str = "vlogan",
        simv_path: str = "./simv",
        compile_flags: Optional[List[str]] = None,
        run_flags: Optional[List[str]] = None,
    ):
        super().__init__(work_dir)
        self.vcs_path = vcs_path
        self.vlogan_path = vlogan_path
        self.simv_path = simv_path
        self.compile_flags = compile_flags or [
            "-sverilog",
            "+v2k",
            "-full64",
            "-debug_acc+all",
            "-lca",
            "-kdb",
            "-timescale=1ns/1ps",
            "+define+UVM_NO_DPI",
            "+define+UVM_NO_RELNOTES",
        ]
        self.run_flags = run_flags or [
            "-l vcs_sim.log",
            "-cm line+cond+tgl+assert",
            "-cm_name test",
            "-cm_dir coverage.vdb",
        ]

    def _check_available(self) -> bool:
        try:
            subprocess.run([self.vcs_path, "-ID"], capture_output=True, timeout=10)
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
                errors=["VCS not found — install Synopsys VCS or use stub simulator"],
                log_output="",
            )

        Path(self.work_dir).mkdir(parents=True, exist_ok=True)
        work_dir = Path(self.work_dir).resolve()

        # Write file list
        flist_path = work_dir / "vcs_files.f"
        flist_path.write_text(
            "\n".join(str(Path(f).resolve()) for f in files if Path(f).exists()),
            encoding="utf-8",
        )

        plusargs_str = " ".join(
            f"+define+{a.removeprefix('+')}" for a in (plusargs or [])
        )

        try:
            # Step 1: Analyze with vlogan
            vlogan_cmd = [
                self.vlogan_path,
                "-sverilog",
                "-full64",
                "-ntb_opts",
                "uvm-1.2",
                "-f",
                str(flist_path),
            ]
            vlogan_result = subprocess.run(
                vlogan_cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(work_dir),
            )
            if vlogan_result.returncode != 0:
                return SimResult(
                    passed=False,
                    errors=[
                        f"vlogan analysis failed:\n{vlogan_result.stderr[:2000]}"
                    ],
                    log_output=vlogan_result.stdout + "\n" + vlogan_result.stderr,
                )

            # Step 2: Elaborate with vcs
            vcs_cmd = [
                self.vcs_path,
                "-full64",
                "-debug_acc+all",
                "-lca",
                "-kdb",
                "-timescale=1ns/1ps",
                "-ntb_opts",
                "uvm-1.2",
                "-top",
                top,
                "-o",
                "simv",
                plusargs_str,
            ]
            vcs_result = subprocess.run(
                vcs_cmd,
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(work_dir),
            )
            if vcs_result.returncode != 0:
                return SimResult(
                    passed=False,
                    errors=[
                        f"VCS elaboration failed:\n{vcs_result.stderr[:2000]}"
                    ],
                    log_output=vcs_result.stdout + "\n" + vcs_result.stderr,
                )

            # Step 3: Run simulation
            simv_path = work_dir / "simv"
            run_cmd = [
                str(simv_path),
                "-cm",
                "line+cond+tgl+assert",
                "-cm_name",
                "test",
                "-l",
                "vcs_sim.log",
                "+UVM_NO_RELNOTES",
            ] + (plusargs or [])
            sim_result = subprocess.run(
                run_cmd,
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(work_dir),
            )
            log = sim_result.stdout + "\n" + sim_result.stderr
            return self.parse_coverage(log)

        except subprocess.TimeoutExpired:
            return SimResult(
                passed=False,
                errors=["VCS simulation timed out (>600s)"],
                log_output="",
            )
        except Exception as e:
            return SimResult(
                passed=False, errors=[f"VCS simulation error: {e}"], log_output=""
            )

    def parse_coverage(self, log: str) -> SimResult:
        bins = []
        errors = []
        passed = True

        # Parse VCS coverage report lines: "COVERAGE: <name> <hit>/<goal>"
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

        # Parse UVM errors/fatals
        err_pattern = re.compile(r"UVM_(ERROR|FATAL)\s*:\s*(.*)")
        for match in err_pattern.finditer(log):
            errors.append(match.group(2).strip())
            passed = False

        # Scoreboard result
        if "SCOREBOARD: FAIL" in log:
            passed = False
            errors.append("Scoreboard mismatch detected")

        # UVM summary
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
