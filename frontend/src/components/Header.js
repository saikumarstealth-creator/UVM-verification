import React, { useState } from "react";
import { Cpu, ChevronDown, ChevronUp, Shield, Download, FileText, CheckCircle, AlertCircle, Loader2 } from "lucide-react";

export default function Header() {
  const [showAbout, setShowAbout] = useState(false);

  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center shadow-lg shadow-brand-500/20">
              <Cpu size={22} className="text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-slate-900 leading-tight tracking-tight">
                UVM Testbench Generator
              </h1>
              <p className="text-[11px] text-slate-500 leading-tight">
                Professional Verification Pipeline
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="hidden md:flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 text-[11px] font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                Production Ready
              </span>
            </div>

            <button
              onClick={() => setShowAbout(!showAbout)}
              className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-600 hover:text-slate-800 hover:bg-slate-100 transition-colors"
            >
              <Shield size={14} className="text-brand-500" />
              About
              {showAbout ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>
          </div>
        </div>

        {showAbout && (
          <div className="pb-4 border-t border-slate-100 pt-4 animate-in fade-in slide-in-from-top-2 duration-200">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="space-y-2">
                <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Version</h3>
                <p className="text-sm text-slate-700 font-medium">v0.3.0</p>
                <p className="text-xs text-slate-500">UVM Testbench Generator with RAL support</p>
              </div>
              <div className="space-y-2">
                <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Supported Protocols</h3>
                <div className="flex flex-wrap gap-1.5">
                  {["UART", "SPI", "I2C", "AXI4-Lite", "APB", "Wishbone"].map((p) => (
                    <span key={p} className="px-2 py-0.5 rounded bg-slate-100 text-slate-600 text-xs font-medium">
                      {p}
                    </span>
                  ))}
                </div>
              </div>
              <div className="space-y-2">
                <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Developer</h3>
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center text-white text-xs font-bold shadow-md shadow-brand-500/20">
                    ST
                  </div>
                  <div>
                    <p className="text-sm font-bold text-brand-700 tracking-tight">Sai Kumar Taraka</p>
                    <p className="text-[11px] text-slate-500">Verification Engineer & Tool Developer</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
