import React from 'react'
import { Activity, Gauge, CheckCircle2, XCircle, FileCode, Shield, Signal } from 'lucide-react'
import useAppStore from '../store/appStore'

const MetricsPanel: React.FC = () => {
  const { metrics, status } = useAppStore()

  const MetricBar: React.FC<{ label: string; value: number; icon: React.ReactNode; color: string }> = 
    ({ label, value, icon, color }) => {
      const percentage = Math.round(value * 100)
      const getColor = () => {
        if (percentage >= 90) return 'bg-eda-success'
        if (percentage >= 70) return 'bg-eda-warning'
        return 'bg-eda-error'
      }
      
      return (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className={color}>{icon}</span>
              <span className="text-xs text-eda-text-secondary">{label}</span>
            </div>
            <span className={`text-xs font-mono font-semibold ${
              percentage >= 90 ? 'text-eda-success' :
              percentage >= 70 ? 'text-eda-warning' : 'text-eda-error'
            }`}>
              {percentage}%
            </span>
          </div>
          <div className="w-full h-1.5 bg-eda-bg-tertiary rounded-full overflow-hidden">
            <div 
              className={`h-full transition-all duration-500 ease-out ${getColor()}`}
              style={{ width: `${percentage}%` }}
            />
          </div>
        </div>
      )
    }

  if (!metrics) {
    if (status === 'running') {
      return (
        <div className="bg-eda-bg-secondary border border-eda-border rounded-lg p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-eda-text flex items-center gap-2">
              <Activity className="w-4 h-4 text-eda-accent" />
              Generation Metrics
            </h2>
          </div>
          <div className="space-y-3 animate-pulse">
            {[1, 2, 3].map(i => (
              <div key={i} className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="h-3 w-24 bg-eda-bg-tertiary rounded" />
                  <div className="h-3 w-10 bg-eda-bg-tertiary rounded" />
                </div>
                <div className="h-1.5 bg-eda-bg-tertiary rounded-full" />
              </div>
            ))}
          </div>
        </div>
      )
    }

    return (
      <div className="bg-eda-bg-secondary border border-eda-border rounded-lg p-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-eda-text flex items-center gap-2">
            <Activity className="w-4 h-4 text-eda-text-tertiary" />
            Generation Metrics
          </h2>
        </div>
        <div className="flex flex-col items-center justify-center py-8 text-eda-text-tertiary">
          <Gauge className="w-10 h-10 mb-3 opacity-30" />
          <p className="text-xs">Run generation to see metrics</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-eda-bg-secondary border border-eda-border rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-eda-text flex items-center gap-2">
          <Activity className="w-4 h-4 text-eda-accent" />
          Generation Metrics
        </h2>
        
        <div className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium ${
          metrics.passed 
            ? 'bg-eda-success/15 text-eda-success' 
            : 'bg-eda-error/15 text-eda-error'
        }`}>
          {metrics.passed 
            ? <CheckCircle2 className="w-3.5 h-3.5" /> 
            : <XCircle className="w-3.5 h-3.5" />
          }
          {metrics.passed ? 'PASSED' : 'NEEDS WORK'}
        </div>
      </div>

      <div className="space-y-4">
        <MetricBar 
          label="Completeness" 
          value={metrics.completeness} 
          icon={<Shield className="w-3.5 h-3.5" />}
          color="text-eda-accent"
        />
        
        <MetricBar 
          label="Signal Coverage" 
          value={metrics.signal_coverage} 
          icon={<Signal className="w-3.5 h-3.5" />}
          color="text-eda-warning"
        />
        
        <MetricBar 
          label="Register Coverage" 
          value={metrics.register_coverage} 
          icon={<FileCode className="w-3.5 h-3.5" />}
          color="text-purple-400"
        />
      </div>

      <div className="mt-4 pt-3 border-t border-eda-border">
        <div className="flex items-center justify-between text-xs">
          <span className="text-eda-text-tertiary">Files Generated</span>
          <span className="font-mono font-semibold text-eda-text">{metrics.files_generated}</span>
        </div>
      </div>
    </div>
  )
}

export default MetricsPanel
