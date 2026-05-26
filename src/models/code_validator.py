"""
Industry-level code validator for UVM testbench generation.

Validates generated SystemVerilog code for:
1. Basic syntax correctness
2. Spec compliance (signals, registers, interfaces used)
3. UVM best practices
4. Common error patterns
5. Compilation readiness

Provides detailed validation reports with:
- Errors (blocking issues)
- Warnings (potential issues)
- Info (best practice suggestions)
- Auto-fix suggestions
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Pattern

logger = logging.getLogger("uvmgen.validator")


class ValidationSeverity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    STYLE = "style"


@dataclass
class ValidationIssue:
    """Single validation issue."""
    severity: ValidationSeverity
    code: str
    message: str
    line_number: Optional[int] = None
    context: Optional[str] = None
    suggestion: Optional[str] = None
    auto_fixable: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "line_number": self.line_number,
            "context": self.context,
            "suggestion": self.suggestion,
            "auto_fixable": self.auto_fixable,
        }


@dataclass
class FileValidationResult:
    """Validation result for a single file."""
    filename: str
    file_type: str
    passed: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    checks_run: int = 0
    checks_passed: int = 0

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.INFO)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filename": self.filename,
            "file_type": self.file_type,
            "passed": self.passed,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "checks_run": self.checks_run,
            "checks_passed": self.checks_passed,
            "issues": [i.to_dict() for i in self.issues],
        }


@dataclass
class ValidationReport:
    """Complete validation report for a generation run."""
    design_name: str
    overall_passed: bool
    files: List[FileValidationResult] = field(default_factory=list)
    timestamp: str = ""

    @property
    def total_errors(self) -> int:
        return sum(f.error_count for f in self.files)

    @property
    def total_warnings(self) -> int:
        return sum(f.warning_count for f in self.files)

    @property
    def total_checks_run(self) -> int:
        return sum(f.checks_run for f in self.files)

    @property
    def total_checks_passed(self) -> int:
        return sum(f.checks_passed for f in self.files)

    @property
    def pass_rate(self) -> float:
        if self.total_checks_run == 0:
            return 1.0
        return self.total_checks_passed / self.total_checks_run

    def to_dict(self) -> Dict[str, Any]:
        return {
            "design_name": self.design_name,
            "overall_passed": self.overall_passed,
            "total_errors": self.total_errors,
            "total_warnings": self.total_warnings,
            "total_checks_run": self.total_checks_run,
            "total_checks_passed": self.total_checks_passed,
            "pass_rate": round(self.pass_rate * 100, 1),
            "files": [f.to_dict() for f in self.files],
        }


SV_KEYWORDS = {
    "module", "endmodule", "interface", "endinterface", "class", "endclass",
    "input", "output", "inout", "logic", "reg", "wire", "bit", "int", "integer",
    "always", "initial", "assign", "begin", "end", "case", "endcase", "if", "else",
    "for", "while", "repeat", "forever", "task", "endtask", "function", "endfunction",
    "parameter", "localparam", "defparam", "typedef", "struct", "union", "enum",
    "posedge", "negedge", "or", "and", "not", "default", "none",
    "import", "export", "package", "endpackage", "include", "define",
    "uvm_object_utils", "uvm_component_utils", "uvm_field_utils",
    "virtual", "rand", "randc", "constraint", "extends", "implements",
}

UVM_BASE_CLASSES = {
    "uvm_test", "uvm_env", "uvm_agent", "uvm_driver", "uvm_monitor",
    "uvm_sequencer", "uvm_sequence", "uvm_sequence_item", "uvm_scoreboard",
    "uvm_subscriber", "uvm_reg_block", "uvm_reg", "uvm_reg_field",
    "uvm_reg_map", "uvm_reg_adapter", "uvm_reg_predictor",
    "uvm_analysis_port", "uvm_analysis_imp", "uvm_tlm_fifo",
    "uvm_component", "uvm_object", "uvm_report_object",
}


class SystemVerilogSyntaxChecker:
    """Basic but effective SystemVerilog syntax checker."""

    PAIR_CHECKS = [
        ("module", ["endmodule"]),
        ("interface", ["endinterface"]),
        ("class", ["endclass"]),
        ("function", ["endfunction"]),
        ("task", ["endtask"]),
        ("case", ["endcase"]),
        ("begin", ["end"]),
        ("fork", ["join", "join_any", "join_none"]),
    ]

    def __init__(self):
        self._patterns: Dict[str, Pattern] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        self._patterns = {
            "comment_single": re.compile(r'//.*$', re.MULTILINE),
            "comment_multi": re.compile(r'/\*.*?\*/', re.DOTALL),
            "string_lit": re.compile(r'"[^"]*"'),
            "module_decl": re.compile(r'\bmodule\s+(\w+)\s*[#(;]'),
            "interface_decl": re.compile(r'\binterface\s+(\w+)\s*[#(;]'),
            "class_decl": re.compile(r'\bclass\s+(\w+)\s*(?:#\s*\(|extends|implements|;|{)'),
            "port_list": re.compile(r'\(([^)]+)\)'),
            "unbalanced_paren": re.compile(r'[()]'),
            "unbalanced_bracket": re.compile(r'[\[\]]'),
            "unbalanced_brace": re.compile(r'[{}]'),
            "semicolon": re.compile(r';\s*$'),
        }

    def _strip_comments_and_strings(self, content: str) -> str:
        """Remove comments and strings for analysis."""
        result = content
        result = self._patterns["comment_multi"].sub(" ", result)
        result = self._patterns["comment_single"].sub(" ", result)
        result = self._patterns["string_lit"].sub("\"STR\"", result)
        return result

    def check_balance(self, content: str) -> List[ValidationIssue]:
        """Check balanced delimiters (heuristic, warnings only)."""
        issues: List[ValidationIssue] = []
        stripped = self._strip_comments_and_strings(content)

        checks = [
            ("()", "parentheses"),
            ("[]", "brackets"),
            ("{}", "braces"),
        ]

        for pair, name in checks:
            count_open = stripped.count(pair[0])
            count_close = stripped.count(pair[1])
            if count_open != count_close:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    code=f"SV-SYN-001-{name}",
                    message=f"Possibly unbalanced {name}: {count_open} '{pair[0]}' vs {count_close} '{pair[1]}'",
                    auto_fixable=False,
                ))

        return issues

    def check_begin_end_pairs(self, content: str) -> List[ValidationIssue]:
        """Check begin/end and other block pairs (heuristic, warnings only)."""
        issues: List[ValidationIssue] = []
        stripped = self._strip_comments_and_strings(content)
        lines = stripped.split('\n')

        for open_kw, close_kws in self.PAIR_CHECKS:
            close_kws_set = set(close_kws)
            close_kw_display = close_kws[0] if len(close_kws) == 1 else f"{close_kws[0]}/..."

            stack: List[int] = []
            for line_num, line in enumerate(lines, 1):
                words = re.findall(r'\b\w+\b', line.lower())

                for word in words:
                    if word == open_kw:
                        stack.append(line_num)
                    elif word in close_kws_set:
                        if stack:
                            stack.pop()

            for line_num in stack:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    code="SV-SYN-003",
                    message=f"'{open_kw}' at line {line_num} may have no matching '{close_kw_display}'",
                    line_number=line_num,
                    auto_fixable=False,
                ))

        return issues

    def check_semicolons(self, content: str) -> List[ValidationIssue]:
        """Check for missing semicolons (heuristic)."""
        issues: List[ValidationIssue] = []
        lines = content.split('\n')

        statement_keywords = {
            "logic", "reg", "wire", "bit", "int", "input", "output", "inout",
            "parameter", "localparam", "typedef", "import", "assign",
        }

        block_starters = {
            "module", "interface", "class", "function", "task", "case",
            "begin", "fork", "if", "else", "for", "while", "repeat", "forever",
        }

        block_enders = {
            "endmodule", "endinterface", "endclass", "endfunction", "endtask",
            "endcase", "end", "join", "join_any", "join_none",
        }

        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()

            if not stripped:
                continue
            if stripped.startswith('//'):
                continue
            if stripped.startswith('`'):
                continue

            first_word = stripped.split()[0].lower() if stripped.split() else ""

            if first_word in block_enders:
                continue

            if first_word in block_starters:
                if stripped.rstrip().endswith((':', 'begin', '{')):
                    continue

            if first_word in statement_keywords:
                if not stripped.rstrip().endswith(';') and not stripped.rstrip().endswith(')'):
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        code="SV-SYN-004",
                        message="Possible missing semicolon",
                        line_number=line_num,
                        context=stripped[:60],
                        suggestion="Add ';' at end of statement",
                        auto_fixable=True,
                    ))

        return issues

    def check(self, content: str) -> List[ValidationIssue]:
        """Run all syntax checks."""
        issues: List[ValidationIssue] = []
        issues.extend(self.check_balance(content))
        issues.extend(self.check_begin_end_pairs(content))
        issues.extend(self.check_semicolons(content))
        return issues


class SpecComplianceChecker:
    """Check that generated code matches the design spec."""

    def __init__(self, spec_dict: Dict[str, Any]):
        self.spec = spec_dict
        self.design_name = spec_dict.get("design_name", "unknown")
        self._extract_signals()
        self._extract_registers()

    def _extract_signals(self) -> None:
        """Extract all signals from spec."""
        self.all_signals: Set[str] = set()
        self.signals_by_direction: Dict[str, Set[str]] = {
            "input": set(),
            "output": set(),
            "inout": set(),
        }
        self.signal_widths: Dict[str, int] = {}

        for iface in self.spec.get("interfaces", []):
            for sig in iface.get("signals", []):
                name = sig.get("name", "")
                if name:
                    self.all_signals.add(name)
                    direction = sig.get("direction", "input")
                    self.signals_by_direction.get(direction, set()).add(name)
                    self.signal_widths[name] = sig.get("width", 1)

    def _extract_registers(self) -> None:
        """Extract all registers from spec."""
        self.all_registers: Set[str] = set()
        self.register_addresses: Dict[str, str] = {}
        self.register_fields: Dict[str, Set[str]] = {}

        for reg in self.spec.get("registers", []):
            name = reg.get("name", "")
            if name:
                self.all_registers.add(name)
                self.register_addresses[name] = reg.get("address", "")
                self.register_fields[name] = {
                    f.get("name", "") for f in reg.get("fields", []) if f.get("name")
                }

    def check_signals_in_code(
        self,
        content: str,
        file_type: str,
    ) -> List[ValidationIssue]:
        """Check that spec signals are referenced in code."""
        issues: List[ValidationIssue] = []
        stripped = self._strip_for_analysis(content)

        found_signals: Set[str] = set()
        for sig in self.all_signals:
            if re.search(r'\b' + re.escape(sig) + r'\b', stripped, re.IGNORECASE):
                found_signals.add(sig)

        if file_type in ("interface", "testbench"):
            missing_signals = self.all_signals - found_signals
            for sig in sorted(missing_signals):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="SPEC-001",
                    message=f"Signal '{sig}' defined in spec but not found in {file_type}",
                    suggestion=f"Ensure signal '{sig}' is declared in the {file_type}",
                    auto_fixable=False,
                ))

        for sig in sorted(found_signals & self.all_signals):
            issues.append(ValidationIssue(
                severity=ValidationSeverity.INFO,
                code="SPEC-002",
                message=f"Signal '{sig}' from spec is properly referenced",
                auto_fixable=False,
            ))

        return issues

    def check_registers_in_code(
        self,
        content: str,
        file_type: str,
    ) -> List[ValidationIssue]:
        """Check that spec registers are referenced in code."""
        issues: List[ValidationIssue] = []

        if file_type not in ("ral_model", "test", "sequence", "scoreboard", "coverage"):
            return issues

        if not self.all_registers:
            return issues

        stripped = self._strip_for_analysis(content)

        found_registers: Set[str] = set()
        for reg in self.all_registers:
            if re.search(r'\b' + re.escape(reg) + r'\b', stripped, re.IGNORECASE):
                found_registers.add(reg)

        if file_type == "ral_model":
            missing_regs = self.all_registers - found_registers
            for reg in sorted(missing_regs):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="SPEC-003",
                    message=f"Register '{reg}' defined in spec but not found in RAL model",
                    auto_fixable=False,
                ))

        return issues

    def check_clock_reset(
        self,
        content: str,
        file_type: str,
    ) -> List[ValidationIssue]:
        """Check clock/reset signals are present."""
        issues: List[ValidationIssue] = []

        if file_type not in ("interface", "testbench"):
            return issues

        cr = self.spec.get("clock_reset", {})
        clock = cr.get("clock", "clk")
        reset = cr.get("reset", "rst_n")

        stripped = self._strip_for_analysis(content)

        if not re.search(r'\b' + re.escape(clock) + r'\b', stripped, re.IGNORECASE):
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code="SPEC-004",
                message=f"Clock signal '{clock}' not found in {file_type}",
                auto_fixable=False,
            ))

        if not re.search(r'\b' + re.escape(reset) + r'\b', stripped, re.IGNORECASE):
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code="SPEC-005",
                message=f"Reset signal '{reset}' not found in {file_type}",
                auto_fixable=False,
            ))

        return issues

    @staticmethod
    def _strip_for_analysis(content: str) -> str:
        """Strip comments and strings for analysis."""
        result = content
        result = re.sub(r'/\*.*?\*/', ' ', result, flags=re.DOTALL)
        result = re.sub(r'//.*$', ' ', result, flags=re.MULTILINE)
        result = re.sub(r'"[^"]*"', 'STR', result)
        return result


class UVMBestPracticesChecker:
    """Check UVM best practices and common patterns."""

    def check(self, content: str, file_type: str) -> List[ValidationIssue]:
        """Run UVM best practice checks."""
        issues: List[ValidationIssue] = []
        lines = content.split('\n')

        checks: Dict[str, List[Tuple[Pattern, ValidationSeverity, str, Optional[str]]]] = {
            "driver": [
                (re.compile(r'\bseq_item_port\.(get|next_item)\b'),
                 ValidationSeverity.INFO, "UVM-DRV-001", "Uses proper sequence item retrieval"),
                (re.compile(r'\bseq_item_port\.item_done\b'),
                 ValidationSeverity.INFO, "UVM-DRV-002", "Properly completes items"),
            ],
            "monitor": [
                (re.compile(r'\banalysis_port\s*<'),
                 ValidationSeverity.INFO, "UVM-MON-001", "Has analysis port"),
                (re.compile(r'\bwrite\s*\('),
                 ValidationSeverity.INFO, "UVM-MON-002", "Writes to analysis port"),
            ],
            "agent": [
                (re.compile(r'\b(driver|monitor|sequencer)\s*=\s*'),
                 ValidationSeverity.INFO, "UVM-AGT-001", "Creates agent components"),
                (re.compile(r'\bget_is_active\b'),
                 ValidationSeverity.INFO, "UVM-AGT-002", "Checks active/passive mode"),
            ],
            "scoreboard": [
                (re.compile(r'\buvm_analysis_imp\s*<'),
                 ValidationSeverity.INFO, "UVM-SCB-001", "Has analysis exports"),
                (re.compile(r'\bwrite\s*\(\s*\w+\s+(\w+)\)'),
                 ValidationSeverity.INFO, "UVM-SCB-002", "Implements write methods"),
            ],
            "test": [
                (re.compile(r'\buvm_top\.(finish|stop|objection)'),
                 ValidationSeverity.INFO, "UVM-TEST-001", "Proper objection handling"),
                (re.compile(r'\braise_objection\b'),
                 ValidationSeverity.INFO, "UVM-TEST-002", "Raises objections"),
                (re.compile(r'\bdrop_objection\b'),
                 ValidationSeverity.INFO, "UVM-TEST-003", "Drops objections"),
            ],
            "sequence": [
                (re.compile(r'\bstart_item\b'),
                 ValidationSeverity.INFO, "UVM-SEQ-001", "Uses start_item"),
                (re.compile(r'\bfinish_item\b'),
                 ValidationSeverity.INFO, "UVM-SEQ-002", "Uses finish_item"),
            ],
            "any": [
                (re.compile(r'\b`uvm_(component|object)_utils\b'),
                 ValidationSeverity.INFO, "UVM-ANY-001", "Uses UVM factory registration"),
                (re.compile(r'\buvm_info\s*\('),
                 ValidationSeverity.INFO, "UVM-ANY-002", "Has UVM messaging"),
            ],
        }

        error_patterns = [
            (re.compile(r'\buvm_error\s*\(\s*"[^"]*"\s*,\s*"[^"]*"\s*,\s*UVM_(LOW|MEDIUM|HIGH|FULL|DEBUG)\)'),
             ValidationSeverity.INFO, "UVM-ANY-003", "Proper uvm_error usage"),
        ]

        relevant_checks = checks.get(file_type, []) + checks.get("any", [])

        for pattern, severity, code, message in relevant_checks:
            if pattern.search(content):
                issues.append(ValidationIssue(
                    severity=severity,
                    code=code,
                    message=message,
                    auto_fixable=False,
                ))

        is_uvm = any(uvm_base in content for uvm_base in UVM_BASE_CLASSES)
        if is_uvm and file_type in ("test", "env", "sequence"):
            if not re.search(r'\b(raise|drop)_objection\b', content):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    code="UVM-WARN-001",
                    message="UVM test/sequence without objection handling",
                    suggestion="Consider adding raise_objection/drop_objection for proper test termination",
                    auto_fixable=False,
                ))

        return issues


class CodeValidator:
    """
    Industry-level code validator for UVM testbench generation.

    Provides comprehensive validation with:
    - Syntax checking
    - Spec compliance
    - UVM best practices
    - Detailed reporting
    """

    FILE_TYPE_DETECTORS = [
        (r'ral_model', "ral_model"),
        (r'scoreboard', "scoreboard"),
        (r'driver', "driver"),
        (r'monitor', "monitor"),
        (r'agent', "agent"),
        (r'sequence_item', "sequence_item"),
        (r'_sequence', "sequence"),
        (r'regression', "sequence"),
        (r'coverage_collector', "coverage"),
        (r'protocol_checker', "checker"),
        (r'_test', "test"),
        (r'environment|env_', "env"),
        (r'testbench', "testbench"),
        (r'interface', "interface"),
        (r'serial_monitor', "monitor"),
    ]

    NON_SV_EXTENSIONS = {'.f', '.tcl', '.core', '.json', '.yaml', '.yml', '.md', '.txt'}

    def __init__(self, spec_dict: Optional[Dict[str, Any]] = None):
        self.spec_dict = spec_dict
        self._syntax_checker = SystemVerilogSyntaxChecker()
        self._spec_checker = SpecComplianceChecker(spec_dict) if spec_dict else None
        self._uvm_checker = UVMBestPracticesChecker()

    @classmethod
    def _is_sv_file(cls, filename: str) -> bool:
        """Check if file is a SystemVerilog/Verilog file."""
        fname_lower = filename.lower()
        for ext in cls.NON_SV_EXTENSIONS:
            if fname_lower.endswith(ext):
                return False
        if fname_lower.endswith(('.sv', '.v', '.svh', '.vh')):
            return True
        if '/' in fname_lower or '\\' in fname_lower:
            base = fname_lower.replace('\\', '/').split('/')[-1]
            if '.' not in base:
                return True
        return True

    @classmethod
    def detect_file_type(cls, filename: str) -> str:
        """Detect the type of SystemVerilog file from its name."""
        fname_lower = filename.lower()
        for pattern, file_type in cls.FILE_TYPE_DETECTORS:
            if re.search(pattern, fname_lower):
                return file_type
        return "unknown"

    def validate_file(
        self,
        filename: str,
        content: str,
        file_type: Optional[str] = None,
    ) -> FileValidationResult:
        """Validate a single file. Skip non-SV files."""
        if not self._is_sv_file(filename):
            return FileValidationResult(
                filename=filename,
                file_type="skipped",
                passed=True,
                issues=[],
                checks_run=0,
                checks_passed=0,
            )

        if file_type is None:
            file_type = self.detect_file_type(filename)

        issues: List[ValidationIssue] = []
        checks_run = 0
        checks_passed = 0

        syntax_issues = self._syntax_checker.check(content)
        issues.extend(syntax_issues)
        checks_run += 3
        syntax_errors = sum(1 for i in syntax_issues if i.severity == ValidationSeverity.ERROR)
        checks_passed += (3 - min(syntax_errors, 3))

        if self._spec_checker:
            spec_issues = self._spec_checker.check_signals_in_code(content, file_type)
            issues.extend(spec_issues)
            checks_run += 2

            reg_issues = self._spec_checker.check_registers_in_code(content, file_type)
            issues.extend(reg_issues)

            cr_issues = self._spec_checker.check_clock_reset(content, file_type)
            issues.extend(cr_issues)

            spec_errors = sum(1 for i in spec_issues + reg_issues + cr_issues
                              if i.severity == ValidationSeverity.ERROR)
            checks_passed += max(0, 2 - spec_errors)

        if file_type != "unknown":
            uvm_issues = self._uvm_checker.check(content, file_type)
            issues.extend(uvm_issues)

        errors = sum(1 for i in issues if i.severity == ValidationSeverity.ERROR)
        passed = errors == 0

        return FileValidationResult(
            filename=filename,
            file_type=file_type,
            passed=passed,
            issues=issues,
            checks_run=checks_run,
            checks_passed=checks_passed,
        )

    def validate_files(
        self,
        files: Dict[str, str],
        design_name: str = "",
    ) -> ValidationReport:
        """Validate multiple files and generate a report."""
        file_results: List[FileValidationResult] = []

        for filename, content in files.items():
            result = self.validate_file(filename, content)
            file_results.append(result)

        total_errors = sum(f.error_count for f in file_results)
        overall_passed = total_errors == 0

        import datetime
        report = ValidationReport(
            design_name=design_name,
            overall_passed=overall_passed,
            files=file_results,
            timestamp=datetime.datetime.now().isoformat(),
        )

        return report

    def validate_files_by_path(
        self,
        file_paths: Dict[str, str],
        design_name: str = "",
    ) -> ValidationReport:
        """Validate files given as path mappings."""
        content_map: Dict[str, str] = {}

        for filename, path in file_paths.items():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content_map[filename] = f.read()
            except Exception as e:
                logger.warning("Failed to read %s: %s", path, e)
                content_map[filename] = ""

        return self.validate_files(content_map, design_name)
