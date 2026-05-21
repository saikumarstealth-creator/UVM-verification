import React, { useMemo } from "react";
import { Eye, AlertCircle, CheckCircle2, Layers } from "lucide-react";
import { toYAML, validateYAML, PROTOCOLS } from "../utils/yamlUtils";

function MissingField({ label }) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-red-50 text-red-600 text-[11px] font-medium">
      <AlertCircle size={12} />
      missing: {label}
    </span>
  );
}

function ProtocolBadge({ protocol }) {
  const colorMap = {
    uart: "bg-sky-50 text-sky-700",
    spi: "bg-violet-50 text-violet-700",
    i2c: "bg-amber-50 text-amber-700",
    axi4lite: "bg-rose-50 text-rose-700",
    apb: "bg-teal-50 text-teal-700",
    wishbone: "bg-indigo-50 text-indigo-700",
  };
  const cls = colorMap[protocol] || "bg-slate-100 text-slate-600";
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${cls}`}>
      {protocol.toUpperCase()}
    </span>
  );
}

function Section({ title, children, icon, count, error }) {
  return (
    <div className={`rounded-lg border ${error ? "border-red-200 bg-red-50/30" : "border-slate-200"} p-4 space-y-3`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
          {icon}
          {title}
          {count !== undefined && (
            <span className="text-xs font-normal text-slate-400">({count})</span>
          )}
        </div>
        {error && <MissingField label={error} />}
      </div>
      {children}
    </div>
  );
}

export default function PreviewPanel({ spec }) {
  const errors = useMemo(() => (spec ? validateYAML(toYAML(spec)) : ["No spec loaded"]), [spec]);

  if (!spec || Object.keys(spec).length === 0) {
    return (
      <div className="card">
        <div className="card-header">
          <Eye size={18} className="text-slate-400" />
          <h2 className="text-slate-400">Preview</h2>
        </div>
        <div className="card-body">
          <div className="flex flex-col items-center justify-center py-12 text-slate-400">
            <Layers size={40} className="mb-3 opacity-40" />
            <p className="text-sm">Load a spec to see the parsed preview</p>
          </div>
        </div>
      </div>
    );
  }

  const hasErrors = errors.length > 0;

  return (
    <div className="card">
      <div className="card-header">
        <Eye size={18} className="text-brand-600" />
        <h2>Parsed Specification</h2>
        <span className={hasErrors ? "badge-error ml-auto" : "badge-success ml-auto"}>
          {hasErrors ? `${errors.length} issue${errors.length > 1 ? "s" : ""}` : "Valid"}
        </span>
      </div>

      <div className="card-body space-y-4">
        {/* Errors */}
        {hasErrors && (
          <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3">
            <div className="text-xs text-red-700 space-y-0.5">
              {errors.map((e, i) => (
                <p key={i} className="flex items-center gap-1.5">
                  <AlertCircle size={12} className="shrink-0" />
                  {e}
                </p>
              ))}
            </div>
          </div>
        )}

        {/* Design metadata */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-slate-50 rounded-lg p-3">
            <p className="text-[11px] text-slate-500 font-medium uppercase tracking-wider">Design</p>
            <p className="text-sm font-semibold text-slate-900 mt-0.5">
              {spec.design_name || <MissingField label="design_name" />}
            </p>
          </div>
          <div className="bg-slate-50 rounded-lg p-3">
            <p className="text-[11px] text-slate-500 font-medium uppercase tracking-wider">Version</p>
            <p className="text-sm text-slate-900 mt-0.5">{spec.version || "—"}</p>
          </div>
          <div className="bg-slate-50 rounded-lg p-3">
            <p className="text-[11px] text-slate-500 font-medium uppercase tracking-wider">Vendor</p>
            <p className="text-sm text-slate-900 mt-0.5">{spec.vendor || "—"}</p>
          </div>
          <div className="bg-slate-50 rounded-lg p-3">
            <p className="text-[11px] text-slate-500 font-medium uppercase tracking-wider">Protocol</p>
            <p className="mt-0.5">
              {spec.protocol ? (
                <ProtocolBadge protocol={spec.protocol} />
              ) : (
                <span className="badge-warning">Auto</span>
              )}
            </p>
          </div>
        </div>

        {/* Clock / Reset */}
        <Section
          title="Clock & Reset"
          icon={<span className="w-2 h-2 rounded-full bg-amber-400" />}
          error={!spec.clock_reset ? "clock_reset" : null}
        >
          <div className="grid grid-cols-3 gap-3 text-sm">
            <div>
              <span className="text-[11px] text-slate-500">Clock</span>
              <p className="font-mono text-slate-900">{spec.clock_reset?.clock || "—"}</p>
            </div>
            <div>
              <span className="text-[11px] text-slate-500">Reset</span>
              <p className="font-mono text-slate-900">{spec.clock_reset?.reset || "—"}</p>
            </div>
            <div>
              <span className="text-[11px] text-slate-500">Active</span>
              <p className="font-mono text-slate-900">
                {spec.clock_reset?.reset_active === 0 ? "Low" : spec.clock_reset?.reset_active === 1 ? "High" : "—"}
              </p>
            </div>
          </div>
        </Section>

        {/* Interfaces */}
        <Section
          title="Interfaces"
          icon={<span className="w-2 h-2 rounded-full bg-brand-500" />}
          count={spec.interfaces?.length}
          error={!spec.interfaces?.length ? "interfaces" : null}
        >
          {(spec.interfaces || []).map((iface, i) => (
            <div key={i} className="border-t border-slate-100 pt-2 first:border-0 first:pt-0">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-sm font-medium text-slate-800">{iface.name || `iface_${i}`}</span>
                {iface.protocol && <ProtocolBadge protocol={iface.protocol} />}
                <span className="text-xs text-slate-400">
                  {Array.isArray(iface.signals) ? iface.signals.length : 0} signals
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {Array.isArray(iface.signals) && iface.signals.map((sig, j) => (
                  <span
                    key={j}
                    className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-mono
                      ${sig.direction === "output"
                        ? "bg-emerald-50 text-emerald-700"
                        : sig.direction === "inout"
                        ? "bg-amber-50 text-amber-700"
                        : "bg-sky-50 text-sky-700"
                      }`}
                  >
                    {sig.name}
                    <span className="opacity-60">
                      {(sig.width || 1) > 1 ? `[${sig.width - 1}:0]` : ""}
                    </span>
                    <span className="opacity-50 text-[10px]">({sig.direction[0]})</span>
                  </span>
                ))}
              </div>
            </div>
          ))}
        </Section>

        {/* Registers */}
        <Section
          title="Registers"
          icon={<span className="w-2 h-2 rounded-full bg-violet-500" />}
          count={spec.registers?.length}
        >
          {(spec.registers || []).length === 0 && (
            <p className="text-xs text-slate-400 italic">No registers defined</p>
          )}
          {(spec.registers || []).map((reg, i) => (
            <div key={i} className="border-t border-slate-100 pt-2 first:border-0 first:pt-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-sm font-mono font-semibold text-slate-800">{reg.name}</span>
                <span className="text-xs font-mono text-slate-500">@{reg.address}</span>
                <span className={`badge text-[10px] ${
                  reg.access === "ro" ? "badge-warning" :
                  reg.access === "wo" ? "badge-error" :
                  "badge-info"
                }`}>
                  [{reg.access || "rw"}]
                </span>
                {reg.description && (
                  <span className="text-xs text-slate-400 truncate max-w-[200px]">{reg.description}</span>
                )}
              </div>
              {(reg.fields || []).length > 0 && (
                <div className="ml-3 flex flex-wrap gap-1">
                  {(reg.fields || []).map((f, j) => (
                    <span key={j} className="inline-flex items-center gap-1 rounded bg-slate-100 px-1.5 py-0.5 text-[11px] font-mono text-slate-600">
                      {f.name}[{f.bits}]
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </Section>

        {/* Parameters */}
        {spec.parameters && Object.keys(spec.parameters).length > 0 && (
          <Section
            title="Parameters"
            icon={<span className="w-2 h-2 rounded-full bg-slate-400" />}
            count={Object.keys(spec.parameters).length}
          >
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {Object.entries(spec.parameters).map(([k, v]) => (
                <div key={k} className="bg-slate-50 rounded px-2.5 py-1.5">
                  <p className="text-[11px] font-mono text-slate-700">{k}</p>
                  <p className="text-xs text-slate-500">{v ?? "—"}</p>
                </div>
              ))}
            </div>
          </Section>
        )}
      </div>
    </div>
  );
}
