import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
  GitBranch, Plus, RefreshCw, Play, Archive,
  Clock, Layers, ArrowRight, MoreHorizontal, CheckCircle, AlertCircle, Eye,
  BarChart3, ShieldAlert, Database, Sparkles, Mail, Code2,
  FileText, Globe, Terminal, Trash2, Bot, Download, Upload, Copy
} from 'lucide-react'
import { workflowsApi, agentsApi, type Workflow } from '../lib/api'
import { useAsync } from '../hooks/useAsync'
import { useNavigate } from 'react-router-dom'
import {
  SectionHeader, StatusBadge, EmptyState, ErrorState,
  Modal, FormGroup, SkeletonRows, PageLoader
} from '../components/ui'

const WORKFLOW_TEMPLATES = [
  {
    id: 'blank',
    name: 'Custom Blank Workflow',
    description: 'Create an empty workflow graph and assemble your own custom agent DAG.',
    agentType: null,
  },
  {
    id: 'data_pipeline',
    name: 'Market Data Analysis & Metrics Pipeline',
    description: 'Pipeline that analyzes revenue datasets, computes statistical metrics, and identifies anomalies.',
    agentType: 'data_analysis',
  },
  {
    id: 'security_audit',
    name: 'Enterprise Security & Compliance Scan',
    description: 'Scans system inputs for prompt injections, leaked credentials, and security compliance violations.',
    agentType: 'security_analysis',
  },
  {
    id: 'email_dispatch',
    name: 'Autonomous Email & Approval Workflow',
    description: 'Sends live emails with Human-in-the-Loop governance approvals via Resend or Gmail SMTP.',
    agentType: 'email',
  },
  {
    id: 'bi_pipeline',
    name: 'SQL & Database Business Intelligence',
    description: 'Executes safe read-only SQL queries to extract KPIs and analytics.',
    agentType: 'database_bi',
  },
  {
    id: 'doc_research',
    name: 'Document Research & Evidence Synthesis',
    description: 'Performs grounded multi-document retrieval with citations and extractive evidence.',
    agentType: 'document_research',
  },
  {
    id: 'report_pipeline',
    name: 'Executive Multi-Agent Report Generation',
    description: 'Compiles professional executive briefing reports across business metrics.',
    agentType: 'report_generation',
  },
  {
    id: 'webhook_dispatch',
    name: 'Webhook & External API Integration',
    description: 'Dispatches signed webhook payloads and handles external REST API integrations.',
    agentType: 'http_webhook',
  },
]

function CreateWorkflowModal({
  open,
  onClose,
  onCreated
}: {
  open: boolean
  onClose: () => void
  onCreated: (wf: Workflow) => void
}) {
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  const [priority, setPriority] = useState<number>(1)
  const [selectedTemplate, setSelectedTemplate] = useState('blank')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSelectTemplate = (tmplId: string) => {
    setSelectedTemplate(tmplId)
    const tmpl = WORKFLOW_TEMPLATES.find((t) => t.id === tmplId)
    if (tmpl && tmpl.id !== 'blank') {
      setName(tmpl.name)
      setDesc(tmpl.description)
    }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const wf = await workflowsApi.create({ name, description: desc, priority: Number(priority) })

      // Auto-attach starter node if a template was picked
      const tmpl = WORKFLOW_TEMPLATES.find((t) => t.id === selectedTemplate)
      if (tmpl && tmpl.agentType) {
        try {
          const agents = await agentsApi.list()
          const matchedAgent = agents.find((a) => a.agent_type === tmpl.agentType)
          if (matchedAgent) {
            await workflowsApi.addNode(wf.public_id, {
              name: `${matchedAgent.name} Task`,
              agent_id: matchedAgent.id,
              instructions: `Execute ${matchedAgent.name} with pipeline inputs.`,
              priority: Number(priority),
            })
            await workflowsApi.activate(wf.public_id)
          }
        } catch {
          // If node add or activate fails, the base workflow was still created
        }
      }

      onCreated(wf)
      setName('')
      setDesc('')
      setPriority(1)
      setSelectedTemplate('blank')
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
      title="Create New Workflow"
      footer={
        <>
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleCreate as unknown as React.MouseEventHandler} disabled={loading}>
            {loading ? <div className="spinner" style={{ width: 14, height: 14 }} /> : null}
            Create Workflow
          </button>
        </>
      }
    >
      <form onSubmit={handleCreate}>
        {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

        {/* Template Selector */}
        <div style={{ marginBottom: 16 }}>
          <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 8 }}>
            Choose a Pipeline Starter Template:
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 8 }}>
            {WORKFLOW_TEMPLATES.map((t) => (
              <div
                key={t.id}
                onClick={() => handleSelectTemplate(t.id)}
                style={{
                  padding: '10px 12px',
                  borderRadius: 8,
                  cursor: 'pointer',
                  border: selectedTemplate === t.id ? '2px solid var(--brand-primary)' : '1px solid var(--border-subtle)',
                  background: selectedTemplate === t.id ? 'rgba(99,102,241,0.08)' : 'var(--surface-1)',
                  transition: 'all 0.15s ease'
                }}
              >
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>{t.name}</div>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>{t.description}</div>
              </div>
            ))}
          </div>
        </div>

        <FormGroup label="Workflow Name" required>
          <input className="input" placeholder="e.g. Sales Data Analysis & Executive Report Pipeline" value={name} onChange={(e) => setName(e.target.value)} required />
        </FormGroup>

        <FormGroup label="Execution Priority" hint="Queue scheduling priority (1 = Normal, 5 = High, 10 = Urgent)">
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <input
              className="input"
              type="number"
              min={1}
              max={100}
              value={priority}
              onChange={(e) => setPriority(parseInt(e.target.value) || 1)}
              style={{ width: 100 }}
            />
            <span style={{ fontSize: 12, color: '#f59e0b', fontWeight: 600 }}>
              {priority >= 8 ? '🔥 Urgent' : priority >= 4 ? '⚡ High' : 'Standard'}
            </span>
          </div>
        </FormGroup>

        <FormGroup label="Description" hint="What does this workflow automate?">
          <textarea className="input" rows={3} placeholder="Analyzes quarterly sales datasets, extracts insights, and compiles an executive report..." value={desc} onChange={(e) => setDesc(e.target.value)} />
        </FormGroup>
      </form>
    </Modal>
  )
}

function ImportWorkflowModal({
  open,
  onClose,
  onImported,
}: {
  open: boolean
  onClose: () => void
  onImported: (wf: Workflow) => void
}) {
  const [jsonText, setJsonText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [warnings, setWarnings] = useState<string[]>([])

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (event) => {
      const content = event.target?.result as string
      setJsonText(content)
    }
    reader.readAsText(file)
  }

  const handleImport = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setWarnings([])
    setLoading(true)
    try {
      let parsed: Record<string, unknown>
      try {
        parsed = JSON.parse(jsonText)
      } catch {
        throw new Error('Invalid JSON format. Please verify the input file or text.')
      }

      if (parsed.schema_version !== '1.0') {
        throw new Error(`Unsupported schema version "${parsed.schema_version}". Expected "1.0".`)
      }

      const res = await workflowsApi.importWorkflow(parsed)
      if (res.warnings && res.warnings.length > 0) {
        setWarnings(res.warnings)
      }
      onImported(res.workflow)
      setJsonText('')
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
      title="Import Workflow (Portable Schema 1.0)"
      maxWidth={600}
      footer={
        <>
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleImport as unknown as React.MouseEventHandler} disabled={loading || !jsonText.trim()}>
            {loading ? <div className="spinner" style={{ width: 14, height: 14 }} /> : <Upload size={14} />}
            Import Workflow
          </button>
        </>
      }
    >
      <form onSubmit={handleImport}>
        {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}
        {warnings.length > 0 && (
          <div className="alert alert-warning" style={{ marginBottom: 16, display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div style={{ fontWeight: 700 }}>⚠️ Integration Advisories:</div>
            {warnings.map((w, i) => (
              <div key={i}>• {w}</div>
            ))}
          </div>
        )}

        <div style={{ marginBottom: 14 }}>
          <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
            Upload Exported Workflow JSON File:
          </label>
          <input
            type="file"
            accept=".json,application/json"
            onChange={handleFileUpload}
            style={{ fontSize: 12, color: 'var(--text-primary)' }}
          />
        </div>

        <FormGroup label="Or Paste Workflow JSON" hint="Supports portable multi-agent workflow specifications with schema_version: 1.0">
          <textarea
            className="input"
            rows={10}
            placeholder={'{\n  "schema_version": "1.0",\n  "name": "Exported Pipeline",\n  "nodes": [...],\n  "dependencies": [...]\n}'}
            value={jsonText}
            onChange={(e) => setJsonText(e.target.value)}
            style={{ fontFamily: 'monospace', fontSize: 11.5 }}
          />
        </FormGroup>
      </form>
    </Modal>
  )
}

function WorkflowRow({ wf, onExecute, onRefresh }: { wf: Workflow; onExecute: (wf: Workflow) => void; onRefresh: () => void }) {
  const navigate = useNavigate()

  const statusColor: Record<string, string> = {
    draft: '#94a3b8', active: '#10b981', archived: '#475569', inactive: '#f59e0b'
  }

  return (
    <tr style={{ cursor: 'pointer' }} onClick={() => navigate(`/workflows/${wf.public_id}`)}>
      <td>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: `${statusColor[wf.status] || '#94a3b8'}18`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: statusColor[wf.status] || '#94a3b8', flexShrink: 0,
          }}>
            <GitBranch size={14} />
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{wf.name}</div>
            {wf.description && (
              <div style={{ fontSize: 11, color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 300 }}>
                {wf.description}
              </div>
            )}
          </div>
        </div>
      </td>
      <td>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <StatusBadge status={wf.status} />
          <span style={{ fontSize: 10.5, padding: '1px 6px', borderRadius: 4, background: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b', fontWeight: 700, border: '1px solid rgba(245, 158, 11, 0.3)' }}>
            P{wf.priority ?? 1}
          </span>
        </div>
      </td>
      <td>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: 'var(--text-muted)' }}>
          <Layers size={12} />
          {wf.nodes?.length ?? 0} nodes
        </div>
      </td>
      <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>v{wf.version}</td>
      <td>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
          <Clock size={11} />
          {new Date(wf.created_at).toLocaleDateString()}
        </div>
      </td>
      <td onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
          <button
            className="btn btn-ghost"
            style={{ padding: '4px 8px', fontSize: 11 }}
            onClick={(e) => { e.stopPropagation(); navigate(`/workflows/${wf.public_id}`) }}
          >
            <Eye size={12} /> View
          </button>
          {wf.status === 'draft' && (
            <button
              className="btn btn-secondary"
              style={{ padding: '4px 8px', fontSize: 11 }}
              onClick={async (e) => {
                e.stopPropagation()
                try {
                  await workflowsApi.activate(wf.public_id)
                  onRefresh()
                } catch (err) {
                  alert((err as Error).message)
                }
              }}
            >
              <CheckCircle size={12} /> Activate
            </button>
          )}
          {wf.status !== 'archived' && (
            <button
              className="btn btn-primary"
              style={{ padding: '4px 10px', fontSize: 11 }}
              onClick={(e) => { e.stopPropagation(); onExecute(wf) }}
            >
              <Play size={11} /> Execute
            </button>
          )}
          <button
            className="btn btn-ghost"
            style={{ padding: '4px 8px', fontSize: 11 }}
            title="Export workflow to portable JSON (Schema 1.0)"
            onClick={async (e) => {
              e.stopPropagation()
              try {
                const exported = await workflowsApi.exportWorkflow(wf.public_id)
                const blob = new Blob([JSON.stringify(exported, null, 2)], { type: 'application/json' })
                const url = URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = `${wf.name.toLowerCase().replace(/[^a-z0-9]/g, '_')}_v${wf.version || 1}.json`
                a.click()
                URL.revokeObjectURL(url)
              } catch (err) {
                alert((err as Error).message)
              }
            }}
          >
            <Download size={12} />
          </button>
          <button
            className="btn btn-ghost"
            style={{ padding: '4px 8px', fontSize: 11 }}
            title="Duplicate / Copy workflow"
            onClick={async (e) => {
              e.stopPropagation()
              try {
                await workflowsApi.duplicateWorkflow(wf.public_id)
                onRefresh()
              } catch (err) {
                alert((err as Error).message)
              }
            }}
          >
            <Copy size={12} />
          </button>
          <button
            className="btn btn-ghost"
            style={{ padding: '4px 8px', fontSize: 11, color: 'var(--accent-rose)' }}
            title="Delete workflow"
            onClick={async (e) => {
              e.stopPropagation()
              if (!confirm(`Are you sure you want to permanently delete workflow "${wf.name}"?`)) return
              try {
                await workflowsApi.delete(wf.public_id)
                onRefresh()
              } catch (err) {
                alert((err as Error).message)
              }
            }}
          >
            <Trash2 size={12} />
          </button>
        </div>
      </td>
    </tr>
  )
}

export default function WorkflowsPage() {
  const { data, isLoading, error, refetch } = useAsync(() => workflowsApi.list(), [], true)
  const navigate = useNavigate()
  const [showCreate, setShowCreate] = useState(false)
  const [showImport, setShowImport] = useState(false)
  const [executing, setExecuting] = useState<Workflow | null>(null)
  const [execError, setExecError] = useState('')
  const [execLoading, setExecLoading] = useState(false)

  // Toggle between pipeline form mode and advanced JSON mode
  const [isJsonMode, setIsJsonMode] = useState<boolean>(false)

  // Data Analysis parameters
  const [wfDataRows, setWfDataRows] = useState(
    JSON.stringify([
      { month: 'Q1', revenue: 140000, margin: 42 },
      { month: 'Q2', revenue: 195000, margin: 48 },
      { month: 'Q3', revenue: 260000, margin: 55 },
      { month: 'Q4', revenue: 410000, margin: 61 }
    ], null, 2)
  )
  const [wfDataCol, setWfDataCol] = useState('revenue')

  // Security parameters
  const [wfSecContent, setWfSecContent] = useState(
    'const query = "SELECT * FROM users WHERE email = \'" + user_input + "\' OR 1=1;";'
  )

  // Database BI parameters
  const [wfSqlQuery, setWfSqlQuery] = useState('SELECT COUNT(*) as user_count, role FROM users GROUP BY role;')

  // Document Research parameters
  const [wfDocQuery, setWfDocQuery] = useState('What are the data retention requirements for financial transaction records?')
  const [wfDocDocs, setWfDocDocs] = useState(
    'SEC Compliance Rule 17a-4 mandates financial transaction records, audit logs, and ledger books must be preserved for at least 7 years in immutable format.\n\nGeneral application diagnostic logs expire after 90 days.'
  )

  // Report parameters
  const [wfReportTitle, setWfReportTitle] = useState('Executive Multi-Agent Operations Briefing')
  const [wfReportFormat, setWfReportFormat] = useState('markdown')

  // Email parameters
  const [providerMode, setProviderMode] = useState<'smtp' | 'resend'>('resend')
  const [customRecipient, setCustomRecipient] = useState(() => localStorage.getItem('last_recipient') || 'mehulpankajmaha@gmail.com')
  const [customSubject, setCustomSubject] = useState('')
  const [customMessage, setCustomMessage] = useState('')
  const [customSenderEmail, setCustomSenderEmail] = useState(() => localStorage.getItem('smtp_user') || '')
  const [customAppPassword, setCustomAppPassword] = useState(() => localStorage.getItem('smtp_password') || '')
  const [customResendKey, setCustomResendKey] = useState(() => localStorage.getItem('resend_api_key') || '')

  // Advanced Raw JSON parameter
  const [customJsonPayload, setCustomJsonPayload] = useState('{}')

  const workflows = data?.items || []

  // Derived properties from active executing workflow nodes
  const executingNodes = executing?.nodes || []
  const hasEmailNode = executingNodes.some(n => {
    const s = `${n.agent_type || ''} ${n.agent_name || ''} ${n.name || ''}`.toLowerCase()
    return s.includes('email') || s.includes('mail')
  })
  const hasDataNode = executingNodes.some(n => {
    const s = `${n.agent_type || ''} ${n.agent_name || ''} ${n.name || ''}`.toLowerCase()
    return s.includes('data') || s.includes('analytic') || s.includes('trend')
  })
  const hasReportNode = executingNodes.some(n => {
    const s = `${n.agent_type || ''} ${n.agent_name || ''} ${n.name || ''}`.toLowerCase()
    return s.includes('report') || s.includes('dossier')
  })
  const hasSecurityNode = executingNodes.some(n => {
    const s = `${n.agent_type || ''} ${n.agent_name || ''} ${n.name || ''}`.toLowerCase()
    return s.includes('security') || s.includes('scan') || s.includes('audit')
  })
  const hasDatabaseNode = executingNodes.some(n => {
    const s = `${n.agent_type || ''} ${n.agent_name || ''} ${n.name || ''}`.toLowerCase()
    return s.includes('database') || s.includes('sql') || s.includes('bi')
  })
  const hasDocNode = executingNodes.some(n => {
    const s = `${n.agent_type || ''} ${n.agent_name || ''} ${n.name || ''}`.toLowerCase()
    return s.includes('research') || s.includes('doc')
  })
  const isGenericPipeline = !hasEmailNode && !hasDataNode && !hasReportNode && !hasSecurityNode && !hasDatabaseNode && !hasDocNode

  useEffect(() => {
    if (!executing) return
    setExecError('')
    setCustomSubject(executing.name)
    setWfReportTitle(executing.name)
    setCustomMessage(`Workflow "${executing.name}" executed successfully with all configured agent tasks.`)
  }, [executing])

  const handleExecute = async () => {
    if (!executing) return
    setExecError('')
    setExecLoading(true)

    try {
      let inputData: Record<string, unknown> = {}

      if (isJsonMode) {
        try {
          inputData = JSON.parse(customJsonPayload)
        } catch {
          throw new Error('Invalid JSON format in custom payload.')
        }
      } else {
        // Collect email provider settings if configured
        if (providerMode === 'smtp') {
          const pass = customAppPassword.replace(/\s+/g, '').trim()
          if (pass && customSenderEmail.trim()) {
            inputData.email_provider = 'smtp'
            inputData.smtp_user = customSenderEmail.trim()
            inputData.smtp_password = pass
            inputData.email_from = customSenderEmail.trim()
            localStorage.setItem('smtp_user', customSenderEmail.trim())
            localStorage.setItem('smtp_password', customAppPassword.trim())
            localStorage.setItem('email_provider_mode', 'smtp')
          } else {
            inputData.email_provider = 'resend'
            const activeResendKey = customResendKey.trim() || localStorage.getItem('resend_api_key') || ''
            if (activeResendKey) {
              inputData.resend_api_key = activeResendKey
            }
          }
        } else {
          const activeResendKey = customResendKey.trim() || localStorage.getItem('resend_api_key') || ''
          inputData.email_provider = 'resend'
          if (activeResendKey) {
            inputData.resend_api_key = activeResendKey
            localStorage.setItem('resend_api_key', activeResendKey)
          }
          localStorage.setItem('email_provider_mode', 'resend')
        }
      }

      if (executing.status === 'draft') {
        try {
          await workflowsApi.activate(executing.public_id)
        } catch {
          // Continue to execute
        }
      }

      const result = await workflowsApi.execute(
        executing.public_id,
        inputData
      )
      setExecuting(null)
      if (result?.job_id || result?.public_id) {
        navigate(`/executions?job_id=${result.job_id || result.public_id}`)
      }
    } catch (err: any) {
      setExecError(err.message || 'Execution failed.')
    } finally {
      setExecLoading(false)
    }
  }

  return (
    <div className="page-container animate-fadeIn">
      <SectionHeader
        title="Workflows"
        subtitle="Design, manage, and execute multi-agent automation pipelines"
        actions={
          <>
            <button className="btn btn-secondary" onClick={refetch} style={{ fontSize: 12 }}>
              <RefreshCw size={13} />
              Refresh
            </button>
            <button className="btn btn-secondary" onClick={() => setShowImport(true)} style={{ fontSize: 12 }}>
              <Upload size={13} />
              Import Workflow
            </button>
            <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
              <Plus size={14} />
              New Workflow
            </button>
          </>
        }
      />

      {error && <ErrorState message={error} onRetry={refetch} />}

      <div className="card" style={{ overflow: 'hidden' }}>
        <table className="table">
          <thead>
            <tr>
              <th>Workflow</th>
              <th>Status</th>
              <th>Nodes</th>
              <th>Version</th>
              <th>Created</th>
              <th style={{ textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <SkeletonRows count={4} />
            ) : workflows.length === 0 ? (
              <tr>
                <td colSpan={6}>
                  <EmptyState
                    icon={<GitBranch size={36} />}
                    title="No workflows yet"
                    description="Create your first workflow to start automating complex multi-agent tasks."
                    action={
                      <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
                        <Plus size={14} />
                        Create Workflow
                      </button>
                    }
                  />
                </td>
              </tr>
            ) : (
              workflows.map((wf) => (
                <WorkflowRow key={wf.public_id} wf={wf} onExecute={setExecuting} onRefresh={refetch} />
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {data?.pagination && data.pagination.total_pages > 1 && (
        <div style={{ display: 'flex', gap: 8, justifyContent: 'center', alignItems: 'center', fontSize: 12, color: 'var(--text-muted)' }}>
          Page {data.pagination.page} of {data.pagination.total_pages} · {data.pagination.total} total
        </div>
      )}

      <CreateWorkflowModal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onCreated={(wf) => { setShowCreate(false); refetch(); navigate(`/workflows/${wf.public_id}`) }}
      />

      <ImportWorkflowModal
        open={showImport}
        onClose={() => setShowImport(false)}
        onImported={(wf) => { setShowImport(false); refetch(); navigate(`/workflows/${wf.public_id}`) }}
      />

      {/* ──────────────────────────────────────────────────────────────────────────── */}
      {/* TAILORED DYNAMIC WORKFLOW EXECUTION MODAL */}
      {/* ──────────────────────────────────────────────────────────────────────────── */}
      <Modal
        open={Boolean(executing)}
        onClose={() => setExecuting(null)}
        title={`Execute Pipeline: ${executing?.name || ''}`}
        maxWidth={720}
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setExecuting(null)}>Cancel</button>
            <button className="btn btn-primary" onClick={handleExecute} disabled={execLoading || (executing?.nodes?.length || 0) === 0} style={{ minWidth: 140 }}>
              {execLoading ? <div className="spinner" style={{ width: 14, height: 14 }} /> : <Play size={14} />}
              Run Pipeline
            </button>
          </>
        }
      >
        {execError && (
          <div className="alert alert-error" style={{ marginBottom: 16 }}>
            <AlertCircle size={15} style={{ flexShrink: 0 }} />
            <span>{execError}</span>
          </div>
        )}

        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
            Execute {executing?.name}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
            Pipeline will execute using saved configurations on each node:
          </div>
        </div>

        {/* View toggle (Form Configuration vs Raw JSON) */}
        <div style={{ display: 'flex', gap: 6, background: 'var(--surface-1)', padding: 4, borderRadius: 8, marginBottom: 16 }}>
          <button
            type="button"
            className={`btn ${!isJsonMode ? 'btn-primary' : 'btn-ghost'}`}
            style={{ flex: 1, fontSize: 11, padding: '7px 8px', justifyContent: 'center' }}
            onClick={() => setIsJsonMode(false)}
          >
            ⚡ Pipeline Nodes & Saved Config ({executing?.nodes?.length || 0})
          </button>
          <button
            type="button"
            className={`btn ${isJsonMode ? 'btn-primary' : 'btn-ghost'}`}
            style={{ flex: 1, fontSize: 11, padding: '7px 8px', justifyContent: 'center' }}
            onClick={() => setIsJsonMode(true)}
          >
            🤖 Advanced JSON Overrides
          </button>
        </div>

        {isJsonMode ? (
          <FormGroup label="Input Payload (JSON)" hint="Passed directly to workflow DAG nodes.">
            <textarea
              className="input"
              rows={8}
              style={{ fontFamily: 'monospace', fontSize: 12 }}
              value={customJsonPayload}
              onChange={(e) => setCustomJsonPayload(e.target.value)}
            />
          </FormGroup>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {/* 1. NODE CONFIGURATION BREAKDOWN */}
            {(!executing?.nodes || executing.nodes.length === 0) ? (
              <div className="alert alert-warning" style={{ fontSize: 12 }}>
                ⚠️ This workflow currently has no nodes. Please open workflow builder and add nodes before executing.
              </div>
            ) : (
              executing.nodes.map((node, idx) => {
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
                          {node.name}
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
                            <CheckCircle size={11} /> Ready
                          </span>
                        )}
                        <button
                          type="button"
                          className="btn btn-ghost"
                          style={{ padding: '2px 6px', fontSize: 11, color: '#818cf8' }}
                          onClick={() => {
                            setExecuting(null)
                            navigate(`/workflows/${executing.public_id}`)
                          }}
                        >
                          <Eye size={12} /> Open in Builder
                        </button>
                      </div>
                    </div>

                    {isMissing && (
                      <div style={{ fontSize: 11.5, color: '#f59e0b', background: 'rgba(245,158,11,0.08)', padding: '6px 10px', borderRadius: 6 }}>
                        ⚠️ <strong>Action Required:</strong> {missingReason} (Open in Builder to configure).
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

            {/* Email Provider Quick Config */}
            {hasEmailNode && (
              <div style={{
                background: 'var(--surface-1)',
                padding: 12,
                borderRadius: 8,
                border: '1px solid var(--border-subtle)',
                marginTop: 8,
                display: 'flex',
                flexDirection: 'column',
                gap: 10
              }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#818cf8', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Mail size={14} /> Email Delivery Connector (Optional credentials)
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  <div>
                    <label style={{ fontSize: 11, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Gmail SMTP Sender</label>
                    <input
                      className="input"
                      style={{ fontSize: 11.5 }}
                      placeholder="e.g. mehulpankajmaha@gmail.com"
                      value={customSenderEmail}
                      onChange={(e) => setCustomSenderEmail(e.target.value)}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: 11, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Google App Password (16 letters)</label>
                    <input
                      type="password"
                      className="input"
                      style={{ fontSize: 11.5 }}
                      placeholder="e.g. abcd efgh ijkl mnop"
                      value={customAppPassword}
                      onChange={(e) => setCustomAppPassword(e.target.value)}
                    />
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        <div className="alert alert-info" style={{ marginTop: 12 }}>
          <ArrowRight size={14} style={{ flexShrink: 0, marginTop: 1 }} />
          Workflow will automatically activate upon execution if currently in draft state.
        </div>
      </Modal>
    </div>
  )
}
