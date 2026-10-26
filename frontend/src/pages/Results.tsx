import React, { useState } from 'react'
import { BarChart3, TrendingUp, DollarSign, Cpu, RefreshCw, Bot, History, Calendar, CheckCircle, AlertTriangle } from 'lucide-react'
import { analyticsApi, type CostBreakdown, type AgentPerformanceStat, type TrendItem } from '../lib/api'
import { useAsync } from '../hooks/useAsync'
import { SectionHeader, StatCard, ErrorState, NotAvailable } from '../components/ui'

function SimpleBarChart({ data }: { data: { label: string; value: number; color: string }[] }) {
  const max = Math.max(...data.map((d) => d.value), 1)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {data.map(({ label, value, color }) => (
        <div key={label}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 12 }}>
            <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
            <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{value.toLocaleString()}</span>
          </div>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${(value / max) * 100}%`, background: color }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}

function CostTable({ breakdown }: { breakdown: CostBreakdown[] }) {
  if (!breakdown.length) {
    return (
      <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '32px 0', fontSize: 13 }}>
        No cost data available yet. Execute some workflows or chat requests to generate usage.
      </div>
    )
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="table">
        <thead>
          <tr>
            <th>Provider</th>
            <th>Model</th>
            <th>Prompt Tokens</th>
            <th>Completion Tokens</th>
            <th>Total Tokens</th>
            <th>Est. Cost</th>
          </tr>
        </thead>
        <tbody>
          {breakdown.map((b, i) => (
            <tr key={`${b.provider}-${b.model}-${i}`}>
              <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{b.provider}</td>
              <td><span className="badge badge-purple">{b.model}</span></td>
              <td style={{ color: 'var(--text-secondary)' }}>{b.prompt_tokens.toLocaleString()}</td>
              <td style={{ color: 'var(--text-secondary)' }}>{b.completion_tokens.toLocaleString()}</td>
              <td style={{ fontWeight: 600 }}>{b.total_tokens.toLocaleString()}</td>
              <td>
                {b.pricing_available === false || b.estimated_cost_usd === null ? (
                  <span className="badge badge-warning" style={{ fontSize: 11 }}>Rate unconfigured</span>
                ) : (
                  <span style={{ color: '#34d399', fontWeight: 600 }}>${b.estimated_cost_usd.toFixed(6)}</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function AgentPerformanceTable({ agents }: { agents: AgentPerformanceStat[] }) {
  if (!agents || !agents.length) {
    return (
      <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '32px 0', fontSize: 13 }}>
        No agent telemetry recorded yet.
      </div>
    )
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="table">
        <thead>
          <tr>
            <th>Agent Name</th>
            <th>Type / Role</th>
            <th>Status</th>
            <th>Invocations</th>
            <th>Success Rate</th>
            <th>Tokens</th>
            <th>LLM Cost</th>
            <th>Avg Duration</th>
          </tr>
        </thead>
        <tbody>
          {agents.map((ag) => {
            const totalRuns = ag.invocations || 0
            const successRate = totalRuns > 0 ? Math.round((ag.successes / totalRuns) * 100) : 100
            return (
              <tr key={ag.agent_id}>
                <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{ag.name}</td>
                <td>
                  <span className="badge badge-blue" style={{ fontSize: 11 }}>{ag.agent_type || ag.role}</span>
                </td>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span className={`status-dot ${ag.status === 'active' ? 'active' : 'inactive'}`} />
                    <span style={{ fontSize: 12, textTransform: 'capitalize' }}>{ag.status}</span>
                  </div>
                </td>
                <td style={{ fontWeight: 600 }}>{totalRuns.toLocaleString()}</td>
                <td>
                  <span style={{ color: successRate >= 90 ? '#10b981' : successRate >= 70 ? '#f59e0b' : '#f43f5e', fontWeight: 600 }}>
                    {totalRuns > 0 ? `${successRate}%` : '—'}
                  </span>
                </td>
                <td style={{ color: 'var(--text-secondary)' }}>{ag.total_tokens.toLocaleString()}</td>
                <td style={{ color: '#34d399', fontWeight: 600 }}>${ag.estimated_cost_usd.toFixed(6)}</td>
                <td style={{ color: 'var(--text-muted)' }}>{ag.avg_duration_ms > 0 ? `${ag.avg_duration_ms} ms` : '—'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function HistoricalTrendsTable({ trends }: { trends: TrendItem[] }) {
  if (!trends || !trends.length) {
    return (
      <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '24px 0', fontSize: 13 }}>
        No historical activity recorded in this time range.
      </div>
    )
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Workflow Runs</th>
            <th>Succeeded</th>
            <th>Failed</th>
            <th>Tokens</th>
            <th>LLM Cost</th>
            <th>LLM Requests</th>
          </tr>
        </thead>
        <tbody>
          {trends.map((t) => (
            <tr key={t.date}>
              <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{t.date}</td>
              <td style={{ fontWeight: 600 }}>{t.workflow_executions}</td>
              <td style={{ color: '#10b981' }}>{t.succeeded_executions}</td>
              <td style={{ color: t.failed_executions > 0 ? '#f43f5e' : 'var(--text-muted)' }}>
                {t.failed_executions}
              </td>
              <td style={{ color: 'var(--text-secondary)' }}>{t.total_tokens.toLocaleString()}</td>
              <td style={{ color: '#34d399', fontWeight: 600 }}>${t.estimated_cost_usd.toFixed(6)}</td>
              <td style={{ color: 'var(--text-muted)' }}>{t.llm_requests}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function ResultsPage() {
  const [historyDays, setHistoryDays] = useState<number>(30)
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false)

  const { data: usage, isLoading: usageLoading, error: usageErr, refetch: refetchUsage } = useAsync(
    () => analyticsApi.usage(), [], true
  )
  const { data: costs, isLoading: costsLoading, error: costsErr, refetch: refetchCosts } = useAsync(
    () => analyticsApi.costs(), [], true
  )
  const { data: wfStats, isLoading: wfLoading, error: wfErr, refetch: refetchWf } = useAsync(
    () => analyticsApi.workflowStats(), [], true
  )
  const { data: agentData, isLoading: agentsLoading, error: agentsErr, refetch: refetchAgents } = useAsync(
    () => analyticsApi.agents(), [], true
  )
  const { data: historyData, isLoading: historyLoading, error: historyErr, refetch: refetchHistory } = useAsync(
    () => analyticsApi.history(historyDays), [historyDays], true
  )

  const refetchAll = async () => {
    setIsRefreshing(true)
    try {
      await Promise.allSettled([
        refetchUsage(),
        refetchCosts(),
        refetchWf(),
        refetchAgents(),
        refetchHistory(),
      ])
    } finally {
      setTimeout(() => setIsRefreshing(false), 400)
    }
  }

  const tokenChartData = (usage && usage.total_tokens > 0) ? [
    { label: 'Prompt Tokens', value: usage.prompt_tokens, color: '#6366f1' },
    { label: 'Completion Tokens', value: usage.completion_tokens, color: '#8b5cf6' },
  ] : []

  const statusColorMap: Record<string, string> = {
    SUCCEEDED: '#10b981',
    COMPLETED: '#10b981',
    FAILED: '#f43f5e',
    PARTIALLY_COMPLETED: '#f59e0b',
    RUNNING: '#0ea5e9',
    STARTED: '#0ea5e9',
    PENDING: '#6366f1',
    QUEUED: '#6366f1',
    CANCELLED: '#94a3b8',
  }

  const statusChartData = wfStats ? Object.entries(wfStats.status_counts || {}).map(([status, count]) => {
    const sUpper = status.toUpperCase()
    return {
      label: sUpper.replace(/_/g, ' '),
      value: count as number,
      color: statusColorMap[sUpper] || '#94a3b8',
    }
  }) : []

  return (
    <div className="page-container animate-fadeIn">
      <SectionHeader
        title="Results & Analytics"
        subtitle="Token consumption, verified model pricing, and execution performance metrics"
        actions={
          <button
            className="btn btn-secondary"
            onClick={refetchAll}
            disabled={isRefreshing}
            style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <RefreshCw size={13} className={isRefreshing ? 'animate-spin' : ''} />
            {isRefreshing ? 'Refreshing…' : 'Refresh all'}
          </button>
        }
      />

      {/* Global error banner if multiple requests fail */}
      {(usageErr && costsErr && wfErr) && (
        <ErrorState message="Failed to communicate with analytics backend. Verify server is running and authenticated." onRetry={refetchAll} />
      )}

      {/* Key metrics */}
      <div className="stat-grid">
        <StatCard
          label="Total Tokens"
          value={usage?.total_tokens !== undefined ? usage.total_tokens.toLocaleString() : '0'}
          icon={<Cpu size={16} />}
          accent="#6366f1"
          loading={usageLoading}
        />
        <StatCard
          label="Prompt Tokens"
          value={usage?.prompt_tokens !== undefined ? usage.prompt_tokens.toLocaleString() : '0'}
          icon={<TrendingUp size={16} />}
          accent="#8b5cf6"
          loading={usageLoading}
        />
        <StatCard
          label="Completion Tokens"
          value={usage?.completion_tokens !== undefined ? usage.completion_tokens.toLocaleString() : '0'}
          icon={<BarChart3 size={16} />}
          accent="#0ea5e9"
          loading={usageLoading}
        />
        <StatCard
          label="Total Cost"
          value={costs?.total_estimated_cost_usd !== undefined ? `$${costs.total_estimated_cost_usd.toFixed(6)}` : '$0.000000'}
          icon={<DollarSign size={16} />}
          accent="#10b981"
          loading={costsLoading}
        />
      </div>

      {/* Visual Analytics Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
        {/* Token consumption card */}
        <div className="card" style={{ padding: '20px 24px' }}>
          <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 16, color: 'var(--text-primary)' }}>
            Token Consumption Breakdown
          </div>
          {usageLoading ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[...Array(2)].map((_, i) => <div key={i} className="skeleton" style={{ height: 40 }} />)}
            </div>
          ) : tokenChartData.length > 0 ? (
            <SimpleBarChart data={tokenChartData} />
          ) : (
            <div style={{ color: 'var(--text-muted)', fontSize: 13, textAlign: 'center', padding: '28px 0' }}>
              No token consumption recorded yet. Execute AI workflows or chat requests to generate usage.
            </div>
          )}
          {usageErr && <div style={{ fontSize: 12, color: 'var(--accent-rose)', marginTop: 8 }}>{usageErr}</div>}
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 12 }}>
            Source: <code className="mono">/api/v1/analytics/usage</code>
          </div>
        </div>

        {/* Job status distribution card */}
        <div className="card" style={{ padding: '20px 24px' }}>
          <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 16, color: 'var(--text-primary)' }}>
            Job Status Distribution
          </div>
          {wfLoading ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[...Array(3)].map((_, i) => <div key={i} className="skeleton" style={{ height: 40 }} />)}
            </div>
          ) : statusChartData.length > 0 ? (
            <SimpleBarChart data={statusChartData} />
          ) : (
            <div style={{ color: 'var(--text-muted)', fontSize: 13, textAlign: 'center', padding: '28px 0' }}>
              No execution data yet.
            </div>
          )}
          {wfErr && <div style={{ fontSize: 12, color: 'var(--accent-rose)', marginTop: 8 }}>{wfErr}</div>}
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 12 }}>
            Source: <code className="mono">/api/v1/analytics/workflows</code>
          </div>
        </div>
      </div>

      {/* Cost breakdown table */}
      <div className="card" style={{ overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px 12px', borderBottom: '1px solid var(--border-subtle)' }}>
          <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--text-primary)' }}>LLM Cost by Provider & Model</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
            Calculated from model-specific pricing per 1M tokens. Source: <code className="mono">/api/v1/analytics/costs</code>
          </div>
        </div>
        <div style={{ padding: '0 4px' }}>
          {costsLoading ? (
            <div style={{ padding: 20 }}><div className="skeleton" style={{ height: 80 }} /></div>
          ) : costsErr ? (
            <div style={{ padding: 20 }}><ErrorState message={costsErr} onRetry={refetchCosts} /></div>
          ) : (
            <CostTable breakdown={costs?.breakdown || []} />
          )}
        </div>
      </div>

      {/* Agent Telemetry & Invocations */}
      <div className="card" style={{ overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px 12px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--text-primary)' }}>Agent Performance & LLM Consumption</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
              Per-agent invocations, success rates, token usage, and latency. Source: <code className="mono">/api/v1/analytics/agents</code>
            </div>
          </div>
          <span className="badge badge-purple" style={{ fontSize: 11 }}>
            {agentData?.total_agents || 0} Registered Agents
          </span>
        </div>
        <div style={{ padding: '0 4px' }}>
          {agentsLoading ? (
            <div style={{ padding: 20 }}><div className="skeleton" style={{ height: 100 }} /></div>
          ) : agentsErr ? (
            <div style={{ padding: 20 }}><ErrorState message={agentsErr} onRetry={refetchAgents} /></div>
          ) : (
            <AgentPerformanceTable agents={agentData?.agents || []} />
          )}
        </div>
      </div>

      {/* Historical Activity & Trends */}
      <div className="card" style={{ overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px 12px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--text-primary)' }}>Historical Usage & Execution Trends</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
              Chronological daily breakdown of workflow executions, token volume, and costs. Source: <code className="mono">/api/v1/analytics/history</code>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {[7, 14, 30].map((d) => (
              <button
                key={d}
                className={`btn btn-secondary ${historyDays === d ? 'active' : ''}`}
                style={{
                  fontSize: 11,
                  padding: '4px 10px',
                  background: historyDays === d ? 'var(--surface-3)' : undefined,
                  borderColor: historyDays === d ? 'var(--border-strong)' : undefined,
                }}
                onClick={() => setHistoryDays(d)}
              >
                {d} Days
              </button>
            ))}
          </div>
        </div>
        <div style={{ padding: '0 4px' }}>
          {historyLoading ? (
            <div style={{ padding: 20 }}><div className="skeleton" style={{ height: 80 }} /></div>
          ) : historyErr ? (
            <div style={{ padding: 20 }}><ErrorState message={historyErr} onRetry={refetchHistory} /></div>
          ) : (
            <HistoricalTrendsTable trends={historyData?.trends || []} />
          )}
        </div>
      </div>

      {/* Streaming capability notice */}
      <NotAvailable
        feature="Real-time streaming analytics"
        endpoint="Real-time WebSocket token streaming is disabled. Historical timeline & batch aggregation are fully operational."
      />
    </div>
  )
}
