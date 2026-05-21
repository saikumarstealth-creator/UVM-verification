from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from src.config import DesignSpec
from src.simulation.base import CoverageBin, SimResult


@dataclass
class CoverageGap:
    bin_name: str
    register_addr: Optional[int] = None
    direction: Optional[str] = None  # "read" or "write"
    description: str = ""

    def to_sequence_hint(self) -> str:
        parts = []
        if self.direction:
            parts.append(f"target_direction={self.direction}")
        if self.register_addr is not None:
            parts.append(f"target_addr=3'h{self.register_addr:x}")
        return ";".join(parts) if parts else ""


@dataclass
class CoverageAnalysis:
    sim_result: SimResult
    gaps: List[CoverageGap] = field(default_factory=list)
    uncovered_registers: Set[int] = field(default_factory=set)
    uncovered_directions: Set[str] = field(default_factory=set)
    coverage_gain_rate: float = 0.0  # % improvement per iteration
    previous_coverage: float = 0.0

    @property
    def total_gaps(self) -> int:
        return len(self.gaps)

    def meets_goal(self, threshold: float = 90.0) -> bool:
        return self.sim_result.coverage_pct >= threshold

    def summary(self) -> str:
        r = self.sim_result
        return (
            f"Coverage: {r.covered_bins}/{r.total_bins} ({r.coverage_pct:.1f}%) | "
            f"Gaps: {self.total_gaps} | "
            f"Uncovered regs: {sorted(self.uncovered_registers) if self.uncovered_registers else 'none'} | "
            f"Rate: {self.coverage_gain_rate:+.1f}%/iter"
        )


class CoverageAnalyzer:
    """Analyzes simulation coverage results and identifies gaps for retraining."""

    def __init__(self, spec: DesignSpec):
        self.spec = spec
        self.known_register_addrs = self._extract_register_addrs()
        self.history: List[float] = []

    def _extract_register_addrs(self) -> Dict[str, int]:
        addrs = {}
        for reg in self.spec.registers:
            try:
                addr = int(str(reg.address), 0) if isinstance(reg.address, str) else int(reg.address)
                addrs[reg.name.lower()] = addr
            except (ValueError, TypeError):
                continue
        return addrs

    def analyze(self, result: SimResult) -> CoverageAnalysis:
        self.history.append(result.coverage_pct)
        gaps = []
        uncovered_regs = set()
        uncovered_dirs = set()

        # Map bin names to register addresses
        for bin_ in result.uncovered_bins:
            name_lower = bin_.name.lower()
            gap = CoverageGap(bin_name=bin_.name)

            # Extract register address from bin name patterns
            addr_match = re.search(r'regs\[(\d+)\]', name_lower)
            if addr_match:
                addr = int(addr_match.group(1))
                gap.register_addr = addr
                uncovered_regs.add(addr)

            # Extract direction
            if 'read' in name_lower or 'rd' in name_lower:
                gap.direction = 'read'
                uncovered_dirs.add('read')
            elif 'write' in name_lower or 'wr' in name_lower:
                gap.direction = 'write'
                uncovered_dirs.add('write')

            # cross_ADRxDIR → specific address-direction combos
            cross_match = re.search(r'cross.*(\d+).*(read|write)', name_lower)
            if cross_match:
                addr = int(cross_match.group(1))
                direction = cross_match.group(2)
                gap.register_addr = addr
                gap.direction = direction
                uncovered_regs.add(addr)
                uncovered_dirs.add(direction)

            gap.description = f"Uncovered: {bin_.name} ({bin_.hit_count}/{bin_.goal})"
            gaps.append(gap)

        # Compute coverage gain rate
        gain_rate = 0.0
        if len(self.history) >= 2:
            recent = self.history[-3:] if len(self.history) >= 3 else self.history
            gain_rate = recent[-1] - recent[0]
            if len(recent) > 1:
                gain_rate /= (len(recent) - 1)

        return CoverageAnalysis(
            sim_result=result,
            gaps=gaps,
            uncovered_registers=uncovered_regs,
            uncovered_directions=uncovered_dirs,
            coverage_gain_rate=gain_rate,
            previous_coverage=self.history[-2] if len(self.history) >= 2 else 0.0
        )

    def generate_target_sequences(self, analysis: CoverageAnalysis) -> List[str]:
        """Generate SystemVerilog sequence code targeting uncovered coverage areas."""
        sequences = []
        seen = set()
        seq_id = len(self.history)

        for gap in analysis.gaps:
            addr = gap.register_addr
            direction = gap.direction

            # Deduplicate: (addr, dir) pairs
            key = (addr, direction)
            if key in seen:
                continue
            seen.add(key)

            seq_name = f"cover_seq_v{seq_id}_a{addr}_{direction or 'any'}"
            lines = [f"class {seq_name} extends {self.spec.design_name}_base_seq;",
                     f"  `uvm_object_utils({seq_name})",
                     "",
                     f"  function new(string name = \"{seq_name}\");",
                     "    super.new(name);",
                     "  endfunction",
                     "",
                     "  virtual task body();"]

            if direction == "write" and addr is not None:
                data_val = 0xA0 | addr
                lines.append(f"    write_reg({addr:0x}, 8'h{data_val:02x});")
                lines.append(f'    `uvm_info(get_type_name(), "Coverage write reg[{addr:0x}]", UVM_LOW)')
            elif direction == "read" and addr is not None:
                lines.append(f"    read_reg({addr:0x});")
                lines.append(f'    `uvm_info(get_type_name(), "Coverage read reg[{addr:0x}]", UVM_LOW)')
            elif addr is not None:
                lines.append(f"    write_reg({addr:0x}, 8'hA5);")
                lines.append(f"    read_reg({addr:0x});")
                lines.append(f'    `uvm_info(get_type_name(), "Coverage rw reg[{addr:0x}]", UVM_LOW)')
            else:
                lines.append("    // Generic coverage sequence")
                lines.append('    `uvm_info(get_type_name(), "Generic coverage seq", UVM_LOW)')

            lines.append("  endtask")
            lines.append("endclass")
            sequences.append("\n".join(lines))

        return sequences

    def generate_regression_test(self, seq_names: List[str],
                                  design_name: str) -> str:
        """Generate a regression test that starts all coverage sequences."""
        if not seq_names:
            seq_names = [f"{design_name}_send_byte_seq",
                         f"{design_name}_write_reg_seq",
                         f"{design_name}_read_reg_seq"]

        seq_decls = "\n".join(f"    {name} seq_{i};"
                              for i, name in enumerate(seq_names))
        seq_starts = "\n".join(
            f"    seq_{i} = {name}::type_id::create(\"seq_{i}\");\n"
            f"    seq_{i}.start(env.agent.sequencer);"
            for i, name in enumerate(seq_names))

        return f"""// Auto-generated regression test — coverage-driven
class {design_name}_regression_test extends {design_name}_test;
  `uvm_component_utils({design_name}_regression_test)

  function new(string name = "{design_name}_regression_test", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  task run_phase(uvm_phase phase);
    super.run_phase(phase);
    phase.raise_objection(this);

{seq_decls}

{seq_starts}

    phase.drop_objection(this);
  endtask
endclass
"""

    def target_list_to_sv(self, gaps: List[CoverageGap]) -> str:
        """Generate inline SV assertions/coverage directives for gaps."""
        triggers = []
        for g in gaps:
            cond_parts = []
            if g.register_addr is not None:
                cond_parts.append(f"wb_addr == 3'h{g.register_addr:x}")
            if g.direction == "write":
                cond_parts.append("wb_we == 1'b1")
            elif g.direction == "read":
                cond_parts.append("wb_we == 1'b0")
            if cond_parts:
                triggers.append(f"  cover property(@(posedge vif.clk) "
                                f"{' && '.join(cond_parts)});")
        return "\n".join(triggers)
