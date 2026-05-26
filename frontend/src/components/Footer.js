import React from "react";
import { Cpu, Github, Mail } from "lucide-react";

export default function Footer() {
  return (
    <footer className="bg-gradient-to-r from-slate-900 to-slate-800 border-t border-slate-700 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-brand-600/20 flex items-center justify-center">
                <Cpu size={18} className="text-brand-400" />
              </div>
              <span className="text-white font-semibold">UVM TB Generator</span>
            </div>
            <p className="text-sm text-slate-400">
              Professional UVM testbench generation from YAML specifications.
              Built for verification engineers, by verification engineers.
            </p>
          </div>

          <div className="space-y-3">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Capabilities</h3>
            <div className="grid grid-cols-2 gap-2 text-sm text-slate-400">
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                RAL Model Generation
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                Serial Monitors
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                Coverage-Driven
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                Scoreboarding
              </span>
            </div>
          </div>

          <div className="space-y-3">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Developer</h3>
            <div className="flex items-center gap-3 p-3 rounded-xl bg-white/5 border border-white/10">
              <div className="w-12 h-12 rounded-full bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center text-white text-lg font-bold shadow-lg shadow-brand-500/30 ring-2 ring-brand-400/30">
                ST
              </div>
              <div>
                <p className="text-sm font-bold text-white tracking-tight">Sai Kumar Taraka</p>
                <p className="text-xs text-slate-400">Verification Engineer</p>
                <div className="flex items-center gap-3 mt-1.5">
                  <a
                    href="https://github.com/saikumarstealth-creator"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-brand-400 transition-colors"
                  >
                    <Github size={12} />
                    GitHub
                  </a>
                  <a
                    href="mailto:saikumar@example.com"
                    className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-brand-400 transition-colors"
                  >
                    <Mail size={12} />
                    Contact
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-8 pt-6 border-t border-slate-700/50 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span>© {new Date().getFullYear()} Sai Kumar Taraka. All rights reserved.</span>
          </div>
          <div className="flex items-center gap-4 text-xs text-slate-600">
            <span>MIT License</span>
            <span className="hidden sm:inline">•</span>
            <span className="hidden sm:inline">Built for Production</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
