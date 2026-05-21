from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


PROTOCOL_SIGNATURES = {
    "uart": {"tx", "rx", "baud"},
    "spi": {"mosi", "miso", "sclk", "ss_n", "cs"},
    "i2c": {"scl", "sda"},
    "axi4lite": {"awvalid", "awready", "arvalid", "arready",
                  "wvalid", "wready", "rvalid", "rready",
                  "bvalid", "bready"},
    "apb": {"psel", "penable", "paddr", "pwrite", "pready"},
    "wishbone": {"wb_cyc", "wb_stb", "wb_we", "wb_ack", "wb_addr"},
}


class SpecPreprocessor:
    def preprocess(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        raw = self._normalise_names(raw)
        raw = self._default_clock_reset(raw)
        raw = self._expand_signals(raw)
        raw = self._validate_address_formats(raw)
        raw = self._detect_protocol(raw)
        return raw

    @staticmethod
    def _normalise_names(raw: Dict[str, Any]) -> Dict[str, Any]:
        if "design_name" in raw:
            raw["design_name"] = re.sub(r"[^a-zA-Z0-9_]", "_", raw["design_name"]).lower()
        return raw

    @staticmethod
    def _default_clock_reset(raw: Dict[str, Any]) -> Dict[str, Any]:
        raw.setdefault("clock_reset", {"clock": "clk", "reset": "rst_n", "reset_active": 0})
        return raw

    @staticmethod
    def _expand_signals(raw: Dict[str, Any]) -> Dict[str, Any]:
        for iface in raw.get("interfaces", []):
            for sig in iface.get("signals", []):
                sig.setdefault("width", 1)
        return raw

    @staticmethod
    def _validate_address_formats(raw: Dict[str, Any]) -> Dict[str, Any]:
        for reg in raw.get("registers", []):
            addr = reg.get("address", "0x00")
            if not isinstance(addr, str) or not addr.startswith("0x"):
                reg["address"] = f"0x{int(addr):02X}" if isinstance(addr, int) else f"0x{addr}"
            for field in reg.get("fields", []):
                bits = field.get("bits")
                if bits is not None and not isinstance(bits, str):
                    field["bits"] = str(bits)
        return raw

    @staticmethod
    def _detect_protocol(raw: Dict[str, Any]) -> Dict[str, Any]:
        signal_names = set()
        for iface in raw.get("interfaces", []):
            for sig in iface.get("signals", []):
                signal_names.add(sig.get("name", "").lower())

        if raw.get("protocol"):
            return raw

        detected = None
        rank = 0
        for proto, sigs in PROTOCOL_SIGNATURES.items():
            matches = sum(1 for kw in sigs if any(kw in s for s in signal_names))
            if matches > rank:
                rank = matches
                detected = proto

        if detected and rank >= 2:
            raw["protocol"] = detected
        elif not raw.get("protocol"):
            raw["protocol"] = "wishbone"

        return raw
