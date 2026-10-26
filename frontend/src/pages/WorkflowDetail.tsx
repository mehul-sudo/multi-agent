/**
 * WorkflowDetail page — View, build, and execute individual workflows.
 * Includes: DAG visualization, node management, dependency management, execute.
 */
import React, { useState, useCallback, useRef, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ArrowLeft, Plus, Play, CheckCircle, Layers, Link2,
  Trash2, RefreshCw, GitBranch, Bot, AlertTriangle, Edit3, Mail,
  BarChart3, FileText, Download, Copy, Upload, Shield, Database,
  Globe, BookOpen, Clock, ChevronDown, ChevronRight, Check
} from 'lucide-react'
import { workflowsApi, agentsApi, schedulesApi, uploadsApi, type Workflow, type WorkflowNode, type Agent } from '../lib/api'
import { useAsync } from '../hooks/useAsync'
import { Modal, FormGroup, StatusBadge, EmptyState, ErrorState, SectionHeader } from '../components/ui'

// ─── DAG Visualizer ───────────────────────────────────────────────────────────

interface DagNode {
  id: string
  name: string
  agentName?: string
  x: number
  y: number
  status?: string
}


function computeDAGLayout(nodes: WorkflowNode[], deps: { source_node_id: string; target_node_id: string }[]) {
  // Topological sort + layer assignment with priority consideration
  const adj: Map<string, string[]> = new Map()
  const inDeg: Map<string, number> = new Map()
  const nodeMap = new Map(nodes.map((n) => [n.public_id, n]))

  nodes.forEach((n) => { adj.set(n.public_id, []); inDeg.set(n.public_id, 0) })
  deps.forEach((d) => {
    adj.get(d.source_node_id)?.push(d.target_node_id)
    inDeg.set(d.target_node_id, (inDeg.get(d.target_node_id) || 0) + 1)
  })

  const layers: string[][] = []
  // Sort initial root nodes by priority descending
  const queue = nodes
    .filter((n) => inDeg.get(n.public_id) === 0)
    .sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0))
    .map((n) => n.public_id)
  const visited = new Set<string>()

  while (queue.length > 0) {
    const layer: string[] = []
    const nextQueue: string[] = []
    for (const id of queue) {
      if (visited.has(id)) continue
      visited.add(id)
      layer.push(id)
      for (const next of adj.get(id) || []) {
        const deg = (inDeg.get(next) || 0) - 1
        inDeg.set(next, deg)
        if (deg === 0) nextQueue.push(next)
      }
    }
    if (layer.length > 0) layers.push(layer)
    queue.length = 0
    // Sort next ready nodes by priority descending
    nextQueue.sort((a, b) => (nodeMap.get(b)?.priority ?? 0) - (nodeMap.get(a)?.priority ?? 0))
    queue.push(...nextQueue)
  }

  const NODE_W = 190, NODE_H = 80, H_GAP = 70, V_GAP = 30
  const dagNodes: DagNode[] = []

  layers.forEach((layer, li) => {
    const totalH = layer.length * NODE_H + (layer.length - 1) * V_GAP
    const startY = -(totalH / 2)
    layer.forEach((id, ni) => {
      const n = nodeMap.get(id)
      dagNodes.push({
        id,
        name: n?.name || id,
        agentName: n?.agent_name || undefined,
        x: li * (NODE_W + H_GAP),
        y: startY + ni * (NODE_H + V_GAP),
      })
    })
  })

  return dagNodes
}

function DAGCanvas({
  workflow,
  agents,
  onDeleteNode,
  onDeleteEdge,
  onEditNode,
}: {
  workflow: Workflow
  agents?: Agent[]
  onDeleteNode: (nodeId: string) => void
  onDeleteEdge: (depId: string) => void
  onEditNode?: (node: WorkflowNode) => void
}) {
  const svgRef = useRef<SVGSVGElement>(null)
  const nodes = workflow.nodes || []
  const deps = workflow.dependencies || []

  const dagNodes = computeDAGLayout(nodes, deps)
  const NODE_W = 190, NODE_H = 80, PAD = 40

  const xs = dagNodes.map((n) => n.x)
  const ys = dagNodes.map((n) => n.y)
  const minX = Math.min(0, ...xs) - PAD
  const minY = Math.min(0, ...ys) - PAD
  const maxX = Math.max(NODE_W, ...xs.map((x) => x + NODE_W)) + PAD
  const maxY = Math.max(NODE_H, ...ys.map((y) => y + NODE_H)) + PAD
  const W = maxX - minX
  const H = maxY - minY

  const nodePos = new Map(dagNodes.map((n) => [n.id, n]))
  const nodeObjMap = new Map(nodes.map((n) => [n.public_id, n]))

  const getCenter = (id: string) => {
    const n = nodePos.get(id)
    return n ? { x: n.x - minX + NODE_W / 2, y: n.y - minY + NODE_H / 2 } : { x: 0, y: 0 }
  }

  const DEP_COLORS: Record<string, string> = {
    on_success: '#10b981',
    on_failure: '#f43f5e',
    always: '#818cf8',
  }
  const DEP_LABELS: Record<string, string> = {
    on_success: '✓ success',
    on_failure: '✗ fail',
    always: '↻ always',
  }

  if (nodes.length === 0) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200, color: 'var(--text-muted)', fontSize: 13, flexDirection: 'column', gap: 8 }}>
        <GitBranch size={32} style={{ opacity: 0.3 }} />
        <span>Add nodes to visualize the workflow DAG</span>
      </div>
    )
  }

  return (
    <div>
      {/* Legend */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 12, flexWrap: 'wrap' }}>
        {Object.entries(DEP_COLORS).map(([type, color]) => (
          <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--text-muted)' }}>
            <div style={{ width: 24, height: 2, background: color, borderRadius: 1 }} />
            <span style={{ color }}>{DEP_LABELS[type]}</span>
          </div>
        ))}
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--text-muted)' }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'rgba(99,102,241,0.4)', border: '1px solid rgba(99,102,241,0.6)' }} />
          <span>Click node to edit</span>
        </div>
      </div>

      <div style={{ overflowX: 'auto', overflowY: 'hidden' }}>
        <svg
          ref={svgRef}
          width={Math.max(600, W)}
          height={Math.max(220, H)}
          style={{ display: 'block' }}
        >
          <defs>
            {Object.entries(DEP_COLORS).map(([type, color]) => (
              <marker key={type} id={`arrow-${type}`} markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
                <polygon points="0 0, 8 3, 0 6" fill={color} opacity="0.8" />
              </marker>
            ))}
            <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
              <polygon points="0 0, 8 3, 0 6" fill="rgba(99,102,241,0.6)" />
            </marker>
            <filter id="node-shadow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="2" stdDeviation="4" floodColor="rgba(0,0,0,0.4)" />
            </filter>
          </defs>

          {/* Edges */}
          {deps.map((dep) => {
            const src = getCenter(dep.source_node_id)
            const tgt = getCenter(dep.target_node_id)
            const cx = (src.x + tgt.x) / 2
            const midX = (src.x + tgt.x) / 2
            const midY = (src.y + tgt.y) / 2
            const depColor = DEP_COLORS[dep.dependency_type] || DEP_COLORS['on_success']
            const depLabel = DEP_LABELS[dep.dependency_type] || dep.dependency_type
            const markerId = DEP_COLORS[dep.dependency_type] ? `arrow-${dep.dependency_type}` : 'arrowhead'
            return (
              <g key={dep.public_id}>
                {/* Wider invisible hit-target for easier clicking */}
                <path
                  d={`M ${src.x} ${src.y} C ${cx} ${src.y}, ${cx} ${tgt.y}, ${tgt.x} ${tgt.y}`}
                  fill="none"
                  stroke="transparent"
                  strokeWidth="12"
                  style={{ cursor: 'pointer' }}
                  onClick={(e) => {
                    e.stopPropagation()
                    onDeleteEdge(dep.public_id)
                  }}
                />
                <path
                  d={`M ${src.x} ${src.y} C ${cx} ${src.y}, ${cx} ${tgt.y}, ${tgt.x} ${tgt.y}`}
                  fill="none"
                  stroke={depColor}
                  strokeWidth="1.75"
                  strokeOpacity="0.7"
                  markerEnd={`url(#${markerId})`}
                />
                {/* Edge type label at midpoint */}
                <rect
                  x={midX - 26}
                  y={midY - 8}
                  width={52}
                  height={16}
                  rx="4"
                  fill="#1a1d2e"
                  stroke={depColor}
                  strokeOpacity="0.5"
                  strokeWidth="1"
                />
                <text
                  x={midX}
                  y={midY + 4}
                  textAnchor="middle"
                  fontSize="8"
                  fontWeight="600"
                  fill={depColor}
                  fontFamily="Inter, monospace"
                >
                  {depLabel}
                </text>
              </g>
            )
          })}

          {/* Nodes */}
        {dagNodes.map((dn) => {
          const x = dn.x - minX
          const y = dn.y - minY
          const nodeObj = nodeObjMap.get(dn.id)
          const prio = nodeObj?.priority ?? 0
          const agent = agents?.find((a) => a.id === nodeObj?.agent_id)
          const agentLabel = agent?.name || nodeObj?.agent_name || (nodeObj?.task_type ? nodeObj.task_type.replace('_', ' ') : 'Agent Task')
          return (
            <g
              key={dn.id}
              transform={`translate(${x}, ${y})`}
              style={{ cursor: onEditNode ? 'pointer' : 'default' }}
              onClick={() => nodeObj && onEditNode && onEditNode(nodeObj)}
            >
              <rect
                width={NODE_W}
                height={NODE_H}
                rx="10"
                fill="#1f2330"
                stroke="rgba(99,102,241,0.3)"
                strokeWidth="1.5"
                filter="url(#node-shadow)"
              />
              {/* Icon bg */}
              <rect x="12" y="14" width="26" height="26" rx="6" fill="rgba(99,102,241,0.15)" />
              <text x="25" y="32" textAnchor="middle" fontSize="13" fill="#818cf8">⬡</text>
              {/* Name */}
              <text x="46" y="28" fontSize="11.5" fontWeight="600" fill="#f1f5f9" fontFamily="Inter, sans-serif">
                {dn.name.length > 15 ? dn.name.slice(0, 15) + '…' : dn.name}
              </text>
              {/* Sub-label (Agent) */}
              <text x="46" y="44" fontSize="9.5" fill="#94a3b8" fontFamily="Inter, sans-serif">
                {agentLabel.length > 18 ? agentLabel.slice(0, 18) + '…' : agentLabel}
              </text>

              {/* Priority badge pill */}
              <g transform="translate(12, 53)">
                <rect
                  width="54"
                  height="18"
                  rx="4"
                  fill="rgba(245, 158, 11, 0.15)"
                  stroke="rgba(245, 158, 11, 0.4)"
                />
                <text x="27" y="12.5" textAnchor="middle" fontSize="9.5" fontWeight="700" fill="#f59e0b" fontFamily="Inter, sans-serif">
                  PRIO {prio}
                </text>
              </g>

              {/* Edit button */}
              {onEditNode && (
                <g
                  transform={`translate(${NODE_W - 40}, 10)`}
                  style={{ cursor: 'pointer' }}
                  onClick={(e) => {
                    e.stopPropagation()
                    if (nodeObj) onEditNode(nodeObj)
                  }}
                >
                  <title>Edit Node & Priority</title>
                  <rect width="16" height="16" rx="3" fill="rgba(99,102,241,0.15)" stroke="rgba(99,102,241,0.3)" />
                  <text x="8" y="12" textAnchor="middle" fontSize="9" fill="#a5b4fc">✎</text>
                </g>
              )}

              {/* Delete button */}
              <g
                transform={`translate(${NODE_W - 20}, 10)`}
                style={{ cursor: 'pointer' }}
                onClick={(e) => {
                  e.stopPropagation()
                  onDeleteNode(dn.id)
                }}
              >
                <title>Delete Node</title>
                <rect width="16" height="16" rx="3" fill="rgba(244,63,94,0.1)" stroke="rgba(244,63,94,0.2)" />
                <text x="8" y="12" textAnchor="middle" fontSize="9" fill="#fb7185">×</text>
              </g>
            </g>
          )
        })}
        </svg>
      </div>
    </div>
  )
}

// ─── Add Node Modal ───────────────────────────────────────────────────────────

// ─── Built-in Platform Agents Guarantee ──────────────────────────────────────────

const BUILTIN_PLATFORM_AGENTS: Agent[] = [
  { id: 'data_analysis', public_id: 'data_analysis', name: 'Data Analysis Agent', display_name: 'Data Analysis Agent', role: 'Statistical & Trend Analytics', agent_type: 'data_analysis', status: 'active', requires_human_approval: false, created_at: '', description: 'Performs statistical summarization, calculations, and outlier detection.', provider: 'gemini', model: 'gemini-3.5-flash', version: 1, capabilities: ['dataset', 'numbers', 'query', 'file_id'] },
  { id: 'document_research', public_id: 'document_research', name: 'Document Research Agent', display_name: 'Document Research Agent', role: 'Document Research & Synthesis', agent_type: 'document_research', status: 'active', requires_human_approval: false, created_at: '', description: 'Grounded document question answering with verified citations.', provider: 'gemini', model: 'gemini-3.5-flash', version: 1, capabilities: ['file_id', 'query', 'documents'] },
  { id: 'report_generation', public_id: 'report_generation', name: 'Report Generation Agent', display_name: 'Report Generation Agent', role: 'Executive Report Publisher', agent_type: 'report_generation', status: 'active', requires_human_approval: false, created_at: '', description: 'Synthesizes intelligence data into structured executive briefs.', provider: 'gemini', model: 'gemini-3.5-flash', version: 1, capabilities: ['title', 'summary', 'format'] },
  { id: 'email', public_id: 'email', name: 'Executive Email Agent', display_name: 'Executive Email Agent', role: 'Email Dispatch & Notifications', agent_type: 'email', status: 'active', requires_human_approval: true, created_at: '', description: 'Dispatches verified email notifications with delivery confirmation.', provider: 'resend', model: 'resend-v1', version: 1, capabilities: ['to', 'subject', 'body', 'mode'] },
  { id: 'security_analysis', public_id: 'security_analysis', name: 'Security Analysis Agent', display_name: 'Security Analysis Agent', role: 'Security & Vulnerability Scanner', agent_type: 'security_analysis', status: 'active', requires_human_approval: false, created_at: '', description: 'Static application security testing and dependency vulnerability detection.', provider: 'gemini', model: 'gemini-3.5-flash', version: 1, capabilities: ['code', 'scan_type'] },
  { id: 'database_bi', public_id: 'database_bi', name: 'Database & SQL BI Agent', display_name: 'Database & SQL BI Agent', role: 'SQL & Business Intelligence', agent_type: 'database_bi', status: 'active', requires_human_approval: false, created_at: '', description: 'Read-only SQL analytics and business intelligence telemetry.', provider: 'sqlite', model: 'sql-v1', version: 1, capabilities: ['query', 'read_only'] },
  { id: 'http_webhook', public_id: 'http_webhook', name: 'HTTP Webhook Agent', display_name: 'HTTP Webhook Agent', role: 'Enterprise Webhook / HTTP Agent', agent_type: 'http_webhook', status: 'active', requires_human_approval: true, created_at: '', description: 'Executes outbound REST calls and webhooks with payload verification.', provider: 'http', model: 'webhook-v1', version: 1, capabilities: ['url', 'method', 'data'] },
]

function getAgentTypeIcon(type?: string) {
  switch ((type || '').toLowerCase()) {
    case 'email': return '✉️'
    case 'data_analysis': return '📊'
    case 'report_generation': return '📄'
    case 'http_webhook': return '🌐'
    case 'security_analysis': return '🛡️'
    case 'database_bi': return '🗄️'
    case 'document_research': return '📚'
    default: return '🤖'
  }
}

// ─── Agent-Specific Node Configuration Form ────────────────────────────────────

interface NodeFormState {
  name: string
  agentId: string
  priority: number
  outputKey: string
  instructions: string
  showAdvanced: boolean

  // Data Analysis
  dataQuery: string
  dataNumbers: string
  dataFileId: string
  dataFileName: string

  // Document Research
  docQuery: string
  docFileId: string
  docFileName: string
  docText: string

  // Report Generation
  reportTitle: string
  reportInstructions: string
  reportFormat: string

  // Email
  emailTo: string
  emailSubject: string
  emailBody: string

  // Security Analysis
  secContent: string
  secScanType: string
  secFileId: string
  secFileName: string

  // Database BI
  dbQuery: string

  // HTTP Webhook
  webhookUrl: string
  webhookMethod: string
  webhookHeaders: string
  webhookBody: string
}

function AgentSpecificConfigForm({
  form,
  setForm,
  allAvailableAgents,
  isLoadingAgents,
  onRefreshAgents
}: {
  form: NodeFormState
  setForm: React.Dispatch<React.SetStateAction<NodeFormState>>
  allAvailableAgents: Agent[]
  isLoadingAgents?: boolean
  onRefreshAgents?: () => void
}) {
  const [uploading, setUploading] = useState(false)
  const [uploadErr, setUploadErr] = useState('')

  const selectedAgent = allAvailableAgents.find((a) => {
    const aid = String(a.id || (a as any).public_id || (a as any).internal_id)
    return aid === String(form.agentId) || a.agent_type === String(form.agentId)
  })

  const agentType = selectedAgent?.agent_type || ''

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>, target: 'data' | 'doc' | 'sec') => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setUploadErr('')
    try {
      const res = await uploadsApi.upload(file)
      if (target === 'data') {
        setForm(prev => ({ ...prev, dataFileId: res.file_id, dataFileName: file.name }))
      } else if (target === 'doc') {
        setForm(prev => ({ ...prev, docFileId: res.file_id, docFileName: file.name }))
      } else {
        setForm(prev => ({ ...prev, secFileId: res.file_id, secFileName: file.name }))
      }
    } catch (err: any) {
      setUploadErr(err.message || 'File upload failed.')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* 1. Node Name */}
      <FormGroup label="Node Step Name" required hint="Display name for this workflow stage">
        <input
          className="input"
          placeholder="e.g. Ingest & Analyze Q3 Data, Generate Executive Report"
          value={form.name}
          onChange={(e) => setForm(prev => ({ ...prev, name: e.target.value }))}
          required
        />
      </FormGroup>

      {/* 2. Agent Selector */}
      <FormGroup
        label={
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
            <span>Specialized Agent *</span>
            {onRefreshAgents && (
              <button
                type="button"
                onClick={onRefreshAgents}
                disabled={isLoadingAgents}
                style={{
                  background: 'none', border: 'none', color: 'var(--brand-primary)',
                  fontSize: 11, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 4
                }}
              >
                <RefreshCw size={11} className={isLoadingAgents ? 'animate-spin' : ''} />
                Refresh ({allAvailableAgents.length})
              </button>
            )}
          </div>
        }
        required
      >
        <select
          className="input"
          value={form.agentId}
          onChange={(e) => {
            const val = e.target.value
            const match = allAvailableAgents.find(a => String(a.id || (a as any).public_id) === val || a.agent_type === val)
            setForm(prev => ({
              ...prev,
              agentId: val,
              name: (!prev.name || prev.name.trim() === '' || allAvailableAgents.some(a => a.name === prev.name || a.display_name === prev.name)) && match
                ? (match.display_name || match.name)
                : prev.name
            }))
          }}
          required
        >
          <option value="">Select a specialized agent...</option>
          {isLoadingAgents && <option disabled value="__loading">⏳ Loading available agents...</option>}
          {allAvailableAgents.map((a) => {
            const aid = a.id || (a as any).public_id
            return (
              <option key={aid} value={aid}>
                {getAgentTypeIcon(a.agent_type)} {a.display_name || a.name} ({a.role || a.agent_type})
              </option>
            )
          })}
        </select>
      </FormGroup>

      {/* 3. AGENT-SPECIFIC HUMAN-FRIENDLY FORMS */}

      {/* DATA ANALYSIS FORM */}
      {(agentType === 'data_analysis' || form.agentId.includes('data')) && (
        <div style={{ background: 'var(--surface-1)', padding: 14, borderRadius: 8, border: '1px solid rgba(245,158,11,0.3)', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#f59e0b', display: 'flex', alignItems: 'center', gap: 6 }}>
            <BarChart3 size={15} /> Data Analysis Configuration
          </div>

          <FormGroup label="Analysis Question / Goal" required hint="Specific statistical questions or instructions">
            <textarea
              className="input"
              rows={2}
              placeholder="e.g. Calculate mean, median, IQR, percentiles (P25-P99), and detect anomalous outliers"
              value={form.dataQuery}
              onChange={(e) => setForm(prev => ({ ...prev, dataQuery: e.target.value }))}
            />
          </FormGroup>

          <FormGroup label="Dataset File (CSV / XLSX)" hint="Upload a real dataset file for tabular processing">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <label className="btn btn-secondary btn-sm" style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <Upload size={13} /> {uploading ? 'Uploading...' : 'Upload CSV / Excel'}
                <input
                  type="file"
                  accept=".csv,.xlsx,.xls,.json"
                  style={{ display: 'none' }}
                  onChange={(e) => handleFileUpload(e, 'data')}
                  disabled={uploading}
                />
              </label>
              {form.dataFileName && (
                <span className="badge badge-emerald" style={{ fontSize: 11, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                  <Check size={11} /> {form.dataFileName}
                </span>
              )}
            </div>
            {uploadErr && <div style={{ fontSize: 11, color: 'var(--accent-rose)', marginTop: 4 }}>⚠️ {uploadErr}</div>}
          </FormGroup>

          <FormGroup label="Inline Numbers / Dataset Values (Alternative)" hint="Comma-separated numbers if no file uploaded">
            <input
              className="input"
              placeholder="e.g. 120, 160, 210, 290, 380, 490, 620"
              value={form.dataNumbers}
              onChange={(e) => setForm(prev => ({ ...prev, dataNumbers: e.target.value }))}
            />
          </FormGroup>
        </div>
      )}

      {/* DOCUMENT RESEARCH FORM */}
      {(agentType === 'document_research' || form.agentId.includes('doc')) && (
        <div style={{ background: 'var(--surface-1)', padding: 14, borderRadius: 8, border: '1px solid rgba(14,165,233,0.3)', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#0ea5e9', display: 'flex', alignItems: 'center', gap: 6 }}>
            <BookOpen size={15} /> Document Research & Q&A Configuration
          </div>

          <FormGroup label="Research Question / Query" required hint="What should the agent research and answer with citations?">
            <textarea
              className="input"
              rows={2}
              placeholder="e.g. What are the key risk factors and regulatory compliance requirements described in the document?"
              value={form.docQuery}
              onChange={(e) => setForm(prev => ({ ...prev, docQuery: e.target.value }))}
            />
          </FormGroup>

          <FormGroup label="Document File (PDF / DOCX / TXT)" hint="Upload a reference document for grounded Q&A">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <label className="btn btn-secondary btn-sm" style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <Upload size={13} /> {uploading ? 'Uploading...' : 'Upload Document'}
                <input
                  type="file"
                  accept=".pdf,.docx,.doc,.txt,.md"
                  style={{ display: 'none' }}
                  onChange={(e) => handleFileUpload(e, 'doc')}
                  disabled={uploading}
                />
              </label>
              {form.docFileName && (
                <span className="badge badge-emerald" style={{ fontSize: 11, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                  <Check size={11} /> {form.docFileName}
                </span>
              )}
            </div>
          </FormGroup>

          <FormGroup label="Inline Document Text / Passages (Alternative)" hint="Direct text snippet if no file uploaded">
            <textarea
              className="input"
              rows={3}
              placeholder="Paste document excerpts or context passages here..."
              value={form.docText}
              onChange={(e) => setForm(prev => ({ ...prev, docText: e.target.value }))}
            />
          </FormGroup>
        </div>
      )}

      {/* REPORT GENERATION FORM */}
      {(agentType === 'report_generation' || form.agentId.includes('report')) && (
        <div style={{ background: 'var(--surface-1)', padding: 14, borderRadius: 8, border: '1px solid rgba(16,185,129,0.3)', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#10b981', display: 'flex', alignItems: 'center', gap: 6 }}>
            <FileText size={15} /> Executive Report Generation Configuration
          </div>

          <FormGroup label="Report Title / Topic" required hint="Determines the entire subject matter of the 9-section report">
            <input
              className="input"
              placeholder="e.g. Cybersecurity Risk Assessment of a Web Application"
              value={form.reportTitle}
              onChange={(e) => setForm(prev => ({ ...prev, reportTitle: e.target.value }))}
            />
          </FormGroup>

          <FormGroup label="Focus Area / Specific Instructions" hint="Guidance for synthesis, key areas to emphasize">
            <textarea
              className="input"
              rows={2}
              placeholder="e.g. Synthesize upstream analytical metrics, evaluate vulnerabilities, and provide actionable next steps."
              value={form.reportInstructions}
              onChange={(e) => setForm(prev => ({ ...prev, reportInstructions: e.target.value }))}
            />
          </FormGroup>

          <FormGroup label="Primary Output Format">
            <select
              className="input"
              value={form.reportFormat}
              onChange={(e) => setForm(prev => ({ ...prev, reportFormat: e.target.value }))}
            >
              <option value="pdf">📄 PDF Document (.pdf)</option>
              <option value="docx">📑 Word Document (.docx)</option>
              <option value="html">🌐 HTML Interactive Report (.html)</option>
              <option value="markdown">📝 Markdown Executive Brief (.md)</option>
            </select>
          </FormGroup>
        </div>
      )}

      {/* EMAIL AGENT FORM */}
      {(agentType === 'email' || form.agentId.includes('email')) && (
        <div style={{ background: 'var(--surface-1)', padding: 14, borderRadius: 8, border: '1px solid rgba(99,102,241,0.3)', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#818cf8', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Mail size={15} /> Executive Email Notification Configuration
          </div>

          <FormGroup label="Recipient Email (To)" required hint="Target inbox to receive email notification">
            <input
              className="input"
              type="email"
              placeholder="e.g. mehulpankajmaha@gmail.com"
              value={form.emailTo}
              onChange={(e) => setForm(prev => ({ ...prev, emailTo: e.target.value }))}
              required
            />
          </FormGroup>

          <FormGroup label="Subject Line" required>
            <input
              className="input"
              placeholder="e.g. Automated Multi-Agent Pipeline Execution Results"
              value={form.emailSubject}
              onChange={(e) => setForm(prev => ({ ...prev, emailSubject: e.target.value }))}
              required
            />
          </FormGroup>

          <FormGroup label="Message Body">
            <textarea
              className="input"
              rows={3}
              placeholder="Leave blank to automatically synthesize upstream pipeline findings and attach generated reports."
              value={form.emailBody}
              onChange={(e) => setForm(prev => ({ ...prev, emailBody: e.target.value }))}
            />
          </FormGroup>
        </div>
      )}

      {/* SECURITY ANALYSIS FORM */}
      {(agentType === 'security_analysis' || form.agentId.includes('sec')) && (
        <div style={{ background: 'var(--surface-1)', padding: 14, borderRadius: 8, border: '1px solid rgba(239,68,68,0.3)', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#f43f5e', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Shield size={15} /> Security & Vulnerability Scan Configuration
          </div>

          <FormGroup label="Scan Type">
            <select
              className="input"
              value={form.secScanType}
              onChange={(e) => setForm(prev => ({ ...prev, secScanType: e.target.value }))}
            >
              <option value="code_vulnerability">Static Code Vulnerability Audit</option>
              <option value="prompt_injection">Prompt Injection & Jailbreak Defense</option>
              <option value="dependency_audit">Dependency & Supply-Chain Audit</option>
              <option value="secret_leakage">Secret & Key Leakage Detection</option>
            </select>
          </FormGroup>

          <FormGroup label="Target Code / Config / Prompt to Scan" required>
            <textarea
              className="input"
              rows={4}
              placeholder="Paste source code snippet, configuration, or prompt to audit..."
              value={form.secContent}
              onChange={(e) => setForm(prev => ({ ...prev, secContent: e.target.value }))}
            />
          </FormGroup>
        </div>
      )}

      {/* DATABASE & SQL BI FORM */}
      {(agentType === 'database_bi' || form.agentId.includes('data_base') || form.agentId.includes('db')) && (
        <div style={{ background: 'var(--surface-1)', padding: 14, borderRadius: 8, border: '1px solid rgba(139,92,246,0.3)', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#8b5cf6', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Database size={15} /> Database & SQL BI Configuration
          </div>

          <FormGroup label="SQL Query / Natural Language Question" required>
            <textarea
              className="input"
              rows={3}
              placeholder="e.g. SELECT status, count(*) FROM jobs GROUP BY status"
              value={form.dbQuery}
              onChange={(e) => setForm(prev => ({ ...prev, dbQuery: e.target.value }))}
            />
          </FormGroup>
        </div>
      )}

      {/* HTTP / WEBHOOK FORM */}
      {(agentType === 'http_webhook' || form.agentId.includes('http') || form.agentId.includes('webhook')) && (
        <div style={{ background: 'var(--surface-1)', padding: 14, borderRadius: 8, border: '1px solid rgba(59,130,246,0.3)', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#3b82f6', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Globe size={15} /> HTTP Webhook Request Configuration
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 10 }}>
            <FormGroup label="Method">
              <select
                className="input"
                value={form.webhookMethod}
                onChange={(e) => setForm(prev => ({ ...prev, webhookMethod: e.target.value }))}
              >
                <option value="POST">POST</option>
                <option value="GET">GET</option>
                <option value="PUT">PUT</option>
                <option value="DELETE">DELETE</option>
                <option value="PATCH">PATCH</option>
              </select>
            </FormGroup>
            <FormGroup label="Target Endpoint URL" required>
              <input
                className="input"
                placeholder="https://api.example.com/v1/webhook"
                value={form.webhookUrl}
                onChange={(e) => setForm(prev => ({ ...prev, webhookUrl: e.target.value }))}
              />
            </FormGroup>
          </div>

          <FormGroup label="Request Headers (JSON)">
            <input
              className="input"
              placeholder='{"Authorization": "Bearer ...", "Content-Type": "application/json"}'
              value={form.webhookHeaders}
              onChange={(e) => setForm(prev => ({ ...prev, webhookHeaders: e.target.value }))}
            />
          </FormGroup>

          <FormGroup label="Request Payload / Body (JSON)">
            <textarea
              className="input"
              rows={3}
              placeholder='{"event": "pipeline_complete", "status": "success"}'
              value={form.webhookBody}
              onChange={(e) => setForm(prev => ({ ...prev, webhookBody: e.target.value }))}
            />
          </FormGroup>
        </div>
      )}

      {/* 4. Collapsible Advanced Configuration */}
      <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: 12 }}>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          style={{ padding: '4px 6px', fontSize: 12, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 6 }}
          onClick={() => setForm(prev => ({ ...prev, showAdvanced: !prev.showAdvanced }))}
        >
          {form.showAdvanced ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          <span>Advanced Pipeline Configuration (Priority, Output Key, System Prompt)</span>
        </button>

        {form.showAdvanced && (
          <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 12, paddingLeft: 8 }}>
            <FormGroup label="Execution Priority" hint="Higher priority tasks execute first among ready nodes (1 = Normal, 5 = High, 10 = Urgent)">
              <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                <input
                  className="input"
                  type="number"
                  min={0}
                  max={100}
                  value={form.priority}
                  onChange={(e) => setForm(prev => ({ ...prev, priority: parseInt(e.target.value) || 0 }))}
                  style={{ width: 100 }}
                />
                <span style={{ fontSize: 12, color: '#f59e0b', fontWeight: 600 }}>
                  {form.priority >= 8 ? '🔥 Urgent Priority' : form.priority >= 4 ? '⚡ High Priority' : form.priority > 0 ? '✓ Standard Priority' : 'Default (0)'}
                </span>
              </div>
            </FormGroup>

            <FormGroup label="Context Output Key (Optional)" hint="Variable name stored in pipeline context for downstream agents">
              <input
                className="input"
                placeholder="e.g. data_summary, research_findings, generated_report"
                value={form.outputKey}
                onChange={(e) => setForm(prev => ({ ...prev, outputKey: e.target.value }))}
              />
            </FormGroup>

            <FormGroup label="General Instructions / Prompt Override" hint="Extra directive passed directly to the agent runtime">
              <textarea
                className="input"
                rows={2}
                placeholder="Optional custom instructions..."
                value={form.instructions}
                onChange={(e) => setForm(prev => ({ ...prev, instructions: e.target.value }))}
              />
            </FormGroup>
          </div>
        )}
      </div>
    </div>
  )
}

function AddNodeModal({ open, onClose, workflowId, agents, onAdded, onRefreshAgents, isLoadingAgents }: {
  open: boolean; onClose: () => void; workflowId: string; agents: Agent[]; onAdded: () => void; onRefreshAgents?: () => void; isLoadingAgents?: boolean
}) {
  const [form, setForm] = useState<NodeFormState>({
    name: '',
    agentId: '',
    priority: 1,
    outputKey: '',
    instructions: '',
    showAdvanced: false,
    dataQuery: 'Analyze dataset, calculate descriptive statistics, and check for anomalies',
    dataNumbers: '120, 160, 210, 290, 380, 490',
    dataFileId: '',
    dataFileName: '',
    docQuery: 'What are the key findings and compliance requirements?',
    docFileId: '',
    docFileName: '',
    docText: '',
    reportTitle: 'Executive Multi-Agent Operational Briefing',
    reportInstructions: 'Synthesize upstream pipeline outputs into an executive briefing.',
    reportFormat: 'pdf',
    emailTo: localStorage.getItem('last_recipient') || 'mehulpankajmaha@gmail.com',
    emailSubject: 'Automated Multi-Agent Pipeline Report',
    emailBody: '',
    secContent: 'SELECT * FROM users WHERE id = ' + "'1' OR '1'='1';",
    secScanType: 'code_vulnerability',
    secFileId: '',
    secFileName: '',
    dbQuery: 'SELECT status, count(*) FROM jobs GROUP BY status',
    webhookUrl: '',
    webhookMethod: 'POST',
    webhookHeaders: '',
    webhookBody: '',
  })

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const allAvailableAgents = React.useMemo(() => {
    const list = [...(agents || [])]
    BUILTIN_PLATFORM_AGENTS.forEach((builtin) => {
      const alreadyPresent = list.some(
        (a) => a.agent_type === builtin.agent_type || a.name?.toLowerCase().includes(builtin.agent_type)
      )
      if (!alreadyPresent) {
        list.push(builtin)
      }
    })
    return list
  }, [agents])

  useEffect(() => {
    if (open && agents.length === 0 && onRefreshAgents) {
      onRefreshAgents()
    }
  }, [open, agents.length, onRefreshAgents])

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const selectedAgent = allAvailableAgents.find(a => String(a.id || (a as any).public_id) === form.agentId || a.agent_type === form.agentId)
      const agentType = selectedAgent?.agent_type || ''

      const inputMapping: Record<string, unknown> = {}
      const nodeConfig: Record<string, unknown> = {}
      let synthInstructions = form.instructions.trim()

      if (agentType === 'data_analysis') {
        const q = form.dataQuery.trim() || 'Analyze dataset metrics.'
        inputMapping.query = q
        nodeConfig.query = q
        nodeConfig.question = q
        if (form.dataFileId) {
          inputMapping.file_id = form.dataFileId
          nodeConfig.file_id = form.dataFileId
          nodeConfig.filename = form.dataFileName
        } else if (form.dataNumbers.trim()) {
          const parsed = form.dataNumbers.split(',').map(s => s.trim()).filter(Boolean)
          inputMapping.numbers = parsed
          inputMapping.values = parsed
          nodeConfig.numbers = parsed
          nodeConfig.values = parsed
        }
        if (!synthInstructions) synthInstructions = q
      } else if (agentType === 'document_research') {
        const q = form.docQuery.trim() || 'Extract grounded document answers.'
        inputMapping.query = q
        nodeConfig.query = q
        nodeConfig.question = q
        if (form.docFileId) {
          inputMapping.file_id = form.docFileId
          nodeConfig.file_id = form.docFileId
          nodeConfig.filename = form.docFileName
        } else if (form.docText.trim()) {
          inputMapping.text = form.docText.trim()
          nodeConfig.text = form.docText.trim()
        }
        if (!synthInstructions) synthInstructions = q
      } else if (agentType === 'report_generation') {
        const t = form.reportTitle.trim() || 'Executive Briefing'
        inputMapping.title = t
        inputMapping.format = form.reportFormat || 'pdf'
        inputMapping.instructions = form.reportInstructions.trim()
        nodeConfig.title = t
        nodeConfig.topic = t
        nodeConfig.format = form.reportFormat || 'pdf'
        nodeConfig.instructions = form.reportInstructions.trim()
        if (!synthInstructions) synthInstructions = `Generate executive report titled "${t}".`
      } else if (agentType === 'email') {
        const targetEmail = form.emailTo.trim() || 'mehulpankajmaha@gmail.com'
        const subj = form.emailSubject.trim()
        const body = form.emailBody.trim()
        inputMapping.to = [targetEmail]
        inputMapping.recipient = targetEmail
        inputMapping.mode = 'send'
        nodeConfig.to = [targetEmail]
        nodeConfig.recipient = targetEmail
        nodeConfig.mode = 'send'
        if (subj) {
          inputMapping.subject = subj
          nodeConfig.subject = subj
        }
        if (body) {
          inputMapping.body = body
          nodeConfig.body = body
        }
        if (!synthInstructions) synthInstructions = `Send email to ${targetEmail}${subj ? ` with subject "${subj}"` : ''}.`
      } else if (agentType === 'security_analysis') {
        const content = form.secContent.trim()
        inputMapping.content = content
        inputMapping.source_code = content
        inputMapping.scan_type = form.secScanType || 'static'
        inputMapping.target = form.secFileName || 'Workflow Source Code'
        nodeConfig.content = content
        nodeConfig.source_code = content
        nodeConfig.scan_type = form.secScanType || 'static'
        nodeConfig.target = form.secFileName || 'Workflow Source Code'
        if (form.secFileId) {
          inputMapping.file_id = form.secFileId
          nodeConfig.file_id = form.secFileId
        }
        if (!synthInstructions) synthInstructions = `Perform ${form.secScanType || 'static'} security analysis.`
      } else if (agentType === 'database_bi') {
        const q = form.dbQuery.trim()
        inputMapping.query = q
        nodeConfig.query = q
        if (!synthInstructions) synthInstructions = `Execute database query: ${q}`
      } else if (agentType === 'http_webhook') {
        inputMapping.url = form.webhookUrl.trim()
        inputMapping.method = form.webhookMethod
        nodeConfig.url = form.webhookUrl.trim()
        nodeConfig.method = form.webhookMethod
        if (form.webhookHeaders.trim()) {
          try {
            const h = JSON.parse(form.webhookHeaders)
            inputMapping.headers = h
            nodeConfig.headers = h
          } catch {
            inputMapping.headers = form.webhookHeaders
            nodeConfig.headers = form.webhookHeaders
          }
        }
        if (form.webhookBody.trim()) {
          try {
            const b = JSON.parse(form.webhookBody)
            inputMapping.body = b
            nodeConfig.body = b
          } catch {
            inputMapping.body = form.webhookBody
            nodeConfig.body = form.webhookBody
          }
        }
        if (!synthInstructions) synthInstructions = `${form.webhookMethod} request to ${form.webhookUrl}`
      }

      await workflowsApi.addNode(workflowId, {
        name: form.name.trim() || (selectedAgent ? selectedAgent.display_name || selectedAgent.name : 'Pipeline Step'),
        agent_id: form.agentId || (selectedAgent ? selectedAgent.id || (selectedAgent as any).public_id || selectedAgent.agent_type : undefined),
        instructions: synthInstructions || 'Execute assigned workflow task',
        priority: Number(form.priority),
        output_key: form.outputKey.trim() || undefined,
        configuration: Object.keys(nodeConfig).length > 0 ? nodeConfig : undefined,
        input_mapping: Object.keys(inputMapping).length > 0 ? inputMapping : undefined,
      })

      onAdded()
      onClose()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add Workflow Node"
      maxWidth={640}
      footer={
        <>
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleAdd as unknown as React.MouseEventHandler} disabled={loading || !form.name.trim() || !form.agentId}>
            {loading ? <div className="spinner" style={{ width: 14, height: 14 }} /> : null}
            Add Step to Pipeline
          </button>
        </>
      }
    >
      <form onSubmit={handleAdd}>
        {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}
        <AgentSpecificConfigForm
          form={form}
          setForm={setForm}
          allAvailableAgents={allAvailableAgents}
          isLoadingAgents={isLoadingAgents}
          onRefreshAgents={onRefreshAgents}
        />
      </form>
    </Modal>
  )
}

// ─── Edit Node Modal ──────────────────────────────────────────────────────────

function EditNodeModal({ open, onClose, workflowId, node, agents, onUpdated, onRefreshAgents, isLoadingAgents }: {
  open: boolean; onClose: () => void; workflowId: string; node: WorkflowNode | null; agents: Agent[]; onUpdated: () => void; onRefreshAgents?: () => void; isLoadingAgents?: boolean
}) {
  const [form, setForm] = useState<NodeFormState>({
    name: '',
    agentId: '',
    priority: 1,
    outputKey: '',
    instructions: '',
    showAdvanced: false,
    dataQuery: 'Analyze dataset, calculate descriptive statistics, and check for anomalies',
    dataNumbers: '',
    dataFileId: '',
    dataFileName: '',
    docQuery: '',
    docFileId: '',
    docFileName: '',
    docText: '',
    reportTitle: '',
    reportInstructions: '',
    reportFormat: 'pdf',
    emailTo: '',
    emailSubject: '',
    emailBody: '',
    secContent: '',
    secScanType: 'code_vulnerability',
    secFileId: '',
    secFileName: '',
    dbQuery: '',
    webhookUrl: '',
    webhookMethod: 'POST',
    webhookHeaders: '',
    webhookBody: '',
  })

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const allAvailableAgents = React.useMemo(() => {
    const list = [...(agents || [])]
    BUILTIN_PLATFORM_AGENTS.forEach((builtin) => {
      const alreadyPresent = list.some(
        (a) => a.agent_type === builtin.agent_type || a.name?.toLowerCase().includes(builtin.agent_type)
      )
      if (!alreadyPresent) {
        list.push(builtin)
      }
    })
    return list
  }, [agents])

  useEffect(() => {
    if (node) {
      const im = { ...(node.configuration || {}), ...(node.input_mapping || {}) } as Record<string, any>
      setForm({
        name: node.name || '',
        agentId: node.agent_id || '',
        priority: node.priority ?? 1,
        outputKey: node.output_key || '',
        instructions: node.instructions || '',
        showAdvanced: false,

        // Data Analysis
        dataQuery: im.query || im.question || node.instructions || '',
        dataNumbers: Array.isArray(im.numbers) ? im.numbers.join(', ') : (im.numbers || ''),
        dataFileId: im.file_id || '',
        dataFileName: im.file_name || im.filename || (im.file_id ? `File #${im.file_id}` : ''),

        // Document Research
        docQuery: im.query || im.question || node.instructions || '',
        docFileId: im.file_id || '',
        docFileName: im.file_name || im.filename || (im.file_id ? `File #${im.file_id}` : ''),
        docText: im.text || im.content || '',

        // Report Generation
        reportTitle: im.title || im.topic || '',
        reportInstructions: im.instructions || '',
        reportFormat: im.format || 'pdf',

        // Email
        emailTo: Array.isArray(im.to) ? im.to[0] : (im.to || im.recipient || ''),
        emailSubject: im.subject || '',
        emailBody: im.body || im.message || '',

        // Security
        secContent: im.content || im.source_code || im.code || '',
        secScanType: im.scan_type || im.scanType || 'code_vulnerability',
        secFileId: im.file_id || '',
        secFileName: im.file_name || im.filename || (im.file_id ? `File #${im.file_id}` : ''),

        // Database
        dbQuery: im.query || '',

        // Webhook
        webhookUrl: im.url || '',
        webhookMethod: im.method || 'POST',
        webhookHeaders: typeof im.headers === 'object' ? JSON.stringify(im.headers) : (im.headers || ''),
        webhookBody: typeof im.body === 'object' ? JSON.stringify(im.body) : (im.body || ''),
      })
    }
  }, [node])

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!node) return
    setError('')
    setLoading(true)
    try {
      const selectedAgent = allAvailableAgents.find(a => String(a.id || (a as any).public_id) === form.agentId || a.agent_type === form.agentId)
      const agentType = selectedAgent?.agent_type || ''

      const inputMapping: Record<string, unknown> = { ...(node.input_mapping || {}) }
      const nodeConfig: Record<string, unknown> = { ...(node.configuration || {}) }
      let synthInstructions = form.instructions.trim()

      if (agentType === 'data_analysis') {
        const q = form.dataQuery.trim() || 'Analyze dataset metrics.'
        inputMapping.query = q
        nodeConfig.query = q
        nodeConfig.question = q
        if (form.dataFileId) {
          inputMapping.file_id = form.dataFileId
          nodeConfig.file_id = form.dataFileId
          nodeConfig.filename = form.dataFileName
        } else if (form.dataNumbers.trim()) {
          const parsed = form.dataNumbers.split(',').map(s => s.trim()).filter(Boolean)
          inputMapping.numbers = parsed
          inputMapping.values = parsed
          nodeConfig.numbers = parsed
          nodeConfig.values = parsed
        }
        if (!synthInstructions) synthInstructions = q
      } else if (agentType === 'document_research') {
        const q = form.docQuery.trim() || 'Extract grounded document answers.'
        inputMapping.query = q
        nodeConfig.query = q
        nodeConfig.question = q
        if (form.docFileId) {
          inputMapping.file_id = form.docFileId
          nodeConfig.file_id = form.docFileId
          nodeConfig.filename = form.docFileName
        } else if (form.docText.trim()) {
          inputMapping.text = form.docText.trim()
          nodeConfig.text = form.docText.trim()
        }
        if (!synthInstructions) synthInstructions = q
      } else if (agentType === 'report_generation') {
        const t = form.reportTitle.trim() || 'Executive Briefing'
        inputMapping.title = t
        inputMapping.format = form.reportFormat || 'pdf'
        inputMapping.instructions = form.reportInstructions.trim()
        nodeConfig.title = t
        nodeConfig.topic = t
        nodeConfig.format = form.reportFormat || 'pdf'
        nodeConfig.instructions = form.reportInstructions.trim()
        if (!synthInstructions) synthInstructions = `Generate executive report titled "${t}".`
      } else if (agentType === 'email') {
        const targetEmail = form.emailTo.trim() || 'mehulpankajmaha@gmail.com'
        const subj = form.emailSubject.trim()
        const body = form.emailBody.trim()
        inputMapping.to = [targetEmail]
        inputMapping.recipient = targetEmail
        inputMapping.mode = 'send'
        nodeConfig.to = [targetEmail]
        nodeConfig.recipient = targetEmail
        nodeConfig.mode = 'send'
        if (subj) {
          inputMapping.subject = subj
          nodeConfig.subject = subj
        } else {
          delete (inputMapping as any).subject
          delete (nodeConfig as any).subject
        }
        if (body) {
          inputMapping.body = body
          nodeConfig.body = body
        } else {
          delete (inputMapping as any).body
          delete (nodeConfig as any).body
        }
        if (!synthInstructions) synthInstructions = `Send email to ${targetEmail}${subj ? ` with subject "${subj}"` : ''}.`
      } else if (agentType === 'security_analysis') {
        const content = form.secContent.trim()
        inputMapping.content = content
        inputMapping.source_code = content
        inputMapping.scan_type = form.secScanType || 'static'
        inputMapping.target = form.secFileName || 'Workflow Source Code'
        nodeConfig.content = content
        nodeConfig.source_code = content
        nodeConfig.scan_type = form.secScanType || 'static'
        nodeConfig.target = form.secFileName || 'Workflow Source Code'
        if (form.secFileId) {
          inputMapping.file_id = form.secFileId
          nodeConfig.file_id = form.secFileId
        }
        if (!synthInstructions) synthInstructions = `Perform ${form.secScanType || 'static'} security analysis.`
      } else if (agentType === 'database_bi') {
        const q = form.dbQuery.trim()
        inputMapping.query = q
        nodeConfig.query = q
        if (!synthInstructions) synthInstructions = `Execute database query: ${q}`
      } else if (agentType === 'http_webhook') {
        inputMapping.url = form.webhookUrl.trim()
        inputMapping.method = form.webhookMethod
        nodeConfig.url = form.webhookUrl.trim()
        nodeConfig.method = form.webhookMethod
        if (form.webhookHeaders.trim()) {
          try {
            const h = JSON.parse(form.webhookHeaders)
            inputMapping.headers = h
            nodeConfig.headers = h
          } catch {
            inputMapping.headers = form.webhookHeaders
            nodeConfig.headers = form.webhookHeaders
          }
        }
        if (form.webhookBody.trim()) {
          try {
            const b = JSON.parse(form.webhookBody)
            inputMapping.body = b
            nodeConfig.body = b
          } catch {
            inputMapping.body = form.webhookBody
            nodeConfig.body = form.webhookBody
          }
        }
        if (!synthInstructions) synthInstructions = `${form.webhookMethod} request to ${form.webhookUrl}`
      }

      await workflowsApi.updateNode(workflowId, node.public_id, {
        name: form.name,
        agent_id: form.agentId || undefined,
        instructions: synthInstructions || form.instructions,
        priority: Number(form.priority),
        output_key: form.outputKey.trim() || undefined,
        configuration: Object.keys(nodeConfig).length > 0 ? nodeConfig : undefined,
        input_mapping: Object.keys(inputMapping).length > 0 ? inputMapping : undefined,
      })

      onUpdated()
      onClose()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Configure Node: ${node?.name || ''}`}
      maxWidth={640}
      footer={
        <>
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleUpdate as unknown as React.MouseEventHandler} disabled={loading || !form.name.trim() || !form.agentId}>
            {loading ? <div className="spinner" style={{ width: 14, height: 14 }} /> : null}
            Save Changes
          </button>
        </>
      }
    >
      <form onSubmit={handleUpdate}>
        {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}
        <AgentSpecificConfigForm
          form={form}
          setForm={setForm}
          allAvailableAgents={allAvailableAgents}
          isLoadingAgents={isLoadingAgents}
          onRefreshAgents={onRefreshAgents}
        />
      </form>
    </Modal>
  )
}

// ─── Add Dependency Modal ─────────────────────────────────────────────────────

function AddDependencyModal({ open, onClose, workflowId, nodes, onAdded }: {
  open: boolean; onClose: () => void; workflowId: string; nodes: WorkflowNode[]; onAdded: () => void
}) {
  const [srcId, setSrcId] = useState('')
  const [tgtId, setTgtId] = useState('')
  const [depType, setDepType] = useState('on_success')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    if (srcId === tgtId) { setError('Source and target must be different nodes'); return }
    setError('')
    setLoading(true)
    try {
      await workflowsApi.addDependency(workflowId, srcId, tgtId, depType)
      setSrcId(''); setTgtId(''); setDepType('on_success')
      onAdded()
      onClose()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const DEP_TYPES = [
    { value: 'on_success', label: '✅ On Success', color: '#10b981', desc: 'Target runs only if source SUCCEEDS' },
    { value: 'on_failure', label: '❌ On Failure', color: '#f43f5e', desc: 'Target runs only if source FAILS' },
    { value: 'always', label: '🔄 Always', color: '#818cf8', desc: 'Target runs regardless of source result' },
  ]
  const selectedType = DEP_TYPES.find(d => d.value === depType)

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add Dependency Edge"
      footer={
        <>
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleAdd as unknown as React.MouseEventHandler} disabled={loading}>
            {loading ? <div className="spinner" style={{ width: 14, height: 14 }} /> : null}
            Add Edge
          </button>
        </>
      }
    >
      <form onSubmit={handleAdd}>
        {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

        <div className="alert alert-info" style={{ marginBottom: 16 }}>
          <Link2 size={13} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>Draw an edge from <strong>Source → Target</strong>. The target will execute based on the edge type you choose below.</span>
        </div>

        <FormGroup label="Source Node (runs first)" required>
          <select className="input" value={srcId} onChange={(e) => setSrcId(e.target.value)} required>
            <option value="">Select source node...</option>
            {nodes.map((n) => <option key={n.public_id} value={n.public_id}>{n.name}</option>)}
          </select>
        </FormGroup>

        <FormGroup label="Target Node (depends on source)" required>
          <select className="input" value={tgtId} onChange={(e) => setTgtId(e.target.value)} required>
            <option value="">Select target node...</option>
            {nodes.filter(n => n.public_id !== srcId).map((n) => <option key={n.public_id} value={n.public_id}>{n.name}</option>)}
          </select>
        </FormGroup>

        <FormGroup label="Edge Type (Execution Condition)" required>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {DEP_TYPES.map((dt) => (
              <label
                key={dt.value}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: '10px 14px',
                  borderRadius: 8,
                  border: `1.5px solid ${depType === dt.value ? dt.color : 'var(--border-subtle)'}`,
                  background: depType === dt.value ? `${dt.color}15` : 'var(--surface-1)',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <input
                  type="radio"
                  name="depType"
                  value={dt.value}
                  checked={depType === dt.value}
                  onChange={() => setDepType(dt.value)}
                  style={{ accentColor: dt.color }}
                />
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13, color: depType === dt.value ? dt.color : 'var(--text-primary)' }}>
                    {dt.label}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{dt.desc}</div>
                </div>
              </label>
            ))}
          </div>
          {srcId && tgtId && (
            <div style={{
              marginTop: 10, padding: '8px 12px', borderRadius: 6,
              background: `${selectedType?.color}15`,
              border: `1px solid ${selectedType?.color}40`,
              fontSize: 12, color: selectedType?.color, fontWeight: 500
            }}>
              📌 Edge: <strong>{nodes.find(n => n.public_id === srcId)?.name || srcId}</strong> →{' '}
              <strong>{nodes.find(n => n.public_id === tgtId)?.name || tgtId}</strong>
              {' '} ({selectedType?.label})
            </div>
          )}
        </FormGroup>
      </form>
    </Modal>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function WorkflowDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const { data: workflow, isLoading, error, refetch } = useAsync(
    () => workflowsApi.get(id!), [id], true
  )
  const { data: agents, isLoading: agentsLoading, refetch: refetchAgents } = useAsync(() => agentsApi.list(), [], true)

  const [showAddNode, setShowAddNode] = useState(false)
  const [showAddDep, setShowAddDep] = useState(false)
  const [editingNode, setEditingNode] = useState<WorkflowNode | null>(null)
  const [showExecModal, setShowExecModal] = useState(false)
  const [showScheduleModal, setShowScheduleModal] = useState(false)
  const [scheduleType, setScheduleType] = useState('cron')
  const [cronExpression, setCronExpression] = useState('')
  const [intervalMinutes, setIntervalMinutes] = useState(60)
  const [providerMode, setProviderMode] = useState<'smtp' | 'resend'>('resend')
  const [execRecipient, setExecRecipient] = useState(() => localStorage.getItem('last_recipient') || 'mehulpankajmaha@gmail.com')
  const [execSubject, setExecSubject] = useState('')
  const [execMessage, setExecMessage] = useState('')
  const [execSenderEmail, setExecSenderEmail] = useState(() => localStorage.getItem('smtp_user') || '')
  const [execAppPassword, setExecAppPassword] = useState(() => localStorage.getItem('smtp_password') || '')
  const [execResendKey, setExecResendKey] = useState(() => localStorage.getItem('resend_api_key') || '')
  const [execTab, setExecTab] = useState<'pipeline' | 'email' | 'custom'>('pipeline')

  // Data Analysis execution inputs
  const [execDataNumbers, setExecDataNumbers] = useState('120, 160, 210, 290, 380, 490')
  const [execDataQuery, setExecDataQuery] = useState('Analyze revenue trends, calculate descriptive statistics, and check for anomalies')

  // Report Generation execution inputs
  const [execReportTitle, setExecReportTitle] = useState('Executive Multi-Agent Performance Briefing')
  const [execReportFormat, setExecReportFormat] = useState('pdf')

  const [customJsonPayload, setCustomJsonPayload] = useState('{\n  "data": [120, 160, 210, 290, 380, 490],\n  "columns": ["revenue_k"],\n  "query": "Analyze revenue trends and detect outliers"\n}')
  const [activating, setActivating] = useState(false)
  const [executing, setExecuting] = useState(false)
  const [scheduling, setScheduling] = useState(false)
  const [actionError, setActionError] = useState('')
  const [validating, setValidating] = useState(false)
  const [validation, setValidation] = useState<{ is_valid: boolean; valid?: boolean; errors: string[] } | null>(null)

  const handleActivate = async () => {
    setActivating(true); setActionError('')
    try { await workflowsApi.activate(id!); refetch() }
    catch (e) { setActionError((e as Error).message) }
    finally { setActivating(false) }
  }

  const handleExecute = async () => {
    setExecuting(true)
    setActionError('')
    try {
      if (workflow && workflow.status !== 'active') {
        await workflowsApi.activate(id!)
        refetch()
      }
      let inputData: Record<string, unknown> = {}

      if (execTab === 'custom') {
        try {
          inputData = JSON.parse(customJsonPayload)
        } catch {
          setActionError('Invalid JSON format in custom payload.')
          setExecuting(false)
          return
        }
      } else {
        // Pass-through email provider credentials if configured
        if (providerMode === 'smtp') {
          const pass = execAppPassword.replace(/\s+/g, '').trim()
          if (pass && execSenderEmail.trim()) {
            inputData.email_provider = 'smtp'
            inputData.smtp_user = execSenderEmail.trim()
            inputData.smtp_password = pass
            inputData.email_from = execSenderEmail.trim()
            localStorage.setItem('smtp_user', execSenderEmail.trim())
            localStorage.setItem('smtp_password', execAppPassword.trim())
            localStorage.setItem('email_provider_mode', 'smtp')
          } else {
            // Auto fallback to active Resend provider
            inputData.email_provider = 'resend'
            const activeResendKey = execResendKey.trim() || localStorage.getItem('resend_api_key') || ''
            if (activeResendKey) {
              inputData.resend_api_key = activeResendKey
            }
          }
        } else {
          const activeResendKey = execResendKey.trim() || localStorage.getItem('resend_api_key') || ''
          inputData.email_provider = 'resend'
          if (activeResendKey) {
            inputData.resend_api_key = activeResendKey
            localStorage.setItem('resend_api_key', activeResendKey)
          }
          localStorage.setItem('email_provider_mode', 'resend')
        }
      }

      const res = await workflowsApi.execute(id!, inputData)
      setShowExecModal(false)
      const targetId = res.public_id || res.job_id
      navigate(`/executions${targetId ? `?job_id=${targetId}` : ''}`)
    } catch (e) {
      setActionError((e as Error).message)
    } finally {
      setExecuting(false)
    }
  }

  const handleSchedule = async (e: React.FormEvent) => {
    e.preventDefault()
    setScheduling(true)
    setActionError('')
    try {
      if (workflow && workflow.status !== 'active') {
        await workflowsApi.activate(id!)
        refetch()
      }
      const payload: any = { schedule_type: scheduleType }
      if (scheduleType === 'cron') {
        payload.cron_expression = cronExpression
      } else {
        payload.interval_seconds = intervalMinutes * 60
      }
      await schedulesApi.create(id!, payload)
      setShowScheduleModal(false)
      setCronExpression('')
      setIntervalMinutes(60)
    } catch (e) {
      setActionError((e as Error).message)
    } finally {
      setScheduling(false)
    }
  }

  const [deletingWorkflow, setDeletingWorkflow] = useState(false)

  const handleValidate = async () => {
    setValidating(true)
    try { const v = await workflowsApi.validate(id!); setValidation(v) }
    catch (e) { setActionError((e as Error).message); setValidation(null) }
    finally { setValidating(false) }
  }

  const handleDeleteNode = async (nodeId: string) => {
    if (!confirm('Delete this node?')) return
    setActionError('')
    try { await workflowsApi.deleteNode(id!, nodeId); refetch() }
    catch (e) { setActionError((e as Error).message) }
  }

  const handleDeleteEdge = async (depId: string) => {
    if (!confirm('Remove this dependency edge?')) return
    setActionError('')
    try { await workflowsApi.deleteDependency(id!, depId); refetch() }
    catch (e) { setActionError((e as Error).message) }
  }

  const handleDeleteWorkflow = async () => {
    if (!confirm(`Are you sure you want to permanently delete workflow "${workflow?.name || 'this workflow'}"? This action cannot be undone.`)) return
    setDeletingWorkflow(true)
    setActionError('')
    try {
      await workflowsApi.delete(id!)
      navigate('/workflows')
    } catch (e) {
      setActionError((e as Error).message)
      setDeletingWorkflow(false)
    }
  }

  if (isLoading) return <div className="page-container"><div className="spinner" style={{ margin: '60px auto' }} /></div>
  if (error) return <div className="page-container"><ErrorState message={error} onRetry={refetch} /></div>
  if (!workflow) return null

  const nodes = workflow.nodes || []
  const deps = workflow.dependencies || []
  const isValid = validation ? (validation.is_valid || validation.valid || false) : false

  return (
    <div className="page-container animate-fadeIn">
      {/* Header */}
      <div>
        <button className="btn btn-ghost" style={{ marginBottom: 12, fontSize: 12 }} onClick={() => navigate('/workflows')}>
          <ArrowLeft size={13} /> Back to Workflows
        </button>
        <div className="page-header">
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
            <div style={{ width: 44, height: 44, borderRadius: 11, background: 'rgba(99,102,241,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <GitBranch size={20} style={{ color: '#818cf8' }} />
            </div>
            <div>
              <h1 className="page-title">{workflow.name}</h1>
              <div style={{ display: 'flex', gap: 8, marginTop: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                <StatusBadge status={workflow.status} />
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>v{workflow.version} · {nodes.length} nodes · {deps.length} edges</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'var(--surface-1)', padding: '2px 8px', borderRadius: 6, border: '1px solid var(--border-subtle)', fontSize: 12 }}>
                  <span style={{ color: 'var(--text-muted)' }}>Workflow Priority:</span>
                  <select
                    value={workflow.priority ?? 1}
                    onChange={async (e) => {
                      const newP = parseInt(e.target.value)
                      try {
                        await workflowsApi.update(id!, { priority: newP })
                        refetch()
                      } catch (err) {
                        setActionError((err as Error).message)
                      }
                    }}
                    style={{ background: 'transparent', border: 'none', color: '#f59e0b', fontWeight: 700, cursor: 'pointer', outline: 'none' }}
                  >
                    <option value={1} style={{ background: '#1e2230', color: '#f1f5f9' }}>P1 (Low)</option>
                    <option value={2} style={{ background: '#1e2230', color: '#f1f5f9' }}>P2 (Normal)</option>
                    <option value={3} style={{ background: '#1e2230', color: '#f1f5f9' }}>P3 (Medium)</option>
                    <option value={5} style={{ background: '#1e2230', color: '#f1f5f9' }}>P5 (High)</option>
                    <option value={10} style={{ background: '#1e2230', color: '#f1f5f9' }}>P10 (Urgent)</option>
                  </select>
                </div>
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button className="btn btn-secondary" style={{ fontSize: 12 }} onClick={handleValidate} disabled={validating}>
              {validating ? <div className="spinner" style={{ width: 13, height: 13 }} /> : <CheckCircle size={13} />}
              Validate
            </button>
            {workflow.status !== 'active' && (
              <button className="btn btn-secondary" style={{ fontSize: 12 }} onClick={handleActivate} disabled={activating}>
                {activating ? <div className="spinner" style={{ width: 13, height: 13 }} /> : <CheckCircle size={13} />}
                Activate
              </button>
            )}
            <button className="btn btn-secondary" style={{ fontSize: 12 }} onClick={() => setShowScheduleModal(true)}>
              <Clock size={13} />
              Schedule
            </button>
            <button
              className="btn btn-secondary"
              style={{ fontSize: 12 }}
              title="Export workflow JSON (Schema 1.0)"
              onClick={async () => {
                try {
                  const exported = await workflowsApi.exportWorkflow(workflow.public_id)
                  const blob = new Blob([JSON.stringify(exported, null, 2)], { type: 'application/json' })
                  const url = URL.createObjectURL(blob)
                  const a = document.createElement('a')
                  a.href = url
                  a.download = `${workflow.name.toLowerCase().replace(/[^a-z0-9]/g, '_')}_v${workflow.version || 1}.json`
                  a.click()
                  URL.revokeObjectURL(url)
                } catch (err) {
                  setActionError((err as Error).message)
                }
              }}
            >
              <Download size={13} />
              Export JSON
            </button>
            <button
              className="btn btn-secondary"
              style={{ fontSize: 12 }}
              title="Duplicate workflow"
              onClick={async () => {
                try {
                  const clone = await workflowsApi.duplicateWorkflow(workflow.public_id)
                  navigate(`/workflows/${clone.public_id}`)
                } catch (err) {
                  setActionError((err as Error).message)
                }
              }}
            >
              <Copy size={13} />
              Duplicate
            </button>
            <button className="btn btn-primary" style={{ fontSize: 12 }} onClick={() => setShowExecModal(true)} disabled={executing}>
              {executing ? <div className="spinner" style={{ width: 13, height: 13 }} /> : <Play size={13} />}
              Execute
            </button>
            <button
              className="btn btn-secondary"
              style={{ fontSize: 12, color: 'var(--accent-rose)', borderColor: 'rgba(244,63,94,0.3)' }}
              onClick={handleDeleteWorkflow}
              disabled={deletingWorkflow}
            >
              {deletingWorkflow ? <div className="spinner" style={{ width: 13, height: 13 }} /> : <Trash2 size={13} />}
              Delete Workflow
            </button>
          </div>
        </div>
      </div>

      {actionError && <div className="alert alert-error">{actionError}</div>}
      {validation && (
        <div className={`alert ${isValid ? 'alert-success' : 'alert-error'}`}>
          {isValid ? <CheckCircle size={14} style={{ flexShrink: 0 }} /> : <AlertTriangle size={14} style={{ flexShrink: 0 }} />}
          <div>
            <div style={{ fontWeight: 500 }}>{isValid ? 'Workflow is valid' : 'Validation failed'}</div>
            {validation.errors?.map((e, i) => <div key={i} style={{ fontSize: 12, marginTop: 2 }}>• {e}</div>)}
          </div>
        </div>
      )}

      {/* DAG Visualization */}
      <div className="card" style={{ padding: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--text-primary)' }}>Workflow DAG</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Visual representation of task nodes and dependencies (click any node to configure priority & options)</div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-secondary" style={{ fontSize: 12 }} onClick={() => setShowAddDep(true)} disabled={nodes.length < 2}>
              <Link2 size={13} />
              Add Edge
            </button>
            <button className="btn btn-primary" style={{ fontSize: 12 }} onClick={() => setShowAddNode(true)}>
              <Plus size={13} />
              Add Node
            </button>
          </div>
        </div>
        <div style={{ background: 'var(--surface-1)', borderRadius: 10, padding: 20, minHeight: 200 }}>
          <DAGCanvas
            workflow={workflow}
            agents={agents || []}
            onDeleteNode={handleDeleteNode}
            onDeleteEdge={handleDeleteEdge}
            onEditNode={setEditingNode}
          />
        </div>
      </div>

      {/* Nodes table */}
      <div className="card" style={{ overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)', fontWeight: 700, fontSize: 13 }}>
          Task Nodes ({nodes.length})
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Agent</th>
              <th>Instructions</th>
              <th>Output Key</th>
              <th>Priority</th>
              <th style={{ textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {nodes.length === 0 ? (
              <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '32px 16px', fontSize: 13 }}>
                No nodes yet — add nodes to build your workflow
              </td></tr>
            ) : nodes.map((node) => (
              <tr key={node.public_id}>
                <td style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 13 }}>{node.name}</td>
                <td>
                  {node.agent_id ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <Bot size={12} style={{ color: '#818cf8' }} />
                      <span style={{ fontSize: 12 }}>{agents?.find(a => a.id === node.agent_id)?.name || node.agent_name || (node.agent_id.length > 8 ? node.agent_id.slice(0, 8) + '…' : node.agent_id)}</span>
                    </div>
                  ) : <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>—</span>}
                </td>
                <td style={{ fontSize: 12, color: 'var(--text-secondary)', maxWidth: 240 }}>
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block' }}>
                    {node.instructions || '—'}
                  </span>
                </td>
                <td style={{ fontSize: 12, color: 'var(--brand-primary)', fontFamily: 'monospace' }}>
                  {node.output_key || <span style={{ color: 'var(--text-muted)' }}>auto</span>}
                </td>
                <td>
                  <select
                    value={node.priority ?? 0}
                    onChange={async (e) => {
                      const newP = parseInt(e.target.value)
                      try {
                        await workflowsApi.updateNode(id!, node.public_id, { priority: newP })
                        refetch()
                      } catch (err) {
                        setActionError((err as Error).message)
                      }
                    }}
                    className="input"
                    style={{ padding: '3px 8px', fontSize: 12, width: 100, height: 28, background: 'var(--surface-base)' }}
                  >
                    <option value={0}>0 (Default)</option>
                    <option value={1}>1 (Low)</option>
                    <option value={2}>2 (Normal)</option>
                    <option value={3}>3 (Medium)</option>
                    <option value={5}>5 (High)</option>
                    <option value={10}>10 (Urgent)</option>
                  </select>
                </td>
                <td style={{ textAlign: 'right' }}>
                  <div style={{ display: 'flex', gap: 4, justifyContent: 'flex-end' }}>
                    <button
                      className="btn btn-ghost"
                      style={{ padding: '4px 6px', color: 'var(--brand-primary)' }}
                      title="Edit node & priority"
                      onClick={() => setEditingNode(node)}
                    >
                      <Edit3 size={13} />
                    </button>
                    <button
                      className="btn btn-ghost"
                      style={{ padding: '4px 6px', color: 'var(--accent-rose)' }}
                      title="Delete node"
                      onClick={() => handleDeleteNode(node.public_id)}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Dependencies table */}
      {deps.length > 0 && (
        <div className="card" style={{ overflow: 'hidden' }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)', fontWeight: 700, fontSize: 13 }}>
            Dependencies / Edges ({deps.length})
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Source Node (Depends On)</th>
                <th>Target Node (Runs After)</th>
                <th>Type</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {deps.map((dep) => {
                const srcNode = nodes.find(n => n.public_id === dep.source_node_id)
                const tgtNode = nodes.find(n => n.public_id === dep.target_node_id)
                return (
                  <tr key={dep.public_id}>
                    <td style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 13 }}>
                      {srcNode?.name || dep.source_node_id}
                    </td>
                    <td style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 13 }}>
                      {tgtNode?.name || dep.target_node_id}
                    </td>
                    <td style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                      {dep.dependency_type || 'default'}
                    </td>
                    <td>
                      <button className="btn btn-ghost" style={{ padding: '4px 6px', color: 'var(--accent-rose)' }} title="Delete dependency edge" onClick={() => handleDeleteEdge(dep.public_id)}>
                        <Trash2 size={13} />
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <AddNodeModal
        open={showAddNode}
        onClose={() => setShowAddNode(false)}
        workflowId={id!}
        agents={agents || []}
        isLoadingAgents={agentsLoading}
        onRefreshAgents={refetchAgents}
        onAdded={refetch}
      />
      <EditNodeModal
        open={!!editingNode}
        onClose={() => setEditingNode(null)}
        workflowId={id!}
        node={editingNode}
        agents={agents || []}
        isLoadingAgents={agentsLoading}
        onRefreshAgents={refetchAgents}
        onUpdated={refetch}
      />
      <AddDependencyModal
        open={showAddDep}
        onClose={() => setShowAddDep(false)}
        workflowId={id!}
        nodes={nodes}
        onAdded={refetch}
      />

      <Modal
        open={showExecModal}
        onClose={() => setShowExecModal(false)}
        title={`Execute Pipeline: ${workflow.name}`}
        maxWidth={720}
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setShowExecModal(false)}>Cancel</button>
            <button className="btn btn-primary" onClick={handleExecute} disabled={executing || (workflow?.nodes?.length || 0) === 0}>
              {executing ? <div className="spinner" style={{ width: 14, height: 14 }} /> : <Play size={14} />}
              Run Pipeline
            </button>
          </>
        }
      >
        <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 14 }}>
          Launch execution for <strong style={{ color: 'var(--text-primary)' }}>{workflow.name}</strong> using saved node configurations.
        </p>

        {/* Tab switch */}
        <div style={{ display: 'flex', gap: 6, background: 'var(--surface-1)', padding: 4, borderRadius: 8, marginBottom: 16 }}>
          <button
            type="button"
            className={`btn ${execTab === 'pipeline' ? 'btn-primary' : 'btn-ghost'}`}
            style={{ flex: 1, fontSize: 11, padding: '7px 8px', justifyContent: 'center' }}
            onClick={() => setExecTab('pipeline')}
          >
            ⚡ Pipeline Nodes & Saved Config ({workflow?.nodes?.length || 0})
          </button>
          <button
            type="button"
            className={`btn ${execTab === 'email' ? 'btn-primary' : 'btn-ghost'}`}
            style={{ flex: 1, fontSize: 11, padding: '7px 8px', justifyContent: 'center' }}
            onClick={() => setExecTab('email')}
          >
            📧 Email Connectors (SMTP / Resend)
          </button>
          <button
            type="button"
            className={`btn ${execTab === 'custom' ? 'btn-primary' : 'btn-ghost'}`}
            style={{ flex: 1, fontSize: 11, padding: '7px 8px', justifyContent: 'center' }}
            onClick={() => setExecTab('custom')}
          >
            🤖 Advanced JSON Overrides
          </button>
        </div>

        {execTab === 'pipeline' ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {(!workflow?.nodes || workflow.nodes.length === 0) ? (
              <div className="alert alert-warning" style={{ fontSize: 12 }}>
                ⚠️ This workflow currently has no nodes. Please add at least one stage before running.
              </div>
            ) : (
              workflow.nodes.map((node, idx) => {
                const im = { ...(node.configuration || {}), ...(node.input_mapping || {}) } as Record<string, any>
                const atype = node.agent_type || (node.agent_name?.toLowerCase().includes('data') ? 'data_analysis' : node.agent_name?.toLowerCase().includes('report') ? 'report_generation' : node.agent_name?.toLowerCase().includes('email') ? 'email' : node.agent_name?.toLowerCase().includes('security') ? 'security_analysis' : node.agent_name?.toLowerCase().includes('doc') ? 'document_research' : node.agent_name?.toLowerCase().includes('database') ? 'database_bi' : 'agent')

                let isMissing = false
                let missingReason = ''
                const details: Array<{ label: string; value: string }> = []

                if (atype === 'data_analysis') {
                  const hasFile = Boolean(im.file_id)
                  const hasNums = Boolean(im.numbers || im.values || im.data || im.rows)
                  if (hasFile) {
                    details.push({ label: 'Dataset File', value: im.filename || im.file_name || `Uploaded File #${im.file_id}` })
                  } else if (hasNums) {
                    details.push({ label: 'Inline Numbers', value: Array.isArray(im.numbers) ? im.numbers.join(', ') : String(im.numbers || im.values) })
                  } else {
                    isMissing = true
                    missingReason = 'Missing CSV/Excel dataset file or inline numbers.'
                  }
                  if (im.query || im.question) {
                    details.push({ label: 'Question', value: im.query || im.question })
                  }
                } else if (atype === 'document_research') {
                  const hasFile = Boolean(im.file_id)
                  const hasText = Boolean(im.text || im.content || im.documents)
                  if (hasFile) {
                    details.push({ label: 'Reference Doc', value: im.filename || im.file_name || `Uploaded Doc #${im.file_id}` })
                  } else if (hasText) {
                    details.push({ label: 'Reference Text', value: String(im.text || im.content).slice(0, 80) + '...' })
                  } else {
                    isMissing = true
                    missingReason = 'Missing reference document or text snippet.'
                  }
                  if (im.query || im.question) {
                    details.push({ label: 'Query', value: im.query || im.question })
                  }
                } else if (atype === 'security_analysis') {
                  const hasContent = Boolean(im.content || im.source_code || im.code || im.file_id)
                  if (hasContent) {
                    details.push({ label: 'Scan Type', value: im.scan_type || 'Static Vulnerability Scan' })
                    details.push({ label: 'Target Code', value: String(im.content || im.source_code || im.code || `File #${im.file_id}`).slice(0, 80) + '...' })
                  } else {
                    isMissing = true
                    missingReason = 'Missing source code or file to audit.'
                  }
                } else if (atype === 'report_generation') {
                  details.push({ label: 'Report Title', value: im.title || im.topic || node.name })
                  details.push({ label: 'Format', value: (im.format || 'PDF').toUpperCase() })
                  if (im.instructions) details.push({ label: 'Focus', value: im.instructions })
                } else if (atype === 'email') {
                  const targetEmail = Array.isArray(im.to) ? im.to[0] : (im.to || im.recipient || '')
                  if (targetEmail) {
                    details.push({ label: 'Recipient (To)', value: targetEmail })
                    details.push({ label: 'Subject', value: im.subject || 'Workflow Notification' })
                  } else {
                    details.push({ label: 'Recipient', value: 'Auto-routed / Developer Verified Inbox' })
                  }
                } else if (atype === 'database_bi') {
                  if (im.query) {
                    details.push({ label: 'SQL Query', value: im.query })
                  } else {
                    isMissing = true
                    missingReason = 'Missing SQL or BI query.'
                  }
                } else if (atype === 'http_webhook') {
                  if (im.url) {
                    details.push({ label: 'Endpoint', value: `[${im.method || 'POST'}] ${im.url}` })
                  } else {
                    isMissing = true
                    missingReason = 'Missing webhook endpoint URL.'
                  }
                }

                return (
                  <div
                    key={node.public_id || idx}
                    style={{
                      background: 'var(--surface-1)',
                      border: `1px solid ${isMissing ? 'rgba(245,158,11,0.5)' : 'var(--border-subtle)'}`,
                      borderRadius: 8,
                      padding: 12,
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 8,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{
                          background: 'rgba(99,102,241,0.15)',
                          color: '#818cf8',
                          width: 22,
                          height: 22,
                          borderRadius: '50%',
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: 11,
                          fontWeight: 700,
                        }}>
                          {idx + 1}
                        </span>
                        <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
                          {getAgentTypeIcon(atype)} {node.name}
                        </span>
                        <span className="badge badge-secondary" style={{ fontSize: 10 }}>
                          {node.agent_name || atype}
                        </span>
                        {(node.priority ?? 0) > 0 && (
                          <span className="badge" style={{ fontSize: 9, background: 'rgba(245,158,11,0.15)', color: '#f59e0b' }}>
                            P{node.priority}
                          </span>
                        )}
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        {isMissing ? (
                          <span className="badge" style={{ background: 'rgba(245,158,11,0.15)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.3)', fontSize: 10.5 }}>
                            ⚠️ WAITING_FOR_INPUT
                          </span>
                        ) : (
                          <span className="badge badge-emerald" style={{ fontSize: 10.5, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                            <Check size={11} /> Ready
                          </span>
                        )}
                        <button
                          type="button"
                          className="btn btn-ghost"
                          style={{ padding: '2px 6px', fontSize: 11, color: '#818cf8' }}
                          onClick={() => {
                            setShowExecModal(false)
                            setEditingNode(node)
                          }}
                        >
                          <Edit3 size={12} /> Edit
                        </button>
                      </div>
                    </div>

                    {isMissing && (
                      <div style={{ fontSize: 11.5, color: '#f59e0b', background: 'rgba(245,158,11,0.08)', padding: '6px 10px', borderRadius: 6 }}>
                        ⚠️ <strong>Action Required:</strong> {missingReason} (Click <strong>Edit</strong> to configure this node).
                      </div>
                    )}

                    {details.length > 0 && (
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 6, fontSize: 11.5, color: 'var(--text-secondary)' }}>
                        {details.map((d, dIdx) => (
                          <div key={dIdx} style={{ background: 'var(--surface-0)', padding: '4px 8px', borderRadius: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            <strong style={{ color: 'var(--text-primary)' }}>{d.label}:</strong> {d.value}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })
            )}
          </div>
        ) : execTab === 'custom' ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
              Pass scoped runtime overrides or dynamic context variables directly to workflow execution:
            </div>
            <FormGroup label="Execution Input Payload (JSON)" hint="Scoped values like { node_id: { query: '...' } } take highest precedence">
              <textarea
                className="input"
                rows={8}
                style={{ fontFamily: 'monospace', fontSize: 12 }}
                value={customJsonPayload}
                onChange={(e) => setCustomJsonPayload(e.target.value)}
              />
            </FormGroup>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 14 }}>
            {/* Provider Selection Tabs */}
            <div style={{ display: 'flex', gap: 6, background: 'var(--surface-1)', padding: 4, borderRadius: 8 }}>
              <button
                type="button"
                className={`btn ${providerMode === 'smtp' ? 'btn-primary' : 'btn-ghost'}`}
                style={{ flex: 1, fontSize: 11, padding: '7px 8px', justifyContent: 'center' }}
                onClick={() => setProviderMode('smtp')}
              >
                🌐 Send to ANY Recipient (Gmail SMTP)
              </button>
              <button
                type="button"
                className={`btn ${providerMode === 'resend' ? 'btn-primary' : 'btn-ghost'}`}
                style={{ flex: 1, fontSize: 11, padding: '7px 8px', justifyContent: 'center' }}
                onClick={() => setProviderMode('resend')}
              >
                ⚡ Resend (Direct to Self)
              </button>
            </div>

            {providerMode === 'smtp' ? (
              <div style={{
                background: 'rgba(59,130,246,0.06)',
                borderRadius: 8,
                padding: 12,
                border: '1px solid rgba(59,130,246,0.25)',
                display: 'flex',
                flexDirection: 'column',
                gap: 10,
              }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span>🌐 Gmail SMTP (Delivers to ANY Email Address in the World)</span>
                  <span className="badge badge-primary" style={{ fontSize: 10 }}>Global Delivery</span>
                </div>
                <div>
                  <label style={{ fontSize: 11, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                    Sender Gmail Address
                  </label>
                  <input
                    type="email"
                    className="input"
                    style={{ fontSize: 12 }}
                    placeholder="e.g. mehulpankajmaha@gmail.com"
                    value={execSenderEmail}
                    onChange={(e) => {
                      setExecSenderEmail(e.target.value)
                      localStorage.setItem('smtp_user', e.target.value)
                    }}
                  />
                </div>
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                    <label style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                      Google App Password (16 letters)
                    </label>
                    <a
                      href="https://myaccount.google.com/apppasswords"
                      target="_blank"
                      rel="noreferrer"
                      style={{ fontSize: 10, color: '#3b82f6', textDecoration: 'underline' }}
                    >
                      Generate App Password ↗
                    </a>
                  </div>
                  <input
                    type="password"
                    className="input"
                    style={{ fontSize: 12 }}
                    placeholder="e.g. abcd efgh ijkl mnop (Spaces are auto-removed)"
                    value={execAppPassword}
                    onChange={(e) => {
                      setExecAppPassword(e.target.value)
                      localStorage.setItem('smtp_password', e.target.value)
                    }}
                  />
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.4 }}>
                  ℹ️ <strong>Sends to ANYONE:</strong> Google gives 500 free emails/day. Open <a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noreferrer" style={{ color: '#3b82f6' }}>Google App Passwords</a> → create password → paste here!
                </div>
              </div>
            ) : (
              <div style={{
                background: 'rgba(16,185,129,0.06)',
                borderRadius: 8,
                padding: 12,
                border: '1px solid rgba(16,185,129,0.2)',
                display: 'flex',
                flexDirection: 'column',
                gap: 10,
              }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span>⚡ Resend API Sandbox</span>
                  <span className="badge badge-emerald" style={{ fontSize: 10 }}>Active</span>
                </div>
                <div>
                  <label style={{ fontSize: 11, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                    Resend API Key
                  </label>
                  <input
                    type="password"
                    className="input"
                    style={{ fontSize: 12 }}
                    placeholder="re_... (Paste your key here)"
                    value={execResendKey}
                    onChange={(e) => {
                      setExecResendKey(e.target.value)
                      localStorage.setItem('resend_api_key', e.target.value)
                    }}
                  />
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  💡 Resend free sandbox sends directly to your registered email <strong>mehulpankajmaha@gmail.com</strong> without passwords. (To send to anyone else, switch to the <strong>Gmail SMTP</strong> tab above).
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>

      <Modal
        open={showScheduleModal}
        onClose={() => setShowScheduleModal(false)}
        title="Schedule Workflow"
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setShowScheduleModal(false)}>Cancel</button>
            <button className="btn btn-primary" onClick={handleSchedule as any} disabled={scheduling || (scheduleType === 'cron' && !cronExpression) || (scheduleType === 'interval' && !intervalMinutes)}>
              {scheduling ? <div className="spinner" style={{ width: 14, height: 14 }} /> : <Clock size={14} />}
              Create Schedule
            </button>
          </>
        }
      >
        <form onSubmit={handleSchedule}>
          <FormGroup label="Schedule Type">
            <select className="input" value={scheduleType} onChange={(e) => setScheduleType(e.target.value)}>
              <option value="cron">Cron</option>
              <option value="interval">Interval</option>
            </select>
          </FormGroup>

          {scheduleType === 'cron' && (
            <>
              <FormGroup label="Cron Expression" hint="e.g. 0 9 * * MON = Every Monday 9 AM">
                <input
                  className="input"
                  placeholder="* * * * *"
                  value={cronExpression}
                  onChange={(e) => setCronExpression(e.target.value)}
                  required
                />
              </FormGroup>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '16px' }}>
                <button type="button" className="btn btn-secondary" style={{ fontSize: 11, padding: '4px 8px' }} onClick={() => setCronExpression('0 * * * *')}>Every hour</button>
                <button type="button" className="btn btn-secondary" style={{ fontSize: 11, padding: '4px 8px' }} onClick={() => setCronExpression('0 9 * * *')}>Every day at 9 AM</button>
                <button type="button" className="btn btn-secondary" style={{ fontSize: 11, padding: '4px 8px' }} onClick={() => setCronExpression('0 9 * * MON')}>Every Monday</button>
                <button type="button" className="btn btn-secondary" style={{ fontSize: 11, padding: '4px 8px' }} onClick={() => setCronExpression('0 0 1 * *')}>Every 1st of month</button>
              </div>
            </>
          )}

          {scheduleType === 'interval' && (
            <FormGroup label="Interval (minutes)" hint="How often to run this workflow">
              <input
                className="input"
                type="number"
                min="1"
                value={intervalMinutes}
                onChange={(e) => setIntervalMinutes(parseInt(e.target.value) || 0)}
                required
              />
            </FormGroup>
          )}
        </form>
      </Modal>
    </div>
  )
}
