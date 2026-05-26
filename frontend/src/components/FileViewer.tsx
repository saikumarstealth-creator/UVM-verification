import React from 'react'
import { FileCode, FileText, Package, Database, Cpu, ClipboardCheck, ArrowDownToLine } from 'lucide-react'
import useAppStore from '../store/appStore'
import { useGenerationAPI } from '../hooks/useGenerationAPI'

const FileViewer: React.FC = () => {
  const { 
    generatedFiles, 
    selectedFile, 
    setSelectedFile, 
    fileContent, 
    setFileContent,
    taskId,
    status
  } = useAppStore()

  const { getFileContent, downloadAll } = useGenerationAPI()

  const handleFileSelect = async (file: string) => {
    setSelectedFile(file)
    if (taskId) {
      const content = await getFileContent(taskId, file)
      setFileContent(content)
    }
  }

  const getFileIcon = (name: string) => {
    if (name.endsWith('.sv')) return <FileCode className="w-3.5 h-3.5" />
    if (name.endsWith('.yaml') || name.endsWith('.yml')) return <Database className="w-3.5 h-3.5" />
    if (name.endsWith('.py')) return <Cpu className="w-3.5 h-3.5" />
    if (name.endsWith('.json')) return <Package className="w-3.5 h-3.5" />
    if (name.endsWith('.txt') || name.endsWith('.md')) return <FileText className="w-3.5 h-3.5" />
    if (name.includes('test')) return <ClipboardCheck className="w-3.5 h-3.5" />
    if (name.includes('env')) return <Package className="w-3.5 h-3.5" />
    return <FileCode className="w-3.5 h-3.5" />
  }

  const getFileColor = (name: string) => {
    if (name.endsWith('.sv')) return 'text-eda-accent'
    if (name.includes('test') || name.includes('sequence')) return 'text-eda-warning'
    if (name.includes('env') || name.includes('agent')) return 'text-eda-success'
    if (name.includes('register') || name.includes('reg')) return 'text-purple-400'
    if (name.includes('driver') || name.includes('monitor')) return 'text-pink-400'
    return 'text-eda-text-secondary'
  }

  // Group files by type
  const groupedFiles: Record<string, string[]> = {}
  generatedFiles.forEach(file => {
    let category = 'Other'
    if (file.includes('env') || file.includes('agent') || file.includes('scoreboard')) category = 'Environment'
    else if (file.includes('test')) category = 'Tests'
    else if (file.includes('sequence') || file.includes('item')) category = 'Sequences'
    else if (file.includes('driver') || file.includes('monitor') || file.includes('sequencer')) category = 'Agents'
    else if (file.includes('register') || file.includes('reg_model')) category = 'Registers'
    else if (file.includes('interface')) category = 'Interfaces'
    else if (file.includes('package')) category = 'Packages'
    else if (file.endsWith('.py')) category = 'Python'
    else if (file.endsWith('.yaml') || file.endsWith('.yml')) category = 'Config'
    groupedFiles[category] = [...(groupedFiles[category] || []), file]
  })

  const categoryOrder = [
    'Packages', 'Environment', 'Agents', 'Sequences', 'Tests', 
    'Registers', 'Interfaces', 'Config', 'Python', 'Other'
  ]

  const renderCode = () => {
    if (!fileContent) {
      return (
        <div className="flex flex-col items-center justify-center h-full text-eda-text-tertiary p-8">
          <FileCode className="w-12 h-12 mb-4 opacity-30" />
          <p className="text-sm">Select a file to view its contents</p>
        </div>
      )
    }

    const lines = fileContent.split('\n')
    
    return (
      <pre className="flex-1 overflow-auto text-xs font-mono leading-relaxed">
        <div className="flex">
          {/* Line numbers */}
          <div className="select-none text-eda-text-tertiary bg-eda-bg/50 pr-3 pl-4 py-4 text-right border-r border-eda-border/30 min-w-[50px]">
            {lines.map((_, i) => (
              <div key={i} className="leading-5">{i + 1}</div>
            ))}
          </div>
          
          {/* Code */}
          <div className="flex-1 py-4 px-4 overflow-x-auto">
            {lines.map((line, i) => {
              // Simple syntax highlighting
              const hasComment = line.trim().startsWith('//') || line.includes('//')
              const hasKeyword = /\b(class|module|interface|function|task|end|begin|typedef|struct|enum|logic|reg|wire|bit|int|parameter|localparam|import|export|package)\b/.test(line)
              const hasString = line.includes('"')
              
              let className = 'text-eda-text'
              if (hasComment) className = 'text-eda-text-tertiary'
              else if (hasKeyword) className = 'text-pink-400'
              else if (hasString) className = 'text-green-400'
              
              return (
                <div key={i} className={`leading-5 whitespace-pre ${className}`}>
                  {line || ' '}
                </div>
              )
            })}
          </div>
        </div>
      </pre>
    )
  }

  const hasFiles = generatedFiles.length > 0
  const isComplete = status === 'completed' || status === 'pending' && generatedFiles.length > 0

  return (
    <div className="bg-eda-bg-secondary border border-eda-border rounded-lg overflow-hidden flex flex-col" style={{ height: '100%' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-eda-border bg-eda-bg-tertiary/50">
        <div className="flex items-center gap-2">
          <Package className="w-4 h-4 text-eda-text-secondary" />
          <span className="text-sm font-medium text-eda-text">Generated Files</span>
          {hasFiles && (
            <span className="text-xs bg-eda-bg-tertiary text-eda-text-tertiary px-1.5 py-0.5 rounded">
              {generatedFiles.length}
            </span>
          )}
        </div>
        
        {isComplete && taskId && (
          <button
            onClick={() => downloadAll(taskId)}
            className="flex items-center gap-1.5 text-xs text-eda-accent hover:text-eda-accent-hover transition-colors"
          >
            <ArrowDownToLine className="w-3.5 h-3.5" />
            Download ZIP
          </button>
        )}
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* File tree */}
        <div className="w-72 border-r border-eda-border flex flex-col overflow-hidden">
          {!hasFiles ? (
            <div className="flex flex-col items-center justify-center h-full text-eda-text-tertiary p-6 text-center">
              <FileCode className="w-10 h-10 mb-3 opacity-30" />
              <p className="text-xs">No files yet</p>
              <p className="text-xs mt-1 opacity-70">Run generation to see files</p>
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto py-2">
              {categoryOrder.filter(cat => groupedFiles[cat]).map(category => (
                <div key={category} className="mb-1">
                  <div className="px-3 py-1 text-xs font-semibold text-eda-text-tertiary uppercase tracking-wide">
                    {category}
                  </div>
                  {groupedFiles[category].map(file => (
                    <button
                      key={file}
                      onClick={() => handleFileSelect(file)}
                      className={`w-full flex items-center gap-2 px-3 py-1.5 text-xs text-left transition-colors ${
                        selectedFile === file 
                          ? 'bg-eda-accent/15 text-eda-accent' 
                          : 'hover:bg-eda-bg-tertiary/50'
                      }`}
                    >
                      <span className={getFileColor(file)}>
                        {getFileIcon(file)}
                      </span>
                      <span className="truncate">{file}</span>
                    </button>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Code view */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* File header */}
          {selectedFile && (
            <div className="flex items-center gap-2 px-4 py-2 bg-eda-bg/50 border-b border-eda-border/30">
              <span className={getFileColor(selectedFile)}>
                {getFileIcon(selectedFile)}
              </span>
              <span className="text-xs font-mono text-eda-text">{selectedFile}</span>
            </div>
          )}
          
          {renderCode()}
        </div>
      </div>
    </div>
  )
}

export default FileViewer
