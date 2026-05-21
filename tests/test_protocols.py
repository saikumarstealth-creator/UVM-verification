# tests/test_protocols.py — Tests for protocol library

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.generation.protocols import ProtocolLibrary


def test_protocol_library_available():
    lib = ProtocolLibrary()
    protocols = lib.list_available()
    assert "uart" in protocols
    assert "spi" in protocols
    assert "i2c" in protocols
    assert "axi4lite" in protocols
    assert "apb" in protocols
    assert "wishbone" in protocols


def test_uart_protocol():
    lib = ProtocolLibrary()
    uart = lib.load("uart")
    assert uart["protocol"] == "uart"
    signals = lib.get_signals("uart")
    names = {s["name"] for s in signals}
    assert "srx" in names
    assert "stx" in names
    registers = lib.get_registers("uart")
    reg_names = {r["name"] for r in registers}
    assert "LCR" in reg_names
    assert "LSR" in reg_names
    body = lib.get_sequence_body("uart")
    assert "drv.write_reg" in body


def test_spi_protocol():
    lib = ProtocolLibrary()
    spi = lib.load("spi")
    assert spi["protocol"] == "spi"
    signals = lib.get_signals("spi")
    names = {s["name"] for s in signals}
    assert "sclk" in names
    assert "mosi" in names
    assert "miso" in names
    assert "ss_n" in names


def test_i2c_protocol():
    lib = ProtocolLibrary()
    i2c = lib.load("i2c")
    assert i2c["protocol"] == "i2c"
    signals = lib.get_signals("i2c")
    names = {s["name"] for s in signals}
    assert "scl" in names
    assert "sda" in names


def test_axi4lite_protocol():
    lib = ProtocolLibrary()
    axi = lib.load("axi4lite")
    assert axi["protocol"] == "axi4lite"
    signals = lib.get_signals("axi4lite")
    names = {s["name"] for s in signals}
    assert "awvalid" in names
    assert "awready" in names
    assert "wdata" in names
    assert "rdata" in names
    assert "bresp" in names


def test_protocol_library_cache():
    lib = ProtocolLibrary()
    p1 = lib.load("uart")
    p2 = lib.load("uart")
    assert p1 is p2  # same object from cache


def test_protocol_coverage_templates():
    lib = ProtocolLibrary()
    for proto in lib.list_available():
        coverage = lib.get_coverage(proto)
        assert len(coverage) >= 1, f"{proto} should have at least 1 coverage item"
        assert coverage[0]["type"] == "covergroup"


def test_protocol_config_parameters():
    lib = ProtocolLibrary()
    params = lib.get_config_parameters("uart")
    param_names = {p["name"] for p in params}
    assert "DATA_BITS" in param_names
    assert "STOP_BITS" in param_names
    assert "PARITY" in param_names
