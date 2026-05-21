import React from "react";
import { Cpu } from "lucide-react";

export default function Footer() {
  return (
    <footer className="bg-white border-t border-slate-200 mt-12">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <Cpu size={16} className="text-brand-500" />
            <span>
              Semiconductor Verification Pipeline &mdash; Developed by{" "}
              <span className="font-semibold text-slate-700">Sai Kumar Taraka</span>
            </span>
          </div>
          <div className="flex items-center gap-4 text-xs text-slate-400">
            <span>UVM TB Generator v0.3.0</span>
            <span className="hidden sm:inline">&middot;</span>
            <span className="hidden sm:inline">MIT License</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
