import yaml from "js-yaml";

const PROTOCOLS = ["uart", "spi", "i2c", "axi4lite", "apb", "wishbone", "custom"];

const DEFAULT_YAML = `# UVM Testbench Generator — UART 16550 Example
# Production-ready specification for full UVM TB generation

design_name: uart
protocol: uart
version: "1.5"
vendor: "Verification IP"
description: "16550 Compatible UART Controller"

clock_reset:
  clock: clk
  reset: rst_n
  reset_active: 0

interfaces:
  - name: uart_intf
    signals:
      - { name: wb_cyc,      direction: input,  width: 1, description: "Wishbone cycle" }
      - { name: wb_stb,      direction: input,  width: 1, description: "Wishbone strobe" }
      - { name: wb_we,       direction: input,  width: 1, description: "Write enable" }
      - { name: wb_addr,     direction: input,  width: 3, description: "Address bus" }
      - { name: wb_data_o,   direction: input,  width: 8, description: "Write data" }
      - { name: wb_data_i,   direction: output, width: 8, description: "Read data" }
      - { name: wb_ack,      direction: output, width: 1, description: "Acknowledge" }
      - { name: uart_tx,     direction: output, width: 1, description: "Serial transmit" }
      - { name: uart_rx,     direction: input,  width: 1, description: "Serial receive" }
      - { name: cts_n,       direction: input,  width: 1, description: "Clear to send" }
      - { name: rts_n,       direction: output, width: 1, description: "Request to send" }
      - { name: uart_intr,   direction: output, width: 1, description: "Interrupt output" }

registers:
  - name: RBR_THR
    address: '0x00'
    access: rw
    description: "Receiver Buffer / Transmitter Holding"
    fields:
      - { name: data, bits: '7:0', access: rw, description: "Data byte" }

  - name: IER
    address: '0x01'
    access: rw
    description: "Interrupt Enable Register"
    fields:
      - { name: erbfi, bits: '0', description: "Enable RX data available interrupt" }
      - { name: etbei, bits: '1', description: "Enable TX holding register empty interrupt" }
      - { name: elsi,  bits: '2', description: "Enable RX line status interrupt" }
      - { name: edssi, bits: '3', description: "Enable modem status interrupt" }

  - name: IIR
    address: '0x02'
    access: ro
    description: "Interrupt Identification Register"
    fields:
      - { name: int_id, bits: '3:0', description: "Interrupt type identifier" }

  - name: LCR
    address: '0x03'
    access: rw
    description: "Line Control Register"
    fields:
      - { name: wls,  bits: '1:0', description: "Word length select (5-8 bits)" }
      - { name: stb,  bits: '2',   description: "Stop bits (0=1, 1=1.5/2)" }
      - { name: pen,  bits: '3',   description: "Parity enable" }
      - { name: eps,  bits: '4',   description: "Even parity select" }
      - { name: sp,   bits: '5',   description: "Stick parity" }
      - { name: bc,   bits: '6',   description: "Break control" }
      - { name: dlab, bits: '7',   description: "Divisor latch access bit" }

  - name: MCR
    address: '0x04'
    access: rw
    description: "Modem Control Register"
    fields:
      - { name: dtr,  bits: '0', description: "Data Terminal Ready" }
      - { name: rts,  bits: '1', description: "Request To Send" }
      - { name: out1, bits: '2', description: "Output 1" }
      - { name: out2, bits: '3', description: "Output 2" }
      - { name: loop, bits: '4', description: "Loopback mode enable" }

  - name: LSR
    address: '0x05'
    access: ro
    description: "Line Status Register"
    fields:
      - { name: dr,   bits: '0', description: "Data Ready" }
      - { name: oe,   bits: '1', description: "Overrun Error" }
      - { name: pe,   bits: '2', description: "Parity Error" }
      - { name: fe,   bits: '3', description: "Framing Error" }
      - { name: bi,   bits: '4', description: "Break Interrupt" }
      - { name: thre, bits: '5', description: "TX Holding Register Empty" }
      - { name: temt, bits: '6', description: "Transmitter Empty" }
      - { name: err,  bits: '7', description: "Error in RX FIFO" }

  - name: MSR
    address: '0x06'
    access: ro
    description: "Modem Status Register"
    fields:
      - { name: dcts, bits: '0', description: "Delta Clear To Send" }
      - { name: cts,  bits: '4', description: "Clear To Send" }

  - name: SCR
    address: '0x07'
    access: rw
    description: "Scratch Register"
    fields:
      - { name: scratch, bits: '7:0', description: "Scratch pad for testing" }
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
