import React, { useState, useEffect, useCallback } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Play, RefreshCw, XCircle, RotateCcw, Filter,
  Clock, CheckCircle2, AlertCircle, AlertTriangle, Loader2, Pause, Activity, Terminal, Bot,
  Layers
} from 'lucide-react'
import { jobsApi, type Job } from '../lib/api'
import { useAsync } from '../hooks/useAsync'
import { SectionHeader, StatusBadge, EmptyState, ErrorState, SkeletonRows, Modal } from '../components/ui'
import { AgentResultRenderer } from '../components/AgentResultRenderer'
import { LiveTerminal } from '../components/LiveTerminal'


const STATUS_OPTIONS = ['', 'QUEUED', 'RUNNING', 'PAUSED', 'SUCCEEDED', 'COMPLETED', 'FAILED', 'CANCELLED']

function JobStatusIcon({ status }: { status: string }) {
  const s = status?.toUpperCase()
  if (s === 'SUCCEEDED' || s === 'COMPLETED') return <CheckCircle2 size={14} style={{ color: '#10b981' }} />
  if (s === 'FAILED') return <AlertCircle size={14} style={{ color: '#f43f5e' }} />
  if (s === 'RUNNING') return <Loader2 size={14} style={{ color: '#0ea5e9', animation: 'spin 1s linear infinite' }} />
  if (s === 'CANCELLED') return <XCircle size={14} style={{ color: '#94a3b8' }} />
  if (s === 'QUEUED' || s === 'PAUSED') return <Pause size={14} style={{ color: '#f59e0b' }} />
  return <Clock size={14} style={{ color: '#94a3b8' }} />
}

function JobDetailModal({ jobId, open, onClose, onOpenTerminal }: { jobId: string; open: boolean; onClose: () => void; onOpenTerminal?: (id: string) => void }) {
  const navigate = useNavigate()
  const { data: job, isLoading, refetch: refetchJob } = useAsync(() => jobsApi.get(jobId), [jobId], open && !!jobId)
  const isFinished = job?.status?.toUpperCase() === 'SUCCEEDED' || job?.status?.toUpperCase() === 'COMPLETED' || job?.status?.toUpperCase() === 'FAILED' || job?.status?.toUpperCase() === 'CANCELLED'
  const isPaused = job?.status?.toUpperCase() === 'PAUSED'
  const { data: result } = useAsync(() => jobsApi.result(jobId), [jobId], open && !!jobId && isFinished)

  const outputPayload = job?.output_data || job?.result_data || result?.result_data
  const errorMessage = job?.error_message || job?.failure_reason
  const taskExecutions = job?.task_executions || []
  const hasBlockedTasks = taskExecutions.some((t: any) => t.status?.toLowerCase() === 'blocked')

  // Auto-refresh execution details while running, queued, or paused
  useEffect(() => {
    if (!open || !jobId || isFinished) return
    const interval = setInterval(() => {
      refetchJob()
    }, 2500)
    return () => clearInterval(interval)
  }, [open, jobId, isFinished, refetchJob])

  const [allExpanded, setAllExpanded] = useState(true)
  const [expandedSteps, setExpandedSteps] = useState<Record<string, boolean>>({})

  const toggleAll = () => {
    const nextState = !allExpanded
    setAllExpanded(nextState)
    const newExpanded: Record<string, boolean> = {}
    taskExecutions.forEach((te: any, idx: number) => {
      newExpanded[te.public_id || `step-${idx}`] = nextState
    })
    setExpandedSteps(newExpanded)
  }

  const isStepOpen = (key: string) => {
    return expandedSteps[key] !== undefined ? expandedSteps[key] : allExpanded
  }

  return (
    <Modal open={open} onClose={onClose} title="Execution & Job Details" maxWidth={720}>
      {isLoading && !job ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}><div className="spinner" /></div>
      ) : job ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Action Row: Refresh + Live Terminal */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {isFinished ? '✓ Execution finished' : isPaused ? '⏸️ Workflow execution paused for approval' : '⚡ Workflow execution running...'}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                className="btn btn-secondary"
                style={{ fontSize: 12, padding: '5px 10px', display: 'flex', alignItems: 'center', gap: 6 }}
                onClick={() => refetchJob()}
                title="Refresh latest execution status"
              >
                <RefreshCw size={13} className={isLoading ? 'animate-spin' : ''} /> Refresh Status
              </button>
              {onOpenTerminal && (
                <button
                  className="btn btn-secondary"
                  style={{ fontSize: 12, padding: '5px 10px', display: 'flex', alignItems: 'center', gap: 6 }}
                  onClick={() => onOpenTerminal(jobId)}
                >
                  <Terminal size={14} /> Live Terminal
                </button>
              )}
            </div>
          </div>

          {/* ⏸️ Workflow Paused for Approval Banner */}
          {(isPaused || hasBlockedTasks) && (
            <div
              style={{
                background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.14) 0%, rgba(217, 119, 6, 0.08) 100%)',
                border: '1.5px solid rgba(245, 158, 11, 0.45)',
                borderRadius: 10,
                padding: '14px 16px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 14,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{
                  width: 36,
                  height: 36,
                  borderRadius: 8,
                  background: 'rgba(245, 158, 11, 0.25)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#f59e0b',
                  flexShrink: 0
                }}>
                  <AlertTriangle size={20} />
                </div>
                <div>
                  <div style={{ fontWeight: 700, color: '#f59e0b', fontSize: 13 }}>
                    Workflow Paused — Awaiting Human Approval
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
                    One of your workflow steps requires authorization before performing its action. Downstream steps will resume execution automatically once approved.
                  </div>
                </div>
              </div>
              <button
                className="btn btn-primary"
                style={{
                  fontSize: 12,
                  padding: '7px 14px',
                  fontWeight: 600,
                  whiteSpace: 'nowrap',
                  background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
                  border: 'none',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6
                }}
                onClick={() => {
                  onClose()
                  navigate('/approvals')
                }}
              >
                Review in Approvals →
              </button>
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10 }}>
            {[
              { label: 'Execution ID', value: job.public_id?.slice(0, 18) + '…' },
              { label: 'Status', value: <StatusBadge status={job.status} /> },
              { label: 'Trigger', value: ((job as any).trigger_type || (job as any).trigger || 'Manual').toUpperCase() },
              { label: 'Priority', value: job.priority ?? 1 },
              { label: 'Started', value: job.started_at ? new Date(job.started_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' }) : '—' },
              {
                label: 'Duration',
                value: job.started_at && job.completed_at
                  ? `${Math.max(1, Math.round((new Date(job.completed_at).getTime() - new Date(job.started_at).getTime()) / 1000))}s`
                  : (job.started_at ? 'In progress' : '—')
              },
            ].map(({ label, value }) => (
              <div key={label} style={{ background: 'var(--surface-1)', borderRadius: 8, padding: '10px 12px' }}>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>{label}</div>
                <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>{value}</div>
              </div>
            ))}
          </div>

          {errorMessage && (
            <div className="alert alert-error">
              <AlertCircle size={14} style={{ flexShrink: 0, marginTop: 1 }} />
              <div>
                <div style={{ fontWeight: 500 }}>Execution Error</div>
                <div style={{ fontSize: 12, marginTop: 2 }}>{errorMessage}</div>
              </div>
            </div>
          )}

          {/* Task Executions / Agent Steps */}
          {taskExecutions.length > 0 && (
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span>Agent Task Steps ({taskExecutions.length})</span>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>— Outputs from every node in pipeline</span>
                </div>
                <button
                  type="button"
                  className="btn btn-ghost"
                  style={{ fontSize: 11, padding: '3px 8px', color: 'var(--brand-primary)', cursor: 'pointer' }}
                  onClick={toggleAll}
                >
                  {allExpanded ? 'Collapse All' : 'Expand All Steps'}
                </button>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {taskExecutions.map((te: any, idx: number) => {
                  const key = te.public_id || `step-${idx}`
                  const isFailed = te.status?.toLowerCase() === 'failed'
                  const isBlocked = te.status?.toLowerCase() === 'blocked'
                  const isWaitingApproval = te.status?.toLowerCase() === 'waiting_for_approval' || te.status?.toLowerCase() === 'awaiting_approval'
                  const errText = te.error_data?.error || te.error_message || (typeof te.error_data === 'string' ? te.error_data : null)
                  const open = isStepOpen(key)
                  return (
                    <details
                      key={key}
                      open={open}
                      onToggle={(e) => {
                        const target = e.target as HTMLDetailsElement
                        setExpandedSteps(prev => ({ ...prev, [key]: target.open }))
                      }}
                      style={{
                        background: 'var(--surface-1)',
                        borderRadius: 8,
                        border: `1px solid ${isFailed ? 'rgba(244,63,94,0.35)' : (isBlocked || isWaitingApproval) ? 'rgba(245,158,11,0.35)' : 'var(--border-subtle)'}`,
                        overflow: 'hidden'
                      }}
                    >
                      <summary
                        style={{
                          padding: '10px 14px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          cursor: 'pointer',
                          background: isFailed ? 'rgba(244,63,94,0.06)' : (isBlocked || isWaitingApproval) ? 'rgba(245,158,11,0.06)' : 'transparent',
                          userSelect: 'none',
                          fontWeight: 600,
                          fontSize: 13
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <StatusBadge status={te.status} />
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                            <Bot size={13} style={{ color: '#818cf8' }} />
                            <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                              Task Step #{idx + 1}
                            </span>
                            {te.agent_name && (
                              <span style={{ color: 'var(--brand-primary)', fontWeight: 600 }}>
                                · {te.agent_name}
                              </span>
                            )}
                            {te.node_name && (
                              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                                ({te.node_name})
                              </span>
                            )}
                          </div>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          {te.duration_ms !== undefined && (
                            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>⏱️ {te.duration_ms} ms</span>
                          )}
                          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{open ? '▲' : '▼'}</span>
                        </div>
                      </summary>

                      <div style={{ padding: '12px 14px', borderTop: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', gap: 10 }}>
                        {/* Notice if Blocked awaiting approval */}
                        {(isBlocked || isWaitingApproval) && (
                          <div style={{
                            background: 'rgba(245, 158, 11, 0.08)',
                            border: '1px dashed rgba(245, 158, 11, 0.3)',
                            borderRadius: 6,
                            padding: '8px 12px',
                            fontSize: 12,
                            color: '#f59e0b',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between'
                          }}>
                            <span>⏳ This node is awaiting user approval in Approvals tab.</span>
                            <button
                              className="btn btn-ghost"
                              style={{ fontSize: 11, color: '#f59e0b', padding: '2px 6px', textDecoration: 'underline' }}
                              onClick={() => { onClose(); navigate('/approvals') }}
                            >
                              Approve Now
                            </button>
                          </div>
                        )}

                        {/* Error Message if Failed */}
                        {errText && (
                          <div className="alert alert-error" style={{ fontSize: 12, padding: '10px 12px' }}>
                            <AlertCircle size={15} style={{ flexShrink: 0, marginTop: 1 }} />
                            <div>
                              <strong style={{ display: 'block', marginBottom: 2 }}>Task Step Failed:</strong>
                              <span>{errText}</span>
                              {te.error_data?.attempts && (
                                <div style={{ fontSize: 11, marginTop: 4, color: 'var(--text-muted)' }}>
                                  Attempts executed: {te.error_data.attempts}
                                </div>
                              )}
                            </div>
                          </div>
                        )}

                        {/* Input Parameters (Collapsed by default, styled as clean attribute tiles) */}
                        {te.input_data && Object.keys(te.input_data).length > 0 && (
                          <details style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                            <summary style={{ cursor: 'pointer', userSelect: 'none', fontWeight: 600, padding: '2px 0', display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                              <span>⚙️ View Input Parameters ({Object.keys(te.input_data).length})</span>
                            </summary>
                            <div style={{
                              marginTop: 6,
                              padding: 10,
                              background: 'var(--surface-0)',
                              borderRadius: 6,
                              border: '1px solid var(--border-subtle)',
                              display: 'grid',
                              gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
                              gap: 8,
                            }}>
                              {Object.entries(te.input_data).map(([k, v]) => (
                                <div key={k} style={{ background: 'var(--surface-1)', padding: '6px 8px', borderRadius: 4, border: '1px solid var(--border-subtle)' }}>
                                  <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{k.replace(/_/g, ' ')}</div>
                                  <div style={{ fontSize: 11, color: 'var(--text-primary)', wordBreak: 'break-word', marginTop: 2, fontWeight: 500 }}>
                                    {typeof v === 'object' && v !== null ? JSON.stringify(v) : String(v)}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </details>
                        )}

                        {/* Output Produced by Agent */}
                        {te.output_data && Object.keys(te.output_data).length > 0 ? (
                          <AgentResultRenderer
                            output={te.output_data as Record<string, unknown>}
                            agentType={te.agent_type || te.agent_name || te.node_name}
                          />
                        ) : !errText && (
                          <div style={{ fontSize: 11, color: 'var(--text-muted)', fontStyle: 'italic', padding: 4 }}>
                            {te.status?.toLowerCase() === 'pending'
                              ? '⏳ Waiting for upstream nodes to complete before executing.'
                              : 'Task step completed successfully.'}
                          </div>
                        )}
                      </div>
                    </details>
                  )
                })}
              </div>
            </div>
          )}

          {/* Artifacts Generated During Run */}
          {(() => {
            const artifacts: Array<{ title: string; type: string; url?: string }> = []
            const seenUrls = new Set<string>()
            const seenKeys = new Set<string>()

            const normalizeFmt = (fmt: string) => {
              const f = fmt.toLowerCase()
              if (f === 'markdown' || f === 'md') return 'MD'
              if (f === 'doc' || f === 'docx') return 'DOCX'
              if (f === 'text' || f === 'txt') return 'TXT'
              return f.toUpperCase()
            }

            taskExecutions.forEach((te: any) => {
              const out = te.output_data || {}
              if (out.downloads && typeof out.downloads === 'object') {
                Object.entries(out.downloads).forEach(([fmt, url]) => {
                  if (typeof url !== 'string' || !url) return
                  const canonicalFmt = normalizeFmt(fmt)
                  const dedupKey = `${canonicalFmt}:${url}`
                  if (seenUrls.has(url) || seenKeys.has(dedupKey)) return
                  seenUrls.add(url)
                  seenKeys.add(dedupKey)
                  artifacts.push({ title: `${out.reportTitle || 'Report'} (${canonicalFmt})`, type: canonicalFmt.toLowerCase(), url: url as string })
                })
              } else if (out.primary_artifact) {
                const u = out.primary_artifact.url || out.primary_artifact.download_url
                if (!u || !seenUrls.has(u)) {
                  if (u) seenUrls.add(u)
                  artifacts.push({ title: out.primary_artifact.filename || out.reportTitle || 'Report Artifact', type: out.primary_artifact.format || 'file', url: u })
                }
              } else if (out.all_artifacts && Array.isArray(out.all_artifacts)) {
                out.all_artifacts.forEach((a: any) => {
                  const u = a.download_url || a.url
                  const canonicalFmt = a.type ? normalizeFmt(a.type) : 'FILE'
                  const dedupKey = `${canonicalFmt}:${u}`
                  if (u && (seenUrls.has(u) || seenKeys.has(dedupKey))) return
                  if (u) {
                    seenUrls.add(u)
                    seenKeys.add(dedupKey)
                  }
                  artifacts.push({ title: a.name || a.filename || 'Artifact', type: a.type || 'file', url: u })
                })
              }
              if (out.image && out.image.image_url) {
                const u = out.image.image_url
                if (!seenUrls.has(u)) {
                  seenUrls.add(u)
                  artifacts.push({ title: out.image.prompt || 'Generated Visual', type: 'image', url: u })
                }
              }
            })

            return artifacts.length > 0 ? (
              <div style={{ marginTop: 8 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span>📦 Generated Run Artifacts ({artifacts.length})</span>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {artifacts.map((art, idx) => (
                    <a
                      key={idx}
                      href={art.url || '#'}
                      target="_blank"
                      rel="noreferrer"
                      download
                      className="btn btn-secondary btn-sm"
                      style={{ fontSize: 12, padding: '6px 12px', display: 'inline-flex', alignItems: 'center', gap: 6, textDecoration: 'none' }}
                    >
                      📄 {art.title}
                    </a>
                  ))}
                </div>
              </div>
            ) : null
          })()}

          {/* Combined Output Data (Fallback if no individual task steps exist) */}
          {outputPayload && Object.keys(outputPayload).length > 0 && taskExecutions.length === 0 && (
            <div>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>Final Workflow Output</div>
              <div style={{ background: 'var(--surface-1)', borderRadius: 8, padding: 14, border: '1px solid var(--border-subtle)' }}>
                <AgentResultRenderer
                  output={outputPayload as Record<string, unknown>}
                  agentType={
                    (outputPayload as Record<string, unknown>).agent_type as string | undefined
                  }
                />
              </div>
            </div>
          )}
        </div>

      ) : <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: 32 }}>Execution details not found</div>}
    </Modal>
  )
}


export default function ExecutionsPage() {
  const [searchParams] = useSearchParams()
  const highlightJobId = searchParams.get('job_id')

  const [statusFilter, setStatusFilter] = useState('')
  const [selectedJobId, setSelectedJobId] = useState(highlightJobId || '')
  const [showDetail, setShowDetail] = useState(!!highlightJobId)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [terminalJobId, setTerminalJobId] = useState<string | null>(null)
  const [showTerminal, setShowTerminal] = useState(false)

  const { data, isLoading, error, refetch } = useAsync(
    () => jobsApi.list(1, 30, statusFilter || undefined),
    [statusFilter],
    true
  )

  const jobs = data?.items || []

  // Auto-open modal if navigated with ?job_id=...
  useEffect(() => {
    if (highlightJobId) {
      setSelectedJobId(highlightJobId)
      setShowDetail(true)
    }
  }, [highlightJobId])

  // Auto-refresh if any running or paused jobs
  useEffect(() => {
    const hasRunning = jobs.some((j) => j.status === 'RUNNING' || j.status === 'QUEUED' || j.status === 'PAUSED')
    if (!hasRunning) return
    const interval = setInterval(refetch, 3000)
    return () => clearInterval(interval)
  }, [jobs])

  const handleCancel = async (jobId: string) => {
    setActionLoading(jobId)
    try { await jobsApi.cancel(jobId, 'Cancelled by user'); refetch() }
    catch { }
    finally { setActionLoading(null) }
  }

  const handleRetry = async (jobId: string) => {
    setActionLoading(jobId)
    try { await jobsApi.retry(jobId); refetch() }
    catch { }
    finally { setActionLoading(null) }
  }

  return (
    <div className="page-container animate-fadeIn">
      <SectionHeader
        title="Executions"
        subtitle="Monitor async workflow jobs, their status and results"
        actions={
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Filter size={13} style={{ color: 'var(--text-muted)' }} />
              <select className="input" style={{ width: 'auto', padding: '6px 10px' }} value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s || 'All Statuses'}</option>)}
              </select>
            </div>
            <button className="btn btn-secondary" onClick={refetch} style={{ fontSize: 12 }}>
              <RefreshCw size={13} />
              Refresh
            </button>
          </>
        }
      />

      {error && <ErrorState message={error} onRetry={refetch} />}

      {/* Live badge */}
      {jobs.some((j) => j.status === 'RUNNING') && (
        <div className="alert alert-info" style={{ padding: '8px 14px' }}>
          <Activity size={13} style={{ flexShrink: 0, color: '#38bdf8' }} />
          <span style={{ fontSize: 12 }}>Live jobs detected — refreshing every 3s automatically</span>
        </div>
      )}

      <div className="card" style={{ overflow: 'hidden' }}>
        <table className="table">
          <thead>
            <tr>
              <th>Status</th>
              <th>Job ID</th>
              <th>Priority</th>
              <th>Created</th>
              <th>Duration</th>
              <th style={{ textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <SkeletonRows count={5} />
            ) : jobs.length === 0 ? (
              <tr>
                <td colSpan={6}>
                  <EmptyState
                    icon={<Play size={36} />}
                    title="No jobs found"
                    description={statusFilter ? `No jobs with status "${statusFilter}"` : "Execute a workflow to see jobs here"}
                  />
                </td>
              </tr>
            ) : (
              jobs.map((job) => {
                const duration = job.started_at && job.completed_at
                  ? Math.round((new Date(job.completed_at).getTime() - new Date(job.started_at).getTime()) / 1000)
                  : null

                const isHighlighted = job.public_id === highlightJobId

                return (
                  <motion.tr
                    key={job.public_id}
                    initial={isHighlighted ? { backgroundColor: 'rgba(99,102,241,0.1)' } : undefined}
                    animate={{ backgroundColor: 'transparent' }}
                    transition={{ delay: 0.5, duration: 1 }}
                    style={{ cursor: 'pointer' }}
                    onClick={() => { setSelectedJobId(job.public_id); setShowDetail(true) }}
                  >
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <JobStatusIcon status={job.status} />
                        <StatusBadge status={job.status} />
                      </div>
                    </td>
                    <td>
                      <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                        {job.public_id?.slice(0, 20)}…
                      </span>
                    </td>
                    <td style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{job.priority}</td>
                    <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                      {new Date(job.created_at).toLocaleString()}
                    </td>
                    <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                      {duration !== null ? `${duration}s` : '—'}
                    </td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <div style={{ display: 'flex', gap: 4, justifyContent: 'flex-end', alignItems: 'center' }}>
                        <button
                          className="btn btn-secondary"
                          style={{ padding: '3px 8px', fontSize: 11, display: 'flex', alignItems: 'center', gap: 4 }}
                          onClick={() => { setTerminalJobId(job.public_id); setShowTerminal(true) }}
                          title="Open Live Execution Terminal"
                        >
                          <Terminal size={12} /> Terminal
                        </button>
                        {(job.status === 'QUEUED' || job.status === 'RUNNING') && (
                          <button
                            className="btn btn-danger"
                            style={{ padding: '3px 8px', fontSize: 11 }}
                            onClick={() => handleCancel(job.public_id)}
                            disabled={actionLoading === job.public_id}
                          >
                            <XCircle size={11} /> Cancel
                          </button>
                        )}
                        {job.status === 'FAILED' && (
                          <button
                            className="btn btn-success"
                            style={{ padding: '3px 8px', fontSize: 11 }}
                            onClick={() => handleRetry(job.public_id)}
                            disabled={actionLoading === job.public_id}
                          >
                            <RotateCcw size={11} /> Retry
                          </button>
                        )}
                      </div>
                    </td>
                  </motion.tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {data?.pagination && (
        <div style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center' }}>
          Showing {jobs.length} of {data.pagination.total} jobs
        </div>
      )}

      <JobDetailModal
        jobId={selectedJobId}
        open={showDetail}
        onClose={() => setShowDetail(false)}
        onOpenTerminal={(id) => { setTerminalJobId(id); setShowTerminal(true) }}
      />

      {terminalJobId && (
        <LiveTerminal
          jobId={terminalJobId}
          isOpen={showTerminal}
          onClose={() => setShowTerminal(false)}
        />
      )}
    </div>
  )
}
