from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class CrossFileIssue:
    file: str
    line: int
    severity: str
    message: str
    reference: str


@dataclass
class CrossFileResult:
    passed: bool
    issues: List[CrossFileIssue]
    spec_coverage: Dict[str, float]


_REG_REF_RE = re.compile(r'reg_model\.(\w+)')
_INTF_REF_RE = re.compile(r'vif\.(\w+)')
_CLASS_REF_RE = re.compile(r'(\w+)_seq_item')
_DECL_RE = re.compile(r'^\s*(class|function|task|module)\s+(\w+)')


def extract_reg_refs(content: str, file_name: str) -> List[Tuple[int, str]]:
    hits: List[Tuple[int, str]] = []
    for i, line in enumerate(content.splitlines(), 1):
        for m in _REG_REF_RE.finditer(line):
            hits.append((i, m.group(1)))
    return hits


def extract_declared_names(content: str) -> Set[str]:
    names: Set[str] = set()
    for line in content.splitlines():
        m = _DECL_RE.match(line)
        if m:
            names.add(m.group(2))
    return names


def validate_generated_files(
    files: Dict[str, str],
    spec: Any,
) -> CrossFileResult:
    spec_reg_names: Set[str] = set()
    if hasattr(spec, 'registers') and spec.registers:
        spec_reg_names = {r.name.lower() for r in spec.registers}
    spec_intf_names: Set[str] = set()
    if hasattr(spec, 'interfaces') and spec.interfaces:
        spec_intf_names = {i.name.lower() for i in spec.interfaces}

    issues: List[CrossFileIssue] = []
    found_reg_refs: Set[str] = set()

    for fname, content in files.items():
        for line_no, reg_name in extract_reg_refs(content, fname):
            found_reg_refs.add(reg_name.lower())
            if spec_reg_names and reg_name.lower() not in spec_reg_names:
                issues.append(CrossFileIssue(
                    file=fname,
                    line=line_no,
                    severity="error",
                    message=f"References register '{reg_name}' not defined in spec registers: {sorted(spec_reg_names)}",
                    reference=reg_name,
                ))

        for i, line in enumerate(content.splitlines(), 1):
            for m in _INTF_REF_RE.finditer(line):
                sig = m.group(1).lower()
                if spec_intf_names and sig not in spec_intf_names:
                    if sig not in ('rx', 'tx'):  # common protocol sigs, not hallucinations
                        issues.append(CrossFileIssue(
                            file=fname,
                            line=i,
                            severity="warning",
                            message=f"References interface signal '{sig}' not found in spec interfaces",
                            reference=sig,
                        ))

    # spec coverage — what % of spec registers are referenced somewhere
    reg_cov = 0.0
    if spec_reg_names:
        covered = sum(1 for r in spec_reg_names if r in found_reg_refs)
        reg_cov = covered / len(spec_reg_names)

    intf_cov = 0.0
    intf_refs: Set[str] = set()
    for fname, content in files.items():
        for m in _INTF_REF_RE.finditer(content):
            intf_refs.add(m.group(1).lower())
    if spec_intf_names:
        covered = sum(1 for i in spec_intf_names if i in intf_refs)
        intf_cov = covered / len(spec_intf_names)

    spec_coverage = {
        "register_reference_coverage": reg_cov,
        "interface_reference_coverage": intf_cov,
    }

    passed = all(iss.severity == "warning" for iss in issues)

    return CrossFileResult(
        passed=passed,
        issues=issues,
        spec_coverage=spec_coverage,
    )
