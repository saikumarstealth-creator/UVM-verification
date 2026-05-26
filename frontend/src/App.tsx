import React from 'react'
import useAppStore, { PipelineStep } from './store/appStore'
import { useGenerationAPI } from './hooks/useGenerationAPI'
import Header from './components/Header'
import PipelineVisualizer from './components/PipelineVisualizer'
import ConfigEditor from './components/ConfigEditor'
import Console from './components/Console'
import FileViewer from './components/FileViewer'
import MetricsPanel from './components/MetricsPanel'

const WS_BASE = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
const WS_URL = `${WS_BASE}//${window.location.host}/ws`

const App: React.FC = () => {
  const { 
    updateFromWs, 
    setWsConnected,
    config
  } = useAppStore()

  const { startGeneration, getFiles } = useGenerationAPI()
  const wsRef = React.useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = React.useRef<NodeJS.Timeout | null>(null)

  // WebSocket connection
  const connectWebSocket = React.useCallback((currentTaskId: string) => {
    try {
      const wsUrl = `${WS_URL}/${currentTaskId}`
      const ws = new WebSocket(wsUrl)
      
      ws.onopen = () => {
        console.log('WebSocket connected')
        setWsConnected(true)
        wsRef.current = ws
      }
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'pipeline_update') {
            updateFromWs({
              status: data.status as any,
              currentStep: data.current_step as PipelineStep | null,
              progress: data.progress,
              message: data.message,
              logs: data.logs || [],
              completedSteps: data.completed_steps as PipelineStep[] || [],
              metrics: data.metrics
            })
          }
        } catch (e) {
          console.error('Failed to parse WS message:', e)
        }
      }
      
      ws.onclose = () => {
        console.log('WebSocket disconnected')
        setWsConnected(false)
        wsRef.current = null
      }
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        setWsConnected(false)
      }
      
      return ws
    } catch (e) {
      console.error('Failed to create WebSocket:', e)
      return null
    }
  }, [updateFromWs, setWsConnected])

  // Handle generation
  const handleGenerate = async () => {
    const newTaskId = await startGeneration(config)
    
    if (newTaskId) {
      // Connect WebSocket
      connectWebSocket(newTaskId)
      
      // Poll for files when complete
      const checkComplete = setInterval(async () => {
        const { status: currentStatus, completedSteps: currentCompleted } = useAppStore.getState()
        if (currentStatus === 'completed' || 
            (currentCompleted.length > 0 && currentCompleted.includes('export'))) {
          clearInterval(checkComplete)
          // Wait a bit then fetch files
          setTimeout(async () => {
            if (useAppStore.getState().taskId) {
              await getFiles(useAppStore.getState().taskId!)
            }
          }, 500)
        }
      }, 500)
      
      // Cleanup after 2 minutes max
      setTimeout(() => clearInterval(checkComplete), 120000)
    }
  }

  // Cleanup on unmount
  React.useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
    }
  }, [])

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-eda-bg text-eda-text font-sans">
      <Header />
      
      {/* Main content area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left column: Config */}
        <div className="w-96 flex flex-col border-r border-eda-border overflow-hidden">
          <div className="flex-1 overflow-hidden">
            <ConfigEditor onGenerate={handleGenerate} />
          </div>
        </div>

        {/* Right column: Pipeline, Metrics, Files */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Top row: Pipeline + Metrics */}
          <div className="h-72 flex shrink-0 border-b border-eda-border">
            {/* Pipeline visualizer */}
            <div className="flex-1 p-3 overflow-hidden">
              <PipelineVisualizer />
            </div>
            
            {/* Metrics panel */}
            <div className="w-80 p-3 overflow-hidden">
              <MetricsPanel />
            </div>
          </div>

          {/* Bottom: File viewer */}
          <div className="flex-1 overflow-hidden p-3">
            <FileViewer />
          </div>
        </div>
      </div>

      {/* Console at bottom */}
      <Console />
    </div>
  )
}

export default App
