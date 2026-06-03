from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional


class IPXACTConverter:
    """Bidirectional converter between DesignSpec YAML and IP-XACT XML (IEEE 1685).

    Handles:
      - memoryMaps → registers → fields
      - addressUnitBits, reset, access policies
      - busInterfaces → ports
      - vendor/library/name/version identification

    Usage:
      # YAML dict (as loaded by DesignSpec) → IP-XACT XML string
      xml_str = IPXACTConverter.to_ipxact(spec_dict)

      # IP-XACT XML string → YAML dict (as DesignSpec expects)
      spec_dict = IPXACTConverter.from_ipxact(xml_str)
    """

    # Access policy mapping: IP-XACT → UVM
    ACCESS_MAP = {
        "read-write": "rw",
        "read-only": "ro",
        "write-only": "wo",
        "read-writeOnce": "rw",
        "readOnce": "ro",
    }

    # Access policy mapping: UVM → IP-XACT
    ACCESS_MAP_REVERSE = {
        "rw": "read-write",
        "ro": "read-only",
        "wo": "write-only",
        "rc": "read-only",
        "w1c": "read-write",
        "w0c": "read-write",
    }

    NS = {
        "ipxact": "http://www.accellera.org/XMLSchema/IPXACT/1685-2014",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    }

    @classmethod
    def to_ipxact(
        cls,
        spec: Dict[str, Any],
        vendor: str = "uvmgen",
        library: str = "UVMGen",
        version: str = "1.0",
    ) -> str:
        """Convert a DesignSpec YAML dict to IP-XACT XML string."""
        design_name = spec.get("design_name", "unknown")
        protocol = spec.get("protocol", "")

        # Root: ipxact:component
        root = ET.Element(
            f"{{{cls.NS['ipxact']}}}component",
            {
                f"{{{cls.NS['xsi']}}}schemaLocation": (
                    "http://www.accellera.org/XMLSchema/IPXACT/1685-2014 "
                    "http://www.accellera.org/XMLSchema/IPXACT/1685-2014/index.xsd"
                ),
            },
        )

        # Identity
        vendor_el = ET.SubElement(root, f"{{{cls.NS['ipxact']}}}vendor")
        vendor_el.text = vendor
        library_el = ET.SubElement(root, f"{{{cls.NS['ipxact']}}}library")
        library_el.text = library
        name_el = ET.SubElement(root, f"{{{cls.NS['ipxact']}}}name")
        name_el.text = design_name
        version_el = ET.SubElement(root, f"{{{cls.NS['ipxact']}}}version")
        version_el.text = version
        bus_type_el = ET.SubElement(root, f"{{{cls.NS['ipxact']}}}busType")
        bus_type_el.text = protocol or "unknown"

        # Description
        desc = ET.SubElement(root, f"{{{cls.NS['ipxact']}}}description")
        desc.text = f"UVM Generator: {design_name} ({protocol})"

        # Parameters
        params = ET.SubElement(root, f"{{{cls.NS['ipxact']}}}parameters")
        for pname, pval in spec.get("parameters", {}).items():
            param = ET.SubElement(
                params, f"{{{cls.NS['ipxact']}}}parameter"
            )
            param.set("parameterId", pname)
            param.set("type", "integer")
            name_el2 = ET.SubElement(param, f"{{{cls.NS['ipxact']}}}name")
            name_el2.text = pname
            val_el = ET.SubElement(param, f"{{{cls.NS['ipxact']}}}value")
            val_el.text = str(pval)

        # Memory maps → registers
        mem_maps = ET.SubElement(
            root, f"{{{cls.NS['ipxact']}}}memoryMaps"
        )
        mem_map = ET.SubElement(
            mem_maps, f"{{{cls.NS['ipxact']}}}memoryMap"
        )
        mem_map_name = ET.SubElement(
            mem_map, f"{{{cls.NS['ipxact']}}}name"
        )
        mem_map_name.text = f"{design_name}_memory_map"

        for reg in spec.get("registers", []):
            addr_str = reg.get("address", "0x0").lstrip("0x").rstrip("h")
            try:
                addr = int(addr_str, 16) if addr_str else 0
            except ValueError:
                addr = 0
            reg_width = reg.get("size", 8)
            access = reg.get("access", "rw").lower()

            addr_block = ET.SubElement(
                mem_map, f"{{{cls.NS['ipxact']}}}addressBlock"
            )
            ab_name = ET.SubElement(
                addr_block, f"{{{cls.NS['ipxact']}}}name"
            )
            ab_name.text = reg.get("name", "unnamed")
            ab_base = ET.SubElement(
                addr_block, f"{{{cls.NS['ipxact']}}}baseAddress"
            )
            ab_base.text = f"'h{addr:08X}"
            ab_range = ET.SubElement(
                addr_block, f"{{{cls.NS['ipxact']}}}range"
            )
            # Range in bytes: stride * register count, default 1 reg
            ab_range.text = str(max(reg_width // 8, 1))
            ab_width = ET.SubElement(
                addr_block, f"{{{cls.NS['ipxact']}}}width"
            )
            ab_width.text = str(reg_width)
            ab_access = ET.SubElement(
                addr_block, f"{{{cls.NS['ipxact']}}}access"
            )
            ab_access.text = cls.ACCESS_MAP_REVERSE.get(
                access, "read-write"
            )

            # Fields
            fields = reg.get("fields", [])
            if fields:
                fields_el = ET.SubElement(
                    addr_block, f"{{{cls.NS['ipxact']}}}field"
                )
                # Nest multiple fields
                for field in fields:
                    f_name = field.get("name", "unnamed")
                    f_bits = field.get("bits", "0")
                    f_desc = field.get("description", "")
                    f_access = field.get("access", access)

                    f_el = ET.SubElement(
                        fields_el, f"{{{cls.NS['ipxact']}}}field"
                    )
                    fn = ET.SubElement(
                        f_el, f"{{{cls.NS['ipxact']}}}name"
                    )
                    fn.text = f_name
                    fd = ET.SubElement(
                        f_el, f"{{{cls.NS['ipxact']}}}description"
                    )
                    fd.text = f_desc

                    if ":" in f_bits:
                        parts = f_bits.split(":")
                        msb = int(parts[0])
                        lsb = int(parts[1])
                    else:
                        lsb = int(f_bits)
                        msb = lsb

                    f_bit_offset = ET.SubElement(
                        f_el, f"{{{cls.NS['ipxact']}}}bitOffset"
                    )
                    f_bit_offset.text = str(lsb)
                    f_bit_width = ET.SubElement(
                        f_el, f"{{{cls.NS['ipxact']}}}bitWidth"
                    )
                    f_bit_width.text = str(msb - lsb + 1)
                    f_acc = ET.SubElement(
                        f_el, f"{{{cls.NS['ipxact']}}}access"
                    )
                    f_acc.text = cls.ACCESS_MAP_REVERSE.get(
                        f_access.lower(), "read-write"
                    )

                    # Reset
                    f_reset = field.get("reset") or reg.get("reset_value")
                    if f_reset:
                        reset_el = ET.SubElement(
                            f_el, f"{{{cls.NS['ipxact']}}}reset"
                        )
                        rst_type = ET.SubElement(
                            reset_el,
                            f"{{{cls.NS['ipxact']}}}type",
                        )
                        rst_type.text = "reset"
                        rst_val = ET.SubElement(
                            reset_el,
                            f"{{{cls.NS['ipxact']}}}value",
                        )
                        rst_val.text = f"'h{f_reset}"

        # Bus interfaces → ports
        interfaces = spec.get("interfaces", [])
        if interfaces:
            bus_interfaces = ET.SubElement(
                root, f"{{{cls.NS['ipxact']}}}busInterfaces"
            )
            for intf in interfaces:
                bi = ET.SubElement(
                    bus_interfaces, f"{{{cls.NS['ipxact']}}}busInterface"
                )
                bi_name = ET.SubElement(
                    bi, f"{{{cls.NS['ipxact']}}}name"
                )
                bi_name.text = intf.get("name", "bus")
                bi_type = ET.SubElement(
                    bi, f"{{{cls.NS['ipxact']}}}busType"
                )
                bi_type.set("vendor", vendor)
                bi_type.set("library", library)
                bi_type.set("name", protocol or "bus")
                bi_type.set("version", version)

                # Ports → abstraction
                ports = intf.get("signals", [])
                if ports:
                    ports_el = ET.SubElement(
                        root, f"{{{cls.NS['ipxact']}}}ports"
                    )
                    for port in ports:
                        p_el = ET.SubElement(
                            ports_el, f"{{{cls.NS['ipxact']}}}port"
                        )
                        pn = ET.SubElement(
                            p_el, f"{{{cls.NS['ipxact']}}}name"
                        )
                        pn.text = port.get("name", "sig")
                        pdir = ET.SubElement(
                            p_el, f"{{{cls.NS['ipxact']}}}direction"
                        )
                        pdir.text = port.get("direction", "inout")
                        pw = port.get("width", 1)
                        if pw and pw != 1:
                            pw_el = ET.SubElement(
                                p_el,
                                f"{{{cls.NS['ipxact']}}}vector",
                            )
                            left = ET.SubElement(
                                pw_el,
                                f"{{{cls.NS['ipxact']}}}left",
                            )
                            left.text = str(pw - 1)
                            right = ET.SubElement(
                                pw_el,
                                f"{{{cls.NS['ipxact']}}}right",
                            )
                            right.text = "0"

        return ET.tostring(root, encoding="unicode", xml_declaration=True)

    @classmethod
    def from_ipxact(cls, xml_str: str) -> Dict[str, Any]:
        """Parse IP-XACT XML string → DesignSpec YAML dict."""
        root = ET.fromstring(xml_str)
        ns = cls.NS["ipxact"]
        spec: Dict[str, Any] = {
            "design_name": "unknown",
            "protocol": "",
            "interfaces": [],
            "registers": [],
            "parameters": {},
        }

        # Identity
        name_el = root.find(f"{{{ns}}}name")
        if name_el is not None and name_el.text:
            spec["design_name"] = name_el.text

        bus_type = root.find(f"{{{ns}}}busType")
        if bus_type is not None and bus_type.text:
            spec["protocol"] = bus_type.text

        # Parameters
        for param in root.findall(f".//{{{ns}}}parameter"):
            pname = param.find(f"{{{ns}}}name")
            pval = param.find(f"{{{ns}}}value")
            if pname is not None and pname.text and pval is not None and pval.text:
                try:
                    spec["parameters"][pname.text] = int(pval.text)
                except ValueError:
                    spec["parameters"][pname.text] = pval.text

        # Ports
        ports = []
        for port in root.findall(f".//{{{ns}}}port"):
            pname = port.find(f"{{{ns}}}name")
            pdir = port.find(f"{{{ns}}}direction")
            if pname is not None and pname.text:
                pw = 1
                vec = port.find(f"{{{ns}}}vector")
                if vec is not None:
                    left = vec.find(f"{{{ns}}}left")
                    right = vec.find(f"{{{ns}}}right")
                    if left is not None and right is not None:
                        try:
                            pw = abs(int(left.text or "0") - int(right.text or "0")) + 1
                        except (ValueError, TypeError):
                            pw = 1
                ports.append(
                    {
                        "name": pname.text,
                        "direction": pdir.text if pdir is not None else "inout",
                        "width": pw,
                    }
                )
        if ports:
            spec["interfaces"] = [{"name": "bus", "signals": ports}]

        # Registers (from addressBlocks)
        registers = []
        for ab in root.findall(f".//{{{ns}}}addressBlock"):
            ab_name = ab.find(f"{{{ns}}}name")
            ab_base = ab.find(f"{{{ns}}}baseAddress")
            ab_width = ab.find(f"{{{ns}}}width")
            ab_access = ab.find(f"{{{ns}}}access")

            reg_name = ab_name.text if ab_name is not None and ab_name.text else "unnamed"
            addr_str = "0x0"
            if ab_base is not None and ab_base.text:
                m = re.search(r"'[hH]([0-9a-fA-F]+)", ab_base.text)
                if m:
                    addr_str = f"0x{m.group(1).upper()}"
            width = 8
            if ab_width is not None and ab_width.text:
                try:
                    width = int(ab_width.text)
                except (ValueError, TypeError):
                    pass
            access = "rw"
            if ab_access is not None and ab_access.text:
                access = cls.ACCESS_MAP.get(ab_access.text.lower(), "rw")

            fields = []
            for field_el in ab.findall(f".//{{{ns}}}field"):
                fname = field_el.find(f"{{{ns}}}name")
                f_offset = field_el.find(f"{{{ns}}}bitOffset")
                f_width = field_el.find(f"{{{ns}}}bitWidth")
                f_desc = field_el.find(f"{{{ns}}}description")
                f_access_el = field_el.find(f"{{{ns}}}access")
                f_reset_el = field_el.find(f".//{{{ns}}}reset/{{{ns}}}value")

                if fname is not None and fname.text:
                    lsb = 0
                    if f_offset is not None and f_offset.text:
                        try:
                            lsb = int(f_offset.text)
                        except (ValueError, TypeError):
                            lsb = 0
                    fw = 1
                    if f_width is not None and f_width.text:
                        try:
                            fw = int(f_width.text)
                        except (ValueError, TypeError):
                            fw = 1
                    bits = f"{lsb + fw - 1}:{lsb}" if fw > 1 else str(lsb)

                    field_dict: Dict[str, Any] = {
                        "name": fname.text,
                        "bits": bits,
                    }
                    if f_desc is not None and f_desc.text:
                        field_dict["description"] = f_desc.text
                    if f_access_el is not None and f_access_el.text:
                        field_dict["access"] = cls.ACCESS_MAP.get(
                            f_access_el.text.lower(), "rw"
                        )
                    if f_reset_el is not None and f_reset_el.text:
                        m2 = re.search(r"'[hH]([0-9a-fA-F]+)", f_reset_el.text)
                        if m2:
                            field_dict["reset"] = m2.group(1)
                    fields.append(field_dict)

            reg_entry: Dict[str, Any] = {
                "name": reg_name,
                "address": addr_str,
                "size": width,
                "access": access,
                "fields": fields,
            }

            # Register-level reset
            for reset_el in ab.findall(f".//{{{ns}}}reset/{{{ns}}}value"):
                if reset_el.text:
                    m2 = re.search(r"'[hH]([0-9a-fA-F]+)", reset_el.text)
                    if m2:
                        reg_entry["reset_value"] = m2.group(1)

            registers.append(reg_entry)

        if registers:
            spec["registers"] = registers

        return spec
