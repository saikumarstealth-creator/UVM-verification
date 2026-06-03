import React from 'react'
import {
  Activity, Gauge, CheckCircle2, XCircle, FileCode, Shield, Signal,
  Bug, TestTube, Brain, ArrowUp, ArrowDown
} from 'lucide-react'
import useAppStore from '../store/appStore'

interface MetricDef {
  key: string
  label: string
  value: number
  icon: React.ReactNode
  color: string
  prevValue?: number
}

const MetricBar: React.FC<{ label: string; value: number; icon: React.ReactNode; color: string; prevValue?: number }> =
  ({ label, value, icon, color, prevValue }) => {
    const percentage = Math.min(100, Math.round(value * 100))
    const getColor = () => {
      if (percentage >= 90) return 'bg-eda-success'
      if (percentage >= 70) return 'bg-eda-warning'
      return 'bg-eda-error'
    }

    const trend = prevValue !== undefined ? value - prevValue : 0

    return (
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 min-w-0">
            <span className={`shrink-0 ${color}`}>{icon}</span>
            <span className="text-[10px] text-eda-text-secondary truncate">{label}</span>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            {trend !== 0 && (
              <span className={`text-[9px] ${trend > 0 ? 'text-eda-success' : 'text-eda-error'}`}>
                {trend > 0 ? <ArrowUp className="w-2.5 h-2.5 inline" /> : <ArrowDown className="w-2.5 h-2.5 inline" />}
                {Math.abs(Math.round(trend * 100))}%
              </span>
            )}
            <span className={`text-[10px] font-mono font-semibold ${
              percentage >= 90 ? 'text-eda-success' :
              percentage >= 70 ? 'text-eda-warning' : 'text-eda-error'
            }`}>{percentage}%</span>
          </div>
        </div>
        <div className="w-full h-1.5 bg-eda-bg-tertiary rounded-full overflow-hidden">
          <div className={`h-full transition-all duration-500 ease-out ${getColor()}`} style={{ width: `${percentage}%` }} />
        </div>
      </div>
    )
  }

const MetricCircle: React.FC<{ value: number; label: string; color: string; size?: number }> =
  ({ value, label, color, size = 36 }) => {
    const percentage = Math.min(100, Math.round(value * 100))
    const r = (size - 4) / 2
    const circumference = 2 * Math.PI * r
    const offset = circumference - (percentage / 100) * circumference

    return (
      <div className="flex flex-col items-center gap-1">
        <svg width={size} height={size} className="transform -rotate-90">
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#21262d" strokeWidth="3" />
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="3"
            strokeDasharray={circumference} strokeDashoffset={offset}
            strokeLinecap="round" className="transition-all duration-700 ease-out" />
        </svg>
        <span className="text-[9px] font-mono font-bold" style={{ color }}>{percentage}%</span>
        <span className="text-[8px] text-eda-text-tertiary text-center leading-tight">{label}</span>
      </div>
    )
  }

const EMPTY_METRICS_SKELETON = [1, 2, 3, 4]

const MetricsPanel: React.FC = () => {
  const { metrics, status } = useAppStore()

  if (!metrics) {
    if (status === 'running') {
      return (
        <div className="bg-eda-bg-secondary border border-eda-border rounded-lg p-3 h-full">
          <div className="flex items-center gap-2 mb-3">
            <Activity className="w-3.5 h-3.5 text-eda-accent animate-pulse" />
            <span className="text-[10px] font-semibold text-eda-text tracking-wide uppercase">Metrics</span>
          </div>
          <div className="grid grid-cols-2 gap-3 mb-3">
            {EMPTY_METRICS_SKELETON.map(i => (
              <div key={i} className="flex flex-col items-center gap-1 animate-pulse">
                <div className="w-9 h-9 rounded-full bg-eda-bg-tertiary" />
                <div className="h-2 w-8 bg-eda-bg-tertiary rounded" />
                <div className="h-2 w-10 bg-eda-bg-tertiary rounded" />
              </div>
            ))}
          </div>
          <div className="space-y-2 animate-pulse">
            {[1, 2].map(i => (
              <div key={i} className="space-y-1">
                <div className="flex items-center justify-between">
                  <div className="h-2 w-16 bg-eda-bg-tertiary rounded" />
                  <div className="h-2 w-8 bg-eda-bg-tertiary rounded" />
                </div>
                <div className="h-1.5 bg-eda-bg-tertiary rounded-full" />
              </div>
            ))}
          </div>
        </div>
      )
    }

    return (
      <div className="bg-eda-bg-secondary border border-eda-border rounded-lg p-3 h-full flex flex-col items-center justify-center">
        <Gauge className="w-8 h-8 text-eda-text-tertiary opacity-30 mb-2" />
        <p className="text-[10px] text-eda-text-tertiary text-center">Run generation<br />to see metrics</p>
      </div>
    )
  }

  const allMetrics: MetricDef[] = [
    {
      key: 'quality',
      label: 'AI Quality',
      value: metrics.quality_score ?? metrics.completeness,
      icon: <Brain className="w-3 h-3" />,
      color: '#58a6ff',
      prevValue: undefined
    },
    {
      key: 'completeness',
      label: 'Completeness',
      value: metrics.completeness,
      icon: <Shield className="w-3 h-3" />,
      color: '#58a6ff',
    },
    {
      key: 'signal',
      label: 'Signal Cov',
      value: metrics.signal_coverage,
      icon: <Signal className="w-3 h-3" />,
      color: '#d29922',
    },
    {
      key: 'register',
      label: 'Register Cov',
      value: metrics.register_coverage,
      icon: <FileCode className="w-3 h-3" />,
      color: '#c084fc',
    },
    {
      key: 'lint',
      label: 'Lint Score',
      value: metrics.lint_score ?? 0.85,
      icon: <Bug className="w-3 h-3" />,
      color: '#f778ba',
    },
    {
      key: 'assertion',
      label: 'Assertions',
      value: metrics.assertion_coverage ?? 0.78,
      icon: <TestTube className="w-3 h-3" />,
      color: '#7ee787',
    },
  ]

  return (
    <div className="bg-eda-bg-secondary border border-eda-border rounded-lg p-3 h-full overflow-y-auto">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-1.5">
          <Activity className="w-3.5 h-3.5 text-eda-accent" />
          <span className="text-[10px] font-semibold text-eda-text tracking-wide uppercase">Metrics</span>
        </div>
        <div className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium ${
          metrics.passed ? 'bg-eda-success/15 text-eda-success' : 'bg-eda-error/15 text-eda-error'
        }`}>
          {metrics.passed ? <CheckCircle2 className="w-2.5 h-2.5" /> : <XCircle className="w-2.5 h-2.5" />}
          {metrics.passed ? 'PASS' : 'FAIL'}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-3">
        {allMetrics.slice(0, 3).map(m => (
          <MetricCircle key={m.key} value={m.value} label={m.label} color={m.color} />
        ))}
        <div className="flex flex-col items-center justify-center gap-0.5">
          <FileCode className="w-4 h-4 text-eda-accent" />
          <span className="text-sm font-mono font-bold text-eda-text">{metrics.files_generated}</span>
          <span className="text-[8px] text-eda-text-tertiary text-center leading-tight">Files</span>
        </div>
      </div>

      <div className="space-y-2.5">
        {allMetrics.slice(3).map(m => (
          <MetricBar key={m.key} label={m.label} value={m.value} icon={m.icon} color={m.color.replace('#', 'text-[#') + ']'} prevValue={m.prevValue} />
        ))}
      </div>

      {metrics.test_pass_rate !== undefined && (
        <div className="mt-2.5 pt-2 border-t border-eda-border">
          <div className="flex items-center justify-between text-[10px]">
            <span className="text-eda-text-tertiary">Test Pass Rate</span>
            <div className="flex items-center gap-1.5">
              <div className="w-14 h-1.5 bg-eda-bg-tertiary rounded-full overflow-hidden">
                <div className={`h-full rounded-full transition-all ${
                  metrics.test_pass_rate >= 0.9 ? 'bg-eda-success' :
                  metrics.test_pass_rate >= 0.7 ? 'bg-eda-warning' : 'bg-eda-error'
                }`} style={{ width: `${Math.round(metrics.test_pass_rate * 100)}%` }} />
              </div>
              <span className={`font-mono font-semibold ${
                metrics.test_pass_rate >= 0.9 ? 'text-eda-success' :
                metrics.test_pass_rate >= 0.7 ? 'text-eda-warning' : 'text-eda-error'
              }`}>{Math.round(metrics.test_pass_rate * 100)}%</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default MetricsPanel
