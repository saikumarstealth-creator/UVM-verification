from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class SVIssue:
    line: int
    severity: str  # "error" | "warning" | "info"
    message: str
    code: str  # unique issue code


@dataclass
class SVSuggestion:
    code: str
    message: str
    fix: str


FIX_SUGGESTIONS: Dict[str, SVSuggestion] = {
    "BLK002": SVSuggestion(
        "BLK002",
        "Mismatched block end",
        "Check that end{keyword} matches the opening keyword at the indicated line. Replace mismatched end{keyword} with the correct terminator.",
    ),
    "BLK004": SVSuggestion(
        "BLK004",
        "Unexpected 'end' without 'begin'",
        "Remove the extra 'end' or add a matching 'begin' before this block.",
    ),
    "BLK005": SVSuggestion(
        "BLK005",
        "Unclosed block",
        "Add the missing 'end{keyword}' at the end of the unclosed block.",
    ),
    "PAR001": SVSuggestion(
        "PAR001",
        "Unbalanced parentheses",
        "Add or remove parentheses to balance — count opening '(' and closing ')' in this line.",
    ),
    "TYP001": SVSuggestion(
        "TYP001",
        "Undefined type reference",
        "Add a typedef or class declaration for the referenced type, or ensure the type is imported via `include.",
    ),
    "PRO001": SVSuggestion(
        "PRO001",
        "Missing protocol signal",
        "Add port declaration or signal assignment for the missing protocol signal to match the interface.",
    ),
    "PIT001": SVSuggestion(
        "PIT001",
        "$display used instead of `uvm_info",
        "Replace `$display(...)` with ```uvm_info(\"ID\", $sformatf(...), UVM_MEDIUM)``` for UVM-compliance.",
    ),
    "PIT002": SVSuggestion(
        "PIT002",
        "$monitor used instead of `uvm_info",
        "Replace `$monitor(...)` with ```uvm_info(\"ID\", $sformatf(...), UVM_MEDIUM)```.",
    ),
    "PIT003": SVSuggestion(
        "PIT003",
        "always @ used instead of always_ff/always_comb",
        "Replace `always @(...)` with `always_ff @(posedge clk)` for sequential or `always_comb` for combinational logic.",
    ),
    "PIT004": SVSuggestion(
        "PIT004",
        "Direct .sv include — use filelist instead",
        "Move `include to a compile.f file list and add the file to the UVM filelist instead of direct include.",
    ),
    "REG001": SVSuggestion(
        "REG001",
        "Register referenced but not defined in spec",
        "Remove the hallucinated register reference, or add it to the YAML spec's `registers` list.",
    ),
    "SEQ001": SVSuggestion(
        "SEQ001",
        "Missing sequence item declaration",
        "Add `uart_seq_item req;` and `uart_seq_item rsp;` before using them in this task.",
    ),
}


@dataclass
class SVCheckResult:
    file_path: str
    passed: bool = False
    confidence: float = 0.0
    issues: List[SVIssue] = field(default_factory=list)
    suggestions: List[SVSuggestion] = field(default_factory=list)
    total_lines: int = 0
    total_issues: int = 0
    errors: int = 0
    warnings: int = 0


BLOCK_KEYWORDS = {
    "module": "endmodule",
    "class": "endclass",
    "function": "endfunction",
    "task": "endtask",
    "begin": "end",
    "covergroup": "endgroup",
    "checker": "endchecker",
    "primitive": "endprimitive",
    "interface": "endinterface",
    "package": "endpackage",
    "program": "endprogram",
    "config": "endconfig",
    "generate": "endgenerate",
    "specify": "endspecify",
    "table": "endtable",
    "property": "endproperty",
    "sequence": "endsequence",
}

SVA_KEYWORDS = {"assert", "assume", "cover", "restrict"}

UVM_OBJECT_TYPES = {
    "uvm_component",
    "uvm_object",
    "uvm_sequence_item",
    "uvm_sequence",
    "uvm_driver",
    "uvm_monitor",
    "uvm_agent",
    "uvm_scoreboard",
    "uvm_subscriber",
    "uvm_env",
    "uvm_test",
    "uvm_reg_block",
    "uvm_reg",
    "uvm_reg_field",
    "uvm_reg_adapter",
    "uvm_reg_predictor",
    "uvm_reg_map",
    "uvm_analysis_port",
    "uvm_analysis_imp",
    "uvm_config_db",
    "uvm_event",
}

PROTOCOL_SIGNAL_PATTERNS = {
    "wishbone": [r"\bcyc\b", r"\bstb\b", r"\bwe\b", r"\bdat_i?\b", r"\bdat_o?\b", r"\baddr?\b", r"\back\b"],
    "uart": [r"\brx\b", r"\btx\b", r"\bcts\b", r"\brts\b"],
    "spi": [r"\bmosi\b", r"\bmiso\b", r"\bss_n\b", r"\bsclk\b"],
    "i2c": [r"\bsda\b", r"\bscl\b"],
    "axi4lite": [r"\bawaddr\b", r"\bwdata\b", r"\bwvalid\b", r"\bwready\b", r"\baraddr\b", r"\brdata\b"],
    "apb": [r"\bpaddr\b", r"\bpwrite\b", r"\bpsel\b", r"\bpenable\b"],
}


class SVSyntaxChecker:
    """Static analysis checker for generated SystemVerilog files.

    Uses regex-based parsing to catch common issues without an external SV compiler.
    Designed for CI/feedback during generation — not a substitute for real linting.
    """

    def __init__(self, protocol: Optional[str] = None):
        self.protocol = protocol

    def check_file(self, file_path: str, content: str) -> SVCheckResult:
        result = SVCheckResult(file_path=file_path)
        lines = content.split("\n")
        result.total_lines = len(lines)

        self._check_block_structure(lines, result)
        self._check_paren_balance(lines, result)
        self._check_undefined_types(lines, result)
        self._check_protocol_consistency(lines, result)
        self._check_common_pitfalls(lines, result)

        result.errors = sum(1 for i in result.issues if i.severity == "error")
        result.warnings = sum(1 for i in result.issues if i.severity == "warning")
        result.total_issues = len(result.issues)
        result.passed = result.errors == 0
        result.confidence = self._compute_confidence(result)

        result.suggestions = list({
            issue.code: FIX_SUGGESTIONS[issue.code]
            for issue in result.issues
            if issue.code in FIX_SUGGESTIONS
        }.values())

        return result

    def _compute_confidence(self, result: SVCheckResult) -> float:
        if result.total_lines == 0:
            return 0.0
        base = 0.9
        error_penalty = result.errors * 0.08
        warning_penalty = result.warnings * 0.02
        confidence = base - error_penalty - warning_penalty
        return max(0.0, min(1.0, confidence))

    # ----------------------------------------------------------------
    # Structural checks
    # ----------------------------------------------------------------

    def _check_block_structure(self, lines: List[str], result: SVCheckResult) -> None:
        stack: List[Tuple[str, int]] = []
        re_open = re.compile(r'^\s*(?:virtual\s+)?(?:pure\s+)?(function|task|class|module|interface|package|program|covergroup|checker|primitive|config|generate|specify|table|property|sequence)\b', re.IGNORECASE)
        re_close = re.compile(r'^\s*end(?:function|task|class|module|interface|package|program|covergroup|checker|primitive|config|generate|specify|table|property|sequence)\b', re.IGNORECASE)
        re_begin = re.compile(r'\bbegin\s*(?::\s*\w+)?\s*(?:$|//|/\*)')
        re_end = re.compile(r'^\s*end\s*(?:$|//|/\*)')

        in_comment_block = False
        for lineno, line in enumerate(lines, 1):
            stripped = line.strip()

            if "/*" in stripped:
                in_comment_block = True
            if in_comment_block:
                if "*/" in stripped:
                    in_comment_block = False
                continue
            if stripped.startswith("//") or stripped.startswith("*"):
                continue

            m = re_open.search(stripped)
            if m:
                kw = m.group(1).lower()
                if kw not in ("virtual", "pure"):
                    stack.append((kw, lineno))
                continue

            m = re_close.search(stripped)
            if m:
                end_kw = stripped[m.start():].split()[0].lower().lstrip("end")
                if stack and stack[-1][0] == end_kw:
                    stack.pop()
                elif not stack:
                    result.issues.append(SVIssue(
                        lineno, "error", f"Unexpected 'end{end_kw}' without matching open", "BLK001"
                    ))
                else:
                    result.issues.append(SVIssue(
                        lineno, "error",
                        f"Mismatched block: 'end{end_kw}' but expected 'end{stack[-1][0]}' (opened at line {stack[-1][1]})",
                        "BLK002"
                    ))

            if re_begin.search(stripped) and not stripped.startswith("end"):
                stack.append(("begin", lineno))
            if re_end.match(stripped):
                if stack and stack[-1][0] == "begin":
                    stack.pop()
                elif stack:
                    result.issues.append(SVIssue(
                        lineno, "warning",
                        f"'end' closes outermost '{stack[-1][0]}' block (line {stack[-1][1]}) — may be intentional",
                        "BLK003"
                    ))
                    stack.pop()
                else:
                    result.issues.append(SVIssue(
                        lineno, "error", "Unexpected 'end' without matching 'begin'", "BLK004"
                    ))

        for kw, lineno in reversed(stack):
            result.issues.append(SVIssue(
                lineno, "error", f"Unclosed '{kw}' block (opened at line {lineno})", "BLK005"
            ))

    def _check_paren_balance(self, lines: List[str], result: SVCheckResult) -> None:
        in_comment_block = False
        for lineno, line in enumerate(lines, 1):
            stripped = line.strip()
            if "/*" in stripped:
                in_comment_block = True
            if in_comment_block:
                if "*/" in stripped:
                    in_comment_block = False
                continue
            if stripped.startswith("//"):
                continue

            parens = 0
            for ch in stripped:
                if ch == "(":
                    parens += 1
                elif ch == ")":
                    parens -= 1
            if parens != 0:
                result.issues.append(SVIssue(
                    lineno, "warning",
                    f"Unbalanced parentheses (net: {parens:+d})", "PAR001"
                ))

    # ----------------------------------------------------------------
    # Type reference checks
    # ----------------------------------------------------------------

    def _check_undefined_types(self, lines: List[str], result: SVCheckResult) -> None:
        defined_types: set = set()
        re_class = re.compile(r'^\s*class\s+(\w+)', re.IGNORECASE)
        re_type_ref = re.compile(r'(?:::\s*)?(\w+)(?:\s+#)?\s+(?:\w+\s*;)', re.IGNORECASE)
        for lineno, line in enumerate(lines, 1):
            m = re_class.search(line)
            if m:
                defined_types.add(m.group(1).lower())

        sv_builtins = {
            "logic", "bit", "byte", "int", "integer", "real", "time", "string",
            "reg", "wire", "tri", "supply0", "supply1", "wand", "wor",
            "void", "shortint", "longint", "shortreal",
            "always", "always_comb", "always_ff", "always_latch",
            "assign", "initial", "final",
            "input", "output", "inout", "ref",
            "parameter", "localparam", "genvar",
            "module", "endmodule", "interface", "endinterface",
            "function", "endfunction", "task", "endtask",
            "class", "endclass", "package", "endpackage",
            "rand", "randc", "constraint",
            "typedef", "enum", "struct", "union", "packed",
            "import", "include",
            "case", "endcase", "for", "foreach", "while", "do", "repeat", "forever",
            "if", "else", "return", "break", "continue",
            "assert", "assume", "cover", "property", "sequence",
            "this", "super", "null",
            "new", "create",
            "fork", "join", "join_any", "join_none",
            "begin", "end",
            "uvm_object_utils", "uvm_component_utils",
            "uvm_info", "uvm_error", "uvm_fatal", "uvm_warning",
            "local", "static", "protected", "virtual", "pure",
            "default", "inside",
            "matches", "intersect", "throughout", "within",
            "svarray", "dynamic_array",
            "primitives",
        }

        all_defined = defined_types | {t.lower() for t in UVM_OBJECT_TYPES} | sv_builtins

        re_use = re.compile(r'\btype_id\s*::\s*create\s*\(\s*"(\w+)"')
        for lineno, line in enumerate(lines, 1):
            m = re_use.search(line)
            if m:
                class_ref = m.group(1).lower()
                if class_ref not in all_defined and "seq" not in class_ref and "item" not in class_ref:
                    result.issues.append(SVIssue(
                        lineno, "warning",
                        f"Type '{m.group(1)}' used via type_id::create but may not be defined in this compilation unit",
                        "TYP001"
                    ))

    # ----------------------------------------------------------------
    # Protocol signal consistency
    # ----------------------------------------------------------------

    def _check_protocol_consistency(self, lines: List[str], result: SVCheckResult) -> None:
        if not self.protocol:
            return
        expected_patterns = PROTOCOL_SIGNAL_PATTERNS.get(self.protocol, [])
        if not expected_patterns:
            return
        content = "\n".join(lines).lower()
        for pattern in expected_patterns:
            if not re.search(pattern, content):
                result.issues.append(SVIssue(
                    0, "warning",
                    f"Expected protocol signal matching '{pattern}' not found in file (protocol={self.protocol})",
                    "PRO001"
                ))

    # ----------------------------------------------------------------
    # Common pitfalls
    # ----------------------------------------------------------------

    def _check_common_pitfalls(self, lines: List[str], result: SVCheckResult) -> None:
        in_comment_block = False
        for lineno, line in enumerate(lines, 1):
            stripped = line.strip()
            if "/*" in stripped:
                in_comment_block = True
            if in_comment_block:
                if "*/" in stripped:
                    in_comment_block = False
                continue
            if stripped.startswith("//") or stripped.startswith("*"):
                continue

            if re.search(r'(?<!\$)\bdisplay\b', stripped) and "`uvm_info" not in stripped:
                result.issues.append(SVIssue(
                    lineno, "warning",
                    "Use `uvm_info instead of $display in UVM testbenches", "PIT001"
                ))
            if re.search(r'(?<!\$)\bmonitor\b', stripped) and "`uvm_info" not in stripped:
                result.issues.append(SVIssue(
                    lineno, "warning",
                    "Use `uvm_info instead of $monitor in UVM testbenches", "PIT002"
                ))
            if "always @" in stripped and "always_ff" not in stripped and "always_comb" not in stripped:
                result.issues.append(SVIssue(
                    lineno, "info",
                    "Use always_ff or always_comb instead of always @ for better lint compliance", "PIT003"
                ))
            if "`include" in stripped and ".sv" in stripped:
                result.issues.append(SVIssue(
                    lineno, "info",
                    f"Verilog `.sv` include — use compile.f filelist for UVM compatibility", "PIT004"
                ))


def check_directory(files: Dict[str, str], protocol: Optional[str] = None) -> Dict[str, SVCheckResult]:
    """Run SV syntax check on a dict of {filename: content}. Returns per-file results."""
    checker = SVSyntaxChecker(protocol=protocol)
    results: Dict[str, SVCheckResult] = {}
    for fname, content in files.items():
        results[fname] = checker.check_file(fname, content)
    return results


def summarize(results: Dict[str, SVCheckResult]) -> Dict[str, float]:
    """Aggregate per-file results into pipeline-friendly metrics dict."""
    if not results:
        return {"sv_compile_confidence": 0.0, "sv_errors": 0, "sv_warnings": 0, "sv_files_passed": 0, "sv_files_total": 0}

    total_files = len(results)
    passed = sum(1 for r in results.values() if r.passed)
    total_errors = sum(r.errors for r in results.values())
    total_warnings = sum(r.warnings for r in results.values())
    avg_confidence = sum(r.confidence for r in results.values()) / total_files

    return {
        "sv_compile_confidence": round(avg_confidence, 4),
        "sv_errors": total_errors,
        "sv_warnings": total_warnings,
        "sv_files_passed": passed,
        "sv_files_total": total_files,
    }


def collect_suggestions(results: Dict[str, SVCheckResult]) -> List[Dict[str, str]]:
    """Collect unique fix suggestions across all files."""
    seen: Set[str] = set()
    suggestions: List[Dict[str, str]] = []
    for fname, result in results.items():
        for s in result.suggestions:
            if s.code not in seen:
                seen.add(s.code)
                suggestions.append({
                    "code": s.code,
                    "issue": s.message,
                    "fix": s.fix,
                    "files": fname,
                })
    return suggestions
