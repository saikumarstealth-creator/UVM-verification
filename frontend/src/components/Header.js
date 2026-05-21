import React from "react";
import { Cpu, GitBranch } from "lucide-react";

export default function Header() {
  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-brand-600 flex items-center justify-center">
              <Cpu size={20} className="text-white" />
            </div>
            <div>
              <h1 className="text-base font-bold text-slate-900 leading-tight">
                Verification Pipeline
              </h1>
              <p className="text-[11px] text-slate-500 leading-tight">
                UVM Testbench Generator
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <a
              href="#"
              className="hidden sm:inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 transition-colors"
            >
              <GitBranch size={14} />
              v0.3.0
            </a>
            <span className="hidden sm:inline-flex items-center gap-1.5 text-xs text-slate-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
              API Ready
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}
