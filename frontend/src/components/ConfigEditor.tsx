import React, { useMemo } from 'react'
import {
  Settings2, FileText, Brain, Zap, Play, RotateCcw,
  AlertCircle, Cpu, Layout, Layers, Hash, List
} from 'lucide-react'
import useAppStore, { SpecStats } from '../store/appStore'

const PRESETS: Record<string, { label: string; protocol: string; desc: string }> = {
  uart: { label: 'UART', protocol: 'uart', desc: 'Universal Asynchronous Receiver-Transmitter' },
  apb: { label: 'APB', protocol: 'apb', desc: 'AMBA Advanced Peripheral Bus' },
  spi: { label: 'SPI', protocol: 'spi', desc: 'Serial Peripheral Interface' },
  i2c: { label: 'I2C', protocol: 'i2c', desc: 'Inter-Integrated Circuit' },
  custom: { label: 'Custom', protocol: 'custom', desc: 'Custom design specification' },
}

function parseSpecStats(yaml: string): SpecStats | null {
  const protocolMatch = yaml.match(/^protocol:\s*(\w+)/m)
  let interfaces = 0; let registers = 0; let signals = 0; let fields = 0; let sequences = 0

  const intfLines = yaml.match(/^\s+- name:\s+\w+/gm)
  if (intfLines) {
    const beforeReg = yaml.split('registers:')[0]
    const ifCount = beforeReg.match(/^\s+- name:\s+\w+/gm)
    interfaces = ifCount ? ifCount.length : 0
  }

  const regSection = yaml.split('registers:')[1]
  if (regSection) {
    const coverageSplit = regSection.split('coverage:')
    const regNames = (coverageSplit[0] || regSection).match(/^\s+- name:\s+\w+/gm)
    registers = regNames ? regNames.length : 0
  }

  const fieldMatches = yaml.match(/^\s+- name:\s+\w+/gm)
  if (fieldMatches) {
    if (interfaces > 0) fields = Math.max(0, fieldMatches.length - interfaces - registers)
    else {
      const afterReg = yaml.split('registers:')[1]
      if (afterReg) {
        const afterSeq = afterReg.split('sequences:')[0]
        const allFieldLines = afterSeq.match(/^\s+- {0,1}\w/gm)
        fields = allFieldLines ? allFieldLines.length - registers : 0
      }
    }
  }

  if (interfaces > 0) {
    const beforeRegSection = yaml.split('registers:')[0]
    const signalLines = beforeRegSection.match(/^\s+- name:\s+\w+/gm)
    signals = signalLines ? Math.max(0, signalLines.length - interfaces) : 0
  }

  const seqSection = yaml.split('sequences:')[1]
  if (seqSection) {
    const seqLines = seqSection.match(/^\s+- name:\s+\w+/gm)
    sequences = seqLines ? seqLines.length : 0
  }

  const protocol = protocolMatch ? protocolMatch[1] : 'custom'

  if (!yaml.trim()) return null
  return { interfaces: Math.max(0, interfaces), registers: Math.max(0, registers), fields: Math.max(0, fields), signals: Math.max(0, signals), sequences: Math.max(0, sequences), protocol }
}

const SpecStatBadge: React.FC<{ icon: React.ReactNode; label: string; value: number; color: string }> =
  ({ icon, label, value, color }) => (
    <div className="flex items-center gap-1.5 bg-eda-bg/30 rounded-md px-2 py-1.5 border border-eda-border/30">
      <span className={color}>{icon}</span>
      <div className="flex flex-col">
        <span className="text-[9px] font-mono font-bold" style={{ color: color.replace('text-', '').replace(/-/g, '') }}>{value}</span>
        <span className="text-[8px] text-eda-text-tertiary">{label}</span>
      </div>
    </div>
  )

const ConfigEditor: React.FC<{ onGenerate: () => void }> = ({ onGenerate }) => {
  const { config, updateConfig, status, resetPipeline } = useAppStore()
  const [activeTab, setActiveTab] = React.useState<'spec' | 'settings'>('spec')
  const textareaRef = React.useRef<HTMLTextAreaElement>(null)

  const isGenerating = status === 'running'
  const hasRun = status !== 'pending' && status !== 'running'

  const specStats = useMemo(() => parseSpecStats(config.spec_yaml), [config.spec_yaml])

  const hasYamlError = useMemo(() => {
    const lines = config.spec_yaml.split('\n')
    for (const line of lines) {
      const trimmed = line.trim()
      if (trimmed && !trimmed.startsWith('#') && !trimmed.startsWith('-') &&
          !trimmed.includes(':') && !trimmed.startsWith('{') && !trimmed.startsWith('}') &&
          !trimmed.match(/^\s*$/) && !trimmed.startsWith('[') && !trimmed.startsWith(']')) {
        if (/^[a-zA-Z]/.test(trimmed) && !trimmed.includes(':')) return true
      }
    }
    return false
  }, [config.spec_yaml])

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
    const newSpec = config.spec_yaml.replace(/design_name: .+/, `design_name: ${value}`)
    updateConfig({ design_name: value, protocol: PRESETS[value]?.protocol || value, spec_yaml: newSpec })
  }

  return (
    <div className="bg-eda-bg-secondary border border-eda-border rounded-lg overflow-hidden flex flex-col flex-1">
      <div className="flex items-center justify-between bg-eda-bg-tertiary/50 border-b border-eda-border">
        <div className="flex">
          <button onClick={() => setActiveTab('spec')}
            className={`flex items-center gap-1.5 px-3 py-2 text-[10px] font-medium transition-colors border-b-2 ${
              activeTab === 'spec' ? 'text-eda-text border-eda-accent' : 'text-eda-text-tertiary border-transparent hover:text-eda-text-secondary'
            }`}>
            <FileText className="w-3 h-3" /> Spec
          </button>
          <button onClick={() => setActiveTab('settings')}
            className={`flex items-center gap-1.5 px-3 py-2 text-[10px] font-medium transition-colors border-b-2 ${
              activeTab === 'settings' ? 'text-eda-text border-eda-accent' : 'text-eda-text-tertiary border-transparent hover:text-eda-text-secondary'
            }`}>
            <Settings2 className="w-3 h-3" /> Settings
          </button>
        </div>
        {specStats && activeTab === 'spec' && (
          <div className="flex items-center gap-1 pr-3">
            <span className={`text-[8px] px-1.5 py-0.5 rounded-sm font-mono font-semibold uppercase ${
              config.protocol === specStats.protocol ? 'bg-eda-accent/10 text-eda-accent' : 'bg-eda-warning/10 text-eda-warning'
            }`}>{specStats.protocol}</span>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto" style={{ scrollbarWidth: 'thin' }}>
        {activeTab === 'spec' ? (
          <div className="p-3 space-y-3">
            <div>
              <label className="block text-[10px] font-medium text-eda-text-secondary mb-1.5">Design Preset</label>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(PRESETS).map(([key, preset]) => (
                  <button key={key} onClick={() => updateDesignNameFromPreset(key)} disabled={isGenerating}
                    className={`px-2 py-1 text-[10px] font-medium rounded-md border transition-all ${
                      config.design_name === key || config.protocol === preset.protocol
                        ? 'bg-eda-accent/15 border-eda-accent text-eda-accent'
                        : 'bg-eda-bg-tertiary border-eda-border text-eda-text-secondary hover:border-eda-border-hover hover:text-eda-text'
                    } ${isGenerating ? 'opacity-50 cursor-not-allowed' : ''}`}>
                    {preset.label}
                  </button>
                ))}
              </div>
              <p className="text-[9px] text-eda-text-tertiary mt-1">{PRESETS[config.design_name]?.desc || PRESETS[config.protocol]?.desc || 'Custom configuration'}</p>
            </div>

            {specStats && (
              <div className="grid grid-cols-3 gap-1.5">
                <SpecStatBadge icon={<Layout className="w-3 h-3" />} label="Interfaces" value={specStats.interfaces} color="text-eda-accent" />
                <SpecStatBadge icon={<Layers className="w-3 h-3" />} label="Registers" value={specStats.registers} color="text-purple-400" />
                <SpecStatBadge icon={<Hash className="w-3 h-3" />} label="Fields" value={specStats.fields} color="text-pink-400" />
                <SpecStatBadge icon={<Cpu className="w-3 h-3" />} label="Signals" value={specStats.signals} color="text-eda-warning" />
                <SpecStatBadge icon={<List className="w-3 h-3" />} label="Sequences" value={specStats.sequences} color="text-eda-success" />
                <SpecStatBadge icon={<FileText className="w-3 h-3" />} label="Lines" value={config.spec_yaml.split('\n').length} color="text-eda-text-tertiary" />
              </div>
            )}

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-[10px] font-medium text-eda-text-secondary">YAML Specification</label>
                <div className="flex items-center gap-2">
                  {hasYamlError && (
                    <span className="flex items-center gap-0.5 text-[9px] text-eda-error">
                      <AlertCircle className="w-2.5 h-2.5" /> Syntax issues
                    </span>
                  )}
                  <span className="text-[9px] text-eda-text-tertiary font-mono">{config.spec_yaml.length} chars</span>
                </div>
              </div>
              <div className="relative">
                <textarea ref={textareaRef} value={config.spec_yaml} onChange={handleSpecChange}
                  disabled={isGenerating} spellCheck={false}
                  className="w-full min-h-[350px] bg-black/20 border border-eda-border rounded-md pl-3 pr-3 py-2 text-[10px] font-mono text-eda-text placeholder-eda-text-tertiary/50 focus:outline-none focus:border-eda-accent/50 focus:ring-1 focus:ring-eda-accent/20 resize-none transition-colors disabled:opacity-50"
                  style={{ lineHeight: '1.5' }} />
              </div>
            </div>
          </div>
        ) : (
          <div className="p-3 space-y-4">
            <div>
              <label className="block text-[10px] font-medium text-eda-text-secondary mb-1.5 flex items-center gap-1.5">
                <Brain className="w-3 h-3" /> ML Engine
              </label>
              <div className="flex gap-1.5">
                {[{ key: 'v2', label: 'Advanced (V2)', desc: 'RL + Pattern Learning' },
                  { key: 'template', label: 'Template', desc: 'Jinja2 only (fast)' }].map(opt => (
                  <button key={opt.key} onClick={() => updateConfig({ model_type: opt.key })} disabled={isGenerating}
                    className={`flex-1 p-2 rounded-md border text-left transition-all ${
                      config.model_type === opt.key ? 'bg-eda-accent/10 border-eda-accent' : 'bg-eda-bg-tertiary/30 border-eda-border hover:border-eda-border-hover'
                    } ${isGenerating ? 'opacity-50 cursor-not-allowed' : ''}`}>
                    <div className={`text-[10px] font-semibold ${config.model_type === opt.key ? 'text-eda-accent' : 'text-eda-text-secondary'}`}>
                      {opt.label}
                    </div>
                    <div className="text-[9px] text-eda-text-tertiary mt-0.5">{opt.desc}</div>
                  </button>
                ))}
              </div>
            </div>

            {config.model_type === 'v2' && (
              <div>
                <label className="block text-[10px] font-medium text-eda-text-secondary mb-1.5 flex items-center gap-1.5">
                  <Zap className="w-3 h-3" /> Exploration Strategy
                </label>
                <select value={config.rl_strategy} onChange={(e) => updateConfig({ rl_strategy: e.target.value })}
                  disabled={isGenerating}
                  className="w-full bg-eda-bg-tertiary/30 border border-eda-border rounded-md px-2 py-1.5 text-[10px] text-eda-text focus:outline-none focus:border-eda-accent/50 disabled:opacity-50">
                  <option value="ucb">UCB1 (Recommended)</option>
                  <option value="epsilon">Epsilon-Greedy</option>
                  <option value="softmax">Softmax (Boltzmann)</option>
                  <option value="thompson">Thompson Sampling</option>
                </select>
              </div>
            )}

            <div>
              <label className="block text-[10px] font-medium text-eda-text-secondary mb-1.5">Iterations</label>
              <input type="range" min="1" max="5" value={config.max_iterations}
                onChange={(e) => updateConfig({ max_iterations: parseInt(e.target.value) })} disabled={isGenerating}
                className="w-full accent-eda-accent" />
              <div className="flex justify-between text-[9px] text-eda-text-tertiary mt-0.5">
                <span>Fast (1)</span>
                <span className="font-mono font-semibold text-eda-text">{config.max_iterations}</span>
                <span>Thorough (5)</span>
              </div>
            </div>

            <div className="space-y-2.5">
              {[{ key: 'enable_learning', label: 'Enable Learning', desc: 'Let RL improve over time' },
                { key: 'strict_uvm', label: 'Strict UVM Compliance', desc: 'Enforce UVM 1.2 standards' }].map(toggle => (
                <div key={toggle.key} className="flex items-center justify-between py-0.5">
                  <div>
                    <div className="text-[10px] text-eda-text">{toggle.label}</div>
                    <div className="text-[9px] text-eda-text-tertiary">{toggle.desc}</div>
                  </div>
                  <button onClick={() => updateConfig({ [toggle.key]: !(config as any)[toggle.key] })} disabled={isGenerating}
                    className={`relative w-9 h-4.5 rounded-full transition-colors ${(config as any)[toggle.key] ? 'bg-eda-accent' : 'bg-eda-border'} ${isGenerating ? 'opacity-50 cursor-not-allowed' : ''}`}
                    style={{ height: '18px', width: '36px' }}>
                    <div className={`absolute top-0.5 w-3.5 h-3.5 bg-white rounded-full transition-transform shadow-sm ${(config as any)[toggle.key] ? 'translate-x-[18px]' : 'translate-x-0.5'}`}
                      style={{ width: '14px', height: '14px' }} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between px-3 py-2 border-t border-eda-border bg-eda-bg-tertiary/30">
        <div className="flex items-center gap-1.5">
          <div className={`w-1.5 h-1.5 rounded-full ${
            isGenerating ? 'bg-eda-accent animate-pulse' :
            status === 'completed' ? 'bg-eda-success' :
            status === 'failed' ? 'bg-eda-error' :
            'bg-eda-text-tertiary'
          }`} />
          <span className="text-[9px] text-eda-text-secondary capitalize">{status}</span>
        </div>
        <div className="flex items-center gap-1.5">
          {hasRun && (
            <button onClick={resetPipeline} disabled={isGenerating}
              className="flex items-center gap-1 px-2 py-1 text-[10px] text-eda-text-secondary hover:text-eda-text border border-eda-border rounded-md hover:border-eda-border-hover transition-colors disabled:opacity-50">
              <RotateCcw className="w-3 h-3" /> Reset
            </button>
          )}
          <button onClick={onGenerate} disabled={isGenerating || !config.spec_yaml.trim()}
            className="flex items-center gap-1 px-3 py-1.5 text-[10px] font-semibold bg-eda-accent text-white rounded-md hover:bg-eda-accent/90 active:bg-eda-accent/80 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-sm">
            {isGenerating ? (
              <><div className="w-3 h-3 border-1.5 border-white/30 border-t-white rounded-full animate-spin" /> Generating...</>
            ) : (
              <><Play className="w-3 h-3" /> Generate</>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

export default ConfigEditor
