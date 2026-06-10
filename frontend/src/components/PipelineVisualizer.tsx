import React from 'react'
import { CheckCircle2, Loader2, Circle, Clock, Zap } from 'lucide-react'
import useAppStore, { PipelineStep } from '../store/appStore'

const STEPS: { key: PipelineStep; label: string; description: string; icon: React.ReactNode }[] = [
  { key: 'spec_parse', label: 'Spec Parse', description: 'Parse YAML specification', icon: <FileIcon /> },
  { key: 'feature_extract', label: 'Feature Extraction', description: 'Extract interfaces & registers', icon: <ExtractIcon /> },
  { key: 'ml_generation', label: 'ML Generation', description: 'AI testbench generation', icon: <AIcon /> },
  { key: 'uvm_validation', label: 'UVM Validation', description: 'Structure & compliance check', icon: <ShieldIcon /> },
  { key: 'coverage_analysis', label: 'Coverage Analysis', description: 'Coverage metric evaluation', icon: <ChartIcon /> },
  { key: 'export', label: 'Export', description: 'Package & prepare files', icon: <ExportIcon /> },
]

function FileIcon() { return <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none"><rect x="1" y="1" width="10" height="10" rx="1" stroke="currentColor" strokeWidth="1.2"/><path d="M3 4h6M3 6h6M3 8h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg> }
function ExtractIcon() { return <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none"><path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/><circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.2"/></svg> }
function AIcon() { return <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none"><path d="M6 1v10M1 6h10" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/><circle cx="6" cy="6" r="2" fill="currentColor"/></svg> }
function ShieldIcon() { return <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none"><path d="M6 1L1 3v3c0 3 5 5 5 5s5-2 5-5V3L6 1z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/><path d="M4.5 6.5l1.5 1.5 2-3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/></svg> }
function ChartIcon() { return <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none"><rect x="1" y="5" width="2" height="5" rx="0.5" fill="currentColor"/><rect x="5" y="3" width="2" height="7" rx="0.5" fill="currentColor"/><rect x="9" y="1" width="2" height="9" rx="0.5" fill="currentColor"/></svg> }
function ExportIcon() { return <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none"><path d="M6 9V2M3 4.5L6 2l3 2.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/><path d="M2 10h8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg> }

type StepStatus = 'completed' | 'active' | 'pending'

const formatDuration = (ms: number): string => {
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  const m = Math.floor(ms / 60000)
  const s = Math.round((ms % 60000) / 1000)
  return `${m}m ${s}s`
}

const PipelineVisualizer: React.FC = () => {
  const { status, currentStep, progress, completedSteps, stepTimings, message } = useAppStore()
  const [elapsed, setElapsed] = React.useState(0)

  React.useEffect(() => {
    if (status !== 'running') {
      setElapsed(0)
      return
    }
    const start = Date.now()
    const interval = setInterval(() => setElapsed(Date.now() - start), 500)
    return () => clearInterval(interval)
  }, [status])

  const getStepStatus = (stepKey: PipelineStep): StepStatus => {
    if (completedSteps.includes(stepKey)) return 'completed'
    if (currentStep === stepKey) return 'active'
    return 'pending'
  }

  const getStepDuration = (stepKey: PipelineStep): number | null => {
    const t = stepTimings.find(s => s.step === stepKey)
    if (!t) return null
    if (t.completedAt && t.startedAt) return t.completedAt - t.startedAt
    if (t.startedAt && currentStep === stepKey) return Date.now() - t.startedAt
    return null
  }

  const getEstimatedRemaining = (): string | null => {
    if (status !== 'running' || stepTimings.length === 0) return null
    const completed = stepTimings.filter(t => t.completedAt && t.startedAt)
    if (completed.length === 0) return null
    const avgMs = completed.reduce((sum, t) => sum + (t.completedAt! - t.startedAt!), 0) / completed.length
    const remaining = STEPS.length - completedSteps.length
    if (remaining <= 0) return null
    return formatDuration(avgMs * remaining)
  }

  const StatusIcon: React.FC<{ status: StepStatus; animate?: boolean }> = ({ status, animate }) => {
    switch (status) {
      case 'completed': return <CheckCircle2 className={`w-4 h-4 text-eda-success ${animate ? 'animate-scale-in' : ''}`} />
      case 'active': return <Loader2 className="w-4 h-4 text-eda-accent animate-spin" />
      case 'pending': return <Circle className="w-4 h-4 text-eda-text-tertiary" />
    }
  }

  return (
    <div className="bg-eda-bg-secondary border border-eda-border rounded-lg p-3 h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <h2 className="text-[11px] font-semibold text-eda-text tracking-wide uppercase">Pipeline</h2>
          {status === 'running' && (
            <span className="text-[9px] text-eda-text-tertiary font-mono flex items-center gap-1 animate-fade-in">
              <Clock className="w-2.5 h-2.5" /> {formatDuration(elapsed)}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {getEstimatedRemaining() && (
            <span className="text-[9px] text-eda-text-tertiary font-mono flex items-center gap-1 animate-fade-in">
              <Zap className="w-2.5 h-2.5 text-eda-warning" /> ETA: {getEstimatedRemaining()}
            </span>
          )}
          <div className="w-20 h-1 bg-eda-bg-tertiary rounded-full overflow-hidden relative">
            <div className="h-full bg-eda-accent transition-all duration-500 ease-out" style={{ width: `${progress}%` }} />
            {status === 'running' && <div className="shimmer-overlay" />}
          </div>
          <span className="text-[9px] font-mono text-eda-text-secondary">{progress}%</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto" style={{ scrollbarWidth: 'thin' }}>
        <div className="grid grid-cols-2 gap-x-3 gap-y-1">
          {STEPS.map((step) => {
            const stepStatus = getStepStatus(step.key)
            const duration = getStepDuration(step.key)
            return (
              <div key={step.key}
                className={`flex items-start gap-2 p-1.5 rounded-md transition-all duration-300 ${
                  stepStatus === 'active' ? 'bg-eda-accent/8 step-glow-ring' :
                  stepStatus === 'completed' ? 'bg-eda-success/[0.04]' : ''
                }`}>
                <div className={`mt-0.5 ${stepStatus === 'completed' ? 'text-eda-success' : stepStatus === 'active' ? 'text-eda-accent' : 'text-eda-text-tertiary'}`}>
                  <StatusIcon status={stepStatus} animate={stepStatus === 'completed'} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className={`text-[10px] ${stepStatus === 'completed' ? 'text-eda-text font-medium' : stepStatus === 'active' ? 'text-eda-accent font-medium' : 'text-eda-text-tertiary'}`}>
                      {step.icon}
                    </span>
                    <span className={`text-[10px] font-medium truncate transition-all duration-300 ${
                      stepStatus === 'completed' ? 'text-eda-text' :
                      stepStatus === 'active' ? 'text-eda-accent' :
                      'text-eda-text-tertiary'
                    }`}>{step.label}</span>
                    {stepStatus === 'active' && <span className="text-[8px] text-eda-accent animate-pulse-soft">●</span>}
                  </div>
                  <p className={`text-[9px] truncate mt-0.5 transition-all duration-300 ${
                    stepStatus === 'active' ? 'text-eda-text-tertiary' : 'text-eda-text-tertiary/70'
                  }`}>{step.description}</p>
                  {duration !== null && (
                    <span className="text-[8px] text-eda-text-tertiary/50 font-mono animate-fade-in">{formatDuration(duration)}</span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div className="mt-2 pt-2 border-t border-eda-border flex items-center justify-between animate-fade-in">
        <div className="flex items-center gap-1.5">
          <div className={`w-1.5 h-1.5 rounded-full transition-all duration-300 ${
            status === 'running' ? 'bg-eda-accent animate-pulse-soft shadow-[0_0_6px_rgba(88,166,255,0.5)]' :
            status === 'completed' ? 'bg-eda-success' :
            status === 'failed' ? 'bg-eda-error' :
            'bg-eda-text-tertiary'
          }`} />
          <span className={`text-[9px] font-medium capitalize transition-all duration-300 ${
            status === 'running' ? 'text-eda-accent' :
            status === 'completed' ? 'text-eda-success' :
            'text-eda-text-tertiary'
          }`}>{status === 'pending' ? 'Ready' : status}</span>
        </div>
        <div className="flex items-center gap-2 text-[9px] text-eda-text-tertiary">
          {message !== 'Ready to generate' && (
            <span className="truncate max-w-[100px] animate-fade-in">{message}</span>
          )}
          <span className="font-mono">{completedSteps.length}/{STEPS.length}</span>
        </div>
      </div>
    </div>
  )
}

export default PipelineVisualizer
