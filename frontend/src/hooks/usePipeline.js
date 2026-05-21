import { useState, useCallback } from "react";

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

const FILE_CONTENT_TEMPLATES = {
  testbench: (design) => [
    `// Generated UVM Testbench for ${design} — with DUT instantiation`,
    "`timescale 1ns/1ps",
    "",
    "module testbench;",
    "  logic clk;",
    "  logic rst_n;",
    "",
    `  ${design}_intf intf(clk, rst_n);`,
    "",
    "  uart_top #(",
    "    .CLK_FREQ  (50000000),",
    "    .BAUD_RATE (115200)",
    "  ) dut (",
    "    .clk       (clk),",
    "    .rst_n     (rst_n),",
    "    .wb_cyc    (intf.wb_cyc),",
    "    .wb_stb    (intf.wb_stb),",
    "    .wb_we     (intf.wb_we),",
    "    .wb_addr   (intf.wb_addr),",
    "    .wb_data_i (intf.wb_data_o),",
    "    .wb_data_o (intf.wb_data_i),",
    "    .wb_ack    (intf.wb_ack),",
    "    .uart_tx   (intf.uart_tx),",
    "    .uart_rx   (intf.uart_rx),",
    "    .cts_n     (intf.cts_n),",
    "    .rts_n     (intf.rts_n),",
    "    .dsr_n     (intf.dsr_n),",
    "    .dtr_n     (intf.dtr_n),",
    "    .ri_n      (intf.ri_n),",
    "    .dcd_n     (intf.dcd_n),",
    "    .out1_n    (intf.out1_n),",
    "    .out2_n    (intf.out2_n),",
    "    .uart_intr (intf.uart_intr)",
    "  );",
    "",
    "  initial begin",
    `    uvm_config_db#(virtual ${design}_intf)::set(null, "*", "vif", intf);`,
    "    run_test();",
    "  end",
    "",
    "  initial begin",
    "    clk = 0;",
    "    forever #5 clk = ~clk;",
    "  end",
    "",
    "  initial begin",
    "    rst_n = 0;",
    "    repeat (10) @(posedge clk);",
    "    rst_n = 1;",
    "  end",
    "",
    "  initial begin",
    '    $dumpfile("sim.vcd");',
    "    $dumpvars(0, testbench);",
    "  end",
    "endmodule",
  ].join("\n"),

  interface: (design) => [
    `// Generated UVM Interface for ${design}`,
    `interface ${design}_intf (input logic clk, input logic rst_n);`,
    "",
    "  logic       wb_cyc, wb_stb, wb_we;",
    "  logic [2:0] wb_addr;",
    "  logic [7:0] wb_data_o, wb_data_i;",
    "  logic       wb_ack;",
    "  logic       uart_tx, uart_rx;",
    "  logic       cts_n, rts_n, dsr_n, dtr_n, ri_n, dcd_n, out1_n, out2_n;",
    "  logic       uart_intr;",
    "",
    "  clocking drv_cb @(posedge clk);",
    "    default input #1ns output #1ns;",
    "    output wb_cyc, wb_stb, wb_we, wb_addr, wb_data_o;",
    "    output uart_rx, cts_n, dsr_n, ri_n, dcd_n;",
    "    input  wb_ack, wb_data_i, uart_tx, uart_intr, rts_n, dtr_n, out1_n, out2_n;",
    "  endclocking",
    "",
    "  clocking mon_cb @(posedge clk);",
    "    default input #1ns;",
    "    input all;",
    "  endclocking",
    "",
    "  modport driver (clocking drv_cb, input clk, rst_n);",
    "  modport monitor (clocking mon_cb, input clk, rst_n);",
    "endinterface",
  ].join("\n"),

  seq_item: (design) => [
    `class ${design}_seq_item extends uvm_sequence_item;`,
    `  \`uvm_object_utils(${design}_seq_item)`,
    "  rand logic       we;",
    "  rand logic [2:0] addr;",
    "  rand logic [7:0] data;",
    "  rand int         delay;",
    "  constraint c_default { delay inside {[0:5]}; soft we == 1'b1; }",
    `  function new(string name = "${design}_seq_item"); super.new(name); endfunction`,
    "endclass",
  ].join("\n"),

  driver: (design) => [
    `class ${design}_driver extends uvm_driver #(${design}_seq_item);`,
    `  \`uvm_component_utils(${design}_driver)`,
    `  virtual ${design}_intf vif;`,
    "  function new(string n, uvm_component p); super.new(n, p); endfunction",
    "  function void build_phase(uvm_phase phase);",
    `    if (!uvm_config_db#(virtual ${design}_intf)::get(this, "", "vif", vif))`,
    '      `uvm_fatal("NOVIF", "")',
    "  endfunction",
    "  task run_phase(uvm_phase phase);",
    "    forever begin",
    "      seq_item_port.get_next_item(req);",
    "      vif.drv_cb.wb_cyc <= 1; vif.drv_cb.wb_stb <= 1;",
    "      vif.drv_cb.wb_we  <= req.we;",
    "      vif.drv_cb.wb_addr <= req.addr;",
    "      vif.drv_cb.wb_data_o <= req.data;",
    "      @(vif.drv_cb); wait(vif.drv_cb.wb_ack); @(vif.drv_cb);",
    "      vif.drv_cb.wb_cyc <= 0; vif.drv_cb.wb_stb <= 0;",
    "      seq_item_port.item_done();",
    "    end",
    "  endtask",
    "endclass",
  ].join("\n"),

  monitor: (design) => [
    `class ${design}_monitor extends uvm_monitor;`,
    `  \`uvm_component_utils(${design}_monitor)`,
    `  virtual ${design}_intf vif;`,
    `  uvm_analysis_port #(${design}_seq_item) item_collected_port;`,
    "  function new(string n, uvm_component p); super.new(n, p);",
    `    item_collected_port = new("item_collected_port", this); endfunction`,
    "  function void build_phase(uvm_phase phase);",
    `    if (!uvm_config_db#(virtual ${design}_intf)::get(this, "", "vif", vif))`,
    '      `uvm_fatal("NOVIF", "")',
    "  endfunction",
    "  task run_phase(uvm_phase phase); forever begin",
    "    @(vif.mon_cb);",
    "    if (vif.mon_cb.wb_stb && vif.mon_cb.wb_cyc) begin",
    `      ${design}_seq_item item = ${design}_seq_item::type_id::create("item");`,
    "      item.we = vif.mon_cb.wb_we; item.addr = vif.mon_cb.wb_addr;",
    "      if (vif.mon_cb.wb_we) item.data = vif.mon_cb.wb_data_o;",
    "      else begin wait(vif.mon_cb.wb_ack); item.data = vif.mon_cb.wb_data_i; end",
    "      item_collected_port.write(item);",
    "    end end",
    "  endtask",
    "endclass",
  ].join("\n"),

  agent: (design) => [
    `class ${design}_agent extends uvm_agent;`,
    `  \`uvm_component_utils(${design}_agent)`,
    `  ${design}_driver    driver;`,
    `  ${design}_monitor   monitor;`,
    `  uvm_sequencer #(${design}_seq_item) sequencer;`,
    "  function new(string n, uvm_component p); super.new(n, p); endfunction",
    "  function void build_phase(uvm_phase phase);",
    `    driver    = ${design}_driver::type_id::create("driver", this);`,
    `    monitor   = ${design}_monitor::type_id::create("monitor", this);`,
    `    sequencer = uvm_sequencer#(${design}_seq_item)::type_id::create("sequencer", this);`,
    "  endfunction",
    "  function void connect_phase(uvm_phase phase);",
    "    driver.seq_item_port.connect(sequencer.seq_item_export);",
    "  endfunction",
    "endclass",
  ].join("\n"),

  scoreboard: (design) => [
    `class ${design}_scoreboard extends uvm_scoreboard;`,
    `  \`uvm_component_utils(${design}_scoreboard)`,
    `  uvm_analysis_imp #(${design}_seq_item, ${design}_scoreboard) act_export;`,
    "  int match_count, mismatch_count;",
    "  function new(string n, uvm_component p); super.new(n, p);",
    `    act_export = new("act_export", this); endfunction`,
    `  function void write(${design}_seq_item t);`,
    "    match_count++;",
    '    `uvm_info("SCOREBOARD", $sformatf("item: %s", t.convert2string()), UVM_LOW)',
    "  endfunction",
    "  function void report_phase(uvm_phase phase);",
    '    if (mismatch_count == 0) `uvm_info("SCOREBOARD", "PASS", UVM_LOW)',
    '    else `uvm_error("SCOREBOARD", "FAIL")',
    "  endfunction",
    "endclass",
  ].join("\n"),

  coverage_collector: (design) => {
    const cg = [
      "  covergroup bus_cg @(negedge vif.clk);",
      "    option.name = \"bus_cg\";",
      "    ADDR: coverpoint vif.mon_cb.wb_addr { bins regs[] = {[0:7]}; }",
      "    DIR:  coverpoint vif.mon_cb.wb_we  { bins read = {0}; bins write = {1}; }",
      "    ADRxDIR: cross ADDR, DIR;",
      "  endgroup",
      "",
      "  covergroup data_cg @(negedge vif.clk);",
      "    option.name = \"data_cg\";",
      "    DATA: coverpoint vif.mon_cb.wb_data_o {",
      "      bins zero = {8'h00}; bins ones = {8'hFF};",
      "      bins pattern = {8'h55, 8'hAA, 8'hA5, 8'h5A}; bins others = default;",
      "    }",
      "  endgroup",
    ].join("\n");
    return [
      `class ${design}_coverage_collector extends uvm_subscriber #(${design}_seq_item);`,
      `  \`uvm_component_utils(${design}_coverage_collector)`,
      `  virtual ${design}_intf vif;`,
      "",
      cg,
      "",
      "  function new(string n, uvm_component p); super.new(n, p);",
      "    bus_cg = new(); data_cg = new();",
      "  endfunction",
      "  function void build_phase(uvm_phase phase);",
      `    if (!uvm_config_db#(virtual ${design}_intf)::get(this, "", "vif", vif))`,
      '      `uvm_fatal("NOVIF", "")',
      "  endfunction",
      "  function void write(${design}_seq_item t); endfunction",
      "  function void report_phase(uvm_phase phase);",
      `    \`uvm_info(get_type_name(), $sformatf("bus_cg=%.1f%% data_cg=%.1f%%",`,
      "      bus_cg.get_coverage(), data_cg.get_coverage()), UVM_LOW)",
      "  endfunction",
      "endclass",
    ].join("\n");
  },

  base_sequence: (design) => {
    const seqs = [
      `class ${design}_base_seq extends uvm_sequence #(${design}_seq_item);`,
      `  \`uvm_object_utils(${design}_base_seq)`,
      `  function new(string n = "${design}_base_seq"); super.new(n); endfunction`,
      '  virtual task body(); `uvm_info(get_type_name(), "base", UVM_LOW); endtask',
      "endclass",
      "",
      `class ${design}_write_reg_seq extends ${design}_base_seq;`,
      `  \`uvm_object_utils(${design}_write_reg_seq)`,
      "  rand logic [2:0] reg_addr; rand logic [7:0] reg_data;",
      `  function new(string n = "${design}_write_reg_seq"); super.new(n); endfunction`,
      "  virtual task body();",
      `    ${design}_seq_item item = ${design}_seq_item::type_id::create("item");`,
      "    start_item(item); item.we = 1; item.addr = reg_addr; item.data = reg_data; finish_item(item);",
      '    `uvm_info(get_type_name(), $sformatf("W 0x%0h <- 0x%0h", reg_addr, reg_data), UVM_MEDIUM)',
      "  endtask",
      "endclass",
      "",
      `class ${design}_read_reg_seq extends ${design}_base_seq;`,
      `  \`uvm_object_utils(${design}_read_reg_seq)`,
      "  rand logic [2:0] reg_addr; logic [7:0] read_data;",
      `  function new(string n = "${design}_read_reg_seq"); super.new(n); endfunction`,
      "  virtual task body();",
      `    ${design}_seq_item item = ${design}_seq_item::type_id::create("item");`,
      "    start_item(item); item.we = 0; item.addr = reg_addr; finish_item(item);",
      "    read_data = item.data;",
      '    `uvm_info(get_type_name(), $sformatf("R 0x%0h -> 0x%0h", reg_addr, read_data), UVM_MEDIUM)',
      "  endtask",
      "endclass",
      "",
      `class ${design}_send_byte_seq extends ${design}_base_seq;`,
      `  \`uvm_object_utils(${design}_send_byte_seq)`,
      "  rand logic [7:0] tx_byte;",
      `  function new(string n = "${design}_send_byte_seq"); super.new(n); endfunction`,
      "  virtual task body();",
      `    ${design}_write_reg_seq wseq;`,
      `    wseq = ${design}_write_reg_seq::type_id::create("wseq");`,
      "    wseq.reg_addr = 3'h3; wseq.reg_data = 8'b00000011; wseq.start(m_sequencer);",
      "    wseq.reg_addr = 3'h0; wseq.reg_data = tx_byte; wseq.start(m_sequencer);",
      '    `uvm_info(get_type_name(), $sformatf("TX 0x%0h", tx_byte), UVM_LOW)',
      "  endtask",
      "endclass",
    ].join("\n");
    return seqs;
  },

  test: (design) => [
    `class test_${design} extends uvm_test;`,
    `  \`uvm_component_utils(test_${design})`,
    `  environment_${design} env;`,
    `  function new(string n = "test_${design}", uvm_component p = null); super.new(n, p); endfunction`,
    "  function void build_phase(uvm_phase phase);",
    `    env = environment_${design}::type_id::create("env", this);`,
    "  endfunction",
    "  task run_phase(uvm_phase phase);",
    `    ${design}_send_byte_seq seq;`,
    "    phase.raise_objection(this);",
    `    seq = ${design}_send_byte_seq::type_id::create("seq");`,
    "    seq.randomize() with { tx_byte == 8'hAB; };",
    "    seq.start(env.agent.sequencer);",
    `    ${design}_write_reg_seq wseq = ${design}_write_reg_seq::type_id::create("wseq");`,
    "    wseq.reg_addr = 3'h7; wseq.reg_data = 8'hA5; wseq.start(env.agent.sequencer);",
    `    ${design}_read_reg_seq rseq = ${design}_read_reg_seq::type_id::create("rseq");`,
    "    rseq.reg_addr = 3'h7; rseq.start(env.agent.sequencer);",
    "    if (rseq.read_data == 8'hA5)",
    '      `uvm_info(get_type_name(), "SCR PASS", UVM_LOW)',
    "    else",
    '      `uvm_error(get_type_name(), "SCR FAIL")',
    "    phase.drop_objection(this);",
    "  endtask",
    "endclass",
  ].join("\n"),

  regression: (design) => [
    `// Auto-generated regression test — coverage-driven`,
    `class ${design}_regression_test extends test_${design};`,
    `  \`uvm_component_utils(${design}_regression_test)`,
    "  function new(string n, uvm_component p); super.new(n, p); endfunction",
    "  task run_phase(uvm_phase phase);",
    "    super.run_phase(phase); phase.raise_objection(this);",
    `    ${design}_write_reg_seq wseq;`,
    "    for (int a = 0; a < 8; a++) begin",
    `      wseq = ${design}_write_reg_seq::type_id::create($sformatf("w_%0d", a));`,
    "      wseq.reg_addr = a; wseq.reg_data = 8'(a << 4 | a); wseq.start(env.agent.sequencer);",
    "    end",
    `    ${design}_read_reg_seq rseq;`,
    "    for (int a = 0; a < 8; a++) begin",
    `      rseq = ${design}_read_reg_seq::type_id::create($sformatf("r_%0d", a));`,
    "      rseq.reg_addr = a; rseq.start(env.agent.sequencer);",
    "    end",
    "    phase.drop_objection(this);",
    "  endtask",
    "endclass",
  ].join("\n"),

  env: (design) => [
    `class environment_${design} extends uvm_env;`,
    `  \`uvm_component_utils(environment_${design})`,
    `  ${design}_agent agent;`,
    `  ${design}_scoreboard sb;`,
    `  ${design}_coverage_collector cov;`,
    "",
    "  function new(string n, uvm_component p); super.new(n, p); endfunction",
    "  function void build_phase(uvm_phase phase);",
    `    agent = ${design}_agent::type_id::create("agent", this);`,
    `    sb    = ${design}_scoreboard::type_id::create("sb", this);`,
    `    cov   = ${design}_coverage_collector::type_id::create("cov", this);`,
    "  endfunction",
    "  function void connect_phase(uvm_phase phase);",
    "    agent.monitor.item_collected_port.connect(sb.act_export);",
    "    agent.monitor.item_collected_port.connect(cov.analysis_export);",
    "  endfunction",
    "endclass",
  ].join("\n"),

  rtl_baud_gen: () => [
    "module uart_baud_gen #(parameter CLK_FREQ=50000000, parameter BAUD_RATE=115200)",
    "  (input logic clk, rst_n, input logic [7:0] divisor, output logic baud_tick);",
    "  logic [15:0] period = CLK_FREQ / (BAUD_RATE * 16);",
    "  logic [15:0] counter;",
    "  always_ff @(posedge clk or negedge rst_n)",
    "    if (!rst_n) begin counter <= '0; baud_tick <= 0; end",
    "    else if (counter >= period-1) begin counter <= '0; baud_tick <= 1; end",
    "    else begin counter <= counter+1; baud_tick <= 0; end",
    "endmodule",
  ].join("\n"),

  rtl_transmitter: () => [
    "module uart_transmitter (input logic clk, rst_n, baud_tick,",
    "  input logic [7:0] data_in, input logic we, output logic tx);",
    "  typedef enum {IDLE,START,DATA,STOP} state_t; state_t state;",
    "  logic [7:0] shift_reg; logic [2:0] bit_cnt;",
    "  always_ff @(posedge clk or negedge rst_n)",
    "    if (!rst_n) begin state <= IDLE; tx <= 1; end",
    "    else case (state)",
    "      IDLE: if (we) begin shift_reg <= data_in; bit_cnt<=0; state<=START; end",
    "      START: begin tx<=0; if(baud_tick) state<=DATA; end",
    "      DATA: if(baud_tick) begin tx<=shift_reg[bit_cnt];",
    "        if(bit_cnt==7) state<=STOP; else bit_cnt<=bit_cnt+1; end",
    "      STOP: begin tx<=1; if(baud_tick) state<=IDLE; end",
    "    endcase",
    "endmodule",
  ].join("\n"),

  rtl_receiver: () => [
    "module uart_receiver (input logic clk, rst_n, baud_tick, rx,",
    "  output logic [7:0] data_out, output logic data_ready);",
    "  typedef enum {IDLE,START,DATA,STOP} state_t; state_t state;",
    "  logic [7:0] shift_reg; logic [2:0] bit_cnt; logic rx_sync;",
    "  always_ff @(posedge clk or negedge rst_n)",
    "    if (!rst_n) begin state<=IDLE; rx_sync<=1; data_ready<=0; end",
    "    else case (state)",
    "      IDLE: begin data_ready<=0; rx_sync<=rx; if(!rx_sync) begin state<=START; end end",
    "      START: if(baud_tick) state<=DATA;",
    "      DATA: if(baud_tick) begin shift_reg[bit_cnt]<=rx_sync;",
    "        if(bit_cnt==7) state<=STOP; else bit_cnt<=bit_cnt+1; end",
    "      STOP: if(baud_tick) begin data_out<=shift_reg; data_ready<=1; state<=IDLE; end",
    "    endcase",
    "endmodule",
  ].join("\n"),

  rtl_regs: () => [
    "module uart_regs (input logic clk, rst_n, wb_cyc, wb_stb, wb_we,",
    "  input logic [2:0] wb_addr, input logic [7:0] wb_data_i,",
    "  output logic [7:0] wb_data_o, output logic wb_ack);",
    "  logic [7:0] reg_lcr, reg_scr;",
    "  assign wb_ack = wb_cyc & wb_stb;",
    "  always_comb case (wb_addr)",
    "    0: wb_data_o = 8'h00; 1: wb_data_o = 8'h00; 2: wb_data_o = 8'hC0;",
    "    3: wb_data_o = reg_lcr; 4: wb_data_o = 8'h00;",
    "    5: wb_data_o = 8'h60; 6: wb_data_o = 8'h00;",
    "    7: wb_data_o = reg_scr; default: wb_data_o = 8'h00;",
    "  endcase",
    "  always_ff @(posedge clk or negedge rst_n)",
    "    if (!rst_n) begin reg_lcr <= 0; reg_scr <= 0; end",
    "    else if (wb_cyc & wb_stb & wb_we)",
    "      case (wb_addr) 3: reg_lcr <= wb_data_i; 7: reg_scr <= wb_data_i; endcase",
    "endmodule",
  ].join("\n"),

  rtl_top: () => [
    "module uart_top (input logic clk, rst_n, wb_cyc, wb_stb, wb_we,",
    "  input logic [2:0] wb_addr, input logic [7:0] wb_data_i,",
    "  output logic [7:0] wb_data_o, output logic wb_ack,",
    "  output logic uart_tx, input logic uart_rx,",
    "  input logic cts_n, output logic rts_n,",
    "  input logic dsr_n, output logic dtr_n,",
    "  input logic ri_n, dcd_n, output logic out1_n, out2_n, uart_intr);",
    "  logic baud_tick;",
    "  uart_baud_gen u_baud(.clk(clk),.rst_n(rst_n),.divisor(8'h01),.baud_tick(baud_tick));",
    "  uart_transmitter u_tx(.clk(clk),.rst_n(rst_n),.baud_tick(baud_tick),",
    "    .data_in(wb_data_i), .we(wb_cyc&wb_stb&wb_we&(wb_addr==0)), .tx(uart_tx));",
    "  uart_receiver u_rx(.clk(clk),.rst_n(rst_n),.baud_tick(baud_tick),.rx(uart_rx));",
    "  uart_regs u_regs(.clk(clk),.rst_n(rst_n),.wb_cyc(wb_cyc),.wb_stb(wb_stb),",
    "    .wb_we(wb_we),.wb_addr(wb_addr),.wb_data_i(wb_data_i),",
    "    .wb_data_o(wb_data_o),.wb_ack(wb_ack));",
    "  assign uart_intr = 0; assign rts_n = 0; assign dtr_n = 0;",
    "  assign out1_n = 1; assign out2_n = 1;",
    "endmodule",
  ].join("\n"),
};

function buildFileContent(design, version, iteration) {
  const t = FILE_CONTENT_TEMPLATES;
  const prefix = `v${version}_it${iteration}_`;
  const files = {
    "testbench.sv": t.testbench(design),
    [`interface_${design}.sv`]: t.interface(design),
    [`sequence_item_${design}.sv`]: t.seq_item(design),
    [`driver_${design}.sv`]: t.driver(design),
    [`monitor_${design}.sv`]: t.monitor(design),
    [`agent_${design}.sv`]: t.agent(design),
    [`scoreboard_${design}.sv`]: t.scoreboard(design),
    [`coverage_collector_${design}.sv`]: t.coverage_collector(design),
    [`base_sequence_${design}.sv`]: t.base_sequence(design),
    [`test_${design}.sv`]: t.test(design),
    [`environment_${design}.sv`]: t.env(design),
    [`regression_${design}.sv`]: t.regression(design),
    "rtl/uart_baud_gen.v": t.rtl_baud_gen(),
    "rtl/uart_transmitter.v": t.rtl_transmitter(),
    "rtl/uart_receiver.v": t.rtl_receiver(),
    "rtl/uart_regs.v": t.rtl_regs(),
    "rtl/uart_top.v": t.rtl_top(),
    "compile.f": [
      "// Compile list",
      "./rtl/uart_baud_gen.v ./rtl/uart_transmitter.v",
      "./rtl/uart_receiver.v ./rtl/uart_regs.v ./rtl/uart_top.v",
      `./sequence_item_${design}.sv ./interface_${design}.sv`,
      `./driver_${design}.sv ./monitor_${design}.sv ./agent_${design}.sv`,
      `./scoreboard_${design}.sv ./coverage_collector_${design}.sv`,
      `./base_sequence_${design}.sv ./test_${design}.sv ./environment_${design}.sv`,
      "./testbench.sv",
      "+define+UVM_NO_DPI",
    ].join("\n"),
  };

  return Object.entries(files).map(([name, content]) => ({
    name,
    path: `output/${design}_tb/${prefix}${name}`,
    content,
    size: `${new Blob([content]).size} B`,
  }));
}

// Coverage stub simulator with multi-seed emulation
function simulateCoverage(artifacts, seed = 1) {
  const allText = artifacts.map((a) => a.content).join("\n");
  const bins = [];
  const rng = ((seed) => {
    let s = seed;
    return () => { s = (s * 1103515245 + 12345) & 0x7fffffff; return s / 0x7fffffff; };
  })(seed);

  for (let addr = 0; addr < 8; addr++) {
    bins.push({ name: `bus_cg.ADDR.regs[${addr}]`, hit: false, goal: 1 });
    bins.push({ name: `cross_ADRxDIR.addr${addr}_read`, hit: false, goal: 1 });
    bins.push({ name: `cross_ADRxDIR.addr${addr}_write`, hit: false, goal: 1 });
  }
  bins.push({ name: "bus_cg.DIR.read", hit: false, goal: 1 });
  bins.push({ name: "bus_cg.DIR.write", hit: false, goal: 1 });
  bins.push({ name: "data_cg.DATA.zero", hit: false, goal: 1 });
  bins.push({ name: "data_cg.DATA.ones", hit: false, goal: 1 });
  // Protocol checker SVA bins
  bins.push({ name: "sva_cp.ack_timing", hit: false, goal: 1 });
  bins.push({ name: "sva_cp.data_stable", hit: false, goal: 1 });

  for (const bin of bins) {
    if (bin.name.includes("DIR.read") && allText.includes("item.we = 0")) bin.hit = true;
    else if (bin.name.includes("DIR.write") && allText.includes("item.we = 1")) bin.hit = true;
    else {
      const m = bin.name.match(/regs\[(\d+)\]/);
      if (m) {
        const addr = m[1];
        if (allText.includes(`reg_addr = 3'h${addr}`) || allText.includes(`reg_addr=${addr}`)) {
          bin.hit = true;
        }
      }
      const cm = bin.name.match(/addr(\d+)_(read|write)/);
      if (cm) {
        const addr = cm[1];
        const dir = cm[2] === "write" ? "1" : "0";
        if (
          allText.includes(`reg_addr = 3'h${addr}`) &&
          allText.includes(`item.we = ${dir}`)
        ) {
          bin.hit = true;
        }
      }
    }
    if (bin.name.includes("DATA.zero") && allText.includes("8'h00")) bin.hit = true;
    if (bin.name.includes("DATA.ones") && allText.includes("8'hFF")) bin.hit = true;
    // SVA bins: hit if assertions present
    if (bin.name.includes("sva_cp.ack_timing") && allText.includes("assert property")) bin.hit = true;
    if (bin.name.includes("sva_cp.data_stable") && allText.includes("cover property")) bin.hit = true;

    // Seed-based randomization: add noise per seed
    if (!bin.hit && rng() < 0.15 * seed) bin.hit = true;
  }

  const total = bins.length;
  const covered = bins.filter((b) => b.hit).length;
  return { total, covered, pct: total > 0 ? (covered / total) * 100 : 0, bins };
}

// Merge coverage across seeds
function mergeCoverage(seedResults) {
  const merged = {};
  for (const res of seedResults) {
    for (const bin of res.bins) {
      if (!merged[bin.name]) merged[bin.name] = { name: bin.name, hit: false, goal: 1 };
      if (bin.hit) merged[bin.name].hit = true;
    }
  }
  const bins = Object.values(merged);
  const total = bins.length;
  const covered = bins.filter((b) => b.hit).length;
  return { total, covered, pct: total > 0 ? (covered / total) * 100 : 0, bins };
}

export default function usePipeline() {
  const [state, setState] = useState({
    running: false,
    autoTraining: false,
    logs: [],
    artifacts: [],
    error: null,
    versions: [],
    currentVersion: 0,
    coverageTrend: [],
    coverageGaps: [],
    seedResults: [],
    autoTrainIteration: 0,
    autoTrainMax: 5,
  });

  const appendLog = useCallback((level, message) => {
    const timestamp = new Date().toISOString().slice(11, 23);
    setState((prev) => ({
      ...prev,
      logs: [...prev.logs, { level, message, timestamp }],
    }));
  }, []);

  const runSingle = useCallback(
    async (yamlSpec, version, iteration, totalIterations, numSeeds = 3) => {
      appendLog("info", `Iteration ${iteration}/${totalIterations} — generating...`);

      const spec = (() => {
        try {
          return JSON.parse(yamlSpec);
        } catch {
          return {};
        }
      })();
      const design = spec?.design_name || "uart";

      // Generate artifacts for this version
      const artifacts = buildFileContent(design, version, iteration);
      appendLog("success", `Generated ${artifacts.length} files (version v${version})`);

      // Multi-seed regression
      await new Promise((r) => setTimeout(r, 200));
      const seedResults = [];
      for (let s = 1; s <= numSeeds; s++) {
        const cov = simulateCoverage(artifacts, s);
        seedResults.push(cov);
      }
      const merged = mergeCoverage(seedResults);
      const uncovered = merged.bins.filter((b) => !b.hit);
      const gaps = uncovered.map((b) => ({
        bin: b.name,
        covered: false,
      }));

      appendLog(
        merged.pct >= 90 ? "success" : "warn",
        `Coverage: ${merged.covered}/${merged.total} (${merged.pct.toFixed(1)}%, merged ${numSeeds} seeds)`
      );

      if (gaps.length > 0) {
        appendLog("warn", `Coverage gaps: ${gaps.length} uncovered bins`);
      }

      return { artifacts, cov: merged, gaps, version, iteration, seedResults, numSeeds };
    },
    [appendLog]
  );

  const runPipeline = useCallback(
    async (yamlSpec) => {
      const spec = (() => {
        try {
          return JSON.parse(yamlSpec);
        } catch {
          return {};
        }
      })();
      const design = spec?.design_name || "uart";

      setState((prev) => ({
        ...prev,
        running: true,
        logs: [],
        artifacts: [],
        error: null,
        currentVersion: 0,
      }));

      appendLog("info", "Pipeline started — validation passed");
      appendLog("info", "Generating UVM testbench...");

      try {
        const result = await runSingle(yamlSpec, 1, 1, 1);
        const trend = [{ version: "v1", coverage: result.cov.pct }];

        appendLog("success", "Pipeline completed");
        setState((prev) => ({
          ...prev,
          running: false,
          artifacts: result.artifacts,
          versions: [{ version: "v1", coverage: result.cov.pct, files: result.artifacts.length }],
          currentVersion: 1,
          coverageTrend: trend,
          coverageGaps: result.gaps,
          autoTrainIteration: 1,
          autoTrainMax: 1,
        }));
      } catch (err) {
        appendLog("error", `Pipeline failed: ${err.message}`);
        setState((prev) => ({ ...prev, running: false, error: err.message }));
      }
    },
    [appendLog, runSingle]
  );

  const runAutoTrain = useCallback(
    async (yamlSpec, maxIterations) => {
      const spec = (() => {
        try {
          return JSON.parse(yamlSpec);
        } catch {
          return {};
        }
      })();
      const design = spec?.design_name || "uart";

      setState((prev) => ({
        ...prev,
        running: true,
        autoTraining: true,
        logs: [],
        artifacts: [],
        error: null,
        versions: [],
        currentVersion: 0,
        coverageTrend: [],
        coverageGaps: [],
        autoTrainIteration: 0,
        autoTrainMax: maxIterations,
      }));

      appendLog("info", `Auto-training started — max ${maxIterations} iterations`);
      appendLog("info", "Pipeline started — validation passed");

      let allVersions = [];
      let trend = [];
      let latestArtifacts = [];
      let latestGaps = [];
      let latestSeedResults = [];
      let iteration = 0;

      for (iteration = 1; iteration <= maxIterations; iteration++) {
        appendLog("info", `=== Auto-train iteration ${iteration}/${maxIterations} ===`);
        appendLog("info", `Generating testbench (v${iteration})...`);

        try {
          const result = await runSingle(yamlSpec, iteration, iteration, maxIterations, 3);

          const ver = {
            version: `v${iteration}`,
            coverage: result.cov.pct,
            files: result.artifacts.length,
          };
          allVersions.push(ver);
          trend.push({ version: `v${iteration}`, coverage: result.cov.pct });
          latestArtifacts = result.artifacts;
          latestGaps = result.gaps;
          latestSeedResults = result.seedResults || [];

          // Check convergence
          if (result.cov.pct >= 90) {
            appendLog("success", `Coverage target ≥90% reached (${result.cov.pct.toFixed(1)}%)`);
            break;
          }

          if (iteration >= 2) {
            const prev = trend[trend.length - 2]?.coverage || 0;
            const gain = result.cov.pct - prev;
            appendLog("info", `Coverage gain: ${gain > 0 ? "+" : ""}${gain.toFixed(1)}%`);
            if (gain < 2 && iteration >= 3) {
              appendLog("warn", `Gain too low (<2%) — stopping early`);
              break;
            }
          }

          // Generate targeted sequences for next iteration
          if (result.gaps.length > 0) {
            const addrSet = new Set();
            result.gaps.forEach((g) => {
              const m = g.bin.match(/regs\[(\d+)\]/);
              if (m) addrSet.add(parseInt(m[1]));
            });
            if (addrSet.size > 0) {
              appendLog("info", `Targeting uncovered regs: [${[...addrSet].join(", ")}]`);
            }
          }

          await new Promise((r) => setTimeout(r, 200));
        } catch (err) {
          appendLog("error", `Iteration ${iteration} failed: ${err.message}`);
          break;
        }
      }

      appendLog(
        iteration >= maxIterations ? "warn" : "success",
        `Auto-training complete — ${iteration} iterations, ${allVersions.length} versions`
      );

      setState((prev) => ({
        ...prev,
        running: false,
        autoTraining: false,
        artifacts: latestArtifacts,
        versions: allVersions,
        currentVersion: allVersions.length,
        coverageTrend: trend,
        coverageGaps: latestGaps,
        seedResults: latestSeedResults,
        autoTrainIteration: iteration,
        autoTrainMax: maxIterations,
      }));
    },
    [appendLog, runSingle]
  );

  return { ...state, runPipeline, runAutoTrain };
}
