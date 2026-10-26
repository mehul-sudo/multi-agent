import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Layers, Play, CheckCircle2, AlertCircle, Clock, ArrowRight,
  RefreshCw, Check, Sparkles, Plus, FileText, ChevronRight,
  ExternalLink, Upload, Shield, Pause, RotateCcw, BarChart2,
  Mail, FileCheck, Filter, Search, XCircle, Eye, List, GitFork
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import {
  orchestrationsApi,
  uploadsApi,
  type OrchestrationSession,
  type OrchestrationPlanTask,
  type TaskOverviewStats,
} from '../lib/api'
import { useAsync } from '../hooks/useAsync'
import { SectionHeader, StatusBadge, EmptyState, Modal } from '../components/ui'
import { MarkdownView } from '../components/MarkdownView'

export default function TaskManagerPage() {
  const navigate = useNavigate()
  const { data: sessionData, isLoading, refetch } = useAsync(() => orchestrationsApi.list(), [], true)
  const sessions = sessionData?.orchestrations || []

  const [objective, setObjective] = useState('')
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null)
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)

  // Execution state
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [activeSession, setActiveSession] = useState<OrchestrationSession | null>(null)
  const [activeTasks, setActiveTasks] = useState<OrchestrationPlanTask[]>([])
  const [isExecuting, setIsExecuting] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')

  // Overview stats & filters
  const [overviewStats, setOverviewStats] = useState<TaskOverviewStats | null>(null)
  const [viewMode, setViewMode] = useState<'pipeline' | 'table'>('pipeline')
  const [statusFilter, setStatusFilter] = useState<string>('ALL')
  const [priorityFilter, setPriorityFilter] = useState<string>('ALL')
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [inspectingTask, setInspectingTask] = useState<OrchestrationPlanTask | null>(null)
  const [actionLoadingTaskId, setActionLoadingTaskId] = useState<string | null>(null)

  const loadOverviewStats = async (orchestrationId?: string) => {
    try {
      const stats = await orchestrationsApi.taskOverview(orchestrationId)
      setOverviewStats(stats)
    } catch (err) {
      console.error('Error loading task overview stats:', err)
    }
  }

  // Load latest session if available
  useEffect(() => {
    if (sessions.length > 0 && !activeSessionId) {
      loadSessionDetails(sessions[0].id)
    } else if (sessions.length === 0) {
      loadOverviewStats()
    }
  }, [sessions])

  // Live polling during active pipeline execution (1200ms)
  useEffect(() => {
    if (!isExecuting || !activeSessionId) return
    const interval = setInterval(async () => {
      try {
        const [planRes, sess] = await Promise.all([
          orchestrationsApi.plan(activeSessionId),
          orchestrationsApi.get(activeSessionId),
        ])
        if (planRes && planRes.tasks) {
          setActiveTasks(planRes.tasks)
        }
        if (sess) {
          setActiveSession(sess)
        }
      } catch (err) {
        // Silently ignore transient network poll errors during active execution
      }
    }, 1200)

    return () => clearInterval(interval)
  }, [isExecuting, activeSessionId])

  const loadSessionDetails = async (id: string) => {
    try {
      setActiveSessionId(id)
      const [sess, planRes] = await Promise.all([
        orchestrationsApi.get(id),
        orchestrationsApi.plan(id),
      ])
      setActiveSession(sess)
      setActiveTasks(planRes.tasks || [])
      await loadOverviewStats(id)
    } catch (err: any) {
      console.error('Error loading session details:', err)
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const res = await uploadsApi.upload(file)
      setSelectedFileId(res.file_id)
      setSelectedFileName(res.filename)
    } catch (err: any) {
      setErrorMessage(err.message || 'File upload failed.')
    } finally {
      setUploading(false)
    }
  }

  const handleCreateAndRun = async () => {
    if (!objective.trim() || isExecuting) return
    setIsExecuting(true)
    setErrorMessage('')

    try {
      const context: Record<string, any> = {}
      if (selectedFileId) {
        context.file_id = selectedFileId
        context.filename = selectedFileName
      }

      const res = await orchestrationsApi.create(objective, context)
      const newSessionId = res.orchestration.id
      setActiveSessionId(newSessionId)

      const planRes = await orchestrationsApi.plan(newSessionId)
      setActiveTasks(planRes.tasks || [])

      await orchestrationsApi.start(newSessionId)

      await loadSessionDetails(newSessionId)
      refetch()
      setObjective('')
      setSelectedFileId(null)
      setSelectedFileName(null)
    } catch (err: any) {
      setErrorMessage(err.message || 'Execution failed.')
    } finally {
      setIsExecuting(false)
    }
  }

  const handleStartSession = async (id: string) => {
    setIsExecuting(true)
    try {
      await orchestrationsApi.start(id)
      await loadSessionDetails(id)
      refetch()
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to start session.')
    } finally {
      setIsExecuting(false)
    }
  }

  const handleRetryTask = async (taskId: string) => {
    if (!activeSessionId) return
    setActionLoadingTaskId(taskId)
    try {
      await orchestrationsApi.retryTask(activeSessionId, taskId)
      await loadSessionDetails(activeSessionId)
      refetch()
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to retry task.')
    } finally {
      setActionLoadingTaskId(null)
    }
  }

  const handleCancelTask = async (taskId: string) => {
    if (!activeSessionId) return
    setActionLoadingTaskId(taskId)
    try {
      await orchestrationsApi.cancelTask(activeSessionId, taskId)
      await loadSessionDetails(activeSessionId)
      refetch()
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to cancel task.')
    } finally {
      setActionLoadingTaskId(null)
    }
  }

  const filteredTasks = activeTasks.filter((task) => {
    if (statusFilter !== 'ALL') {
      if (statusFilter === 'COMPLETED' && task.status !== 'COMPLETED') return false
      if (statusFilter === 'RUNNING' && task.status !== 'RUNNING') return false
      if (statusFilter === 'AWAITING_APPROVAL' && task.status !== 'AWAITING_APPROVAL' && !task.awaiting_approval) return false
      if (statusFilter === 'PENDING' && !['PENDING', 'READY'].includes(task.status)) return false
      if (statusFilter === 'FAILED' && !['FAILED', 'CANCELLED', 'BLOCKED'].includes(task.status)) return false
    }
    if (priorityFilter !== 'ALL') {
      const p = String(task.priority ?? 1)
      if (priorityFilter === '3') {
        if ((task.priority ?? 1) < 3) return false
      } else if (p !== priorityFilter) {
        return false
      }
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      const matchesName = task.name.toLowerCase().includes(q)
      const matchesDesc = (task.description || '').toLowerCase().includes(q)
      const matchesAgent = (task.assigned_agent_name || task.assigned_agent_type || '').toLowerCase().includes(q)
      const matchesKey = task.task_key.toLowerCase().includes(q)
      if (!matchesName && !matchesDesc && !matchesAgent && !matchesKey) return false
    }
    return true
  })

  return (
    <div style={{ padding: '24px', maxWidth: 1400, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <SectionHeader
          title="Task Manager & Supervisor"
          subtitle="Interpret enterprise goals, coordinate multi-agent DAG execution, track task dependencies, and supervise live lifecycles."
          actions={
            <button
              onClick={() => {
                refetch()
                if (activeSessionId) loadSessionDetails(activeSessionId)
                loadOverviewStats()
              }}
              className="btn btn-secondary btn-sm"
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <RefreshCw size={14} /> Refresh
            </button>
          }
        />
      </div>

      {/* Persisted Task Overview Stats Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: 12,
          marginBottom: 24,
        }}
      >
        <div className="card" style={{ padding: '14px 18px', background: 'var(--surface-1)', border: '1px solid var(--border-subtle)', borderRadius: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
            <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Total Tasks</span>
            <Layers size={16} color="var(--primary)" />
          </div>
          <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-primary)' }}>
            {overviewStats?.total ?? 0}
          </div>
        </div>

        <div className="card" style={{ padding: '14px 18px', background: 'var(--surface-1)', border: '1px solid var(--border-subtle)', borderRadius: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
            <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Pending / Queued</span>
            <Clock size={16} color="var(--accent-sky)" />
          </div>
          <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--accent-sky)' }}>
            {overviewStats?.pending_queued ?? 0}
          </div>
        </div>

        <div className="card" style={{ padding: '14px 18px', background: 'var(--surface-1)', border: '1px solid var(--border-subtle)', borderRadius: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
            <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>In Progress</span>
            <RefreshCw size={16} color="var(--primary)" />
          </div>
          <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--primary)' }}>
            {overviewStats?.in_progress ?? 0}
          </div>
        </div>

        <div className="card" style={{ padding: '14px 18px', background: 'var(--surface-1)', border: '1px solid var(--border-subtle)', borderRadius: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
            <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Awaiting Approval</span>
            <Shield size={16} color="var(--accent-amber)" />
          </div>
          <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--accent-amber)' }}>
            {overviewStats?.awaiting_approval ?? 0}
          </div>
        </div>

        <div className="card" style={{ padding: '14px 18px', background: 'var(--surface-1)', border: '1px solid var(--border-subtle)', borderRadius: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
            <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Completed</span>
            <CheckCircle2 size={16} color="var(--accent-emerald)" />
          </div>
          <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--accent-emerald)' }}>
            {overviewStats?.completed ?? 0}
          </div>
        </div>

        <div className="card" style={{ padding: '14px 18px', background: 'var(--surface-1)', border: '1px solid var(--border-subtle)', borderRadius: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
            <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Failed / Cancelled</span>
            <AlertCircle size={16} color="var(--accent-rose)" />
          </div>
          <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--accent-rose)' }}>
            {overviewStats?.failed ?? 0}
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(340px, 420px) 1fr', gap: 24, alignItems: 'start' }}>
        {/* Left Column: Create Goal & Recent Sessions */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Create Box */}
          <div className="card" style={{ padding: 20 }}>
            <h3 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 12px', display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-primary)' }}>
              <Sparkles size={16} color="var(--primary)" />
              New Enterprise Goal
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                  Natural Language Objective
                </label>
                <textarea
                  value={objective}
                  onChange={(e) => setObjective(e.target.value)}
                  placeholder="e.g., Analyze quarterly financial figures, generate executive report, and notify the manager."
                  rows={4}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: 8,
                    background: 'var(--surface-0)',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--text-primary)',
                    fontSize: 13,
                    resize: 'none',
                    outline: 'none',
                  }}
                />
              </div>

              {/* Optional File Attachment */}
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                  Attach Document / Dataset (Optional)
                </label>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <label
                    className="btn btn-secondary btn-sm"
                    style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
                  >
                    <Upload size={14} /> {uploading ? 'Uploading…' : 'Upload File'}
                    <input
                      type="file"
                      style={{ display: 'none' }}
                      onChange={handleFileUpload}
                      disabled={uploading}
                    />
                  </label>
                  {selectedFileName && (
                    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.25)', padding: '3px 8px', borderRadius: 6 }}>
                      <CheckCircle2 size={13} color="var(--accent-emerald)" />
                      <span style={{ fontSize: 12, color: 'var(--accent-emerald)', fontWeight: 600 }}>
                        {selectedFileName}
                      </span>
                      <button
                        type="button"
                        onClick={() => { setSelectedFileId(null); setSelectedFileName(null); }}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex', alignItems: 'center', color: 'var(--text-muted)' }}
                        title="Remove file"
                      >
                        <XCircle size={13} />
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {errorMessage && (
                <div style={{
                  padding: '8px 12px',
                  borderRadius: 6,
                  background: 'rgba(239, 68, 68, 0.1)',
                  color: 'var(--accent-rose)',
                  fontSize: 12,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}>
                  <AlertCircle size={14} /> {errorMessage}
                </div>
              )}

              <button
                onClick={handleCreateAndRun}
                disabled={!objective.trim() || isExecuting}
                className="btn btn-primary"
                style={{
                  padding: '10px 16px',
                  fontSize: 13,
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                  marginTop: 6,
                }}
              >
                {isExecuting ? (
                  <>
                    <span className="spinner" style={{ width: 14, height: 14 }} />
                    Supervisor Executing Pipeline…
                  </>
                ) : (
                  <>
                    <Play size={15} />
                    Plan & Execute with Multi-Agent Team
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Recent Task Sessions List */}
          <div className="card" style={{ padding: 20 }}>
            <h3 style={{ fontSize: 14, fontWeight: 700, margin: '0 0 14px', color: 'var(--text-primary)' }}>
              Recent Orchestrations ({sessions.length})
            </h3>

            {isLoading ? (
              <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)' }}>
                <span className="spinner" /> Loading tasks…
              </div>
            ) : sessions.length === 0 ? (
              <div style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', padding: '16px 0' }}>
                No active orchestration sessions. Create your first task above.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 400, overflowY: 'auto' }}>
                {sessions.map((s: any) => {
                  const isSelected = s.id === activeSessionId
                  return (
                    <div
                      key={s.id}
                      onClick={() => loadSessionDetails(s.id)}
                      style={{
                        padding: '10px 14px',
                        borderRadius: 8,
                        background: isSelected ? 'var(--surface-2)' : 'var(--surface-0)',
                        border: isSelected ? '1px solid var(--primary)' : '1px solid var(--border-subtle)',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', maxWidth: '70%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {s.objective}
                        </span>
                        <StatusBadge
                          status={s.status === 'COMPLETED' ? 'success' : s.status === 'RUNNING' ? 'running' : 'info'}
                          label={s.status}
                        />
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 11, color: 'var(--text-muted)' }}>
                        <span>{new Date(s.created_at).toLocaleDateString()}</span>
                        {s.total_tokens_used ? <span>{s.total_tokens_used} tokens</span> : null}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Active Session Workspace (Pipeline or Task Table) */}
        <div className="card" style={{ padding: 24 }}>
          {activeSession ? (
            <div>
              {/* Session Top Bar: Distinct Orchestration Workflow Status */}
              <div style={{
                paddingBottom: 16,
                borderBottom: '1px solid var(--border-subtle)',
                marginBottom: 18,
              }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  justifyContent: 'space-between',
                  gap: 16,
                  marginBottom: 12,
                }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        Orchestration Workflow Status:
                      </span>
                      <StatusBadge
                        status={
                          activeSession.status === 'COMPLETED' ? 'success'
                          : activeSession.status === 'RUNNING' ? 'running'
                          : activeSession.status === 'AWAITING_APPROVAL' ? 'warning'
                          : (activeSession.status === 'FAILED' || activeSession.status === 'CANCELLED') ? 'error'
                          : 'info'
                        }
                        label={activeSession.status}
                      />
                      <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                        Session ID: {activeSession.id}
                      </span>
                    </div>
                    <h2 style={{ fontSize: 17, fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                      {activeSession.objective}
                    </h2>
                  </div>

                  <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                    {activeSession.status !== 'COMPLETED' && (
                      <button
                        onClick={() => handleStartSession(activeSession.id)}
                        disabled={isExecuting}
                        className="btn btn-primary btn-sm"
                        style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                      >
                        <Play size={13} /> {isExecuting ? 'Running…' : 'Run / Resume'}
                      </button>
                    )}
                    <button
                      onClick={() => navigate('/executions')}
                      className="btn btn-ghost btn-sm"
                      style={{ display: 'flex', alignItems: 'center', gap: 4 }}
                    >
                      <ExternalLink size={13} /> Full Logs
                    </button>
                  </div>
                </div>

                {/* Workflow Execution Progress Summary */}
                {activeTasks.length > 0 && (() => {
                  const completedCount = activeTasks.filter(t => t.status === 'COMPLETED').length
                  const failedCount = activeTasks.filter(t => t.status === 'FAILED' || t.status === 'BLOCKED' || t.status === 'CANCELLED').length
                  const runningCount = activeTasks.filter(t => t.status === 'RUNNING').length
                  const awaitingCount = activeTasks.filter(t => t.status === 'AWAITING_APPROVAL' || t.awaiting_approval).length
                  const percent = Math.round((completedCount / activeTasks.length) * 100)

                  return (
                    <div style={{
                      padding: '10px 14px',
                      borderRadius: 8,
                      background: 'var(--surface-1)',
                      border: '1px solid var(--border-subtle)',
                      display: 'flex',
                      flexWrap: 'wrap',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 12,
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 16, fontSize: 12 }}>
                        <span>
                          <strong style={{ color: 'var(--text-primary)' }}>Task Progress:</strong>{' '}
                          <span style={{ color: 'var(--accent-emerald)', fontWeight: 700 }}>{completedCount}</span> / {activeTasks.length} Completed ({percent}%)
                        </span>
                        {runningCount > 0 && (
                          <span style={{ color: 'var(--primary)', display: 'flex', alignItems: 'center', gap: 4 }}>
                            <RefreshCw size={12} className="animate-spin" /> {runningCount} In Progress
                          </span>
                        )}
                        {awaitingCount > 0 && (
                          <span style={{ color: 'var(--accent-amber)', display: 'flex', alignItems: 'center', gap: 4 }}>
                            <Shield size={12} /> {awaitingCount} Awaiting Approval
                          </span>
                        )}
                        {failedCount > 0 && (
                          <span style={{ color: 'var(--accent-rose)', display: 'flex', alignItems: 'center', gap: 4 }}>
                            <AlertCircle size={12} /> {failedCount} Blocked/Failed
                          </span>
                        )}
                      </div>

                      {/* Mini Progress Bar */}
                      <div style={{
                        width: 140,
                        height: 6,
                        borderRadius: 3,
                        background: 'var(--surface-2)',
                        overflow: 'hidden',
                      }}>
                        <div style={{
                          width: `${percent}%`,
                          height: '100%',
                          background: failedCount > 0 ? 'var(--accent-rose)' : 'var(--accent-emerald)',
                          transition: 'width 0.3s ease',
                        }} />
                      </div>
                    </div>
                  )
                })()}
              </div>

              {/* View Mode Toggle and Filter Controls */}
              <div style={{
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 12,
                marginBottom: 18,
                padding: '10px 14px',
                background: 'var(--surface-0)',
                borderRadius: 8,
                border: '1px solid var(--border-subtle)',
              }}>
                {/* View Mode Switcher */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <button
                    onClick={() => setViewMode('pipeline')}
                    className={`btn btn-xs ${viewMode === 'pipeline' ? 'btn-primary' : 'btn-ghost'}`}
                    style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 10px', fontSize: 12 }}
                  >
                    <GitFork size={13} /> Pipeline Steps ({activeTasks.length})
                  </button>
                  <button
                    onClick={() => setViewMode('table')}
                    className={`btn btn-xs ${viewMode === 'table' ? 'btn-primary' : 'btn-ghost'}`}
                    style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 10px', fontSize: 12 }}
                  >
                    <List size={13} /> Task Manager Table
                  </button>
                </div>

                {/* Filters */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  {/* Search */}
                  <div style={{ position: 'relative' }}>
                    <Search size={13} style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                    <input
                      type="text"
                      placeholder="Search tasks…"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      style={{
                        padding: '4px 8px 4px 26px',
                        borderRadius: 6,
                        background: 'var(--surface-1)',
                        border: '1px solid var(--border-subtle)',
                        fontSize: 12,
                        color: 'var(--text-primary)',
                        width: 140,
                        outline: 'none',
                      }}
                    />
                  </div>

                  {/* Status Filter */}
                  <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    style={{
                      padding: '4px 8px',
                      borderRadius: 6,
                      background: 'var(--surface-1)',
                      border: '1px solid var(--border-subtle)',
                      fontSize: 12,
                      color: 'var(--text-secondary)',
                      outline: 'none',
                    }}
                  >
                    <option value="ALL">All Statuses</option>
                    <option value="COMPLETED">Completed</option>
                    <option value="RUNNING">In Progress</option>
                    <option value="AWAITING_APPROVAL">Awaiting Approval</option>
                    <option value="PENDING">Pending / Ready</option>
                    <option value="FAILED">Failed / Cancelled</option>
                  </select>

                  {/* Priority Filter */}
                  <select
                    value={priorityFilter}
                    onChange={(e) => setPriorityFilter(e.target.value)}
                    style={{
                      padding: '4px 8px',
                      borderRadius: 6,
                      background: 'var(--surface-1)',
                      border: '1px solid var(--border-subtle)',
                      fontSize: 12,
                      color: 'var(--text-secondary)',
                      outline: 'none',
                    }}
                  >
                    <option value="ALL">All Priorities</option>
                    <option value="1">Priority 1</option>
                    <option value="2">Priority 2</option>
                    <option value="3">Priority 3+</option>
                  </select>
                </div>
              </div>

              {/* View 1: Pipeline DAG Steps View */}
              {viewMode === 'pipeline' && (
                <div style={{ marginBottom: 24 }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    {filteredTasks.length === 0 ? (
                      <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
                        No tasks match the active filters.
                      </div>
                    ) : (
                      filteredTasks.map((task, idx) => {
                        const isDone = task.status === 'COMPLETED'
                        const isRunning = task.status === 'RUNNING'
                        const isFailed = task.status === 'FAILED' || task.status === 'CANCELLED' || task.status === 'BLOCKED'
                        const isAwaiting = task.status === 'AWAITING_APPROVAL' || task.awaiting_approval
                        const canRetry = isFailed
                        const canCancel = ['PENDING', 'READY', 'RUNNING', 'AWAITING_APPROVAL'].includes(task.status)

                        return (
                          <div
                            key={task.id}
                            style={{
                              padding: 16,
                              borderRadius: 10,
                              background: 'var(--surface-0)',
                              border: isRunning
                                ? '1px solid var(--primary)'
                                : isDone
                                  ? '1px solid var(--accent-emerald)'
                                  : isFailed
                                    ? '1px solid var(--accent-rose)'
                                    : isAwaiting
                                      ? '1px solid var(--accent-amber)'
                                      : '1px solid var(--border-subtle)',
                              display: 'flex',
                              alignItems: 'flex-start',
                              gap: 14,
                            }}
                          >
                            {/* Step Number / Icon */}
                            <div style={{
                              width: 30, height: 30, borderRadius: '50%',
                              background: isDone
                                ? 'rgba(16, 185, 129, 0.15)'
                                : isRunning
                                  ? 'rgba(99, 102, 241, 0.15)'
                                  : isFailed
                                    ? 'rgba(239, 68, 68, 0.15)'
                                    : isAwaiting
                                      ? 'rgba(245, 158, 11, 0.15)'
                                      : 'var(--surface-2)',
                              color: isDone
                                ? 'var(--accent-emerald)'
                                : isRunning
                                  ? 'var(--primary)'
                                  : isFailed
                                    ? 'var(--accent-rose)'
                                    : isAwaiting
                                      ? 'var(--accent-amber)'
                                      : 'var(--text-muted)',
                              display: 'flex', alignItems: 'center', justifyContent: 'center',
                              flexShrink: 0,
                              fontWeight: 700,
                              fontSize: 12,
                            }}>
                              {isDone ? (
                                <Check size={16} />
                              ) : isRunning ? (
                                <RefreshCw size={14} className="animate-spin" />
                              ) : isFailed ? (
                                <AlertCircle size={15} />
                              ) : isAwaiting ? (
                                <Shield size={14} />
                              ) : (
                                idx + 1
                              )}
                            </div>

                            {/* Step Details */}
                            <div style={{ flex: 1 }}>
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4, flexWrap: 'wrap', gap: 6 }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                  <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
                                    {task.name}
                                  </span>
                                  {task.priority && (
                                    <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, background: 'var(--surface-2)', color: 'var(--text-muted)', fontWeight: 600 }}>
                                      P{task.priority}
                                    </span>
                                  )}
                                </div>

                                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                  <StatusBadge
                                    status={isDone ? 'success' : isRunning ? 'running' : isFailed ? 'error' : isAwaiting ? 'warning' : 'info'}
                                    label={task.status}
                                  />

                                  {/* Action Buttons */}
                                  <button
                                    onClick={() => setInspectingTask(task)}
                                    className="btn btn-ghost btn-xs"
                                    style={{ padding: '3px 8px', fontSize: 11, display: 'flex', alignItems: 'center', gap: 4 }}
                                    title="Inspect Task Output and Metadata"
                                  >
                                    <Eye size={12} /> Inspect
                                  </button>

                                  {canRetry && (
                                    <button
                                      onClick={() => handleRetryTask(task.id)}
                                      disabled={actionLoadingTaskId === task.id}
                                      className="btn btn-secondary btn-xs"
                                      style={{ padding: '3px 8px', fontSize: 11, display: 'flex', alignItems: 'center', gap: 4 }}
                                    >
                                      {actionLoadingTaskId === task.id ? (
                                        <RefreshCw size={11} className="animate-spin" />
                                      ) : (
                                        <RotateCcw size={11} />
                                      )}
                                      Retry
                                    </button>
                                  )}

                                  {canCancel && (
                                    <button
                                      onClick={() => handleCancelTask(task.id)}
                                      disabled={actionLoadingTaskId === task.id}
                                      className="btn btn-ghost btn-xs text-rose-400"
                                      style={{ padding: '3px 8px', fontSize: 11, display: 'flex', alignItems: 'center', gap: 4 }}
                                    >
                                      {actionLoadingTaskId === task.id ? (
                                        <RefreshCw size={11} className="animate-spin" />
                                      ) : (
                                        <XCircle size={11} />
                                      )}
                                      Cancel
                                    </button>
                                  )}
                                </div>
                              </div>

                              <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '0 0 8px' }}>
                                {task.description}
                              </p>

                               {/* Prerequisites & Upstream Blocking Indicators */}
                               {(() => {
                                 const depDetails = (task.dependencies || []).map((depKey) => {
                                   const parentTask = activeTasks.find((t) => t.task_key === depKey)
                                   return {
                                     key: depKey,
                                     name: parentTask?.name || depKey,
                                     status: parentTask?.status || 'UNKNOWN',
                                     error: parentTask?.error_message,
                                   }
                                 })

                                 const blockedByDep = depDetails.find(
                                   (d) => d.status === 'FAILED' || d.status === 'BLOCKED' || d.status === 'CANCELLED'
                                 )
                                 const waitingOnDep = depDetails.find(
                                   (d) => d.status === 'RUNNING' || d.status === 'PENDING' || d.status === 'READY' || d.status === 'AWAITING_APPROVAL'
                                 )

                                 return (
                                   <>
                                     {depDetails.length > 0 && (
                                       <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8, fontSize: 11, flexWrap: 'wrap' }}>
                                         <span style={{ color: 'var(--text-muted)' }}>Prerequisites:</span>
                                         {depDetails.map((d, dIdx) => (
                                           <span
                                             key={dIdx}
                                             style={{
                                               padding: '2px 7px',
                                               borderRadius: 4,
                                               background: d.status === 'COMPLETED'
                                                 ? 'rgba(16, 185, 129, 0.12)'
                                                 : (d.status === 'FAILED' || d.status === 'BLOCKED')
                                                   ? 'rgba(239, 68, 68, 0.12)'
                                                   : 'var(--surface-2)',
                                               color: d.status === 'COMPLETED'
                                                 ? 'var(--accent-emerald)'
                                                 : (d.status === 'FAILED' || d.status === 'BLOCKED')
                                                   ? 'var(--accent-rose)'
                                                   : 'var(--text-secondary)',
                                               display: 'inline-flex',
                                               alignItems: 'center',
                                               gap: 4,
                                             }}
                                           >
                                             <span>{d.name}</span>
                                             <span style={{ fontSize: 9.5, opacity: 0.85 }}>({d.status})</span>
                                           </span>
                                         ))}
                                       </div>
                                     )}

                                     {/* Explicit Upstream Blocking Warning */}
                                     {(task.status === 'BLOCKED' || (task.status === 'PENDING' && blockedByDep)) && (
                                       <div style={{
                                         marginTop: 6,
                                         marginBottom: 8,
                                         padding: '8px 12px',
                                         borderRadius: 6,
                                         background: 'rgba(239, 68, 68, 0.1)',
                                         border: '1px solid rgba(239, 68, 68, 0.25)',
                                         fontSize: 12,
                                         color: 'var(--accent-rose)',
                                         display: 'flex',
                                         alignItems: 'center',
                                         gap: 8,
                                       }}>
                                         <AlertCircle size={15} style={{ flexShrink: 0 }} />
                                         <div>
                                           <strong>Blocked by prerequisite:</strong> {blockedByDep ? `${blockedByDep.name} (${blockedByDep.key})` : 'Upstream task'} &mdash; {task.error_message || blockedByDep?.error || 'Prerequisite execution failed.'}
                                         </div>
                                       </div>
                                     )}

                                     {/* Waiting on Prerequisite Notice */}
                                     {(task.status === 'PENDING' || task.status === 'READY') && waitingOnDep && !blockedByDep && (
                                       <div style={{
                                         marginTop: 6,
                                         marginBottom: 8,
                                         padding: '6px 10px',
                                         borderRadius: 6,
                                         background: 'rgba(14, 165, 233, 0.08)',
                                         border: '1px solid rgba(14, 165, 233, 0.2)',
                                         fontSize: 11.5,
                                         color: 'var(--accent-sky)',
                                         display: 'flex',
                                         alignItems: 'center',
                                         gap: 6,
                                       }}>
                                         <Clock size={13} style={{ flexShrink: 0 }} />
                                         <span>Waiting on prerequisite: <strong>{waitingOnDep.name}</strong> ({waitingOnDep.status})</span>
                                       </div>
                                     )}
                                   </>
                                 )
                               })()}

                               {/* Task Lifecycle Execution Summary (No Domain Data Analytics Injection) */}
                               {task.status === 'COMPLETED' && (() => {
                                 const out = task.output_data?.output || task.output_data || {}
                                 const artifacts = task.output_data?.artifacts || out.artifacts || []
                                 const execDuration = task.output_data?.execution_duration_ms || out.execution_duration_ms

                                 return (
                                   <div style={{
                                     marginTop: 8,
                                     padding: '10px 14px',
                                     borderRadius: 8,
                                     background: 'var(--surface-1)',
                                     border: '1px solid var(--border-subtle)',
                                     display: 'flex',
                                     flexDirection: 'column',
                                     gap: 8,
                                   }}>
                                     <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 6 }}>
                                       <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent-emerald)', display: 'flex', alignItems: 'center', gap: 6 }}>
                                         <Check size={14} /> Execution Succeeded by {task.assigned_agent_name || task.assigned_agent_type || 'Agent'}
                                       </span>
                                       <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 11, color: 'var(--text-muted)' }}>
                                         {execDuration && (
                                           <span>Duration: {(execDuration / 1000).toFixed(2)}s</span>
                                         )}
                                         <span>Attempts: {task.attempt_count || 1}</span>
                                       </div>
                                     </div>

                                     {/* Domain-Specific Human-Readable Summary & KPI Highlights */}
                                     {(() => {
                                       const agentType = (task.assigned_agent_type || '').toLowerCase()
                                       const bMetrics = out.business_metrics
                                       const summaryText = out.summary || out.executive_summary || out.message || out.answer || (typeof out === 'string' ? out : null)

                                       return (
                                         <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 4 }}>
                                           {/* Financial KPI Cards for Data Analysis */}
                                           {bMetrics?.has_financial_metrics && (
                                             <div style={{
                                               display: 'grid',
                                               gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))',
                                               gap: 8,
                                               padding: '8px 10px',
                                               borderRadius: 6,
                                               background: 'var(--surface-0)',
                                               border: '1px solid var(--border-subtle)',
                                             }}>
                                               <div>
                                                 <span style={{ fontSize: 9.5, color: 'var(--text-muted)', display: 'block', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Revenue</span>
                                                 <span style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--accent-emerald)' }}>
                                                   ${Number(bMetrics.total_revenue || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                                 </span>
                                               </div>
                                               {bMetrics.total_cost != null && (
                                                 <div>
                                                   <span style={{ fontSize: 9.5, color: 'var(--text-muted)', display: 'block', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Costs</span>
                                                   <span style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--text-secondary)' }}>
                                                     ${Number(bMetrics.total_cost || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                                   </span>
                                                 </div>
                                               )}
                                               {bMetrics.gross_profit != null && (
                                                 <div>
                                                   <span style={{ fontSize: 9.5, color: 'var(--text-muted)', display: 'block', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Profit</span>
                                                   <span style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--primary)' }}>
                                                     ${Number(bMetrics.gross_profit || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                                   </span>
                                                 </div>
                                               )}
                                               {bMetrics.gross_margin_pct != null && (
                                                 <div>
                                                   <span style={{ fontSize: 9.5, color: 'var(--text-muted)', display: 'block', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Margin</span>
                                                   <span style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--accent-sky)' }}>
                                                     {bMetrics.gross_margin_pct}%
                                                   </span>
                                                 </div>
                                               )}
                                             </div>
                                           )}

                                           {/* Email Summary Preview */}
                                           {agentType === 'email' && (out.subject || out.draft?.subject) && (
                                             <div style={{
                                               padding: '8px 10px',
                                               borderRadius: 6,
                                               background: 'var(--surface-0)',
                                               border: '1px solid var(--border-subtle)',
                                               fontSize: 11.5,
                                             }}>
                                               <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>
                                                 Subject: {out.subject || out.draft?.subject}
                                               </div>
                                               <div style={{ color: 'var(--text-muted)' }}>
                                                 Recipients: {(out.recipients || out.draft?.recipients || []).join(', ') || 'Default'}
                                               </div>
                                             </div>
                                           )}

                                           {/* Report Generation Downloads Toolbar */}
                                           {agentType === 'report_generation' && out.downloads && Object.keys(out.downloads).length > 0 && (
                                             <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                                               <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Download Formats:</span>
                                               {Object.entries(out.downloads).map(([fmt, url]: [string, any], dlIdx: number) => (
                                                 <a
                                                   key={dlIdx}
                                                   href={String(url)}
                                                   target="_blank"
                                                   rel="noopener noreferrer"
                                                   className="btn btn-ghost btn-xs"
                                                   style={{
                                                     fontSize: 10.5,
                                                     padding: '1px 6px',
                                                     borderRadius: 4,
                                                     background: 'var(--surface-0)',
                                                     border: '1px solid var(--border-subtle)',
                                                     color: 'var(--accent-sky)',
                                                     textDecoration: 'none',
                                                   }}
                                                 >
                                                   {fmt.toUpperCase()}
                                                 </a>
                                               ))}
                                             </div>
                                           )}

                                           {/* Formatted Markdown Body */}
                                           {summaryText && (
                                             <div style={{
                                               fontSize: 12,
                                               color: 'var(--text-secondary)',
                                               lineHeight: 1.6,
                                               padding: '8px 12px',
                                               background: 'var(--surface-0)',
                                               borderRadius: 6,
                                               border: '1px solid var(--border-subtle)',
                                               maxHeight: 220,
                                               overflowY: 'auto',
                                             }}>
                                               <MarkdownView content={summaryText} />
                                             </div>
                                           )}
                                         </div>
                                       )
                                     })()}

                                     {/* Generated Artifacts Link */}
                                     {Array.isArray(artifacts) && artifacts.length > 0 && (
                                       <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginTop: 2 }}>
                                         <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Generated Artifact(s):</span>
                                         {artifacts.map((art: any, aIdx: number) => (
                                           <button
                                             key={aIdx}
                                             onClick={() => navigate('/reports')}
                                             className="btn btn-ghost btn-xs"
                                             style={{
                                               fontSize: 11,
                                               padding: '2px 8px',
                                               borderRadius: 4,
                                               background: 'rgba(99, 102, 241, 0.1)',
                                               color: 'var(--primary)',
                                               border: '1px solid rgba(99, 102, 241, 0.25)',
                                               display: 'flex',
                                               alignItems: 'center',
                                               gap: 4,
                                             }}
                                             title="View in Reports"
                                           >
                                             <FileText size={12} /> {art.name || art.path || 'Report Artifact'} <ExternalLink size={10} />
                                           </button>
                                         ))}
                                       </div>
                                     )}

                                     {/* Collapsible Technical Output Details */}
                                     <details style={{ marginTop: 2 }}>
                                       <summary style={{ fontSize: 11, color: 'var(--text-muted)', cursor: 'pointer' }}>
                                         Technical Details (Collapsible Raw JSON)
                                       </summary>
                                       <pre style={{
                                         marginTop: 6,
                                         padding: 8,
                                         borderRadius: 4,
                                         background: 'var(--surface-0)',
                                         fontSize: 10.5,
                                         color: 'var(--text-secondary)',
                                         overflowX: 'auto',
                                         maxHeight: 180,
                                       }}>
                                         {JSON.stringify(task.output_data, null, 2)}
                                       </pre>
                                     </details>
                                   </div>
                                 )
                               })()}

                              {/* Failure Message */}
                              {isFailed && (
                                <div style={{
                                  marginTop: 8,
                                  padding: '8px 12px',
                                  borderRadius: 6,
                                  background: 'rgba(239, 68, 68, 0.1)',
                                  border: '1px solid rgba(239, 68, 68, 0.2)',
                                  fontSize: 12,
                                  color: 'var(--accent-rose)',
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: 6,
                                }}>
                                  <AlertCircle size={14} /> Execution error: {task.error_message || 'Task failed.'}
                                </div>
                              )}

                              {/* Pending Approval Warning */}
                              {isAwaiting && (
                                <div style={{
                                  marginTop: 8,
                                  padding: '8px 12px',
                                  borderRadius: 6,
                                  background: 'rgba(245, 158, 11, 0.1)',
                                  border: '1px solid rgba(245, 158, 11, 0.2)',
                                  fontSize: 12,
                                  color: 'var(--accent-amber)',
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'space-between',
                                }}>
                                  <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                    <Shield size={14} /> Awaiting human authorization before side-effect execution.
                                  </span>
                                  <button
                                    onClick={() => navigate('/approvals')}
                                    className="btn btn-warning btn-xs"
                                    style={{ padding: '2px 8px', fontSize: 11 }}
                                  >
                                    Go to Approvals
                                  </button>
                                </div>
                              )}
                            </div>
                          </div>
                        )
                      })
                    )}
                  </div>
                </div>
              )}

              {/* View 2: Task Manager Table / List View */}
              {viewMode === 'table' && (
                <div style={{ marginBottom: 24, overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-subtle)', textAlign: 'left', color: 'var(--text-muted)' }}>
                        <th style={{ padding: '10px 12px', fontWeight: 600 }}>Task Key / Name</th>
                        <th style={{ padding: '10px 12px', fontWeight: 600 }}>Assigned Agent</th>
                        <th style={{ padding: '10px 12px', fontWeight: 600 }}>Priority</th>
                        <th style={{ padding: '10px 12px', fontWeight: 600 }}>Task Status</th>
                        <th style={{ padding: '10px 12px', fontWeight: 600 }}>Prerequisites & Blockers</th>
                        <th style={{ padding: '10px 12px', fontWeight: 600 }}>Attempts</th>
                        <th style={{ padding: '10px 12px', fontWeight: 600 }}>Updated</th>
                        <th style={{ padding: '10px 12px', fontWeight: 600, textAlign: 'right' }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredTasks.length === 0 ? (
                        <tr>
                          <td colSpan={8} style={{ padding: '24px 12px', textAlign: 'center', color: 'var(--text-muted)' }}>
                            No tasks match the active filters.
                          </td>
                        </tr>
                      ) : (
                        filteredTasks.map((task) => {
                          const isFailed = task.status === 'FAILED' || task.status === 'CANCELLED' || task.status === 'BLOCKED'
                          const canRetry = isFailed
                          const canCancel = ['PENDING', 'READY', 'RUNNING', 'AWAITING_APPROVAL'].includes(task.status)

                          const depDetails = (task.dependencies || []).map((depKey) => {
                            const parentTask = activeTasks.find((t) => t.task_key === depKey)
                            return {
                              key: depKey,
                              name: parentTask?.name || depKey,
                              status: parentTask?.status || 'UNKNOWN',
                            }
                          })
                          const blockedBy = depDetails.find(d => d.status === 'FAILED' || d.status === 'BLOCKED' || d.status === 'CANCELLED')

                          return (
                            <tr
                              key={task.id}
                              style={{
                                borderBottom: '1px solid var(--border-subtle)',
                                background: 'var(--surface-0)',
                                transition: 'background 0.15s ease',
                              }}
                            >
                              <td style={{ padding: '12px' }}>
                                <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{task.name}</div>
                                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{task.task_key}</div>
                              </td>
                              <td style={{ padding: '12px' }}>
                                <span style={{ padding: '2px 8px', borderRadius: 4, background: 'var(--surface-2)', color: 'var(--primary)', fontSize: 11 }}>
                                  {task.assigned_agent_name || task.assigned_agent_type || 'Worker'}
                                </span>
                              </td>
                              <td style={{ padding: '12px' }}>
                                <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>
                                  P{task.priority ?? 1}
                                </span>
                              </td>
                              <td style={{ padding: '12px' }}>
                                <StatusBadge
                                  status={task.status === 'COMPLETED' ? 'success' : task.status === 'RUNNING' ? 'running' : isFailed ? 'error' : 'info'}
                                  label={task.status}
                                />
                              </td>
                              <td style={{ padding: '12px' }}>
                                {depDetails.length > 0 ? (
                                  <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
                                    {depDetails.map((dep, dIdx) => (
                                      <span
                                        key={dIdx}
                                        style={{
                                          fontSize: 10.5,
                                          padding: '1px 6px',
                                          borderRadius: 3,
                                          background: dep.status === 'COMPLETED'
                                            ? 'rgba(16, 185, 129, 0.12)'
                                            : (dep.status === 'FAILED' || dep.status === 'BLOCKED')
                                              ? 'rgba(239, 68, 68, 0.12)'
                                              : 'var(--surface-2)',
                                          color: dep.status === 'COMPLETED'
                                            ? 'var(--accent-emerald)'
                                            : (dep.status === 'FAILED' || dep.status === 'BLOCKED')
                                              ? 'var(--accent-rose)'
                                              : 'var(--text-muted)',
                                        }}
                                      >
                                        {dep.name} ({dep.status})
                                      </span>
                                    ))}
                                    {blockedBy && (
                                      <span style={{ fontSize: 10.5, color: 'var(--accent-rose)', fontWeight: 600 }}>
                                        ⚠️ Blocked
                                      </span>
                                    )}
                                  </div>
                                ) : (
                                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>None (Root)</span>
                                )}
                              </td>
                              <td style={{ padding: '12px', color: 'var(--text-secondary)', fontSize: 11 }}>
                                {task.attempt_count || 1}
                              </td>
                              <td style={{ padding: '12px', color: 'var(--text-muted)', fontSize: 11 }}>
                                {task.updated_at ? new Date(task.updated_at).toLocaleTimeString() : '—'}
                              </td>
                              <td style={{ padding: '12px', textAlign: 'right' }}>
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 6 }}>
                                  <button
                                    onClick={() => setInspectingTask(task)}
                                    className="btn btn-ghost btn-xs"
                                    style={{ padding: '3px 8px', fontSize: 11, display: 'flex', alignItems: 'center', gap: 3 }}
                                  >
                                    <Eye size={12} /> Inspect
                                  </button>

                                  {canRetry && (
                                    <button
                                      onClick={() => handleRetryTask(task.id)}
                                      disabled={actionLoadingTaskId === task.id}
                                      className="btn btn-secondary btn-xs"
                                      style={{ padding: '3px 8px', fontSize: 11, display: 'flex', alignItems: 'center', gap: 3 }}
                                    >
                                      {actionLoadingTaskId === task.id ? <RefreshCw size={11} className="animate-spin" /> : <RotateCcw size={11} />}
                                      Retry
                                    </button>
                                  )}

                                  {canCancel && (
                                    <button
                                      onClick={() => handleCancelTask(task.id)}
                                      disabled={actionLoadingTaskId === task.id}
                                      className="btn btn-ghost btn-xs text-rose-400"
                                      style={{ padding: '3px 8px', fontSize: 11, display: 'flex', alignItems: 'center', gap: 3 }}
                                    >
                                      {actionLoadingTaskId === task.id ? <RefreshCw size={11} className="animate-spin" /> : <XCircle size={11} />}
                                      Cancel
                                    </button>
                                  )}
                                </div>
                              </td>
                            </tr>
                          )
                        })
                      )}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Execution Metrics & Summary */}
              {activeSession.result_summary && (
                <div style={{
                  padding: 16,
                  borderRadius: 10,
                  background: 'var(--surface-0)',
                  border: '1px solid var(--border-subtle)',
                }}>
                  <h4 style={{ fontSize: 13, fontWeight: 700, margin: '0 0 8px', color: 'var(--text-primary)' }}>
                    Result Summary & Metrics
                  </h4>
                  <div style={{ display: 'flex', gap: 20, fontSize: 12, color: 'var(--text-secondary)' }}>
                    <span><strong>Total Tasks:</strong> {activeSession.result_summary.total_tasks}</span>
                    <span><strong>Completed:</strong> {activeSession.result_summary.completed_tasks}</span>
                    <span><strong>Status:</strong> {activeSession.result_summary.status}</span>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
              <Layers size={36} style={{ marginBottom: 12, opacity: 0.5 }} />
              <p style={{ margin: 0, fontSize: 14 }}>
                Select a task on the left or create a new enterprise goal to view its multi-agent pipeline.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Task Inspection Modal */}
      {inspectingTask && (
        <Modal
          open={Boolean(inspectingTask)}
          title={`Task Inspection: ${inspectingTask.name}`}
          onClose={() => setInspectingTask(null)}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 10, background: 'var(--surface-1)', padding: 12, borderRadius: 8 }}>
              <div>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Task Key</span>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{inspectingTask.task_key}</div>
              </div>
              <div>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Task Status</span>
                <div><StatusBadge status={inspectingTask.status} label={inspectingTask.status} /></div>
              </div>
              <div>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Overall Workflow</span>
                <div>
                  <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 4, background: 'var(--surface-2)', color: 'var(--text-secondary)', fontWeight: 600 }}>
                    {activeSession?.status || 'UNKNOWN'}
                  </span>
                </div>
              </div>
              <div>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Assigned Agent</span>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--primary)' }}>
                  {inspectingTask.assigned_agent_name || inspectingTask.assigned_agent_type || 'Worker Agent'}
                </div>
              </div>
              <div>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Priority</span>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>Priority {inspectingTask.priority ?? 1}</div>
              </div>
              <div>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Attempts</span>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{inspectingTask.attempt_count || 1}</div>
              </div>
            </div>

            {/* Timestamps */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 8, fontSize: 11, background: 'var(--surface-0)', padding: 10, borderRadius: 6, border: '1px solid var(--border-subtle)' }}>
              <div>
                <span style={{ color: 'var(--text-muted)' }}>Created:</span>{' '}
                <span style={{ color: 'var(--text-secondary)' }}>{inspectingTask.created_at ? new Date(inspectingTask.created_at).toLocaleTimeString() : '—'}</span>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)' }}>Started:</span>{' '}
                <span style={{ color: 'var(--text-secondary)' }}>{inspectingTask.started_at ? new Date(inspectingTask.started_at).toLocaleTimeString() : '—'}</span>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)' }}>Completed:</span>{' '}
                <span style={{ color: 'var(--text-secondary)' }}>{inspectingTask.completed_at ? new Date(inspectingTask.completed_at).toLocaleTimeString() : '—'}</span>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)' }}>Updated:</span>{' '}
                <span style={{ color: 'var(--text-secondary)' }}>{inspectingTask.updated_at ? new Date(inspectingTask.updated_at).toLocaleTimeString() : '—'}</span>
              </div>
            </div>

            <div>
              <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)' }}>Description</span>
              <div style={{ fontSize: 12, color: 'var(--text-primary)', marginTop: 4 }}>{inspectingTask.description}</div>
            </div>

            {inspectingTask.dependencies && inspectingTask.dependencies.length > 0 && (
              <div>
                <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)' }}>Prerequisites & Dependency Status</span>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
                  {inspectingTask.dependencies.map((dep, i) => {
                    const pTask = activeTasks.find(t => t.task_key === dep)
                    return (
                      <span
                        key={i}
                        style={{
                          padding: '2px 8px',
                          borderRadius: 4,
                          background: pTask?.status === 'COMPLETED' ? 'rgba(16, 185, 129, 0.12)' : 'var(--surface-2)',
                          color: pTask?.status === 'COMPLETED' ? 'var(--accent-emerald)' : 'var(--text-muted)',
                          fontSize: 11,
                        }}
                      >
                        {pTask ? `${pTask.name} (${pTask.status})` : dep}
                      </span>
                    )
                  })}
                </div>
              </div>
            )}

            {inspectingTask.error_message && (
              <div style={{ padding: '10px 12px', borderRadius: 6, background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)', color: 'var(--accent-rose)', fontSize: 12 }}>
                <strong>Execution Error:</strong> {inspectingTask.error_message}
              </div>
            )}

            {/* Generated Artifacts */}
            {(() => {
              const out = inspectingTask.output_data?.output || inspectingTask.output_data || {}
              const artifacts = inspectingTask.output_data?.artifacts || out.artifacts || []
              if (!Array.isArray(artifacts) || artifacts.length === 0) return null

              return (
                <div>
                  <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6, display: 'block' }}>
                    Generated Artifacts
                  </span>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {artifacts.map((art: any, aIdx: number) => (
                      <button
                        key={aIdx}
                        onClick={() => navigate('/reports')}
                        className="btn btn-ghost btn-xs"
                        style={{
                          fontSize: 11,
                          padding: '3px 10px',
                          borderRadius: 4,
                          background: 'rgba(99, 102, 241, 0.1)',
                          color: 'var(--primary)',
                          border: '1px solid rgba(99, 102, 241, 0.25)',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 4,
                        }}
                      >
                        <FileText size={12} /> {art.name || art.path || 'Artifact'} &rarr; View in Reports
                      </button>
                    ))}
                  </div>
                </div>
              )
            })()}

            {inspectingTask.output_data && Object.keys(inspectingTask.output_data).length > 0 && (() => {
              const out = inspectingTask.output_data?.output || inspectingTask.output_data || {}
              const agentType = (inspectingTask.assigned_agent_type || '').toLowerCase()
              const bMetrics = out.business_metrics
              const summaryText = out.summary || out.executive_summary || out.message || out.answer || (typeof out === 'string' ? out : null)

              return (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {/* Human-Readable Summary & Key Insights */}
                  <div>
                    <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6, display: 'block' }}>
                      Execution Result & Key Insights
                    </span>

                    {/* KPI Cards for financial data analysis */}
                    {bMetrics?.has_financial_metrics && (
                      <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                        gap: 8,
                        marginBottom: 10,
                      }}>
                        <div style={{ padding: '8px 10px', borderRadius: 6, background: 'var(--surface-0)', border: '1px solid var(--border-subtle)' }}>
                          <span style={{ fontSize: 10, color: 'var(--text-muted)', display: 'block' }}>Total Revenue</span>
                          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent-emerald)' }}>
                            ${Number(bMetrics.total_revenue || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                          </span>
                        </div>
                        {bMetrics.total_cost != null && (
                          <div style={{ padding: '8px 10px', borderRadius: 6, background: 'var(--surface-0)', border: '1px solid var(--border-subtle)' }}>
                            <span style={{ fontSize: 10, color: 'var(--text-muted)', display: 'block' }}>Operating Costs</span>
                            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)' }}>
                              ${Number(bMetrics.total_cost || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                            </span>
                          </div>
                        )}
                        {bMetrics.gross_profit != null && (
                          <div style={{ padding: '8px 10px', borderRadius: 6, background: 'var(--surface-0)', border: '1px solid var(--border-subtle)' }}>
                            <span style={{ fontSize: 10, color: 'var(--text-muted)', display: 'block' }}>Gross Profit</span>
                            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--primary)' }}>
                              ${Number(bMetrics.gross_profit || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                            </span>
                          </div>
                        )}
                        {bMetrics.gross_margin_pct != null && (
                          <div style={{ padding: '8px 10px', borderRadius: 6, background: 'var(--surface-0)', border: '1px solid var(--border-subtle)' }}>
                            <span style={{ fontSize: 10, color: 'var(--text-muted)', display: 'block' }}>Gross Margin</span>
                            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent-sky)' }}>
                              {bMetrics.gross_margin_pct}%
                            </span>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Email Specific Telemetry */}
                    {agentType === 'email' && (out.subject || out.draft?.subject) && (
                      <div style={{ padding: '8px 12px', borderRadius: 6, background: 'var(--surface-0)', border: '1px solid var(--border-subtle)', marginBottom: 10, fontSize: 11.5 }}>
                        <div><strong>Subject:</strong> {out.subject || out.draft?.subject}</div>
                        <div><strong>Recipients:</strong> {(out.recipients || out.draft?.recipients || []).join(', ')}</div>
                        <div><strong>Status:</strong> {out.email_status || out.status || 'Draft Staged'}</div>
                      </div>
                    )}

                    {/* Formatted Markdown Content */}
                    {summaryText ? (
                      <div style={{
                        padding: '10px 14px',
                        borderRadius: 6,
                        background: 'var(--surface-0)',
                        border: '1px solid var(--border-subtle)',
                        fontSize: 12,
                        maxHeight: 280,
                        overflowY: 'auto',
                      }}>
                        <MarkdownView content={summaryText} />
                      </div>
                    ) : (
                      <div style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>
                        Execution completed successfully with verified payload.
                      </div>
                    )}
                  </div>

                  {/* Collapsible Technical Details (Raw JSON) */}
                  <details style={{ marginTop: 4 }}>
                    <summary style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', cursor: 'pointer' }}>
                      Technical Details (Raw JSON Payload)
                    </summary>
                    <pre style={{
                      marginTop: 6,
                      padding: 12,
                      borderRadius: 6,
                      background: 'var(--surface-0)',
                      border: '1px solid var(--border-subtle)',
                      fontSize: 11,
                      color: 'var(--text-secondary)',
                      maxHeight: 220,
                      overflowY: 'auto',
                    }}>
                      {JSON.stringify(inspectingTask.output_data, null, 2)}
                    </pre>
                  </details>
                </div>
              )
            })()}
          </div>
        </Modal>
      )}
    </div>
  )
}
