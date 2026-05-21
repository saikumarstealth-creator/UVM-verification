import React, { useState, useRef, useCallback } from "react";
import {
  Upload,
  FileCode,
  Plus,
  Trash2,
  AlertCircle,
  CheckCircle2,
  Settings2,
} from "lucide-react";
import { parseYAML, validateYAML, toYAML, PROTOCOLS, DEFAULT_YAML } from "../utils/yamlUtils";

export default function YAMLForm({ onSpecChange, validationErrors }) {
  const [yamlText, setYamlText] = useState(DEFAULT_YAML);
  const [parsed, setParsed] = useState(() => parseYAML(DEFAULT_YAML));
  const [mode, setMode] = useState("editor"); // editor | parsed | split
  const [activeTab, setActiveTab] = useState("spec"); // spec | signals | registers
  const fileRef = useRef(null);

  const handleChange = useCallback(
    (text) => {
      setYamlText(text);
      try {
        const obj = parseYAML(text);
        setParsed(obj);
        onSpecChange(obj);
      } catch {
        // keep previous parsed state
      }
    },
    [onSpecChange]
  );

  const handleFileUpload = useCallback(
    (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => handleChange(ev.target.result);
      reader.readAsText(file);
    },
    [handleChange]
  );

  const handlePasteExample = useCallback(() => {
    handleChange(DEFAULT_YAML);
  }, [handleChange]);

  const errors = validateYAML(yamlText);

  // ── Signal / Register editors ────────────────────────────────────

  const updateInterface = (idx, field, value) => {
    const ifaces = [...(parsed.interfaces || [])];
    ifaces[idx] = { ...ifaces[idx], [field]: value };
    const updated = { ...parsed, interfaces: ifaces };
    setParsed(updated);
    handleChange(toYAML(updated));
  };

  const addSignal = (ifaceIdx) => {
    const ifaces = [...(parsed.interfaces || [])];
    const existing = Array.isArray(ifaces[ifaceIdx]?.signals) ? ifaces[ifaceIdx].signals : [];
    const signals = [...existing, { name: "", direction: "input", width: 1 }];
    ifaces[ifaceIdx] = { ...ifaces[ifaceIdx], signals };
    const updated = { ...parsed, interfaces: ifaces };
    setParsed(updated);
    handleChange(toYAML(updated));
  };

  const updateSignal = (ifaceIdx, sigIdx, field, value) => {
    const ifaces = [...(parsed.interfaces || [])];
    const existing = Array.isArray(ifaces[ifaceIdx]?.signals) ? ifaces[ifaceIdx].signals : [];
    const signals = [...existing];
    signals[sigIdx] = { ...signals[sigIdx], [field]: value };
    ifaces[ifaceIdx] = { ...ifaces[ifaceIdx], signals };
    const updated = { ...parsed, interfaces: ifaces };
    setParsed(updated);
    handleChange(toYAML(updated));
  };

  const removeSignal = (ifaceIdx, sigIdx) => {
    const ifaces = [...(parsed.interfaces || [])];
    const sigs = Array.isArray(ifaces[ifaceIdx].signals) ? ifaces[ifaceIdx].signals : [];
    ifaces[ifaceIdx] = {
      ...ifaces[ifaceIdx],
      signals: sigs.filter((_, i) => i !== sigIdx),
    };
    const updated = { ...parsed, interfaces: ifaces };
    setParsed(updated);
    handleChange(toYAML(updated));
  };

  const addRegister = () => {
    const regs = [...(parsed.registers || []), { name: "", address: "0x00", access: "rw", fields: [] }];
    const updated = { ...parsed, registers: regs };
    setParsed(updated);
    handleChange(toYAML(updated));
  };

  const updateRegister = (idx, field, value) => {
    const regs = [...(parsed.registers || [])];
    regs[idx] = { ...regs[idx], [field]: value };
    const updated = { ...parsed, registers: regs };
    setParsed(updated);
    handleChange(toYAML(updated));
  };

  const removeRegister = (idx) => {
    const updated = { ...parsed, registers: parsed.registers.filter((_, i) => i !== idx) };
    setParsed(updated);
    handleChange(toYAML(updated));
  };

  const addField = (regIdx) => {
    const regs = [...(parsed.registers || [])];
    const fields = [...(regs[regIdx]?.fields || []), { name: "", bits: "0", description: "" }];
    regs[regIdx] = { ...regs[regIdx], fields };
    const updated = { ...parsed, registers: regs };
    setParsed(updated);
    handleChange(toYAML(updated));
  };

  const updateField = (regIdx, fldIdx, field, value) => {
    const regs = [...(parsed.registers || [])];
    const fields = [...(regs[regIdx]?.fields || [])];
    fields[fldIdx] = { ...fields[fldIdx], [field]: value };
    regs[regIdx] = { ...regs[regIdx], fields };
    const updated = { ...parsed, registers: regs };
    setParsed(updated);
    handleChange(toYAML(updated));
  };

  const removeField = (regIdx, fldIdx) => {
    const regs = [...(parsed.registers || [])];
    regs[regIdx] = {
      ...regs[regIdx],
      fields: regs[regIdx].fields.filter((_, i) => i !== fldIdx),
    };
    const updated = { ...parsed, registers: regs };
    setParsed(updated);
    handleChange(toYAML(updated));
  };

  return (
    <div className="card">
      <div className="card-header">
        <FileCode size={18} className="text-brand-600" />
        <h2>Design Specification</h2>
      </div>

      <div className="card-body space-y-4">
        {/* Toolbar */}
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn-secondary text-xs" onClick={() => fileRef.current?.click()}>
            <Upload size={14} /> Upload .core / .yaml
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".yaml,.yml,.core,.json"
            className="hidden"
            onChange={handleFileUpload}
          />
          <button className="btn-secondary text-xs" onClick={handlePasteExample}>
            Load Example
          </button>
          <div className="ml-auto flex items-center gap-1 bg-slate-100 rounded-lg p-0.5">
            {["spec", "signals", "registers"].map((t) => (
              <button
                key={t}
                onClick={() => setActiveTab(t)}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  activeTab === t
                    ? "bg-white text-slate-900 shadow-sm"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                {t === "spec" ? "Spec" : t === "signals" ? "Signals" : "Registers"}
              </button>
            ))}
          </div>
        </div>

        {/* Validation status */}
        {errors.length > 0 && (
          <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3">
            <div className="flex items-start gap-2">
              <AlertCircle size={16} className="text-red-500 mt-0.5 shrink-0" />
              <div className="text-xs text-red-700 space-y-0.5">
                {errors.map((e, i) => (
                  <p key={i}>{e}</p>
                ))}
              </div>
            </div>
          </div>
        )}
        {errors.length === 0 && yamlText.trim() && (
          <div className="flex items-center gap-2 text-xs text-emerald-600">
            <CheckCircle2 size={14} />
            YAML syntax valid
          </div>
        )}

        {/* ── Spec tab ─────────────────────────────────── */}
        {activeTab === "spec" && (
          <div className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Design Name</label>
                <input
                  className="input-field text-sm"
                  value={parsed.design_name || ""}
                  onChange={(e) => {
                    const updated = { ...parsed, design_name: e.target.value };
                    setParsed(updated);
                    handleChange(toYAML(updated));
                  }}
                  placeholder="uart16550"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Version</label>
                <input
                  className="input-field text-sm"
                  value={parsed.version || ""}
                  onChange={(e) => {
                    const updated = { ...parsed, version: e.target.value };
                    setParsed(updated);
                    handleChange(toYAML(updated));
                  }}
                  placeholder="1.5"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Vendor</label>
                <input
                  className="input-field text-sm"
                  value={parsed.vendor || ""}
                  onChange={(e) => {
                    const updated = { ...parsed, vendor: e.target.value };
                    setParsed(updated);
                    handleChange(toYAML(updated));
                  }}
                  placeholder="DV Automation"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Description</label>
              <textarea
                className="input-field text-sm resize-none"
                rows={2}
                value={parsed.description || ""}
                onChange={(e) => {
                  const updated = { ...parsed, description: e.target.value };
                  setParsed(updated);
                  handleChange(toYAML(updated));
                }}
                placeholder="Core description"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Protocol</label>
                <select
                  className="select-field text-sm"
                  value={parsed.protocol || ""}
                  onChange={(e) => {
                    const updated = { ...parsed, protocol: e.target.value };
                    setParsed(updated);
                    handleChange(toYAML(updated));
                  }}
                >
                  <option value="">Auto-detect</option>
                  {PROTOCOLS.map((p) => (
                    <option key={p} value={p}>{p.toUpperCase()}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Language</label>
                <select
                  className="select-field text-sm"
                  value={parsed.language || "systemverilog"}
                  onChange={(e) => {
                    const updated = { ...parsed, language: e.target.value };
                    setParsed(updated);
                    handleChange(toYAML(updated));
                  }}
                >
                  <option value="systemverilog">SystemVerilog</option>
                  <option value="verilog">Verilog</option>
                  <option value="vhdl">VHDL</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Clock (clk)</label>
                <input className="input-field text-sm" value={parsed.clock_reset?.clock || "clk"} onChange={(e) => {
                  const cr = { ...(parsed.clock_reset || {}), clock: e.target.value };
                  const updated = { ...parsed, clock_reset: cr };
                  setParsed(updated); handleChange(toYAML(updated));
                }} />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Reset (rst_n)</label>
                <input className="input-field text-sm" value={parsed.clock_reset?.reset || "rst_n"} onChange={(e) => {
                  const cr = { ...(parsed.clock_reset || {}), reset: e.target.value };
                  const updated = { ...parsed, clock_reset: cr };
                  setParsed(updated); handleChange(toYAML(updated));
                }} />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Reset Active</label>
                <select className="select-field text-sm" value={parsed.clock_reset?.reset_active ?? 0} onChange={(e) => {
                  const cr = { ...(parsed.clock_reset || {}), reset_active: Number(e.target.value) };
                  const updated = { ...parsed, clock_reset: cr };
                  setParsed(updated); handleChange(toYAML(updated));
                }}>
                  <option value={0}>Active Low (0)</option>
                  <option value={1}>Active High (1)</option>
                </select>
              </div>
            </div>

            {/* Raw YAML editor */}
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Raw YAML / .core Editor
              </label>
              <textarea
                className="input-field text-xs font-mono resize-y"
                rows={10}
                value={yamlText}
                onChange={(e) => handleChange(e.target.value)}
                spellCheck={false}
              />
            </div>
          </div>
        )}

        {/* ── Signals tab ─────────────────────────────────── */}
        {activeTab === "signals" && (
          <div className="space-y-4">
            {(parsed.interfaces || []).length === 0 && (
              <p className="text-xs text-slate-400">No interfaces defined. Add one in the Spec tab.</p>
            )}
            {(parsed.interfaces || []).map((iface, iIdx) => (
              <div key={iIdx} className="rounded-lg border border-slate-200 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="badge-info">{iface.name || `Interface #${iIdx + 1}`}</span>
                    <select
                      className="select-field text-xs py-1 w-28"
                      value={iface.protocol || ""}
                      onChange={(e) => updateInterface(iIdx, "protocol", e.target.value)}
                    >
                      <option value="">Protocol</option>
                      {PROTOCOLS.map((p) => (
                        <option key={p} value={p}>{p.toUpperCase()}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="space-y-2">
                  {Array.isArray(iface.signals) && iface.signals.map((sig, sIdx) => (
                    <div key={sIdx} className="flex items-center gap-2">
                      <input
                        className="input-field text-xs py-1.5 w-28"
                        value={sig.name}
                        onChange={(e) => updateSignal(iIdx, sIdx, "name", e.target.value)}
                        placeholder="signal_name"
                      />
                      <select
                        className="select-field text-xs py-1.5 w-22"
                        value={sig.direction}
                        onChange={(e) => updateSignal(iIdx, sIdx, "direction", e.target.value)}
                      >
                        <option value="input">input</option>
                        <option value="output">output</option>
                        <option value="inout">inout</option>
                      </select>
                      <div className="flex items-center gap-1">
                        <span className="text-[11px] text-slate-500">w:</span>
                        <input
                          className="input-field text-xs py-1.5 w-16 text-center"
                          type="number"
                          min={1}
                          value={sig.width || 1}
                          onChange={(e) => updateSignal(iIdx, sIdx, "width", Number(e.target.value))}
                        />
                      </div>
                      <button
                        className="p-1.5 rounded-md text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                        onClick={() => removeSignal(iIdx, sIdx)}
                        title="Remove signal"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                </div>
                <button
                  className="btn-secondary text-xs"
                  onClick={() => addSignal(iIdx)}
                >
                  <Plus size={14} /> Add Signal
                </button>
              </div>
            ))}
          </div>
        )}

        {/* ── Registers tab ─────────────────────────────────── */}
        {activeTab === "registers" && (
          <div className="space-y-4">
            {(parsed.registers || []).length === 0 && (
              <p className="text-xs text-slate-400">No registers defined.</p>
            )}
            {(parsed.registers || []).map((reg, rIdx) => (
              <div key={rIdx} className="rounded-lg border border-slate-200 p-4 space-y-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <input
                    className="input-field text-xs py-1.5 w-28"
                    value={reg.name}
                    onChange={(e) => updateRegister(rIdx, "name", e.target.value)}
                    placeholder="REG_NAME"
                  />
                  <input
                    className="input-field text-xs py-1.5 w-22 font-mono"
                    value={reg.address}
                    onChange={(e) => updateRegister(rIdx, "address", e.target.value)}
                    placeholder="0x00"
                  />
                  <select
                    className="select-field text-xs py-1.5 w-20"
                    value={reg.access || "rw"}
                    onChange={(e) => updateRegister(rIdx, "access", e.target.value)}
                  >
                    <option value="rw">rw</option>
                    <option value="ro">ro</option>
                    <option value="wo">wo</option>
                    <option value="rc">rc</option>
                    <option value="w1c">w1c</option>
                  </select>
                  <input
                    className="input-field text-xs py-1.5 w-32"
                    value={reg.description || ""}
                    onChange={(e) => updateRegister(rIdx, "description", e.target.value)}
                    placeholder="Description"
                  />
                  <button
                    className="p-1.5 rounded-md text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors ml-auto"
                    onClick={() => removeRegister(rIdx)}
                    title="Remove register"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>

                {/* Fields */}
                {(reg.fields || []).length > 0 && (
                  <div className="ml-2 pl-3 border-l-2 border-brand-200 space-y-2">
                    <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">
                      Fields
                    </span>
                    {(reg.fields || []).map((fld, fIdx) => (
                      <div key={fIdx} className="flex items-center gap-2">
                        <input
                          className="input-field text-xs py-1 w-24"
                          value={fld.name}
                          onChange={(e) => updateField(rIdx, fIdx, "name", e.target.value)}
                          placeholder="field_name"
                        />
                        <input
                          className="input-field text-xs py-1 w-16 font-mono text-center"
                          value={fld.bits}
                          onChange={(e) => updateField(rIdx, fIdx, "bits", e.target.value)}
                          placeholder="7:0"
                        />
                        <input
                          className="input-field text-xs py-1 flex-1"
                          value={fld.description || ""}
                          onChange={(e) => updateField(rIdx, fIdx, "description", e.target.value)}
                          placeholder="Description"
                        />
                        <button
                          className="p-1 rounded-md text-slate-400 hover:text-red-500 hover:bg-red-50"
                          onClick={() => removeField(rIdx, fIdx)}
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                <button className="btn-secondary text-xs" onClick={() => addField(rIdx)}>
                  <Plus size={14} /> Add Field
                </button>
              </div>
            ))}
            <button className="btn-secondary text-xs" onClick={addRegister}>
              <Plus size={14} /> Add Register
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
