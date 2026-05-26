import { useCallback } from 'react'
import axios from 'axios'
import useAppStore, { GenerationConfig } from '../store/appStore'

const API_BASE = '' // Using Vite proxy

export const useGenerationAPI = () => {
  const { 
    resetPipeline, 
    setTaskId, 
    setStatus, 
    setMessage, 
    clearLogs,
    setGeneratedFiles,
    setMetrics,
    setError
  } = useAppStore()

  const startGeneration = useCallback(async (config: GenerationConfig): Promise<string | null> => {
    resetPipeline()
    clearLogs()
    
    try {
      const response = await axios.post(`${API_BASE}/api/generate`, config)
      const data = response.data
      
      setTaskId(data.task_id)
      setStatus(data.status)
      setMessage(data.message)
      
      return data.task_id
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || 'Failed to start generation'
      setStatus('failed')
      setError(errorMsg)
      setMessage(`Error: ${errorMsg}`)
      return null
    }
  }, [resetPipeline, clearLogs, setTaskId, setStatus, setMessage, setError])

  const getStatus = useCallback(async (taskId: string) => {
    try {
      const response = await axios.get(`${API_BASE}/api/generate/${taskId}`)
      return response.data
    } catch (err) {
      console.error('Failed to get status:', err)
      return null
    }
  }, [])

  const getFiles = useCallback(async (taskId: string) => {
    try {
      const response = await axios.get(`${API_BASE}/api/generate/${taskId}/files`)
      setGeneratedFiles(response.data.files || [])
      return response.data.files || []
    } catch (err) {
      console.error('Failed to get files:', err)
      return []
    }
  }, [setGeneratedFiles])

  const getFileContent = useCallback(async (taskId: string, filename: string): Promise<string | null> => {
    try {
      const response = await axios.get(
        `${API_BASE}/api/generate/${taskId}/files/${encodeURIComponent(filename)}`,
        { responseType: 'text' }
      )
      return response.data
    } catch (err) {
      console.error('Failed to get file content:', err)
      return null
    }
  }, [])

  const getMetrics = useCallback(async (taskId: string) => {
    try {
      const response = await axios.get(`${API_BASE}/api/generate/${taskId}/metrics`)
      setMetrics(response.data)
      return response.data
    } catch (err) {
      console.error('Failed to get metrics:', err)
      return null
    }
  }, [setMetrics])

  const downloadAll = useCallback(async (taskId: string) => {
    try {
      const response = await axios.get(
        `${API_BASE}/api/generate/${taskId}/download`,
        { responseType: 'blob' }
      )
      
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', 'uvm_testbench.zip')
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Failed to download:', err)
    }
  }, [])

  const listPipelines = useCallback(async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/pipelines`)
      return response.data
    } catch (err) {
      console.error('Failed to list pipelines:', err)
      return null
    }
  }, [])

  return {
    startGeneration,
    getStatus,
    getFiles,
    getFileContent,
    getMetrics,
    downloadAll,
    listPipelines
  }
}
