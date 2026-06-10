import React from 'react'
import {
  Terminal, Minus, Maximize2, Play, Check, AlertCircle,
  AlertTriangle, Info, Copy, Trash2, Filter, ChevronDown
} from 'lucide-react'
import useAppStore, { PipelineStatus, LogLevel } from '../store/appStore'

const LOG_LEVEL_CONFIG: Record<LogLevel, { color: string; bg: string; icon: React.ReactNode; label: string }> = {
  error: {
    color: 'text-eda-error',
    bg: 'bg-eda-error/10',
    icon: <AlertCircle className="w-3 h-3 shrink-0" />,
    label: 'ERR'
  },
  warn: {
    color: 'text-eda-warning',
    bg: 'bg-eda-warning/10',
    icon: <AlertTriangle className="w-3 h-3 shrink-0" />,
    label: 'WARN'
  },
  success: {
    color: 'text-eda-success',
    bg: 'bg-eda-success/10',
    icon: <Check className="w-3 h-3 shrink-0" />,
    label: 'OK'
  },
  info: {
    color: 'text-eda-text-secondary',
    bg: 'bg-transparent',
    icon: <Info className="w-3 h-3 shrink-0" />,
    label: 'INFO'
  }
}

type LogFilter = 'all' | LogLevel

const Console: React.FC = () => {
  const { logs, message, status, clearLogs } = useAppStore()
  const [isMinimized, setIsMinimized] = React.useState(false)
  const [logFilter, setLogFilter] = React.useState<LogFilter>('all')
  const [showFilterMenu, setShowFilterMenu] = React.useState(false)
  const [prevLogCount, setPrevLogCount] = React.useState(0)
  const consoleRef = React.useRef<HTMLDivElement>(null)

  React.useEffect(() => {
    if (consoleRef.current) {
      consoleRef.current.scrollTo({ top: consoleRef.current.scrollHeight, behavior: 'smooth' })
    }
  }, [logs])

  React.useEffect(() => {
    setPrevLogCount(logs.length)
  }, [logs.length])

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

  const filteredLogs = logFilter === 'all' ? logs : logs.filter(l => l.level === logFilter)

  const logCounts = {
    all: logs.length,
    error: logs.filter(l => l.level === 'error').length,
    warn: logs.filter(l => l.level === 'warn').length,
    success: logs.filter(l => l.level === 'success').length,
    info: logs.filter(l => l.level === 'info').length,
  }

  const handleCopyLogs = async () => {
    const text = logs.map(l => `[${l.timestamp}] [${l.level.toUpperCase()}] ${l.message}`).join('\n')
    await navigator.clipboard.writeText(text)
  }

  if (isMinimized) {
    return (
      <div className="bg-eda-bg-secondary border-t border-eda-border">
        <div className="flex items-center justify-between px-4 py-2 cursor-pointer hover:bg-eda-bg-tertiary/50"
             onClick={() => setIsMinimized(false)}>
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-eda-text-secondary" />
            <span className="text-xs font-medium text-eda-text-secondary">Console</span>
            {logs.length > 0 && (
              <div className="flex items-center gap-1.5 ml-1">
                {logCounts.error > 0 && (
                  <span className="text-[10px] px-1 py-0.5 rounded bg-eda-error/15 text-eda-error font-mono">{logCounts.error}</span>
                )}
                {logCounts.warn > 0 && (
                  <span className="text-[10px] px-1 py-0.5 rounded bg-eda-warning/15 text-eda-warning font-mono">{logCounts.warn}</span>
                )}
                <span className="text-[10px] text-eda-text-tertiary font-mono">{logCounts.all} lines</span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            {getStatusIcon(status)}
            <span className={`text-xs font-mono ${getStatusColor(status)}`}>{message}</span>
            <Maximize2 className="w-3.5 h-3.5 text-eda-text-tertiary" />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-eda-bg-secondary border-t border-eda-border flex flex-col" style={{ height: '220px' }}>
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-eda-border bg-eda-bg-tertiary/30">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-eda-text-secondary" />
          <span className="text-xs font-medium text-eda-text">Console</span>
          {logs.length > 0 && (
            <div className="flex items-center gap-1 text-[10px] text-eda-text-tertiary font-mono">
              <span className="text-eda-success">{logCounts.success}</span>
              <span className="text-eda-text-tertiary">/</span>
              <span className="text-eda-warning">{logCounts.warn}</span>
              <span className="text-eda-text-tertiary">/</span>
              <span className="text-eda-error">{logCounts.error}</span>
              <span className="text-eda-text-tertiary">/</span>
              <span>{logCounts.info}</span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-1">
          <div className="relative">
            <button onClick={() => setShowFilterMenu(!showFilterMenu)}
              className="flex items-center gap-1 px-2 py-1 text-[10px] text-eda-text-tertiary hover:text-eda-text hover:bg-eda-bg-tertiary rounded transition-colors">
              <Filter className="w-3 h-3" />
              {logFilter === 'all' ? 'All' : logFilter}
              <ChevronDown className="w-2.5 h-2.5" />
            </button>
            {showFilterMenu && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setShowFilterMenu(false)} />
                <div className="absolute right-0 top-full mt-1 bg-eda-bg-tertiary border border-eda-border rounded-md shadow-lg z-20 min-w-[100px]">
                  {(['all', 'error', 'warn', 'success', 'info'] as LogFilter[]).map(f => (
                    <button key={f} onClick={() => { setLogFilter(f); setShowFilterMenu(false) }}
                      className={`w-full flex items-center gap-2 px-3 py-1.5 text-xs text-left transition-colors ${
                        logFilter === f ? 'text-eda-accent bg-eda-accent/10' : 'text-eda-text-secondary hover:bg-eda-bg'
                      }`}>
                      {f !== 'all' && LOG_LEVEL_CONFIG[f].icon}
                      <span className="capitalize">{f}</span>
                      <span className="ml-auto text-[10px] text-eda-text-tertiary">({logCounts[f]})</span>
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>

          <button onClick={handleCopyLogs} disabled={logs.length === 0}
            className="p-1 hover:bg-eda-bg-tertiary rounded transition-colors disabled:opacity-30" title="Copy all logs">
            <Copy className="w-3.5 h-3.5 text-eda-text-tertiary" />
          </button>
          <button onClick={clearLogs} disabled={logs.length === 0}
            className="p-1 hover:bg-eda-bg-tertiary rounded transition-colors disabled:opacity-30" title="Clear console">
            <Trash2 className="w-3.5 h-3.5 text-eda-text-tertiary" />
          </button>
          <div className="flex items-center gap-1 ml-1 pl-2 border-l border-eda-border">
            {getStatusIcon(status)}
            <span className={`text-[10px] font-mono ${getStatusColor(status)}`}>{message}</span>
            <button onClick={() => setIsMinimized(true)}
              className="p-1 hover:bg-eda-bg-tertiary rounded transition-colors">
              <Minus className="w-3.5 h-3.5 text-eda-text-tertiary" />
            </button>
          </div>
        </div>
      </div>

      <div ref={consoleRef} className="flex-1 overflow-y-auto bg-black/30 font-mono">
        {filteredLogs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-eda-text-tertiary">
            <Terminal className="w-6 h-6 mb-1.5 opacity-40" />
            <span className="text-[10px]">{logs.length > 0 ? 'No logs match filter' : 'Logs will appear here during generation'}</span>
          </div>
        ) : (
          <div className="py-1">
            {filteredLogs.map((log, i) => {
              const cfg = LOG_LEVEL_CONFIG[log.level]
              const originalIdx = logs.findIndex(l => l === log)
              const isNew = originalIdx >= prevLogCount
              return (
                <div key={`${i}-${log.timestamp}`}
                  className={`flex items-start gap-2 px-3 py-0.5 text-[10px] leading-relaxed hover:bg-white/[0.02] transition-colors ${cfg.color} ${isNew ? 'animate-slide-up log-entry-new' : ''}`}>
                  <span className="text-[9px] text-eda-text-tertiary/50 w-[60px] shrink-0 text-right select-none">{log.timestamp}</span>
                  <span className={`mt-0.5 ${cfg.bg} rounded-sm px-1 text-[8px] font-semibold uppercase tracking-wider ${cfg.color}`}>
                    {cfg.label}
                  </span>
                  <span className="flex-1">{log.message}</span>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

export default Console
