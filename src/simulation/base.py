from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class CoverageBin:
    name: str
    hit_count: int
    goal: int = 1

    @property
    def covered(self) -> bool:
        return self.hit_count >= self.goal


@dataclass
class SimResult:
    passed: bool
    total_bins: int = 0
    covered_bins: int = 0
    bins: List[CoverageBin] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    log_output: str = ""
    seed: int = 0

    @property
    def coverage_pct(self) -> float:
        if self.total_bins == 0:
            return 0.0
        return (self.covered_bins / self.total_bins) * 100.0

    @property
    def uncovered_bins(self) -> List[CoverageBin]:
        return [b for b in self.bins if not b.covered]


class CoverageDB:
    """Merges coverage results across multiple seeds for regression."""

    def __init__(self):
        self.seed_results: List[SimResult] = []
        self.merged_bins: Dict[str, CoverageBin] = {}

    def add_seed_result(self, result: SimResult) -> None:
        self.seed_results.append(result)
        for b in result.bins:
            key = b.name
            if key in self.merged_bins:
                existing = self.merged_bins[key]
                existing.hit_count = max(existing.hit_count, b.hit_count)
                existing.goal = max(existing.goal, b.goal)
            else:
                self.merged_bins[key] = CoverageBin(name=b.name, hit_count=b.hit_count, goal=b.goal)

    def merge(self) -> SimResult:
        bins = list(self.merged_bins.values())
        covered = sum(1 for b in bins if b.covered)
        total = len(bins)
        return SimResult(
            passed=covered == total,
            total_bins=total,
            covered_bins=covered,
            bins=bins,
            errors=[],
            log_output=self._format_summary(bins, covered, total),
        )

    def _format_summary(self, bins: List[CoverageBin], covered: int, total: int) -> str:
        pct = (covered / total * 100) if total else 0
        lines = [
            f"--- CoverageDB merged ({len(self.seed_results)} seeds) ---",
        ]
        for b in bins:
            status = "HIT" if b.covered else "MISS"
            lines.append(f"COVERAGE: {b.name} {b.hit_count}/{b.goal} [{status}]")
        lines.append(f"--- Merged: {covered}/{total} ({pct:.1f}%) ---")
        return "\n".join(lines)

    def save(self, path: str) -> None:
        data = {
            "num_seeds": len(self.seed_results),
            "merged": {k: {"hit_count": v.hit_count, "goal": v.goal}
                       for k, v in self.merged_bins.items()},
        }
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> CoverageDB:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        db = cls()
        for name, bdata in data.get("merged", {}).items():
            db.merged_bins[name] = CoverageBin(name=name, **bdata)
        return db

    @property
    def uncovered(self) -> List[CoverageBin]:
        return [b for b in self.merged_bins.values() if not b.covered]


class Simulator:
    def __init__(self, work_dir: str = "sim_output"):
        self.work_dir = work_dir

    def run(self, files: List[str], top: str = "testbench",
            plusargs: Optional[List[str]] = None) -> SimResult:
        raise NotImplementedError

    def run_multi_seed(self, files: List[str], num_seeds: int = 3,
                       top: str = "testbench") -> Tuple[SimResult, CoverageDB]:
        db = CoverageDB()
        merged = None
        for s in range(num_seeds):
            result = self.run(files, top=top, plusargs=[f"+seed={s+1}"])
            result.seed = s + 1
            db.add_seed_result(result)
        merged = db.merge()
        return merged, db

    def parse_coverage(self, log: str) -> SimResult:
        raise NotImplementedError

    def name(self) -> str:
        return self.__class__.__name__
