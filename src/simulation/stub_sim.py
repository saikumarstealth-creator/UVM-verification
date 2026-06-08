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

        # Parse coverpoint bins with nested-brace-safe regex
        for m in re.finditer(r'\bcoverpoint\s+(\w+)', all_text):
            start = m.end()
            depth = 0
            body_start = None
            body_end = None
            for i in range(start, len(all_text)):
                ch = all_text[i]
                if ch == '{':
                    if depth == 0:
                        body_start = i + 1
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0 and body_start is not None:
                        body_end = i
                        break
            if body_start is not None and body_end is not None:
                body = all_text[body_start:body_end]
                cp_name = m.group(1)
                for bm in re.finditer(r'\bbins\s+(\w+)\s*=', body):
                    key = f"{cp_name}.{bm.group(1)}"
                    if key not in bins_dict:
                        bins_dict[key] = CoverageBin(name=key, hit_count=0, goal=1)

        # Parse cross coverage (with or without options block)
        for m in re.finditer(r'\bcross\s+(\w+)\s*,\s*(\w+)', all_text):
            key = f"cross_{m.group(1)}x{m.group(2)}"
            if key not in bins_dict:
                bins_dict[key] = CoverageBin(name=key, hit_count=0, goal=1)

        # Also parse protocol-specific SVAs
        for m in re.finditer(r'\bcover property\s*\(', all_text):
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
            # Generated code uses item.addr == 3'hX
            f"item.addr == 3'h{addr:x}",
            f"item.addr == 'h{addr:x}",
            f"addr == 3'h{addr:x}",
        ]
        return any(p in all_text for p in patterns)

    def _simulate_coverage(self, bins: List[CoverageBin],
                           files: List[str]) -> List[CoverageBin]:
        if not files:
            return bins

        all_text = "\n".join(
            Path(f).read_text(errors="replace") for f in files if Path(f).exists()
        )

        has_write = ("item.we = 1" in all_text or "item.we == 1" in all_text
                     or "wb_we = 1" in all_text or "pwrite = 1" in all_text)
        has_read = ("item.we = 0" in all_text or "item.we == 0" in all_text
                    or "wb_we = 0" in all_text or "pwrite = 0" in all_text)
        has_any_txn = bool(re.search(r'reg_addr\s*=|wb_addr\s*=|paddr\s*=|item\.addr', all_text))
        has_baud = bool(re.search(r'baud|115200|9600|19200', all_text, re.I))
        has_parity = bool(re.search(r'parity|PARITY', all_text))
        has_reset = "rst_n" in all_text or "reset" in all_text.lower()
        has_fifo = bool(re.search(r'fifo|FIFO', all_text))
        has_ier = bool(re.search(r'ier|IER|erbfi|etbei|elsi|edssi', all_text))
        has_lsr = bool(re.search(r'lsr|LSR', all_text))
        has_loopback = ("loopback" in all_text.lower() or "mismatch" in all_text.lower())

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
                if hit == 0:
                    if has_any_txn:
                        hit = 1  # auto-generated addr bins without register numbers

            elif "read" in nl and ("dir" in nl or "direction" in nl):
                hit = 1 if has_read else 0
            elif "write" in nl and ("dir" in nl or "direction" in nl):
                hit = 1 if has_write else 0

            elif "cross" in nl:
                # Check specific domains before generic "addr"
                if "rst" in nl:
                    hit = 1 if has_reset else 0
                elif "fifo" in nl:
                    hit = 1 if has_fifo else 0
                elif "ier" in nl or "erbfi" in nl or "etbei" in nl or "elsi" in nl or "edssi" in nl:
                    hit = 1 if has_ier else 0
                elif "lsr" in nl:
                    hit = 1 if has_lsr else 0
                elif "int_type" in nl or "irq" in nl:
                    hit = 1 if has_any_txn else 0
                elif "err_type" in nl or "hw_detected" in nl or "parity_en" in nl:
                    hit = 1 if has_any_txn else 0
                elif "baud" in nl or "parity" in nl or "frame" in nl or "stop_bits" in nl or "data_bits" in nl:
                    hit = (1 if has_baud else 0) + (1 if has_parity else 0)
                    hit = min(hit, 2)
                elif "result" in nl or "mismatch" in nl or "match" in nl:
                    hit = 1 if has_loopback else 0
                elif "addr" in nl or "access" in nl or "we" in nl:
                    cnt = sum(1 for a in range(8) if self._is_register_hit(a, all_text))
                    hit = min(cnt, 8) if cnt else (1 if has_any_txn else 0)
                else:
                    hit = 1 if has_any_txn else 0

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

            # New coverpoint types from reset/fifo/IER-interrupt/error-LSR covergroups
            elif "rst" in nl or "reset" in nl:
                hit = 1 if has_reset else 0
            elif "fifo" in nl:
                hit = 1 if has_fifo else 0
            elif "ier" in nl or "erbfi" in nl or "etbei" in nl or "elsi" in nl or "edssi" in nl:
                hit = 1 if has_ier else 0
            elif "lsr" in nl:
                hit = 1 if has_lsr else 0
            elif "loopback" in nl or "pass" in nl or "fail" in nl or "match" in nl:
                hit = 1 if has_loopback else 0
            elif "baud" in nl:
                hit = 1 if has_baud else 0
            elif "parity" in nl or "parity_mode" in nl:
                hit = 1 if has_parity else 0
            elif "enabled" in nl or "disabled" in nl:
                hit = 1 if has_any_txn else 0
            elif "rx_data" in nl or "tx_empty" in nl or "line_status" in nl or "modem_status" in nl:
                hit = 1 if has_any_txn else 0
            elif "brk" in nl or "overrun" in nl or "framing" in nl:
                hit = 1 if has_any_txn else 0
            elif "d5" in nl or "d6" in nl or "d7" in nl or "d8" in nl:
                hit = 1 if has_any_txn else 0
            elif "s1" in nl or "s2" in nl:
                hit = 1 if has_any_txn else 0
            elif "none" in nl or "odd" in nl or "even" in nl or "mark" in nl or "space" in nl:
                hit = 1 if has_any_txn else 0
            elif "halted" in nl or "running" in nl or "idle" in nl:
                hit = 1 if has_any_txn else 0
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
