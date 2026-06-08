import React from 'react'
import { Cpu, Github, Activity, HelpCircle, Server } from 'lucide-react'
import useAppStore from '../store/appStore'

const Header: React.FC = () => {
  const { wsConnected, status, progress, generatedFiles } = useAppStore()

  const wsColor = wsConnected ? 'bg-eda-success' : 'bg-eda-text-tertiary'
  const wsLabel = wsConnected ? 'Live' : 'Offline'

  return (
    <header className="h-11 bg-eda-bg-secondary border-b border-eda-border flex items-center justify-between px-4 shrink-0">
      <div className="flex items-center gap-2.5">
        <div className="flex items-center justify-center w-6 h-6 bg-eda-accent/15 rounded-md">
          <Cpu className="w-3.5 h-3.5 text-eda-accent" />
        </div>
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <h1 className="text-[12px] font-semibold text-eda-text leading-none">UVM Generator</h1>
            <span className="text-[9px] bg-eda-bg-tertiary text-eda-text-tertiary px-1.5 py-0.5 rounded-sm font-mono">v2.1</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[9px] text-eda-text-tertiary/60">AI-Powered Testbench Generation</span>
            <span className="text-[9px] text-eda-text-tertiary/60">by</span>
            <span className="text-[13px] text-eda-accent font-bold tracking-wide">Sai Kumar Taraka</span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-0.5 text-[9px] text-eda-text-tertiary bg-eda-bg-tertiary/30 px-2 py-1 rounded-md border border-eda-border/30">
          <Server className="w-2.5 h-2.5 mr-0.5" />
          <div className={`w-1.5 h-1.5 rounded-full ${wsColor} mr-0.5`} />
          {wsLabel}
        </div>

        {status !== 'pending' && (
          <div className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium ${
            status === 'running' ? 'bg-eda-accent/15 text-eda-accent' :
            status === 'completed' ? 'bg-eda-success/15 text-eda-success' :
            'bg-eda-error/15 text-eda-error'
          }`}>
            <Activity className="w-2.5 h-2.5" />
            {status === 'running' ? `${progress}%` :
             status === 'completed' ? `${generatedFiles.length} files` :
             status === 'failed' ? 'Failed' : status}
          </div>
        )}

        <div className="flex items-center gap-0.5">
          <a href="https://github.com/saikumarstealth-creator/UVM-verification"
             target="_blank" rel="noopener noreferrer"
             className="p-1 text-eda-text-tertiary hover:text-eda-text hover:bg-eda-bg-tertiary rounded transition-colors"
             title="GitHub">
            <Github className="w-3.5 h-3.5" />
          </a>
          <button className="p-1 text-eda-text-tertiary hover:text-eda-text hover:bg-eda-bg-tertiary rounded transition-colors" title="Help">
            <HelpCircle className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </header>
  )
}

export default Header
