import React from 'react'
import { Cpu, Github, Activity, HelpCircle } from 'lucide-react'
import useAppStore from '../store/appStore'

const Header: React.FC = () => {
  const { wsConnected, status } = useAppStore()

  return (
    <header className="h-12 bg-eda-bg-secondary border-b border-eda-border flex items-center justify-between px-6 shrink-0">
      <div className="flex items-center gap-3">
        <div className="flex items-center justify-center w-7 h-7 bg-eda-accent/15 rounded-md">
          <Cpu className="w-4 h-4 text-eda-accent" />
        </div>
        <div className="flex flex-col">
          <h1 className="text-sm font-semibold text-eda-text leading-none">
            UVM Generator
          </h1>
          <span className="text-[10px] text-eda-text-tertiary">
            AI-Powered Testbench Generation v2.1
          </span>
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* Connection status */}
        <div className="flex items-center gap-1.5">
          <div className={`w-2 h-2 rounded-full ${
            wsConnected ? 'bg-eda-success' : 'bg-eda-text-tertiary'
          }`} />
          <span className="text-[11px] text-eda-text-tertiary">
            {wsConnected ? 'Live' : 'Offline'}
          </span>
        </div>

        {/* Status indicator */}
        {status !== 'pending' && (
          <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium ${
            status === 'running' ? 'bg-eda-accent/15 text-eda-accent' :
            status === 'completed' ? 'bg-eda-success/15 text-eda-success' :
            'bg-eda-error/15 text-eda-error'
          }`}>
            <Activity className="w-3 h-3" />
            {status === 'running' ? 'Generating...' :
             status === 'completed' ? 'Complete' :
             status === 'failed' ? 'Failed' : status}
          </div>
        )}

        {/* Links */}
        <div className="flex items-center gap-1">
          <a
            href="https://github.com/saikumarstealth-creator/UVM-verification"
            target="_blank"
            rel="noopener noreferrer"
            className="p-1.5 text-eda-text-tertiary hover:text-eda-text hover:bg-eda-bg-tertiary rounded transition-colors"
            title="GitHub"
          >
            <Github className="w-4 h-4" />
          </a>
          <button
            className="p-1.5 text-eda-text-tertiary hover:text-eda-text hover:bg-eda-bg-tertiary rounded transition-colors"
            title="Help"
          >
            <HelpCircle className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  )
}

export default Header
