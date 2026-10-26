import React from 'react'
import { motion } from 'framer-motion'
import { Bot, GitBranch, Zap, DollarSign, Activity, TrendingUp, Clock, CheckCircle2 } from 'lucide-react'
import { useAsync } from '../hooks/useAsync'
import { analyticsApi, healthApi } from '../lib/api'
import { StatCard, ErrorState, SectionHeader, StatusBadge } from '../components/ui'

const cardAnim = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0 },
}

function HealthPanel() {
  const { data: health } = useAsync(() => healthApi.ready(), [], true)

  const items = [
    { label: 'API Server', status: health?.status === 'ready' ? 'ready' : health?.status === 'unreachable' ? 'unreachable' : health?.status || 'checking' },
    { label: 'Database', status: health?.database || (health?.status === 'unreachable' ? 'unreachable' : '—') },
    { label: 'AI Provider', status: health?.llm_engine || (health?.ai_status === 'LIVE' ? 'LIVE' : health?.status === 'ready' ? 'connected' : '—') },
    { label: 'Redis Queue', status: health?.redis || 'not checked' },
  ]

  return (
    <div className="card" style={{ padding: '20px 24px' }}>
      <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 16, color: 'var(--text-primary)' }}>
        System Health
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {items.map(({ label, status }) => (
          <div key={label} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{label}</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span className={`status-dot ${
                status === 'ready' || status === 'connected' || status === 'LIVE' || status?.includes('openai') || status?.includes('anthropic') || status?.includes('gemini') || status?.includes('ready') ? 'active'
                : status === 'unreachable' ? 'error'
                : 'warning'
              }`} />
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{status}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function WorkflowStatsPanel({ stats }: { stats: { succeeded: number; failed: number; cancelled: number; total: number } | null }) {
  const total = stats ? stats.total || 1 : 1
  const succeeded = stats?.succeeded || 0
  const failed = stats?.failed || 0

  const segments = [
    { label: 'Succeeded', value: succeeded, color: '#10b981' },
    { label: 'Failed', value: failed, color: '#f43f5e' },
    { label: 'Other', value: total - succeeded - failed, color: '#475569' },
  ]

  return (
    <div className="card" style={{ padding: '20px 24px' }}>
      <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 16, color: 'var(--text-primary)' }}>
        Execution Outcomes
      </div>

      {stats ? (
        <>
          {/* Simple bar chart */}
          <div style={{ display: 'flex', height: 8, borderRadius: 4, overflow: 'hidden', marginBottom: 16, gap: 2 }}>
            {segments.map(({ label, value, color }) => {
              const pct = Math.round((value / total) * 100)
              if (pct === 0) return null
              return (
                <div key={label} style={{ flex: pct, background: color, transition: 'flex 0.5s ease' }} />
              )
            })}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {segments.map(({ label, value, color }) => (
              <div key={label} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ width: 8, height: 8, borderRadius: 2, background: color }} />
                  <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{label}</span>
                </div>
                <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{value}</span>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>No execution data yet</div>
      )}
    </div>
  )
}

export default function OverviewPage() {
  const { data: summary, isLoading: sumLoading, error: sumErr, refetch } = useAsync(
    () => analyticsApi.summary(), [], true
  )
  const { data: wfStats } = useAsync(() => analyticsApi.workflowStats(), [], true)

  const processedStats = wfStats ? {
    total: wfStats.total_jobs || 0,
    succeeded: wfStats.succeeded_jobs || 0,
    failed: wfStats.failed_jobs || 0,
    cancelled: wfStats.cancelled_jobs || 0,
  } : null

  return (
    <div className="page-container animate-fadeIn">
      <SectionHeader
        title="Overview"
        subtitle="Executive summary of your AI automation platform"
        actions={
          <button className="btn btn-secondary" onClick={refetch} style={{ fontSize: 12 }}>
            <Activity size={13} />
            Refresh
          </button>
        }
      />

      {sumErr && <ErrorState message={sumErr} onRetry={refetch} />}

      {/* KPI Cards */}
      <motion.div
        variants={{ show: { transition: { staggerChildren: 0.07 } } }}
        initial="hidden"
        animate="show"
        className="stat-grid"
      >
        <motion.div variants={cardAnim}>
          <StatCard
            label="Workflows"
            value={summary?.total_workflows ?? null}
            icon={<GitBranch size={16} />}
            accent="#6366f1"
            loading={sumLoading}
          />
        </motion.div>
        <motion.div variants={cardAnim}>
          <StatCard
            label="Agents"
            value={summary?.total_agents ?? null}
            icon={<Bot size={16} />}
            accent="#8b5cf6"
            loading={sumLoading}
          />
        </motion.div>
        <motion.div variants={cardAnim}>
          <StatCard
            label="Total Jobs"
            value={summary?.total_jobs ?? null}
            icon={<Zap size={16} />}
            accent="#0ea5e9"
            loading={sumLoading}
          />
        </motion.div>
        <motion.div variants={cardAnim}>
          <StatCard
            label="Tokens Used"
            value={summary?.total_tokens_consumed !== undefined ? summary.total_tokens_consumed.toLocaleString() : null}
            icon={<TrendingUp size={16} />}
            accent="#10b981"
            loading={sumLoading}
          />
        </motion.div>
        <motion.div variants={cardAnim}>
          <StatCard
            label="Total Cost"
            value={summary?.total_cost_usd !== undefined ? `$${summary.total_cost_usd.toFixed(4)}` : null}
            icon={<DollarSign size={16} />}
            accent="#f59e0b"
            loading={sumLoading}
          />
        </motion.div>
      </motion.div>

      {/* Secondary panels */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16 }}>
        <HealthPanel />
        <WorkflowStatsPanel stats={processedStats} />

        {/* Enterprise Automation Quick Launch */}
        <div className="card" style={{ padding: '20px 24px' }}>
          <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 16, color: 'var(--text-primary)' }}>
            Enterprise Workspaces
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            {[
              { label: 'Chat Assistant', href: '/chat', icon: <Bot size={14} color="#6366f1" /> },
              { label: 'Task Manager', href: '/tasks', icon: <Zap size={14} color="#f59e0b" /> },
              { label: 'Data Analysis', href: '/data-analysis', icon: <Activity size={14} color="#10b981" /> },
              { label: 'Documents', href: '/documents', icon: <GitBranch size={14} color="#0ea5e9" /> },
              { label: 'Executive Reports', href: '/reports', icon: <TrendingUp size={14} color="#8b5cf6" /> },
              { label: 'Human Approvals', href: '/approvals', icon: <Clock size={14} color="#ec4899" /> },
            ].map(({ label, href, icon }) => (
              <a
                key={label}
                href={href}
                className="btn btn-ghost"
                style={{ justifyContent: 'flex-start', fontSize: 12, padding: '8px 10px', background: 'var(--surface-0)' }}
              >
                {icon}
                {label}
              </a>
            ))}
          </div>
        </div>
      </div>

      {/* Usage note */}
      <div style={{ fontSize: 11, color: 'var(--text-muted)', textAlign: 'center', paddingBottom: 8 }}>
        Data sourced from <code className="mono">/api/v1/analytics/summary</code> · Refresh to update
      </div>
    </div>
  )
}
