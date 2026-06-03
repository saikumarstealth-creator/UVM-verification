import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type PipelineStatus = 'pending' | 'running' | 'completed' | 'failed'
export type PipelineStep = 'spec_parse' | 'feature_extract' | 'ml_generation' | 'uvm_validation' | 'coverage_analysis' | 'export'
export type LogLevel = 'info' | 'warn' | 'error' | 'success'

export interface LogEntry {
  level: LogLevel
  message: string
  timestamp: string
}

export interface PipelineMetrics {
  completeness: number
  signal_coverage: number
  register_coverage: number
  files_generated: number
  passed: boolean
  lint_score?: number
  assertion_coverage?: number
  test_pass_rate?: number
  quality_score?: number
}

export interface StepTiming {
  step: PipelineStep
  startedAt: number | null
  completedAt: number | null
}

export interface PipelineState {
  taskId: string | null
  status: PipelineStatus
  currentStep: PipelineStep | null
  progress: number
  message: string
  logs: LogEntry[]
  completedSteps: PipelineStep[]
  metrics: PipelineMetrics | null
  generatedFiles: string[]
  selectedFile: string | null
  fileContent: string | null
  error: string | null
  stepTimings: StepTiming[]
  specStats: SpecStats | null
}

export interface SpecStats {
  interfaces: number
  registers: number
  fields: number
  signals: number
  sequences: number
  protocol: string
}

export interface GenerationConfig {
  design_name: string
  protocol: string
  model_type: string
  rl_strategy: string
  enable_learning: boolean
  strict_uvm: boolean
  max_iterations: number
  spec_yaml: string
}

interface AppState extends PipelineState {
  config: GenerationConfig
  wsConnected: boolean

  setTaskId: (id: string) => void
  setStatus: (status: PipelineStatus) => void
  setCurrentStep: (step: PipelineStep | null) => void
  setProgress: (progress: number) => void
  setMessage: (message: string) => void
  addLogs: (logs: string[]) => void
  clearLogs: () => void
  setCompletedSteps: (steps: PipelineStep[]) => void
  setMetrics: (metrics: PipelineMetrics | null) => void
  setGeneratedFiles: (files: string[]) => void
  setSelectedFile: (file: string | null) => void
  setFileContent: (content: string | null) => void
  setError: (error: string | null) => void
  setWsConnected: (connected: boolean) => void
  setSpecStats: (stats: SpecStats | null) => void

  updateFromWs: (data: Partial<PipelineState>) => void
  resetPipeline: () => void
  updateConfig: (updates: Partial<GenerationConfig>) => void
}

function inferLogLevel(message: string): LogLevel {
  const lower = message.toLowerCase()
  if (lower.includes('error') || lower.includes('fail')) return 'error'
  if (lower.includes('warning') || lower.includes('warn')) return 'warn'
  if (lower.includes('✓') || lower.includes('passed') || lower.includes('success')) return 'success'
  return 'info'
}

function parseLogsToEntries(logs: string[]): LogEntry[] {
  return logs.map(msg => ({
    level: inferLogLevel(msg),
    message: msg,
    timestamp: new Date().toLocaleTimeString('en-US', { hour12: false })
  }))
}

const defaultConfig: GenerationConfig = {
  design_name: 'uart',
  protocol: 'uart',
  model_type: 'template',
  rl_strategy: 'ucb',
  enable_learning: true,
  strict_uvm: true,
  max_iterations: 1,
  spec_yaml: `design_name: uart
protocol: uart
clock_reset:
  clock: clk
  reset: rst_n
  reset_active: 0

interfaces:
  - name: wb_intf
    signals:
      - { name: wb_cyc, direction: input }
      - { name: wb_stb, direction: input }
      - { name: wb_we, direction: input }
      - { name: wb_addr, direction: input, width: 3 }
      - { name: wb_data_o, direction: output, width: 8 }
      - { name: wb_data_i, direction: input, width: 8 }
      - { name: wb_ack, direction: output }

  - name: uart_intf
    signals:
      - { name: uart_tx, direction: output }
      - { name: uart_rx, direction: input }
      - { name: cts_n, direction: input }
      - { name: rts_n, direction: output }
      - { name: uart_intr, direction: output }

registers:
  - name: RBR_THR, address: '0x00', access: rw, description: "Receiver Buffer / Transmitter Holding"
    fields:
      - { name: data, bits: '7:0', description: "Data bits" }
  - name: IER, address: '0x01', access: rw, description: "Interrupt Enable"
    fields:
      - { name: erbfi, bits: '0', description: "Enable RX data interrupt" }
      - { name: etbei, bits: '1', description: "Enable TX empty interrupt" }
      - { name: elsi, bits: '2', description: "Enable RX line status" }
      - { name: edssi, bits: '3', description: "Enable modem status" }
  - name: LCR, address: '0x03', access: rw, description: "Line Control"
    fields:
      - { name: wls, bits: '1:0', description: "Word length select" }
      - { name: stb, bits: '2', description: "Stop bits" }
      - { name: pen, bits: '3', description: "Parity enable" }
      - { name: eps, bits: '4', description: "Even parity select" }
      - { name: dlab, bits: '7', description: "Divisor latch access bit" }
  - name: LSR, address: '0x05', access: ro, description: "Line Status"
    fields:
      - { name: dr, bits: '0', description: "Data Ready" }
      - { name: oe, bits: '1', description: "Overrun Error" }
      - { name: pe, bits: '2', description: "Parity Error" }
      - { name: fe, bits: '3', description: "Framing Error" }
      - { name: thre, bits: '5', description: "TX Holding Register Empty" }
      - { name: temt, bits: '6', description: "Transmitter Empty" }

coverage:
  groups:
    baud_rate: [9600, 115200, 1000000]
    data_bits: [7, 8]
    parity: [none, even, odd]

sequences:
  - { name: uart_smoke, type: smoke, description: "Basic smoke test" }
  - { name: uart_reg_access, type: register, description: "Register access test" }
  - { name: uart_loopback, type: data, description: "Loopback data test" }
  - { name: uart_random, type: random, description: "Random data test" }
  - { name: uart_error_injection, type: error, description: "Error injection test" }`
}

export const DEFAULT_SPEC_YAML = defaultConfig.spec_yaml

const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      taskId: null,
      status: 'pending',
      currentStep: null,
      progress: 0,
      message: 'Ready to generate',
      logs: [],
      completedSteps: [],
      metrics: null,
      generatedFiles: [],
      selectedFile: null,
      fileContent: null,
      error: null,
      wsConnected: false,
      stepTimings: [],
      specStats: null,
      config: defaultConfig,

      setTaskId: (id) => set({ taskId: id }),
      setStatus: (status) => set({ status }),
      setCurrentStep: (step) => set({ currentStep: step }),
      setProgress: (progress) => set({ progress }),
      setMessage: (message) => set({ message }),
      addLogs: (newLogs) => set((state) => ({
        logs: [...state.logs, ...parseLogsToEntries(newLogs)]
      })),
      clearLogs: () => set({ logs: [] }),
      setCompletedSteps: (steps) => set({ completedSteps: steps, stepTimings: steps.map((s, i) => ({
        step: s,
        startedAt: Date.now() - (steps.length - i) * 3000,
        completedAt: Date.now()
      })) }),
      setMetrics: (metrics) => set({ metrics }),
      setGeneratedFiles: (files) => set({ generatedFiles: files }),
      setSelectedFile: (file) => set({ selectedFile: file }),
      setFileContent: (content) => set({ fileContent: content }),
      setError: (error) => set({ error }),
      setWsConnected: (connected) => set({ wsConnected: connected }),
      setSpecStats: (stats) => set({ specStats: stats }),

      updateFromWs: (data) => set((state) => {
        const updated: Partial<PipelineState> = {}
        if (data.status) updated.status = data.status
        if (data.currentStep !== undefined) updated.currentStep = data.currentStep
        if (data.progress !== undefined) updated.progress = data.progress
        if (data.message) updated.message = data.message
        if (data.logs) {
          const rawLogs = data.logs as unknown as string[]
          const existingMsgs = new Set(state.logs.map(l => l.message))
          const newStrings = rawLogs.filter(l => !existingMsgs.has(l))
          if (newStrings.length > 0) updated.logs = [...state.logs, ...parseLogsToEntries(newStrings)]
        }
        if (data.completedSteps) {
          updated.completedSteps = data.completedSteps
          const timings = [...state.stepTimings]
          data.completedSteps.forEach(step => {
            const existing = timings.find(t => t.step === step)
            if (existing && !existing.completedAt) {
              existing.completedAt = Date.now()
            } else if (!existing) {
              timings.push({ step, startedAt: null, completedAt: Date.now() })
            }
          })
          updated.stepTimings = timings
        }
        if (data.metrics) updated.metrics = data.metrics
        return updated
      }),

      resetPipeline: () => set({
        taskId: null, status: 'pending', currentStep: null, progress: 0,
        message: 'Ready to generate', logs: [], completedSteps: [],
        metrics: null, generatedFiles: [], selectedFile: null, fileContent: null,
        error: null, stepTimings: [], specStats: null,
      }),

      updateConfig: (updates) => set((state) => ({
        config: { ...state.config, ...updates }
      })),
    }),
    {
      name: 'uvm-generator-config',
      partialize: (state) => ({ config: state.config }),
      onRehydrateStorage: () => (state) => {
        if (state) {
          state.taskId = null
          state.status = 'pending'
          state.currentStep = null
          state.progress = 0
          state.message = 'Ready to generate'
          state.logs = []
          state.completedSteps = []
          state.metrics = null
          state.generatedFiles = []
          state.selectedFile = null
          state.fileContent = null
          state.error = null
          state.wsConnected = false
          state.stepTimings = []
          state.specStats = null
        }
      },
    }
  )
)

export default useAppStore
