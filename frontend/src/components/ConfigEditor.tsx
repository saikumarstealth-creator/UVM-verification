import React from 'react'
import { Settings2, FileText, Brain, Zap, Play, RotateCcw } from 'lucide-react'
import useAppStore from '../store/appStore'

const PRESETS: Record<string, { label: string; protocol: string; desc: string }> = {
  uart: { label: 'UART', protocol: 'uart', desc: 'Universal Asynchronous Receiver-Transmitter' },
  apb: { label: 'APB', protocol: 'apb', desc: 'AMBA Advanced Peripheral Bus' },
  spi: { label: 'SPI', protocol: 'spi', desc: 'Serial Peripheral Interface' },
  i2c: { label: 'I2C', protocol: 'i2c', desc: 'Inter-Integrated Circuit' },
  custom: { label: 'Custom', protocol: 'custom', desc: 'Custom design specification' },
}

const ConfigEditor: React.FC<{ onGenerate: () => void }> = ({ onGenerate }) => {
  const { config, updateConfig, status, resetPipeline } = useAppStore()
  const [activeTab, setActiveTab] = React.useState<'spec' | 'settings'>('spec')
  const textareaRef = React.useRef<HTMLTextAreaElement>(null)

  const isGenerating = status === 'running'
  const hasRun = status !== 'pending' && status !== 'running'

  // Auto-resize textarea
  React.useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px'
    }
  }, [config.spec_yaml])

  const handleSpecChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    updateConfig({ spec_yaml: e.target.value })
  }

  const updateDesignNameFromPreset = (value: string) => {
    // Update design name in spec
    const newSpec = config.spec_yaml.replace(
      /design_name: .+/,
      `design_name: ${value}`
    )
    updateConfig({ 
      design_name: value,
      protocol: PRESETS[value]?.protocol || value,
      spec_yaml: newSpec
    })
  }

  return (
    <div className="bg-eda-bg-secondary border border-eda-border rounded-lg overflow-hidden flex flex-col">
      {/* Header with tabs */}
      <div className="flex items-center justify-between bg-eda-bg-tertiary/50 border-b border-eda-border">
        <div className="flex">
          <button
            onClick={() => setActiveTab('spec')}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-medium transition-colors border-b-2 ${
              activeTab === 'spec'
                ? 'text-eda-text border-eda-accent'
                : 'text-eda-text-tertiary border-transparent hover:text-eda-text-secondary'
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            Specification
          </button>
          <button
            onClick={() => setActiveTab('settings')}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-medium transition-colors border-b-2 ${
              activeTab === 'settings'
                ? 'text-eda-text border-eda-accent'
                : 'text-eda-text-tertiary border-transparent hover:text-eda-text-secondary'
            }`}
          >
            <Settings2 className="w-3.5 h-3.5" />
            Generation Settings
          </button>
        </div>
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'spec' ? (
          <div className="p-4 space-y-4">
            {/* Preset selector */}
            <div>
              <label className="block text-xs font-medium text-eda-text-secondary mb-2">
                Design Preset
              </label>
              <div className="flex flex-wrap gap-2">
                {Object.entries(PRESETS).map(([key, preset]) => (
                  <button
                    key={key}
                    onClick={() => updateDesignNameFromPreset(key)}
                    disabled={isGenerating}
                    className={`px-3 py-1.5 text-xs font-medium rounded-md border transition-all ${
                      config.design_name === key || config.protocol === preset.protocol
                        ? 'bg-eda-accent/15 border-eda-accent text-eda-accent'
                        : 'bg-eda-bg-tertiary border-eda-border text-eda-text-secondary hover:border-eda-border-hover hover:text-eda-text'
                    } ${isGenerating ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
              <p className="text-[11px] text-eda-text-tertiary mt-1.5">
                {PRESETS[config.design_name]?.desc || PRESETS[config.protocol]?.desc || 'Custom configuration'}
              </p>
            </div>

            {/* YAML Editor */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="block text-xs font-medium text-eda-text-secondary">
                  YAML Specification
                </label>
                <span className="text-[11px] text-eda-text-tertiary font-mono">
                  {config.spec_yaml.length} chars
                </span>
              </div>
              <div className="relative">
                <div className="absolute top-0 left-0 bottom-0 w-10 bg-eda-bg/50 border-r border-eda-border/30 rounded-l-md pointer-events-none" />
                <textarea
                  ref={textareaRef}
                  value={config.spec_yaml}
                  onChange={handleSpecChange}
                  disabled={isGenerating}
                  spellCheck={false}
                  className="w-full min-h-[400px] bg-black/20 border border-eda-border rounded-md pl-12 pr-3 py-2.5 text-xs font-mono text-eda-text placeholder-eda-text-tertiary/50 focus:outline-none focus:border-eda-accent/50 focus:ring-1 focus:ring-eda-accent/20 resize-none transition-colors disabled:opacity-50"
                  style={{ lineHeight: '1.6' }}
                />
              </div>
            </div>
          </div>
        ) : (
          <div className="p-4 space-y-5">
            {/* Model type */}
            <div>
              <label className="block text-xs font-medium text-eda-text-secondary mb-2 flex items-center gap-2">
                <Brain className="w-3.5 h-3.5" />
                ML Engine
              </label>
              <div className="flex gap-2">
                {[
                  { key: 'v2', label: 'Advanced (V2)', desc: 'RL + Pattern Learning' },
                  { key: 'template', label: 'Template', desc: 'Jinja2 only (fast)' },
                ].map(opt => (
                  <button
                    key={opt.key}
                    onClick={() => updateConfig({ model_type: opt.key })}
                    disabled={isGenerating}
                    className={`flex-1 p-3 rounded-md border text-left transition-all ${
                      config.model_type === opt.key
                        ? 'bg-eda-accent/10 border-eda-accent'
                        : 'bg-eda-bg-tertiary/30 border-eda-border hover:border-eda-border-hover'
                    } ${isGenerating ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    <div className={`text-xs font-semibold ${
                      config.model_type === opt.key ? 'text-eda-accent' : 'text-eda-text-secondary'
                    }`}>
                      {opt.label}
                    </div>
                    <div className="text-[11px] text-eda-text-tertiary mt-0.5">{opt.desc}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* RL Strategy */}
            {config.model_type === 'v2' && (
              <div>
                <label className="block text-xs font-medium text-eda-text-secondary mb-2 flex items-center gap-2">
                  <Zap className="w-3.5 h-3.5" />
                  Exploration Strategy
                </label>
                <select
                  value={config.rl_strategy}
                  onChange={(e) => updateConfig({ rl_strategy: e.target.value })}
                  disabled={isGenerating}
                  className="w-full bg-eda-bg-tertiary/30 border border-eda-border rounded-md px-3 py-2 text-xs text-eda-text focus:outline-none focus:border-eda-accent/50 disabled:opacity-50"
                >
                  <option value="ucb">UCB1 - Upper Confidence Bound (Recommended)</option>
                  <option value="epsilon">Epsilon-Greedy</option>
                  <option value="softmax">Softmax (Boltzmann)</option>
                  <option value="thompson">Thompson Sampling</option>
                </select>
              </div>
            )}

            {/* Iterations */}
            <div>
              <label className="block text-xs font-medium text-eda-text-secondary mb-2">
                Generation Iterations
              </label>
              <input
                type="range"
                min="1"
                max="5"
                value={config.max_iterations}
                onChange={(e) => updateConfig({ max_iterations: parseInt(e.target.value) })}
                disabled={isGenerating}
                className="w-full accent-eda-accent"
              />
              <div className="flex justify-between text-[11px] text-eda-text-tertiary mt-1">
                <span>Fast (1)</span>
                <span className="font-mono font-semibold text-eda-text">{config.max_iterations}</span>
                <span>Thorough (5)</span>
              </div>
            </div>

            {/* Toggles */}
            <div className="space-y-3">
              {[
                { key: 'enable_learning', label: 'Enable Learning', desc: 'Let RL learn from patterns' },
                { key: 'strict_uvm', label: 'Strict UVM Compliance', desc: 'Enforce UVM 1.2 standards' },
              ].map(toggle => (
                <div key={toggle.key} className="flex items-center justify-between py-1">
                  <div>
                    <div className="text-xs text-eda-text">{toggle.label}</div>
                    <div className="text-[11px] text-eda-text-tertiary">{toggle.desc}</div>
                  </div>
                  <button
                    onClick={() => updateConfig({ 
                      [toggle.key]: !(config as any)[toggle.key] 
                    })}
                    disabled={isGenerating}
                    className={`relative w-10 h-5 rounded-full transition-colors ${
                      (config as any)[toggle.key] ? 'bg-eda-accent' : 'bg-eda-border'
                    } ${isGenerating ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full transition-transform shadow-sm ${
                      (config as any)[toggle.key] ? 'translate-x-5' : 'translate-x-0.5'
                    }`} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Action bar */}
      <div className="flex items-center justify-between px-4 py-3 border-t border-eda-border bg-eda-bg-tertiary/30">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${
            isGenerating ? 'bg-eda-accent animate-pulse' :
            status === 'completed' ? 'bg-eda-success' :
            status === 'failed' ? 'bg-eda-error' :
            'bg-eda-text-tertiary'
          }`} />
          <span className="text-xs text-eda-text-secondary capitalize">{status}</span>
        </div>

        <div className="flex items-center gap-2">
          {hasRun && (
            <button
              onClick={resetPipeline}
              disabled={isGenerating}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-eda-text-secondary hover:text-eda-text border border-eda-border rounded-md hover:border-eda-border-hover transition-colors disabled:opacity-50"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Reset
            </button>
          )}
          <button
            onClick={onGenerate}
            disabled={isGenerating || !config.spec_yaml.trim()}
            className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-semibold bg-eda-accent text-white rounded-md hover:bg-eda-accent/90 active:bg-eda-accent/80 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
          >
            {isGenerating ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5" />
                Generate Testbench
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

export default ConfigEditor
