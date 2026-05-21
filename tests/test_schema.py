# tests/test_schema.py — Tests for master JSON schema

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_schema_exists():
    schema_path = Path("configs/schema/master_schema.json")
    assert schema_path.exists()
    schema = json.loads(schema_path.read_text())
    assert schema["$id"] is not None
    assert "definitions" in schema
    assert "interface" in schema["definitions"]
    assert "register" in schema["definitions"]
    assert "field" in schema["definitions"]
    assert "signal" in schema["definitions"]


def test_schema_has_required_top_level():
    schema_path = Path("configs/schema/master_schema.json")
    schema = json.loads(schema_path.read_text())
    assert "design_name" in schema.get("properties", {})
    assert "interfaces" in schema.get("properties", {})
    assert "registers" in schema.get("properties", {})
    assert "clock_reset" in schema.get("properties", {})
    assert "required" in schema
    assert "design_name" in schema["required"]
    assert "interfaces" in schema["required"]


def test_schema_defines_all_protocols():
    schema_path = Path("configs/schema/master_schema.json")
    schema = json.loads(schema_path.read_text())
    proto_enum = schema["definitions"]["interface"]["properties"]["protocol"]["enum"]
    assert "uart" in proto_enum
    assert "spi" in proto_enum
    assert "i2c" in proto_enum
    assert "axi" in proto_enum
    assert "axi4" in proto_enum
    assert "apb" in proto_enum
    assert "wishbone" in proto_enum


def test_schema_has_fab_validation_rules():
    schema_path = Path("configs/schema/master_schema.json")
    schema = json.loads(schema_path.read_text())
    props = schema.get("properties", {})
    assert "validation_rules" in props
    rules = props["validation_rules"]
    assert "properties" in rules
    rule_props = rules["properties"]
    assert "require_reset" in rule_props
    assert "address_alignment" in rule_props
    assert "no_reserved_holes" in rule_props


def test_schema_has_interrupts_and_memory_maps():
    schema_path = Path("configs/schema/master_schema.json")
    schema = json.loads(schema_path.read_text())
    props = schema.get("properties", {})
    assert "interrupts" in props
    assert "memory_maps" in props
    assert "assertions" in props
    assert "coverage" in props
