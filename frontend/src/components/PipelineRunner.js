import React, { useRef, useEffect, useState } from "react";
import {
  Play,
  Square,
  FileText,
  Download,
  Terminal,
  CheckCircle2,
  XCircle,
  Loader2,
  AlertTriangle,
  Info,
  BarChart3,
  GitBranch,
  RefreshCw,
  Target,
  TrendingUp,
} from "lucide-react";
import usePipeline from "../hooks/usePipeline";
import { toYAML } from "../utils/yamlUtils";

const LOG_ICONS = {
  info: Info,
  success: CheckCircle2,
  error: XCircle,
  warn: AlertTriangle,
};

const LOG_COLORS = {
  info: "text-slate-600",
  success: "text-emerald-600",
  error: "text-red-600",
  warn: "text-amber-600",
};

function LogEntry({ entry }) {
  const Icon = LOG_ICONS[entry.level] || Info;
  return (
    <div className={`flex items-start gap-2 ${LOG_COLORS[entry.level] || "text-slate-600"}`}>
      <Icon size={14} className="shrink-0 mt-0.5" />
      <span className="flex-1">{entry.message}</span>
      <span className="text-[10px] text-slate-400 font-mono shrink-0">{entry.timestamp}</span>
    </div>
  );
}

function CoverageBar({ pct }) {
  const color =
    pct >= 90 ? "bg-emerald-500" : pct >= 70 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <span className="text-xs font-mono text-slate-600 w-10 text-right">{pct.toFixed(0)}%</span>
    </div>
  );
}

function CoverageTrendChart({ trend }) {
  if (!trend || trend.length < 2) return null;
  const max = Math.max(...trend.map((t) => t.coverage));
  const min = Math.min(...trend.map((t) => t.coverage));
  const range = max - min || 1;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center gap-2 mb-3">
        <TrendingUp size={16} className="text-brand-600" />
        <span className="text-sm font-semibold text-slate-800">Coverage Trend</span>
        {trend.length >= 2 && (
          <span className="text-xs text-slate-400 ml-auto">
            Delta: {(trend[trend.length-1].coverage - trend[0].coverage) > 0 ? '+' : ''}
            {(trend[trend.length-1].coverage - trend[0].coverage).toFixed(1)}%
          </span>
        )}
      </div>
      <div className="flex items-end gap-1 h-28">
        {trend.map((t, i) => {
          const h = ((t.coverage - min) / range) * 100;
          const color =
            t.coverage >= 90 ? "bg-emerald-400" :
            t.coverage >= 70 ? "bg-amber-400" : "bg-red-400";
          const prevCov = i > 0 ? trend[i-1].coverage : t.coverage;
          const gain = t.coverage - prevCov;
          return (
            <div key={i} className="flex-1 flex flex-col items-center gap-1">
              <span className="text-[10px] font-mono text-slate-500">{t.coverage.toFixed(0)}%</span>
              <div className="flex flex-col items-center w-full">
                {i > 0 && gain !== 0 && (
                  <span className={`text-[8px] ${gain > 0 ? 'text-emerald-500' : 'text-red-400'}`}>
                    {gain > 0 ? '+' : ''}{gain.toFixed(1)}%
                  </span>
                )}
                <div
                  className={`w-full rounded-t transition-all duration-500 ${color}`}
                  style={{ height: `${Math.max(h, 5)}%`, minHeight: '8px' }}
                  title={`${t.version}: ${t.coverage.toFixed(1)}%`}
                />
              </div>
              <span className="text-[9px] text-slate-400">{t.version}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SeedCoverageSummary({ seeds }) {
  if (!seeds || seeds.length === 0) return null;
  const best = Math.max(...seeds.map(s => s.pct));
  const worst = Math.min(...seeds.map(s => s.pct));
  return (
    <div className="flex items-center gap-3 text-xs text-slate-500">
      <span className="font-medium text-slate-600">Seeds:</span>
      {seeds.map((s, i) => {
        const color = s.pct >= 90 ? "text-emerald-600" : s.pct >= 70 ? "text-amber-600" : "text-red-600";
        return <span key={i} className={`font-mono ${color}`}>s{i+1}={s.pct.toFixed(0)}%</span>;
      })}
      <span className="text-slate-300">|</span>
      <span className="font-mono text-slate-500">Δ{best - worst > 0 ? '+' : ''}{(best - worst).toFixed(0)}%</span>
    </div>
  );
}

function VersionHistory({ versions, latestGaps }) {
  if (!versions || versions.length === 0) return null;
  const passed = versions.filter(v => v.coverage >= 90).length;
  const failed = versions.length - passed;
  const bestCov = Math.max(...versions.map(v => v.coverage));
  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-100">
        <GitBranch size={16} className="text-brand-600" />
        <span className="text-sm font-semibold text-slate-800">Version History</span>
        <span className="text-xs text-slate-400 ml-auto">{versions.length} versions</span>
      </div>
      {/* Pass/Fail summary */}
      <div className="flex items-center gap-4 px-4 py-2 bg-slate-50 border-b border-slate-100">
        <div className="flex items-center gap-1.5">
          <CheckCircle2 size={14} className="text-emerald-500" />
          <span className="text-xs font-medium text-slate-700">{passed} passed</span>
        </div>
        <div className="flex items-center gap-1.5">
          <XCircle size={14} className="text-red-500" />
          <span className="text-xs font-medium text-slate-700">{failed} failed</span>
        </div>
        <div className="flex items-center gap-1.5 ml-auto">
          <span className="text-xs text-slate-400">Best:</span>
          <span className="text-xs font-bold text-slate-700">{bestCov.toFixed(1)}%</span>
        </div>
      </div>
      <div className="divide-y divide-slate-100 max-h-64 overflow-y-auto">
        {[...versions].reverse().map((v, i) => {
          const prev = i < versions.length - 1 ? versions[versions.length - 1 - (i + 1)] : null;
          const delta = prev ? v.coverage - prev.coverage : null;
          return (
            <div key={i} className="flex items-center gap-3 px-4 py-2.5">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                v.coverage >= 90 ? 'bg-emerald-50' : v.coverage >= 70 ? 'bg-amber-50' : 'bg-red-50'
              }`}>
                <span className={`text-xs font-bold ${
                  v.coverage >= 90 ? 'text-emerald-700' : v.coverage >= 70 ? 'text-amber-700' : 'text-red-700'
                }`}>{v.version}</span>
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-slate-700">{v.files} files</span>
                  <span className="text-[11px] text-slate-300">|</span>
                  <span className={`text-sm font-medium ${
                    v.coverage >= 90 ? 'text-emerald-700' : 'text-slate-800'
                  }`}>{v.coverage.toFixed(1)}%</span>
                  {delta !== null && (
                    <span className={`text-[11px] font-mono ${
                      delta > 0 ? 'text-emerald-500' : delta < 0 ? 'text-red-400' : 'text-slate-400'
                    }`}>
                      {delta > 0 ? '+' : ''}{delta.toFixed(1)}%
                    </span>
                  )}
                </div>
                <CoverageBar pct={v.coverage} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CoverageGapsList({ gaps }) {
  if (!gaps || gaps.length === 0) return null;
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-amber-100">
        <Target size={16} className="text-amber-600" />
        <span className="text-sm font-semibold text-amber-800">Coverage Gaps</span>
        <span className="text-xs text-amber-600 ml-auto">{gaps.length} uncovered</span>
      </div>
      <div className="p-3 space-y-1 max-h-32 overflow-y-auto">
        {gaps.map((g, i) => (
          <div key={i} className="flex items-center gap-2 text-xs text-amber-700 font-mono">
            <span className="w-2 h-2 rounded-full bg-amber-400 shrink-0" />
            {g.bin}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function PipelineRunner({ spec }) {
  const {
    running,
    autoTraining,
    logs,
    artifacts,
    error,
    versions,
    coverageTrend,
    coverageGaps,
    seedResults,
    autoTrainMax,
    runPipeline,
    runAutoTrain,
  } = usePipeline();
  const logEndRef = useRef(null);
  const [maxIter, setMaxIter] = useState(5);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const handleRun = () => {
    if (!spec) return;
    const yamlText = toYAML(spec);
    runPipeline(yamlText);
  };

  const handleAutoTrain = () => {
    if (!spec) return;
    const yamlText = toYAML(spec);
    runAutoTrain(yamlText, maxIter);
  };

  const handleDownload = (file) => {
    const blob = new Blob([file.content || ""], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = file.name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleDownloadAll = () => {
    artifacts.forEach((file) => handleDownload(file));
  };

  const canRun = spec && Object.keys(spec).length > 0 && !running;

  return (
    <div className="card">
      <div className="card-header">
        <Terminal size={18} className="text-brand-600" />
        <h2>Pipeline Runner</h2>
        {autoTraining && (
          <span className="badge badge-warning text-xs ml-2">
            <RefreshCw size={12} className="animate-spin inline mr-1" />
            Auto-Training
          </span>
        )}
        {versions.length > 0 && !running && (
          <span className="badge badge-success text-xs ml-2">v{versions.length}</span>
        )}

        <div className="ml-auto flex items-center gap-3">
          {spec && (
            <span className="text-xs text-slate-400">
              Spec: <span className="font-mono text-slate-600">{spec.design_name || "unnamed"}</span>
            </span>
          )}
          <div className="flex items-center gap-2">
            <label className="text-[11px] text-slate-400">Iterations</label>
            <input
              type="number"
              min={1}
              max={20}
              value={maxIter}
              onChange={(e) => setMaxIter(Math.max(1, Math.min(20, parseInt(e.target.value) || 5)))}
              className="w-14 px-2 py-1 text-xs border border-slate-200 rounded-md text-center"
              disabled={running}
            />
          </div>
          <button
            className="btn-primary text-xs"
            onClick={handleRun}
            disabled={!canRun}
            title="Single pass generation"
          >
            {running && !autoTraining ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                Running...
              </>
            ) : (
              <>
                <Play size={14} />
                Run
              </>
            )}
          </button>
          <button
            className={running ? "btn-secondary text-xs opacity-50" : "btn-primary text-xs bg-amber-600 hover:bg-amber-700"}
            onClick={handleAutoTrain}
            disabled={!canRun}
            title={`Coverage-driven auto-training (${maxIter} iterations max)`}
          >
            {running && autoTraining ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                Training...
              </>
            ) : (
              <>
                <RefreshCw size={14} />
                Auto-Train
              </>
            )}
          </button>
        </div>
      </div>

      <div className="card-body space-y-4">
        {/* Logs */}
        <div className="rounded-lg bg-slate-900 border border-slate-700">
          <div className="flex items-center justify-between px-4 py-2 border-b border-slate-700">
            <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">
              Pipeline Logs
            </span>
            <span className="text-[11px] text-slate-500">{logs.length} entries</span>
          </div>
          <div className="p-4 space-y-1 max-h-48 overflow-y-auto" style={{ minHeight: "80px" }}>
            {logs.length === 0 && (
              <p className="text-xs text-slate-500 italic">Click "Run" or "Auto-Train" to start</p>
            )}
            {logs.map((entry, i) => (
              <LogEntry key={i} entry={entry} />
            ))}
            <div ref={logEndRef} />
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3">
            <div className="flex items-center gap-2 text-sm text-red-700">
              <XCircle size={16} />
              {error}
            </div>
          </div>
        )}

        {/* Coverage Trend */}
        {coverageTrend && coverageTrend.length > 1 && <CoverageTrendChart trend={coverageTrend} />}

        {/* Seed Coverage Summary */}
        {seedResults && seedResults.length > 0 && (
          <SeedCoverageSummary seeds={seedResults} />
        )}

        {/* Coverage Gaps */}
        <CoverageGapsList gaps={coverageGaps} />

        {/* Version History + Artifacts side by side */}
        {versions.length > 0 && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Version History */}
            <div className="lg:col-span-1">
              <VersionHistory versions={versions} latestGaps={coverageGaps} />
            </div>

            {/* Artifacts */}
            <div className="lg:col-span-2">
              <div className="rounded-lg border border-slate-200 bg-white">
                <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
                  <div className="flex items-center gap-2">
                    <FileText size={16} className="text-brand-600" />
                    <h3 className="text-sm font-semibold text-slate-800">Generated Artifacts</h3>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-400">{artifacts.length} files</span>
                    <button className="btn-secondary text-xs" onClick={handleDownloadAll}>
                      <Download size={14} />
                      Download All
                    </button>
                  </div>
                </div>
                <div className="divide-y divide-slate-100 max-h-80 overflow-y-auto">
                  {artifacts.map((file, i) => (
                    <div
                      key={i}
                      className="flex items-center gap-3 px-4 py-2.5 hover:bg-slate-50 cursor-pointer transition-colors"
                      onClick={() => handleDownload(file)}
                    >
                      <div className="w-8 h-8 rounded-md bg-brand-50 flex items-center justify-center shrink-0">
                        <FileText size={16} className="text-brand-600" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-slate-800 truncate">{file.name}</p>
                        <p className="text-[11px] text-slate-400 truncate">{file.path}</p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-[11px] text-slate-400">{file.size}</span>
                        <button className="p-1.5 rounded-md text-slate-400 hover:text-brand-600 hover:bg-brand-50 transition-all">
                          <Download size={14} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Summary footer */}
        {versions.length > 0 && !running && (
          <div className="flex items-center justify-between text-xs text-slate-400 border-t border-slate-100 pt-3">
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1">
                <GitBranch size={12} />
                {versions.length} versions
              </span>
              <span className="flex items-center gap-1">
                <BarChart3 size={12} />
                Best: {Math.max(...versions.map((v) => v.coverage)).toFixed(1)}%
              </span>
              <span className="flex items-center gap-1">
                <FileText size={12} />
                {artifacts.length} files
              </span>
            </div>
            {coverageGaps && coverageGaps.length > 0 && (
              <span className="text-amber-600 flex items-center gap-1">
                <Target size={12} />
                {coverageGaps.length} gaps remaining
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
