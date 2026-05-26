import { create } from 'zustand'

export type PipelineStatus = 'pending' | 'running' | 'completed' | 'failed'
export type PipelineStep = 'spec_parse' | 'feature_extract' | 'ml_generation' | 'uvm_validation' | 'coverage_analysis' | 'export'

export interface PipelineMetrics {
  completeness: number
  signal_coverage: number
  register_coverage: number
  files_generated: number
  passed: boolean
}

export interface PipelineState {
  taskId: string | null
  status: PipelineStatus
  currentStep: PipelineStep | null
  progress: number
  message: string
  logs: string[]
  completedSteps: PipelineStep[]
  metrics: PipelineMetrics | null
  generatedFiles: string[]
  selectedFile: string | null
  fileContent: string | null
  error: string | null
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
  
  updateFromWs: (data: Partial<PipelineState>) => void
  resetPipeline: () => void
  updateConfig: (updates: Partial<GenerationConfig>) => void
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
      - name: wb_cyc
        direction: input
      - name: wb_stb
        direction: input
      - name: wb_we
        direction: input
      - name: wb_addr
        direction: input
        width: 3
      - name: wb_data_o
        direction: output
        width: 8
      - name: wb_data_i
        direction: input
        width: 8
      - name: wb_ack
        direction: output

  - name: uart_intf
    signals:
      - name: uart_tx
        direction: output
      - name: uart_rx
        direction: input
      - name: cts_n
        direction: input
      - name: rts_n
        direction: output
      - name: uart_intr
        direction: output

registers:
  - name: RBR_THR
    address: '0x00'
    access: rw
    description: Receiver Buffer / Transmitter Holding
    fields:
      - name: data
        bits: '7:0'
        description: Data bits

  - name: IER
    address: '0x01'
    access: rw
    description: Interrupt Enable
    fields:
      - name: erbfi
        bits: '0'
        description: Enable RX data interrupt
      - name: etbei
        bits: '1'
        description: Enable TX empty interrupt
      - name: elsi
        bits: '2'
        description: Enable RX line status
      - name: edssi
        bits: '3'
        description: Enable modem status

  - name: LCR
    address: '0x03'
    access: rw
    description: Line Control
    fields:
      - name: wls
        bits: '1:0'
        description: Word length select
      - name: stb
        bits: '2'
        description: Stop bits
      - name: pen
        bits: '3'
        description: Parity enable
      - name: eps
        bits: '4'
        description: Even parity select
      - name: dlab
        bits: '7'
        description: Divisor latch access bit

  - name: LSR
    address: '0x05'
    access: ro
    description: Line Status
    fields:
      - name: dr
        bits: '0'
        description: Data Ready
      - name: oe
        bits: '1'
        description: Overrun Error
      - name: pe
        bits: '2'
        description: Parity Error
      - name: fe
        bits: '3'
        description: Framing Error
      - name: thre
        bits: '5'
        description: TX Holding Register Empty
      - name: temt
        bits: '6'
        description: Transmitter Empty

coverage:
  groups:
    baud_rate: [9600, 115200, 1000000]
    data_bits: [7, 8]
    parity: [none, even, odd]

sequences:
  - name: uart_smoke
    type: smoke
    description: Basic smoke test
  - name: uart_reg_access
    type: register
    description: Register access test
  - name: uart_loopback
    type: data
    description: Loopback data test
  - name: uart_random
    type: random
    description: Random data test
  - name: uart_error_injection
    type: error
    description: Error injection test`
}

const useAppStore = create<AppState>((set) => ({
  // Pipeline state
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
  
  // Config
  config: defaultConfig,
  
  // Actions
  setTaskId: (id) => set({ taskId: id }),
  setStatus: (status) => set({ status }),
  setCurrentStep: (step) => set({ currentStep: step }),
  setProgress: (progress) => set({ progress }),
  setMessage: (message) => set({ message }),
  addLogs: (newLogs) => set((state) => ({ logs: [...state.logs, ...newLogs] })),
  clearLogs: () => set({ logs: [] }),
  setCompletedSteps: (steps) => set({ completedSteps: steps }),
  setMetrics: (metrics) => set({ metrics }),
  setGeneratedFiles: (files) => set({ generatedFiles: files }),
  setSelectedFile: (file) => set({ selectedFile: file }),
  setFileContent: (content) => set({ fileContent: content }),
  setError: (error) => set({ error }),
  setWsConnected: (connected) => set({ wsConnected: connected }),
  
  updateFromWs: (data) => set((state) => {
    const updated: Partial<PipelineState> = {}
    if (data.status) updated.status = data.status
    if (data.currentStep !== undefined) updated.currentStep = data.currentStep
    if (data.progress !== undefined) updated.progress = data.progress
    if (data.message) updated.message = data.message
    if (data.logs) updated.logs = [...state.logs, ...data.logs.filter(l => !state.logs.includes(l))]
    if (data.completedSteps) updated.completedSteps = data.completedSteps
    if (data.metrics) updated.metrics = data.metrics
    return updated
  }),
  
  resetPipeline: () => set({
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
  }),
  
  updateConfig: (updates) => set((state) => ({
    config: { ...state.config, ...updates }
  })),
}))

export default useAppStore
