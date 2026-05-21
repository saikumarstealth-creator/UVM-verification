import yaml from "js-yaml";

const PROTOCOLS = ["uart", "spi", "i2c", "axi4lite", "apb", "wishbone", "custom"];

const DEFAULT_YAML = `# UART 16550 Core Specification
design_name: uart16550
version: "1.5"
vendor: "DV Automation"
description: "Universal Asynchronous Receiver-Transmitter"
clock_reset:
  clock: clk
  reset: rst_n
  reset_active: 0
interfaces:
  - name: bus
    protocol: wishbone
    signals:
      - { name: addr,    direction: input,  width: 3 }
      - { name: data_in, direction: input,  width: 8 }
      - { name: data_out,direction: output, width: 8 }
      - { name: we,      direction: input,  width: 1 }
      - { name: irq,     direction: output, width: 1 }
  - name: serial
    protocol: uart
    signals:
      - { name: srx, direction: input,  width: 1 }
      - { name: stx, direction: output, width: 1 }
registers:
  - name: LCR
    address: '0x03'
    access: rw
    fields:
      - { name: wls,  bits: '1:0', description: "Word length" }
      - { name: stb,  bits: '2',   description: "Stop bits" }
      - { name: dlab, bits: '7',   description: "Divisor latch" }
  - name: LSR
    address: '0x05'
    access: ro
    fields:
      - { name: dr,   bits: '0', description: "Data ready" }
      - { name: thre, bits: '5', description: "THR empty" }
`;

export function parseYAML(text) {
  const doc = yaml.load(text);
  return doc || {};
}

export function validateYAML(text) {
  const errors = [];
  try {
    const doc = yaml.load(text);
    if (!doc || typeof doc !== "object") {
      errors.push("Root must be a YAML mapping (object)");
      return errors;
    }
    if (!doc.design_name) errors.push("Missing required field: design_name");
    if (!doc.interfaces || !doc.interfaces.length)
      errors.push("At least one interface required");
    if (doc.interfaces) {
      doc.interfaces.forEach((iface, i) => {
        if (!iface.name) errors.push(`Interface #${i + 1} missing name`);
        if (!Array.isArray(iface.signals) || iface.signals.length === 0)
          errors.push(`Interface "${iface.name || "#" + (i + 1)}" has no signals`);
      });
    }
    if (doc.registers) {
      doc.registers.forEach((reg, i) => {
        if (!reg.name) errors.push(`Register #${i + 1} missing name`);
        if (!reg.address) errors.push(`Register "${reg.name || "#" + (i + 1)}" missing address`);
        if (reg.address && !/^0x[0-9a-fA-F]+$/.test(String(reg.address)))
          errors.push(`Register "${reg.name}" address should be hex (0x...)`);
      });
    }
  } catch (e) {
    errors.push(`YAML parse error: ${e.message}`);
  }
  return errors;
}

export function toYAML(obj) {
  return yaml.dump(obj, { indent: 2, lineWidth: 120, noRefs: true });
}

export { PROTOCOLS, DEFAULT_YAML };
