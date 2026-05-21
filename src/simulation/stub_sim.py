from __future__ import annotations

import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.simulation.base import CoverageBin, SimResult, Simulator


PROTOCOL_BUS_SIGNALS = {
    "axi4lite": {"awvalid", "awready", "awaddr", "wvalid", "wready", "wdata",
                 "bvalid", "bready", "bresp", "arvalid", "arready", "araddr",
                 "rvalid", "rready", "rdata", "rresp"},
    "apb": {"psel", "penable", "paddr", "pwrite", "pwdata", "prdata", "pready", "pslverr"},
    "wishbone": {"wb_cyc", "wb_stb", "wb_we", "wb_addr", "wb_data_o", "wb_data_i", "wb_ack"},
    "uart": {"tx", "rx", "wb_cyc", "wb_stb", "wb_we", "wb_addr", "wb_data_o", "wb_ack"},
    "spi": {"mosi", "miso", "sclk", "ss_n", "wb_cyc", "wb_stb", "wb_we", "wb_addr"},
    "i2c": {"scl", "sda", "wb_cyc", "wb_stb", "wb_we", "wb_addr"},
}


class StubSimulator(Simulator):
    def __init__(self, work_dir: str = "sim_output", seed: int = 42):
        super().__init__(work_dir)
        self.rng = random.Random(seed)
        self.history: List[Dict[str, Any]] = []

    def run(self, files: List[str], top: str = "testbench",
            plusargs: Optional[List[str]] = None) -> SimResult:
        # Extract seed from plusargs
        seed = 42
        if plusargs:
            for pa in plusargs:
                if "+seed=" in pa:
                    try:
                        seed = int(pa.split("=")[1])
                    except (IndexError, ValueError):
                        pass
        self.rng = random.Random(seed)

        all_files = self._collect_all_files(files)
        bins = self._discover_bins(all_files)
        covered = self._simulate_coverage(bins, all_files)
        pct = (sum(1 for b in covered if b.covered) / len(covered) * 100) if covered else 0
        return SimResult(
            passed=pct >= 60,
            total_bins=len(covered),
            covered_bins=sum(1 for b in covered if b.covered),
            bins=covered,
            errors=[],
            log_output=self._format_log(covered, pct),
            seed=seed,
        )

    def _collect_all_files(self, files: List[str]) -> List[str]:
        collected = []
        seen = set()
        for f in files:
            p = Path(f)
            if not p.exists():
                continue
            resolved = str(p.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            collected.append(resolved)
            # Also scan subdirectories (sequences/, rtl/)
            for subdir in p.parent.glob("**/*"):
                if subdir.is_file() and subdir.suffix in (".sv", ".v", ".vh"):
                    r = str(subdir.resolve())
                    if r not in seen:
                        seen.add(r)
                        collected.append(r)
        return collected

    def _discover_bins(self, files: List[str]) -> List[CoverageBin]:
        bins_dict: Dict[str, CoverageBin] = {}
        all_text = "\n".join(
            Path(f).read_text(errors="replace") for f in files if Path(f).exists()
        )

        # Parse coverpoint bins from generated coverage_collector
        for m in re.finditer(r'coverpoint\s+(\w+)\s*\{([^}]+)\}', all_text):
            cp_name = m.group(1)
            body = m.group(2)
            for bm in re.finditer(r'bins\s+(\w+)\s*=', body):
                key = f"{cp_name}.{bm.group(1)}"
                if key not in bins_dict:
                    bins_dict[key] = CoverageBin(name=key, hit_count=0, goal=1)

        # Parse cross coverage
        for m in re.finditer(r'cross\s+(\w+)\s*,\s*(\w+)\s*\{', all_text):
            key = f"cross_{m.group(1)}x{m.group(2)}"
            if key not in bins_dict:
                bins_dict[key] = CoverageBin(name=key, hit_count=0, goal=1)

        # Also parse protocol-specific SVAs
        for m in re.finditer(r'cover property\s*\([^)]*\)', all_text):
            key = f"sva_cover_{len(bins_dict)}"
            if key not in bins_dict:
                bins_dict[key] = CoverageBin(name=key, hit_count=0, goal=1)

        if not bins_dict:
            for addr in range(8):
                bins_dict[f"bus_cg.ADDR.regs[{addr}]"] = CoverageBin(
                    f"bus_cg.ADDR.regs[{addr}]", 0, 1)
                bins_dict[f"cross_ADRxDIR.addr{addr}_read"] = CoverageBin(
                    f"cross_ADRxDIR.addr{addr}_read", 0, 1)
                bins_dict[f"cross_ADRxDIR.addr{addr}_write"] = CoverageBin(
                    f"cross_ADRxDIR.addr{addr}_write", 0, 1)
            bins_dict["bus_cg.DIR.read"] = CoverageBin("bus_cg.DIR.read", 0, 1)
            bins_dict["bus_cg.DIR.write"] = CoverageBin("bus_cg.DIR.write", 0, 1)

        return list(bins_dict.values())

    def _is_register_hit(self, addr: int, all_text: str) -> bool:
        patterns = [
            f"reg_addr = 3'h{addr:x}",
            f"reg_addr=3'h{addr:x}",
            f"wb_addr = 3'h{addr:x}",
            f"addr={addr}",
            f"target_addr=3'h{addr:x}",
        ]
        return any(p in all_text for p in patterns)

    def _simulate_coverage(self, bins: List[CoverageBin],
                           files: List[str]) -> List[CoverageBin]:
        if not files:
            return bins

        all_text = "\n".join(
            Path(f).read_text(errors="replace") for f in files if Path(f).exists()
        )

        has_write = "item.we = 1" in all_text or "wb_we = 1" in all_text or "pwrite = 1" in all_text
        has_read = "item.we = 0" in all_text or "wb_we = 0" in all_text or "pwrite = 0" in all_text
        has_any_txn = bool(re.search(r'reg_addr\s*=|wb_addr\s*=|paddr\s*=', all_text))

        result = []
        for b in bins:
            nl = b.name.lower()
            hit = 0
            goal = b.goal

            if "addr" in nl or "regs[" in nl:
                for a in range(8):
                    if self._is_register_hit(a, all_text):
                        if f"[{a}]" in b.name or f"regs[{a}]" in nl:
                            hit += 1
                        if f"addr{a}" in nl:
                            hit += 1
                if hit == 0 and has_any_txn:
                    for a in range(8):
                        if f"regs[{a}]" in nl and any(
                            f"for (int a = {a}" in all_text or f"a == {a}" in all_text
                            or f"a={a}" in all_text
                            for _ in [0]
                        ):
                            hit += 1

            elif "read" in nl and ("dir" in nl or "direction" in nl):
                hit = 1 if has_read else 0
            elif "write" in nl and ("dir" in nl or "direction" in nl):
                hit = 1 if has_write else 0

            elif "cross" in nl:
                if has_write and has_read:
                    hit = sum(1 for a in range(8) if self._is_register_hit(a, all_text))
                    hit = min(hit, 8)
                elif has_write or has_read:
                    hit = sum(1 for a in range(8) if self._is_register_hit(a, all_text))

            elif "zero" in nl:
                hit = 1 if "8'h00" in all_text else 0
            elif "ones" in nl:
                hit = 1 if "8'hFF" in all_text else 0
            elif "pattern" in nl or "data" in nl:
                hit = 1 if re.search(r"8'h[0-9A-Fa-f]{2}", all_text) else 0

            elif "sva" in nl:
                hit = 1 if "assert property" in all_text or "cover property" in all_text else 0

            elif "serial" in nl or "uart" in nl or "tx" in nl:
                tx_present = "uart_tx" in all_text or ".tx" in all_text
                rx_present = "uart_rx" in all_text or ".rx" in all_text
                hit = (1 if tx_present else 0) + (1 if rx_present else 0)
                goal = 2

            elif "spi" in nl or "sclk" in nl or "mosi" in nl:
                hit = 1 if any(s in all_text for s in ["mosi", "miso", "sclk", "ss_n"]) else 0

            elif "i2c" in nl or "scl" in nl or "sda" in nl:
                hit = 1 if "scl" in all_text or "sda" in all_text else 0

            else:
                hit = 1 if has_any_txn else 0
                goal = 1

            result.append(CoverageBin(name=b.name, hit_count=hit, goal=goal))

        return result

    def _format_log(self, bins: List[CoverageBin], pct: float) -> str:
        lines = [
            "--- Simulation Start ---",
            "UVM_INFO @ 0: reporter [RNTST] Running test ...",
        ]
        for b in bins:
            status = "HIT" if b.covered else "MISS"
            lines.append(f"COVERAGE: {b.name} {b.hit_count}/{b.goal} [{status}]")
        covered = sum(1 for b in bins if b.covered)
        total = len(bins)
        lines.append(f"--- Coverage: {covered}/{total} ({pct:.1f}%) ---")
        if covered == total:
            lines.append("SCOREBOARD: PASS")
            lines.append("UVM Report Summary: Errors: 0")
        else:
            lines.append("SCOREBOARD: PARTIAL")
            lines.append(f"UVM Report Summary: Warnings: {total - covered}")
        return "\n".join(lines)

    def name(self) -> str:
        return "StubSimulator"
