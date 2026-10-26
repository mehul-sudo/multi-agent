import React, { useState } from 'react'
import { motion } from 'framer-motion'
import {
  Database, Play, Table, CheckCircle2, AlertTriangle,
  Copy, Check, ShieldCheck, Terminal
} from 'lucide-react'
import { agentsApi } from '../lib/api'
import { SectionHeader, StatusBadge } from '../components/ui'
import { MarkdownView } from '../components/MarkdownView'

export default function DatabaseBIWorkspacePage() {
  const [query, setQuery] = useState('SELECT id, username, email, role, is_active FROM users LIMIT 15;')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState('')

  const handleExecute = async () => {
    if (!query.trim()) return
    setRunning(true)
    setError('')
    setResult(null)

    try {
      const payload = {
        query,
        operation: 'select',
        read_only: true,
      }
      const res = await agentsApi.runAgent('database_bi', payload)
      setResult(res)
    } catch (err: any) {
      setError(err.message || 'Database query failed.')
    } finally {
      setRunning(false)
    }
  }

  const rows = result?.output?.rows || result?.output?.results || []
  const columns = rows.length > 0 ? Object.keys(rows[0]) : []

  return (
    <div style={{ padding: '24px', maxWidth: 1400, margin: '0 auto' }}>
      <SectionHeader
        title="Database & Business Intelligence Workspace"
        subtitle="Execute verified, read-only SQL queries or natural language inquiries against enterprise database tables."
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(380px, 460px) 1fr', gap: 24, alignItems: 'start', marginTop: 24 }}>
        {/* Left Column: Query Editor */}
        <div className="card" style={{ padding: 20 }}>
          <h3 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 16px', display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-primary)' }}>
            <Database size={18} color="var(--primary)" />
            Safe SQL & BI Query
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                SQL Query (Read-Only Guardrailed)
              </label>
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                rows={6}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  borderRadius: 8,
                  background: 'var(--surface-0)',
                  border: '1px solid var(--border-subtle)',
                  color: 'var(--text-primary)',
                  fontSize: 12,
                  fontFamily: 'monospace',
                  resize: 'vertical',
                }}
              />
            </div>

            {/* Quick Queries */}
            <div>
              <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                Quick Queries
              </label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {[
                  { label: 'All Users', sql: 'SELECT id, username, email, role, is_active FROM users LIMIT 15;' },
                  { label: 'Active Workflows', sql: 'SELECT id, name, status, created_at FROM workflows LIMIT 10;' },
                  { label: 'Pending Approvals', sql: 'SELECT id, requested_action, risk_level, status FROM approval_requests LIMIT 10;' },
                ].map((q, idx) => (
                  <button
                    key={idx}
                    onClick={() => setQuery(q.sql)}
                    className="btn btn-ghost btn-sm"
                    style={{ fontSize: 11, padding: '4px 8px' }}
                  >
                    {q.label}
                  </button>
                ))}
              </div>
            </div>

            {error && (
              <div style={{
                padding: '8px 12px',
                borderRadius: 6,
                background: 'rgba(239, 68, 68, 0.1)',
                color: 'var(--accent-rose)',
                fontSize: 12,
              }}>
                ⚠️ {error}
              </div>
            )}

            <button
              onClick={handleExecute}
              disabled={running || !query.trim()}
              className="btn btn-primary"
              style={{ width: '100%', padding: '10px 16px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
            >
              {running ? (
                <>
                  <span className="spinner" style={{ width: 14, height: 14 }} />
                  Database BI Querying…
                </>
              ) : (
                <>
                  <Play size={15} />
                  Execute Query
                </>
              )}
            </button>
          </div>
        </div>

        {/* Right Column: Query Results Table & BI Insights */}
        <div className="card" style={{ padding: 24, minHeight: 400 }}>
          {result ? (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18, borderBottom: '1px solid var(--border-subtle)', paddingBottom: 14 }}>
                <StatusBadge status="success" label="Query Executed" />
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  Returned {rows.length} row(s)
                </span>
              </div>

              {/* BI Insights if generated */}
              {result.output?.bi_insights && (
                <div style={{
                  padding: 16,
                  borderRadius: 8,
                  background: 'var(--surface-0)',
                  border: '1px solid var(--border-subtle)',
                  marginBottom: 16,
                  fontSize: 13,
                  lineHeight: 1.6,
                }}>
                  <div style={{ fontWeight: 700, color: 'var(--primary)', marginBottom: 6 }}>BI Insights:</div>
                  <MarkdownView content={result.output.bi_insights} />
                </div>
              )}

              {/* Data Table */}
              {rows.length > 0 ? (
                <div style={{ overflowX: 'auto', borderRadius: 8, border: '1px solid var(--border-subtle)' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                    <thead>
                      <tr style={{ background: 'var(--surface-2)', borderBottom: '1px solid var(--border-subtle)' }}>
                        {columns.map((c) => (
                          <th key={c} style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 600, color: 'var(--text-secondary)' }}>
                            {c}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row: any, rIdx: number) => (
                        <tr
                          key={rIdx}
                          style={{
                            borderBottom: '1px solid var(--border-subtle)',
                            background: rIdx % 2 === 0 ? 'var(--surface-0)' : 'var(--surface-1)',
                          }}
                        >
                          {columns.map((col) => (
                            <td key={col} style={{ padding: '8px 12px', color: 'var(--text-primary)' }}>
                              {typeof row[col] === 'boolean' ? (row[col] ? 'true' : 'false') : String(row[col] ?? '')}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
                  No matching records returned.
                </div>
              )}
            </div>
          ) : (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
              <Database size={36} style={{ marginBottom: 12, opacity: 0.5 }} />
              <p style={{ margin: 0, fontSize: 14 }}>
                Enter a safe SQL query on the left to inspect records and derive enterprise BI insights.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
