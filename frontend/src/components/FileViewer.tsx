import React, { useState, useCallback } from 'react'
import {
  FileCode, FileText, Package, Database, Cpu, ClipboardCheck,
  ArrowDownToLine, BarChart3, Search, X, FileType, Info, Hash
} from 'lucide-react'
import useAppStore from '../store/appStore'
import { useGenerationAPI } from '../hooks/useGenerationAPI'

const SV_KEYWORDS = new Set([
  'class', 'module', 'interface', 'function', 'task', 'endclass', 'endmodule',
  'endinterface', 'endfunction', 'endtask', 'begin', 'end', 'typedef', 'struct',
  'enum', 'logic', 'reg', 'wire', 'bit', 'int', 'byte', 'shortint', 'longint',
  'integer', 'real', 'string', 'parameter', 'localparam', 'import', 'export',
  'package', 'endpackage', 'if', 'else', 'for', 'while', 'foreach', 'do',
  'repeat', 'case', 'endcase', 'default', 'return', 'break', 'continue',
  'new', 'this', 'super', 'null', 'void', 'program', 'endprogram',
  'clocking', 'endclocking', 'property', 'endproperty', 'sequence', 'endsequence',
  'assert', 'assume', 'cover', 'rand', 'randc', 'constraint', 'solve', 'before',
  'dist', 'unique', 'priority', 'always', 'assign', 'initial', 'final',
  'generate', 'endgenerate', 'fork', 'join', 'join_any', 'join_none',
  'disable', 'wait', 'event', 'mailbox', 'semaphore', 'time', 'unit',
  'checker', 'endchecker', 'modport', 'clocking', 'global', 'ref', 'const',
  'pure', 'virtual', 'static', 'protected', 'local', 'public', 'extern',
  'input', 'output', 'inout', 'signed', 'unsigned', 'automatic',
  'uvm_component_utils', 'uvm_object_utils', 'uvm_field_*',
  '`uvm_*', 'uvm_*',
])

const SV_DIRECTIVES = new Set([
  'uvm_component_utils', 'uvm_object_utils', 'uvm_field_int', 'uvm_field_string',
  'uvm_field_enum', 'uvm_field_object', 'uvm_field_sarray_int', 'uvm_field_array_object',
  'uvm_do', 'uvm_do_with', 'uvm_do_pri', 'uvm_do_on', 'uvm_do_on_with',
  'uvm_create', 'uvm_send', 'uvm_rand_send',
  'uvm_info', 'uvm_warning', 'uvm_error', 'uvm_fatal',
  'uvm_report_info', 'uvm_report_warning', 'uvm_report_error', 'uvm_report_fatal',
  'uvm_config_db', 'uvm_resource_db',
  'uvm_object_utils_begin', 'uvm_object_utils_end',
  'uvm_component_utils_begin', 'uvm_component_utils_end',
  'uvm_field_utils_begin', 'uvm_field_utils_end',
  'include', 'ifdef', 'ifndef', 'define', 'endif', 'elsif', 'else',
  'timescale', 'celldefine', 'endcelldefine', 'unconnected_drive', 'nounconnected_drive',
  'default_nettype', 'resetall', 'line',
])

interface TokenStyle {
  text: string
  className: string
}

function tokenizeLine(line: string): TokenStyle[] {
  try {
    const tokens: TokenStyle[] = []
    let i = 0

    while (i < line.length) {
      if (line[i] === '/' && i + 1 < line.length && line[i + 1] === '/') {
        tokens.push({ text: line.slice(i), className: 'text-eda-text-tertiary italic' })
        return tokens
      }

      if (line[i] === '"') {
        const end = line.indexOf('"', i + 1)
        if (end === -1) { tokens.push({ text: line.slice(i), className: 'text-green-400' }); return tokens }
        tokens.push({ text: line.slice(i, end + 1), className: 'text-green-400' })
        i = end + 1
        continue
      }

      if (line[i] === "'" && i + 2 < line.length && line[i + 2] === "'") {
        tokens.push({ text: line.slice(i, i + 3), className: 'text-green-400' })
        i += 3
        continue
      }

      if (/[0-9]/.test(line[i]) && (i === 0 || /[\s,([=+\-/*]/.test(line[i - 1]))) {
        let num = ''
        while (i < line.length && /[0-9'xz?bhod]/.test(line[i])) { num += line[i]; i++ }
        tokens.push({ text: num, className: 'text-orange-400' })
        continue
      }

      if (/[a-zA-Z_`]/.test(line[i]) || line[i] === '\\') {
        let word = ''
        if (line[i] === '\\') { word += '\\'; i++ }
        while (i < line.length && /[a-zA-Z0-9_$`]/.test(line[i])) { word += line[i]; i++ }
        if (word === '') {
          tokens.push({ text: line[i], className: 'text-eda-text' })
          i++
          continue
        }
        const lower = word.toLowerCase().replace(/^`/, '')
        if (SV_DIRECTIVES.has(word) || (word.startsWith('`') && word.length > 1)) {
          tokens.push({ text: word, className: 'text-pink-400 font-semibold' })
        } else if (SV_KEYWORDS.has(lower) || lower.startsWith('uvm_')) {
          tokens.push({ text: word, className: 'text-pink-400' })
        } else if (i < line.length && line[i] === '(') {
          tokens.push({ text: word, className: 'text-eda-accent' })
        } else if (word.startsWith('`')) {
          tokens.push({ text: word, className: 'text-pink-400 font-semibold' })
        } else {
          tokens.push({ text: word, className: 'text-eda-text' })
        }
        continue
      }

      const operators = /[{}()\[\];,:.=+*/<>!&|^~%@#$?]/
      if (operators.test(line[i])) {
        tokens.push({ text: line[i], className: 'text-eda-text-secondary' })
        i++
        continue
      }

      tokens.push({ text: line[i], className: 'text-eda-text' })
      i++
    }

    return tokens
  } catch {
    return [{ text: line, className: 'text-eda-text' }]
  }
}

const FILE_TYPE_BADGES: Record<string, { label: string; color: string }> = {
  sv: { label: 'SV', color: 'bg-eda-accent/15 text-eda-accent' },
  v: { label: 'V', color: 'bg-eda-accent/10 text-eda-accent' },
  yaml: { label: 'YAML', color: 'bg-eda-warning/15 text-eda-warning' },
  yml: { label: 'YAML', color: 'bg-eda-warning/15 text-eda-warning' },
  py: { label: 'PY', color: 'bg-eda-success/15 text-eda-success' },
  json: { label: 'JSON', color: 'bg-purple-400/15 text-purple-400' },
  txt: { label: 'TXT', color: 'bg-eda-text-tertiary/15 text-eda-text-tertiary' },
  md: { label: 'MD', color: 'bg-eda-text-tertiary/15 text-eda-text-tertiary' },
  xml: { label: 'XML', color: 'bg-eda-text-tertiary/15 text-eda-text-tertiary' },
  ipxact: { label: 'IP-XACT', color: 'bg-eda-accent/10 text-eda-accent' },
}

function getFileBadge(name: string) {
  const ext = name.split('.').pop() || ''
  if (name.includes('ipxact')) return FILE_TYPE_BADGES['ipxact']
  return FILE_TYPE_BADGES[ext] || { label: ext.toUpperCase(), color: 'bg-eda-text-tertiary/10 text-eda-text-tertiary' }
}

const FileViewer: React.FC = () => {
  const { generatedFiles, selectedFile, setSelectedFile, fileContent, setFileContent, taskId, status } = useAppStore()
  const { getFileContent, downloadFile, downloadAll } = useGenerationAPI()
  const [showDashboard, setShowDashboard] = useState(false)
  const [dashboardHtml, setDashboardHtml] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<number[]>([])
  const [currentSearchIdx, setCurrentSearchIdx] = useState(0)
  const [showSearch, setShowSearch] = useState(false)

  const loadDashboard = useCallback(async () => {
    if (!taskId) return
    setShowDashboard(!showDashboard)
    if (!showDashboard && !dashboardHtml) {
      try {
        const base = window.location.origin
        const resp = await fetch(`${base}/api/generate/${taskId}/dashboard`)
        if (resp.ok) setDashboardHtml(await resp.text())
      } catch { /* ignore */ }
    }
  }, [taskId, showDashboard, dashboardHtml])

  const fileReqId = React.useRef(0)

  const handleFileSelect = useCallback(async (file: string) => {
    const reqId = ++fileReqId.current
    setFileContent(null)
    setSelectedFile(file)
    setSearchQuery('')
    setSearchResults([])
    setShowSearch(false)
    if (taskId) {
      const content = await getFileContent(taskId, file)
      if (reqId === fileReqId.current) {
        setFileContent(typeof content === 'string' ? content : null)
      }
    }
  }, [taskId, getFileContent, setSelectedFile, setFileContent])

  const performSearch = useCallback((query: string) => {
    setSearchQuery(query)
    if (!query || !fileContent) {
      setSearchResults([])
      return
    }
    const results: number[] = []
    const lines = fileContent.split('\n')
    lines.forEach((line, idx) => {
      if (line.toLowerCase().includes(query.toLowerCase())) results.push(idx + 1)
    })
    setSearchResults(results)
    setCurrentSearchIdx(0)
  }, [fileContent])

  const getFileIcon = (name: string) => {
    if (name.endsWith('.sv') || name.endsWith('.v')) return <FileCode className="w-3 h-3" />
    if (name.endsWith('.yaml') || name.endsWith('.yml')) return <Database className="w-3 h-3" />
    if (name.endsWith('.py')) return <Cpu className="w-3 h-3" />
    if (name.endsWith('.json')) return <Package className="w-3 h-3" />
    if (name.endsWith('.xml') || name.includes('ipxact')) return <FileType className="w-3 h-3" />
    if (name.endsWith('.txt') || name.endsWith('.md')) return <FileText className="w-3 h-3" />
    if (name.includes('test')) return <FileText className="w-3 h-3" />
    if (name.includes('env')) return <Package className="w-3 h-3" />
    return <FileCode className="w-3 h-3" />
  }

  const getFileColor = (name: string) => {
    if (name.endsWith('.sv') || name.endsWith('.v')) return 'text-eda-accent'
    if (name.includes('test') || name.includes('sequence')) return 'text-eda-warning'
    if (name.includes('env') || name.includes('agent')) return 'text-eda-success'
    if (name.includes('register') || name.includes('reg')) return 'text-purple-400'
    if (name.includes('driver') || name.includes('monitor')) return 'text-pink-400'
    return 'text-eda-text-secondary'
  }

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
    else if (file.endsWith('.py') || file.includes('python')) category = 'Scripts'
    else if (file.endsWith('.yaml') || file.endsWith('.yml')) category = 'Config'
    else if (file.endsWith('.xml') || file.includes('ipxact')) category = 'IP-XACT'
    groupedFiles[category] = [...(groupedFiles[category] || []), file]
  })

  const categoryOrder = [
    'Packages', 'Environment', 'Agents', 'Sequences', 'Tests',
    'Registers', 'Interfaces', 'Scripts', 'Config', 'IP-XACT', 'Other'
  ]

  const renderCode = () => {
    try {
      if (!fileContent) {
        return (
          <div className="flex flex-col items-center justify-center h-full text-eda-text-tertiary p-8">
            <FileCode className="w-10 h-10 mb-3 opacity-30" />
            <p className="text-xs">Select a file to view its contents</p>
          </div>
        )
      }

      const rawLines = fileContent.split('\n')
      const FILE_WARN_LINES = 3000
      const FILE_MAX_LINES = 10000
      const isLargeFile = rawLines.length > FILE_WARN_LINES
      const lines = rawLines.slice(0, FILE_MAX_LINES)
      const truncated = rawLines.length > FILE_MAX_LINES

    return (
      <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
        {truncated && (
          <div className="px-3 py-1.5 text-[10px] bg-amber-900/20 text-amber-400 border-b border-amber-800/30">
            File truncated — showing first {FILE_MAX_LINES} of {rawLines.length} lines
          </div>
        )}
        {isLargeFile && !truncated && (
          <div className="px-3 py-1 text-[9px] bg-eda-bg-tertiary/40 text-eda-text-tertiary border-b border-eda-border/20">
            Large file ({rawLines.length} lines) — syntax highlighting disabled to save memory
          </div>
        )}
        <pre className="flex-1 min-h-0 overflow-auto text-[11px] font-mono leading-relaxed" style={{ scrollbarWidth: 'thin' }}>
          <div className="flex">
            <div className="select-none text-eda-text-tertiary/50 bg-eda-bg/50 pr-2 pl-3 py-3 text-right border-r border-eda-border/20 min-w-[40px] text-[10px]">
              {lines.map((_, i) => {
                const lineNum = i + 1
                const isSearchMatch = searchResults.includes(lineNum)
                const isCurrentMatch = searchResults.length > 0 && searchResults[currentSearchIdx] === lineNum
                return (
                  <div key={i} className="leading-[1.6]"
                    style={{ backgroundColor: isCurrentMatch ? '#58a6ff33' : isSearchMatch ? '#58a6ff15' : 'transparent' }}>{lineNum}</div>
                )
              })}
            </div>
            <div className="flex-1 py-3 px-3 overflow-x-auto">
              {lines.map((line, i) => {
                const lineNum = i + 1
                const isSearchMatch = searchResults.includes(lineNum)
                const isCurrentMatch = searchResults.length > 0 && searchResults[currentSearchIdx] === lineNum
                const tokens = isLargeFile
                  ? [{ text: line, className: 'text-eda-text' }]
                  : tokenizeLine(line)
                return (
                  <div key={i} className="leading-[1.6] whitespace-pre"
                    style={{ backgroundColor: isCurrentMatch ? '#58a6ff33' : isSearchMatch ? '#58a6ff15' : 'transparent' }}>
                    {tokens.map((t, j) => <span key={j} className={t.className}>{t.text}</span>)}
                  </div>
                )
              })}
            </div>
          </div>
        </pre>
      </div>
    )
    } catch {
      return (
        <div className="flex flex-col items-center justify-center h-full text-eda-text-tertiary p-8">
          <FileCode className="w-10 h-10 mb-3 opacity-30" />
          <p className="text-xs">Error rendering file content</p>
        </div>
      )
    }
  }

  const hasFiles = generatedFiles.length > 0
  const isComplete = (status === 'completed' || status === 'failed') && generatedFiles.length > 0
  const rawLineCount = fileContent ? fileContent.split('\n').length : 0
  const displayLineCount = Math.min(rawLineCount, 10000)

  return (
    <div className="bg-eda-bg-secondary border border-eda-border rounded-lg overflow-hidden flex flex-col" style={{ height: '100%' }}>
      <div className="flex items-center justify-between px-3 py-2 border-b border-eda-border bg-eda-bg-tertiary/50">
        <div className="flex items-center gap-2">
          <Package className="w-3.5 h-3.5 text-eda-text-secondary" />
          <span className="text-[11px] font-medium text-eda-text">Generated Files</span>
          {hasFiles && (
            <span className="text-[10px] bg-eda-bg-tertiary text-eda-text-tertiary px-1.5 py-0.5 rounded-md font-mono">{generatedFiles.length}</span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          {selectedFile && fileContent && (
            <div className="flex items-center gap-1.5 text-[9px] text-eda-text-tertiary/60 mr-1">
              <Info className="w-2.5 h-2.5" />
              <span>{displayLineCount}{rawLineCount > 10000 ? '+' : ''} lines</span>
              <span className="opacity-50">|</span>
              <span>{fileContent.length} bytes</span>
            </div>
          )}
          {isComplete && taskId && (
            <>
              <button onClick={loadDashboard}
                className={`flex items-center gap-1 px-2 py-1 text-[10px] rounded transition-colors ${
                  showDashboard ? 'text-eda-accent bg-eda-accent/10' : 'text-eda-text-tertiary hover:text-eda-accent hover:bg-eda-bg-tertiary'
                }`}>
                <BarChart3 className="w-3 h-3" /> Dashboard
              </button>
              <button onClick={() => downloadAll(taskId)}
                className="flex items-center gap-1 px-2 py-1 text-[10px] text-eda-accent hover:text-eda-accent-hover hover:bg-eda-bg-tertiary rounded transition-colors">
                <ArrowDownToLine className="w-3 h-3" /> ZIP
              </button>
            </>
          )}
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <div className="w-64 border-r border-eda-border flex flex-col overflow-hidden">
          {!hasFiles ? (
            <div className="flex flex-col items-center justify-center h-full text-eda-text-tertiary p-6 text-center">
              <FileCode className="w-8 h-8 mb-2 opacity-30" />
              <p className="text-[10px]">No files yet</p>
              <p className="text-[10px] mt-0.5 opacity-70">Run generation to see files</p>
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto py-1" style={{ scrollbarWidth: 'thin' }}>
              {categoryOrder.filter(cat => groupedFiles[cat]).map(category => (
                  <div key={category} className="mb-0.5">
                    <div className="px-2.5 py-1 text-[9px] font-semibold text-eda-text-tertiary/70 uppercase tracking-wider flex items-center gap-1 hover:text-eda-text-secondary transition-colors">
                      <Hash className="w-2 h-2" /> {category}
                      <span className="text-[8px] text-eda-text-tertiary/40 ml-auto">{groupedFiles[category].length}</span>
                    </div>
                  {groupedFiles[category].map(file => {
                    const badge = getFileBadge(file)
                    return (
                      <button key={file} onClick={() => handleFileSelect(file)}
                        className={`w-full flex items-center gap-1.5 px-2.5 py-1 text-[10px] text-left file-item-hover ${
                          selectedFile === file ? 'bg-eda-accent/10 text-eda-accent border-l-2 border-eda-accent' : 'hover:bg-eda-bg-tertiary/50 border-l-2 border-transparent'
                        }`}>
                        <span className={getFileColor(file)}>{getFileIcon(file)}</span>
                        <span className="truncate flex-1">{file}</span>
                        <span className={`text-[7px] px-1 py-0.5 rounded-sm font-semibold ${badge.color}`}>{badge.label}</span>
                      </button>
                    )
                  })}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex-1 flex flex-col overflow-hidden">
          {selectedFile && (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-eda-bg/50 border-b border-eda-border/20">
              <span className={getFileColor(selectedFile)}>{getFileIcon(selectedFile)}</span>
              <span className="text-[10px] font-mono text-eda-text flex-1">{selectedFile}</span>
              <button onClick={() => setShowSearch(!showSearch)}
                className={`p-1 rounded transition-colors ${showSearch ? 'text-eda-accent bg-eda-accent/10' : 'text-eda-text-tertiary hover:text-eda-text hover:bg-eda-bg-tertiary'}`}
                title="Search in file">
                <Search className="w-3 h-3" />
              </button>
              <button onClick={async () => {
                if (fileContent) {
                  await navigator.clipboard.writeText(fileContent)
                  setCopied(true)
                  setTimeout(() => setCopied(false), 2000)
                }
              }} className="p-1 text-eda-text-tertiary hover:text-eda-accent hover:bg-eda-bg-tertiary rounded transition-colors" title="Copy to clipboard">
                <ClipboardCheck className="w-3 h-3" /> {copied && <span className="text-[8px] ml-0.5">Copied!</span>}
              </button>
              {taskId && (
                <button onClick={() => downloadFile(taskId, selectedFile)}
                  className="p-1 text-eda-text-tertiary hover:text-eda-accent hover:bg-eda-bg-tertiary rounded transition-colors" title="Download file">
                  <ArrowDownToLine className="w-3 h-3" />
                </button>
              )}
            </div>
          )}

          {showSearch && fileContent && (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-eda-bg/30 border-b border-eda-border/20">
              <Search className="w-3 h-3 text-eda-text-tertiary" />
              <input type="text" value={searchQuery} onChange={e => performSearch(e.target.value)}
                placeholder="Search in file..."
                className="flex-1 bg-transparent border-0 text-[10px] font-mono text-eda-text placeholder-eda-text-tertiary/50 focus:outline-none"
                autoFocus />
              {searchResults.length > 0 && (
                <div className="flex items-center gap-1.5 text-[10px] text-eda-text-tertiary">
                  <span className="font-mono">{currentSearchIdx + 1}/{searchResults.length}</span>
                  <button onClick={() => setCurrentSearchIdx(i => Math.max(0, i - 1))}
                    className="p-0.5 hover:text-eda-text transition-colors">↑</button>
                  <button onClick={() => setCurrentSearchIdx(i => Math.min(searchResults.length - 1, i + 1))}
                    className="p-0.5 hover:text-eda-text transition-colors">↓</button>
                </div>
              )}
              <button onClick={() => { setShowSearch(false); setSearchQuery(''); setSearchResults([]) }}
                className="p-0.5 text-eda-text-tertiary hover:text-eda-text transition-colors">
                <X className="w-3 h-3" />
              </button>
            </div>
          )}

          {showDashboard && dashboardHtml ? (
            <iframe srcDoc={dashboardHtml} className="w-full h-full border-0 animate-fade-in" title="Coverage Dashboard" sandbox="allow-scripts" />
          ) : (
            <div key={selectedFile || 'empty'} className="animate-fade-in flex-1 flex flex-col min-h-0">
              {renderCode()}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default FileViewer
