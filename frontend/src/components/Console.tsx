import React from 'react'
import { Terminal, Minus, Maximize2, Play, Check, AlertCircle } from 'lucide-react'
import useAppStore, { PipelineStatus } from '../store/appStore'

const Console: React.FC = () => {
  const { logs, message, status } = useAppStore()
  const [isMinimized, setIsMinimized] = React.useState(false)
  const consoleRef = React.useRef<HTMLDivElement>(null)

  React.useEffect(() => {
    if (consoleRef.current) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight
    }
  }, [logs])

  const getStatusColor = (s: PipelineStatus) => {
    switch (s) {
      case 'running': return 'text-eda-accent'
      case 'completed': return 'text-eda-success'
      case 'failed': return 'text-eda-error'
      default: return 'text-eda-text-secondary'
    }
  }

  const getStatusIcon = (s: PipelineStatus) => {
    switch (s) {
      case 'running': return <Play className="w-3 h-3" />
      case 'completed': return <Check className="w-3 h-3" />
      case 'failed': return <AlertCircle className="w-3 h-3" />
      default: return null
    }
  }

  const parseLogLine = (line: string) => {
    const hasError = line.toLowerCase().includes('error') || line.toLowerCase().includes('fail')
    const hasWarning = line.toLowerCase().includes('warning')
    const hasSuccess = line.toLowerCase().includes('✓') || line.toLowerCase().includes('passed')
    
    if (hasError) return 'text-eda-error'
    if (hasWarning) return 'text-eda-warning'
    if (hasSuccess) return 'text-eda-success'
    return 'text-eda-text-secondary'
  }

  if (isMinimized) {
    return (
      <div className="bg-eda-bg-secondary border-t border-eda-border">
        <div className="flex items-center justify-between px-4 py-2 cursor-pointer hover:bg-eda-bg-tertiary/50"
             onClick={() => setIsMinimized(false)}>
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-eda-text-secondary" />
            <span className="text-xs font-medium text-eda-text-secondary">Console</span>
          </div>
          <div className="flex items-center gap-2">
            {getStatusIcon(status)}
            <span className={`text-xs font-mono ${getStatusColor(status)}`}>
              {message}
            </span>
            <Maximize2 className="w-4 h-4 text-eda-text-tertiary" />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-eda-bg-secondary border-t border-eda-border flex flex-col" style={{ height: '220px' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-eda-border">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-eda-text-secondary" />
          <span className="text-xs font-medium text-eda-text">Console</span>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            {getStatusIcon(status)}
            <span className={`text-xs font-mono ${getStatusColor(status)}`}>
              {message}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <button onClick={() => setIsMinimized(true)}
                    className="p-1 hover:bg-eda-bg-tertiary rounded transition-colors">
              <Minus className="w-3.5 h-3.5 text-eda-text-tertiary" />
            </button>
          </div>
        </div>
      </div>

      {/* Logs */}
      <div 
        ref={consoleRef}
        className="flex-1 overflow-y-auto px-4 py-2 bg-black/30"
      >
        {logs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-eda-text-tertiary">
            <Terminal className="w-8 h-8 mb-2 opacity-40" />
            <span className="text-xs">Logs will appear here during generation</span>
          </div>
        ) : (
          logs.map((log, i) => (
            <div key={i} className={`text-xs font-mono leading-relaxed ${parseLogLine(log)}`}>
              {log}
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default Console
