import React, { useState, useCallback } from "react";
import Header from "./components/Header";
import Footer from "./components/Footer";
import YAMLForm from "./components/YAMLForm";
import PreviewPanel from "./components/PreviewPanel";
import PipelineRunner from "./components/PipelineRunner";
import ErrorBoundary from "./components/ErrorBoundary";

export default function App() {
  const [spec, setSpec] = useState(null);

  const handleSpecChange = useCallback((parsed) => {
    setSpec(parsed);
  }, []);

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <Header />

      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Intro */}
        <div className="bg-gradient-to-r from-brand-600 to-brand-800 rounded-xl px-6 py-5 text-white">
          <h2 className="text-lg font-bold">UVM Testbench Generator</h2>
          <p className="text-sm text-brand-100 mt-1 max-w-2xl">
            Upload or paste a FuseSoC-style YAML / .core specification, edit signals and registers
            directly, then run the pipeline to generate a complete UVM testbench.
          </p>
        </div>

        {/* Form + Preview side by side */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <ErrorBoundary>
            <YAMLForm onSpecChange={handleSpecChange} />
          </ErrorBoundary>
          <ErrorBoundary>
            <PreviewPanel spec={spec} />
          </ErrorBoundary>
        </div>

        {/* Pipeline runner */}
        <ErrorBoundary>
          <PipelineRunner spec={spec} />
        </ErrorBoundary>
      </main>

      <Footer />
    </div>
  );
}
