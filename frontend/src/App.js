import React, { useState, useCallback } from "react";
import Header from "./components/Header";
import Footer from "./components/Footer";
import YAMLForm from "./components/YAMLForm";
import PreviewPanel from "./components/PreviewPanel";
import PipelineRunner from "./components/PipelineRunner";
import ErrorBoundary from "./components/ErrorBoundary";
import { Cpu, FileCode, ShieldCheck, Zap } from "lucide-react";

const FEATURES = [
  {
    icon: Cpu,
    title: "Full UVM Generation",
    description: "Complete testbenches with agents, drivers, monitors, scoreboards, and sequences.",
  },
  {
    icon: FileCode,
    title: "RAL Model Support",
    description: "Automatic UVM Register Abstraction Layer generation from YAML register specs.",
  },
  {
    icon: ShieldCheck,
    title: "Built-in Verification",
    description: "Multi-stage verification validates syntax, signals, registers, and coverage.",
  },
  {
    icon: Zap,
    title: "Coverage-Driven",
    description: "Auto-training mode iterates to maximize coverage with targeted sequences.",
  },
];

export default function App() {
  const [spec, setSpec] = useState(null);

  const handleSpecChange = useCallback((parsed) => {
    setSpec(parsed);
  }, []);

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-b from-slate-50 to-white">
      <Header />

      <main className="flex-1">
        {/* Hero Section */}
        <div className="bg-gradient-to-br from-slate-900 via-slate-800 to-brand-900 relative overflow-hidden">
          <div className="absolute inset-0 opacity-20">
            <div className="absolute top-10 left-10 w-64 h-64 bg-brand-500 rounded-full blur-3xl" />
            <div className="absolute bottom-10 right-10 w-96 h-96 bg-sky-500 rounded-full blur-3xl" />
          </div>
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 relative">
            <div className="text-center max-w-3xl mx-auto">
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/10 border border-white/10 mb-6">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-[11px] font-medium text-white/80">Production Ready v0.3.0</span>
              </div>
              <h1 className="text-3xl sm:text-4xl font-bold text-white tracking-tight mb-4">
                Professional UVM Testbench
                <br />
                <span className="bg-gradient-to-r from-brand-400 to-sky-400 bg-clip-text text-transparent">
                  Generator
                </span>
              </h1>
              <p className="text-base text-slate-300 mb-8 max-w-2xl mx-auto leading-relaxed">
                Generate complete, production-grade UVM verification environments from simple YAML specifications.
                Supports UART, SPI, I2C, AXI4-Lite, APB, and Wishbone protocols out of the box.
              </p>

              {/* Feature badges */}
              <div className="flex flex-wrap items-center justify-center gap-3">
                {["UVM RAL", "Serial Monitors", "Scoreboarding", "Coverage", "Auto-Train"].map((f) => (
                  <span
                    key={f}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs font-medium text-white/80"
                  >
                    <span className="w-1 h-1 rounded-full bg-brand-400" />
                    {f}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Feature Cards */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {FEATURES.map((feature, i) => {
              const Icon = feature.icon;
              return (
                <div
                  key={i}
                  className="rounded-xl border border-slate-200 bg-white p-5 hover:shadow-md hover:border-brand-200 transition-all duration-200 group"
                >
                  <div className="w-10 h-10 rounded-lg bg-brand-50 flex items-center justify-center mb-3 group-hover:bg-brand-100 transition-colors">
                    <Icon size={20} className="text-brand-600" />
                  </div>
                  <h3 className="text-sm font-semibold text-slate-900 mb-1.5">{feature.title}</h3>
                  <p className="text-xs text-slate-500 leading-relaxed">{feature.description}</p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Main Workspace */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-12 space-y-6">
          {/* Section header */}
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-900 tracking-tight">Design Workspace</h2>
              <p className="text-xs text-slate-500 mt-1">Configure your spec, preview, and generate</p>
            </div>
            {spec && (
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-50 border border-emerald-200 text-xs font-medium text-emerald-700">
                  <CheckCircledDot size={12} />
                  Spec Loaded: <span className="font-mono">{spec.design_name || "unnamed"}</span>
                </span>
              </div>
            )}
          </div>

          {/* Form + Preview */}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <ErrorBoundary>
              <YAMLForm onSpecChange={handleSpecChange} />
            </ErrorBoundary>
            <ErrorBoundary>
              <PreviewPanel spec={spec} />
            </ErrorBoundary>
          </div>

          {/* Pipeline */}
          <ErrorBoundary>
            <PipelineRunner spec={spec} />
          </ErrorBoundary>
        </div>
      </main>

      <Footer />
    </div>
  );
}

function CheckCircledDot({ size }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className="shrink-0">
      <circle cx="12" cy="12" r="10" fill="#d1fae5" />
      <path
        d="M8 12L10.5 14.5L16 9"
        stroke="#059669"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
