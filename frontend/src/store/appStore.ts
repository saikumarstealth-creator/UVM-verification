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
  model_type: 'v2',
  rl_strategy: 'ucb',
  enable_learning: true,
  strict_uvm: true,
  max_iterations: 1,
  spec_yaml: `design_name: uart
module_name: uart_core
clk_rst:
  clk: clk
  rst_n: rst_n

interfaces:
  apb:
    type: apb
    role: slave
    ports:
      paddr: input wire [7:0]
      psel: input wire
      penable: input wire
      pwrite: input wire
      pwdata: input wire [7:0]
      prdata: output wire [7:0]
      pready: output wire
      pslverr: output wire
  
  uart_rx:
    type: uart
    role: receiver
    ports:
      rx: input wire
      rx_data: output wire [7:0]
      rx_valid: output wire
      rx_error: output wire
  
  uart_tx:
    type: uart
    role: transmitter
    ports:
      tx: output wire
      tx_data: input wire [7:0]
      tx_valid: input wire
      tx_ready: output wire

registers:
  - name: tx_data
    addr: '0x00'
    width: 8
    direction: WO
    description: TX Data Register
  
  - name: rx_data
    addr: '0x04'
    width: 8
    direction: RO
    description: RX Data Register
  
  - name: ctrl
    addr: '0x08'
    width: 8
    direction: RW
    fields:
      - name: tx_en
        bit: 0
        reset: 0
      - name: rx_en
        bit: 1
        reset: 0
      - name: parity_en
        bit: 2
        reset: 0
    description: Control Register
  
  - name: status
    addr: '0x0C'
    width: 8
    direction: RO
    fields:
      - name: tx_busy
        bit: 0
      - name: rx_valid
        bit: 1
      - name: parity_err
        bit: 2
    description: Status Register

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
