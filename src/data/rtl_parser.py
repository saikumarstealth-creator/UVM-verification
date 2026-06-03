from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from src.data.preprocessor import SpecPreprocessor, PROTOCOL_SIGNATURES


class RTLParser:
    """Parses Verilog RTL files into DesignSpec-compatible dictionaries.

    Extracts:
      - Module name / ports
      - Registers from always_ff blocks and reg/logic declarations
      - Register addresses from case statements (address decoding)
      - Parameters
      - Protocol auto-detection from port names
    """

    SKIP_REGISTERS = {'i', 'j', 'k', 'idx', 'tmp', 'temp', 'clk', 'clock',
                      'rst', 'rst_n', 'reset', 'reset_n', 'counter', 'count'}

    def parse(self, content: str) -> Dict[str, Any]:
        raw: Dict[str, Any] = {
            "design_name": "unknown",
            "clock_reset": {"clock": "clk", "reset": "rst_n", "reset_active": 0},
            "interfaces": [],
            "registers": [],
            "parameters": {},
        }
        text = self._strip_comments(content)

        ports = self._extract_ports(text)
        port_names = {p['name'] for p in ports}

        raw["design_name"] = self._extract_module_name(text)
        raw["interfaces"] = [{"name": "bus", "signals": ports}]
        raw["registers"] = self._extract_registers(text, port_names)
        raw["parameters"] = self._extract_parameters(text)
        raw["clock_reset"] = self._extract_clock_reset(port_names)
        raw = self._detect_protocol_from_ports(port_names, raw)
        return SpecPreprocessor().preprocess(raw)

    @staticmethod
    def _strip_comments(content: str) -> str:
        text = re.sub(r'//.*', '', content)
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
        return text

    @staticmethod
    def _extract_module_name(content: str) -> str:
        m = re.search(r'\bmodule\s+(\w+)', content, re.IGNORECASE)
        return m.group(1).lower() if m else "unknown"

    @staticmethod
    def _extract_ports(text: str) -> List[Dict[str, Any]]:
        ports_dict: Dict[str, Dict[str, Any]] = {}

        module_match = re.search(
            r'\bmodule\s+\w+\s*(?:#\s*\(.*?\))?\s*\(',
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if module_match:
            start = module_match.end()
            depth = 1
            i = start
            while i < len(text) and depth > 0:
                if text[i] == '(':
                    depth += 1
                elif text[i] == ')':
                    depth -= 1
                i += 1
            port_list_text = text[start:i-1]
        else:
            port_list_text = ""

        # ANSI-style: input logic [7:0] sig, output logic sig, ...
        for m in re.finditer(
            r'(input|output|inout)\s+'
            r'(?:wire|reg|logic|tri|wand|wor|signed|unsigned)?(?:\s+logic)?\s*'
            r'(?:\[(\d+):(\d+)\])?\s*'
            r'(\w+)',
            port_list_text,
            re.IGNORECASE,
        ):
            name = m.group(4).lower()
            direction = m.group(1).lower()
            width = 1
            if m.group(2) and m.group(3):
                msb, lsb = int(m.group(2)), int(m.group(3))
                width = abs(msb - lsb) + 1
            ports_dict[name] = {"name": name, "direction": direction, "width": width}

        # Non-ANSI: declarations inside module body
        for m in re.finditer(
            r'(input|output|inout)\s+'
            r'(?:wire|reg|logic|tri)?\s*'
            r'(?:\[(\d+):(\d+)\])?\s*'
            r'(\w+)\s*;',
            text,
            re.IGNORECASE,
        ):
            name = m.group(4).lower()
            if name not in ports_dict:
                direction = m.group(1).lower()
                width = 1
                if m.group(2) and m.group(3):
                    msb, lsb = int(m.group(2)), int(m.group(3))
                    width = abs(msb - lsb) + 1
                ports_dict[name] = {"name": name, "direction": direction, "width": width}

        return list(ports_dict.values())

    @staticmethod
    def _extract_registers(text: str, port_names: Set[str]) -> List[Dict[str, Any]]:
        registers: List[Dict[str, Any]] = []
        reg_names: List[str] = []

        # Find reg/logic declarations inside the module body (not ports)
        for m in re.finditer(
            r'\b(reg|logic)\s+'
            r'(?:\[(\d+):(\d+)\])?\s+'
            r'(\w+)\b',
            text,
            re.IGNORECASE,
        ):
            name = m.group(4).lower()
            if not name or len(name) == 0:
                continue
            if (name not in RTLParser.SKIP_REGISTERS
                    and name not in port_names
                    and not name.startswith('_')):
                reg_names.append(name)

        # Extract addresses from case statements
        addr_map: Dict[str, int] = {}
        for cm in re.finditer(
            r'\bcase\s*\(\s*(\w+)\s*\)\s*(.*?)\s*endcase',
            text,
            re.DOTALL | re.IGNORECASE,
        ):
            case_var = cm.group(1).lower()
            if any(kw in case_var for kw in ['addr', 'address', 'adr']):
                case_body = cm.group(2)
                for item in re.finditer(
                    r"(\d+)'[hHdDbB]\s*([0-9a-fA-FxXzZ]+)\s*:",
                    case_body,
                ):
                    try:
                        addr_val = int(item.group(2), 16)
                    except ValueError:
                        continue
                    after_addr = case_body[item.end():]
                    target_m = re.search(r'(\w+)\s*<=\s*', after_addr)
                    if target_m:
                        target = target_m.group(1).lower()
                        if target not in addr_map:
                            addr_map[target] = addr_val

        # Build register list in declaration order
        seen = set()
        addr = 0
        for name in reg_names:
            if name in seen:
                continue
            seen.add(name)
            reg_addr = addr_map.get(name, addr)
            registers.append({
                "name": name.capitalize(),
                "address": f"0x{reg_addr:02X}",
                "access": "rw",
                "description": f"Auto-extracted register {name}",
                "fields": [],
                "size": 8,
            })
            if name not in addr_map:
                addr += 4

        return registers

    @staticmethod
    def _extract_parameters(text: str) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        for m in re.finditer(
            r'\bparameter\s+(?:integer|real|time)?\s*(\w+)\s*=\s*(\d+)',
            text,
            re.IGNORECASE,
        ):
            name = m.group(1).upper()
            try:
                params[name] = int(m.group(2))
            except ValueError:
                params[name] = m.group(2)

        for pm in re.finditer(r'#\s*\(\s*(.*?)\s*\)', text, re.DOTALL):
            body = pm.group(1)
            for m in re.finditer(
                r'(?:parameter\s+)?(\w+)\s*=\s*(\d+)', body,
            ):
                name = m.group(1).upper()
                try:
                    params[name] = int(m.group(2))
                except ValueError:
                    params[name] = m.group(2)

        return params

    @staticmethod
    def _extract_clock_reset(port_names: Set[str]) -> Dict[str, Any]:
        clock = 'clk' if 'clk' in port_names else 'clock'
        reset = ('rst_n' if 'rst_n' in port_names else
                 'rst' if 'rst' in port_names else 'reset_n')
        reset_active = 0 if '_n' in reset or reset.endswith('n') else 1
        return {"clock": clock, "reset": reset, "reset_active": reset_active}

    @staticmethod
    def _detect_protocol_from_ports(
        port_names: Set[str],
        raw: Dict[str, Any],
    ) -> Dict[str, Any]:
        if raw.get("protocol"):
            return raw
        detected, rank = None, 0
        for proto, sigs in PROTOCOL_SIGNATURES.items():
            matches = sum(1 for kw in sigs if any(kw in s for s in port_names))
            if matches > rank:
                rank, detected = matches, proto
        raw["protocol"] = detected if detected and rank >= 2 else "wishbone"
        return raw

    @staticmethod
    def parse_file(path: str) -> Dict[str, Any]:
        with open(path, 'r') as f:
            return RTLParser().parse(f.read())

    @staticmethod
    def to_yaml(spec: Dict[str, Any]) -> str:
        import yaml
        return yaml.dump(spec, default_flow_style=False, sort_keys=False)
