import React from 'react'
import { CheckCircle2, Loader2, Circle } from 'lucide-react'
import useAppStore, { PipelineStep } from '../store/appStore'

const STEPS: { key: PipelineStep; label: string; description: string }[] = [
  { key: 'spec_parse', label: 'Spec Parse', description: 'Parse YAML specification' },
  { key: 'feature_extract', label: 'Feature Extraction', description: 'Extract interfaces & registers' },
  { key: 'ml_generation', label: 'ML Generation', description: 'AI testbench generation' },
  { key: 'uvm_validation', label: 'UVM Validation', description: 'Structure & compliance check' },
  { key: 'coverage_analysis', label: 'Coverage Analysis', description: 'Coverage metric evaluation' },
  { key: 'export', label: 'Export', description: 'Package & prepare files' },
]

type StepStatus = 'completed' | 'active' | 'pending'

const PipelineVisualizer: React.FC = () => {
  const { status, currentStep, progress, completedSteps } = useAppStore()

  const getStepStatus = (stepKey: PipelineStep): StepStatus => {
    if (completedSteps.includes(stepKey)) return 'completed'
    if (currentStep === stepKey) return 'active'
    return 'pending'
  }

  const StatusIcon: React.FC<{ status: StepStatus }> = ({ status }) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="w-5 h-5 text-eda-success" />
      case 'active':
        return <Loader2 className="w-5 h-5 text-eda-accent animate-spin" />
      case 'pending':
        return <Circle className="w-5 h-5 text-eda-text-tertiary" />
    }
  }

  return (
    <div className="bg-eda-bg-secondary border border-eda-border rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-eda-text">Generation Pipeline</h2>
        <div className="flex items-center gap-2">
          <div className="w-32 h-1.5 bg-eda-bg-tertiary rounded-full overflow-hidden">
            <div 
              className="h-full bg-eda-accent transition-all duration-300 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
          <span className="text-xs font-mono text-eda-text-secondary">{progress}%</span>
        </div>
      </div>

      {/* Pipeline Steps */}
      <div className="flex flex-col gap-1">
        {STEPS.map((step, index) => {
          const stepStatus = getStepStatus(step.key)
          const isLast = index === STEPS.length - 1
          
          return (
            <div key={step.key} className="flex items-start gap-3">
              {/* Icon */}
              <div className="flex flex-col items-center">
                <div className="p-1">
                  <StatusIcon status={stepStatus} />
                </div>
                {!isLast && (
                  <div 
                    className={`w-px h-8 transition-colors duration-300 ${
                      stepStatus === 'completed' ? 'bg-eda-success' : 'bg-eda-border'
                    }`}
                  />
                )}
              </div>
              
              {/* Content */}
              <div className="py-1 flex-1">
                <div className="flex items-center gap-2">
                  <span 
                    className={`text-sm font-medium transition-colors ${
                      stepStatus === 'completed' ? 'text-eda-text' :
                      stepStatus === 'active' ? 'text-eda-accent' :
                      'text-eda-text-tertiary'
                    }`}
                  >
                    {step.label}
                  </span>
                  {stepStatus === 'active' && (
                    <span className="text-xs text-eda-accent animate-pulse">Running...</span>
                  )}
                </div>
                <p className="text-xs text-eda-text-tertiary mt-0.5">
                  {step.description}
                </p>
              </div>
            </div>
          )
        })}
      </div>

      {/* Status summary */}
      <div className="mt-4 pt-3 border-t border-eda-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div 
            className={`w-2 h-2 rounded-full ${
              status === 'running' ? 'bg-eda-accent animate-pulse' :
              status === 'completed' ? 'bg-eda-success' :
              status === 'failed' ? 'bg-eda-error' :
              'bg-eda-text-tertiary'
            }`}
          />
          <span className="text-xs text-eda-text-secondary capitalize">{status}</span>
        </div>
        <span className="text-xs text-eda-text-tertiary">
          {completedSteps.length}/{STEPS.length} steps
        </span>
      </div>
    </div>
  )
}

export default PipelineVisualizer
