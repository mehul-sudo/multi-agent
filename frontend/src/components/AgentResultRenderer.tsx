/**
 * AgentResultRenderer — renders agent-type-specific output.
 *
 * Mandatory structure (Prompt Sections 19 & 20):
 * 1. HUMAN-READABLE RESULT (primary display)
 * 2. TECHNICAL DETAILS (collapsible accordion)
 * 3. RAW JSON (collapsible accordion with copy button)
 */

import React, { useState } from 'react'
import {
  Mail, BarChart2, FileText, Globe, Database, Shield,
  ClipboardList, Copy, Check, ChevronDown, Clock, Tag, Cpu, AlertTriangle,
  CheckSquare, User, Calendar, MessageSquare, GitBranch, ArrowRight, Table, Layers, Bot
} from 'lucide-react'
import { MarkdownView } from './MarkdownView'

interface AgentResultProps {
  output: Record<string, unknown>
  agentType?: string
}

// ── Copy button ──────────────────────────────────────────────────────────────
function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(text)
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      }}
      title="Copy raw JSON"
      style={{
        background: 'none',
        border: '1px solid var(--border-subtle)',
        cursor: 'pointer',
        color: copied ? '#10b981' : 'var(--text-muted)',
        padding: '3px 8px',
        borderRadius: 4,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        fontSize: 11,
      }}
    >
      {copied ? <Check size={12} /> : <Copy size={12} />}
      <span>{copied ? 'Copied' : 'Copy JSON'}</span>
    </button>
  )
}

// ── Shared field row ─────────────────────────────────────────────────────────
function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', gap: 8, padding: '5px 0', borderBottom: '1px solid var(--border-subtle)' }}>
      <span style={{
        fontSize: 11,
        color: 'var(--text-muted)',
        minWidth: 100,
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
        paddingTop: 1,
      }}>
        {label}
      </span>
      <span style={{ fontSize: 12, color: 'var(--text-primary)', wordBreak: 'break-all', flex: 1 }}>
        {value}
      </span>
    </div>
  )
}

// ── Status badge ─────────────────────────────────────────────────────────────
function StatusBadgePill({ status, mode, simulationOnly }: { status?: string; mode?: string; simulationOnly?: boolean }) {
  const s = status?.toLowerCase()

  if (s === 'sent') {
    return (
      <span style={{
        padding: '2px 8px', borderRadius: 12, fontSize: 11, fontWeight: 600,
        background: 'rgba(16,185,129,0.12)', color: '#10b981', border: '1px solid rgba(16,185,129,0.3)',
      }}>
        ✓ Email Sent
      </span>
    )
  }

  if (s === 'awaiting_approval' || mode === 'awaiting_approval') {
    return (
      <span style={{
        padding: '2px 8px', borderRadius: 12, fontSize: 11, fontWeight: 600,
        background: 'rgba(245,158,11,0.15)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.3)',
      }}>
        🟡 Waiting for Approval
      </span>
    )
  }

  if (s === 'drafted' || mode === 'draft') {
    return (
      <span style={{
        padding: '2px 8px', borderRadius: 12, fontSize: 11, fontWeight: 600,
        background: 'rgba(99,102,241,0.12)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.3)',
      }}>
        📝 Draft Created
      </span>
    )
  }

  if (s === 'failed') {
    return (
      <span style={{
        padding: '2px 8px', borderRadius: 12, fontSize: 11, fontWeight: 600,
        background: 'rgba(244,63,94,0.12)', color: '#f43f5e', border: '1px solid rgba(244,63,94,0.3)',
      }}>
        🔴 Failed
      </span>
    )
  }

  if (s === 'created' || s === 'success' || s === 'completed') {
    return (
      <span style={{
        padding: '2px 8px', borderRadius: 12, fontSize: 11, fontWeight: 600,
        background: 'rgba(16,185,129,0.12)', color: '#10b981', border: '1px solid rgba(16,185,129,0.3)',
      }}>
        ✓ Completed
      </span>
    )
  }

  return (
    <span style={{
      padding: '2px 8px', borderRadius: 12, fontSize: 11, fontWeight: 600,
      background: 'rgba(148,163,184,0.12)', color: '#94a3b8',
    }}>
      {status || 'Unknown'}
    </span>
  )
}

// ── Email Result ─────────────────────────────────────────────────────────────
function EmailResult({ output }: { output: Record<string, unknown> }) {
  const to = (output.to || output.recipient) as string[] | string | undefined
  const subject = output.subject as string | undefined
  const body = output.body as string | undefined
  const status = output.status as string | undefined
  const mode = output.mode as string | undefined
  const provider = (output.provider as string || 'Resend')
  const emailMode = (output.email_mode as string || 'live').toLowerCase()
  const sandboxNotice = output.sandbox_notice as string | undefined
  const messageId = (output.message_id || output.messageId) as string | undefined
  const timestamp = output.timestamp as string | undefined
  const simulationOnly = output.simulation_only as boolean | undefined
  const attachments = output.attachments as string[] | undefined
  const sourceReportName = (output.source_report_name || output.sourceReportName) as string | undefined
  const attachmentFilename = (output.attachment_filename || output.attachmentFilename) as string | undefined
  const attachmentFormat = (output.attachment_format || output.attachmentFormat) as string | undefined
  const attachmentStatus = (output.attachment_status || output.attachmentStatus) as string | undefined

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ background: 'rgba(99,102,241,0.12)', borderRadius: 8, padding: 6, color: '#818cf8' }}>
            <Mail size={16} />
          </div>
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Email Agent</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <StatusBadgePill status={status} mode={mode} simulationOnly={simulationOnly} />
          {emailMode === 'sandbox' && (
            <span style={{
              padding: '2px 6px', borderRadius: 8, fontSize: 10, fontWeight: 600,
              background: 'rgba(245,158,11,0.1)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.2)',
            }}>
              Sandbox Mode
            </span>
          )}
        </div>
      </div>

      {sandboxNotice && (
        <div style={{
          marginBottom: 12, padding: '10px 14px', borderRadius: 8,
          background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)',
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <AlertTriangle size={15} style={{ color: '#f59e0b', flexShrink: 0 }} />
          <span style={{ fontSize: 12, color: '#f59e0b', lineHeight: 1.4 }}>
            <strong>SANDBOX EMAIL:</strong> Not delivered to the requested recipient. {sandboxNotice}
          </span>
        </div>
      )}

      {status === 'awaiting_approval' && (
        <div style={{
          marginBottom: 12, padding: '10px 14px', borderRadius: 8,
          background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)',
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <AlertTriangle size={15} style={{ color: '#f59e0b', flexShrink: 0 }} />
          <span style={{ fontSize: 12, color: '#f59e0b', lineHeight: 1.4 }}>
            <strong>Action Paused:</strong> Outbound email requires your review. Authorize in the <strong>Approvals</strong> drawer to send.
          </span>
        </div>
      )}

      {status === 'sent' && (
        <div style={{
          marginBottom: 12, padding: '10px 14px', borderRadius: 8,
          background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.25)',
          fontSize: 12, color: '#10b981',
        }}>
          <span>✓ <strong>Email Sent:</strong> Successfully dispatched via {provider.toUpperCase()} (ID: {messageId || 'confirmed'}).</span>
        </div>
      )}

      {to && <Row label="To" value={Array.isArray(to) ? to.join(', ') : String(to)} />}
      {subject && <Row label="Subject" value={subject} />}
      <Row label="Provider" value={provider.toUpperCase()} />
      <Row label="Mode" value={emailMode.toUpperCase()} />
      {messageId && <Row label="Message ID" value={messageId} />}
      {timestamp && <Row label="Timestamp" value={new Date(timestamp).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })} />}
      {sourceReportName && <Row label="Source Report" value={sourceReportName} />}

      {attachments && attachments.length > 0 && (
        <div style={{ marginTop: 8, marginBottom: 8, padding: '10px 14px', background: 'var(--surface-0)', borderRadius: 8, border: '1px solid var(--border-subtle)' }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            📎 Attached Report Artifact
          </div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', wordBreak: 'break-all' }}>
              {attachmentFilename || attachments[0]}
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              {attachmentFormat && (
                <span className="badge badge-indigo" style={{ fontSize: 10, textTransform: 'uppercase', fontWeight: 700 }}>
                  {attachmentFormat}
                </span>
              )}
              <span className="badge badge-emerald" style={{ fontSize: 10, fontWeight: 700 }}>
                {attachmentStatus || 'attached'}
              </span>
            </div>
          </div>
        </div>
      )}

      {body && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 4 }}>
            Message Content
          </div>
          <div style={{
            background: 'var(--surface-0)', borderRadius: 8, padding: 12,
            fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6,
            whiteSpace: 'pre-wrap', border: '1px solid var(--border-subtle)',
          }}>
            {body}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Data Analysis Result ──────────────────────────────────────────────────────
function DataAnalysisResult({ output }: { output: Record<string, unknown> }) {
  const summary = output.summary as string | undefined
  const stats = (output.statistics || output.stats || {}) as Record<string, any>
  const quality = (output.dataQuality || output.data_quality || {}) as Record<string, any>
  const insights = (output.insights || output.key_insights || []) as string[]
  const outliers = (output.outliers || {}) as Record<string, any>

  const outlierItems = (outliers.items || outliers.outlier_rows || outliers.detected || []) as any[]
  const totalOutliers = outliers.total_outliers_detected ?? outliers.total ?? outlierItems.length

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ background: 'rgba(245,158,11,0.12)', borderRadius: 8, padding: 6, color: '#f59e0b' }}>
            <BarChart2 size={16} />
          </div>
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Data Analysis Summary</span>
        </div>
        <StatusBadgePill status="completed" />
      </div>

      {summary && (
        <div style={{
          marginBottom: 12, padding: '10px 14px', background: 'var(--surface-0)',
          borderRadius: 8, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6,
          border: '1px solid var(--border-subtle)',
        }}>
          <MarkdownView content={summary} />
        </div>
      )}

      {/* Statistical Summary Cards */}
      {stats && Object.keys(stats).length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 6, fontWeight: 700 }}>
            Key Column Statistics
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 8 }}>
            {Object.entries(stats).slice(0, 6).map(([col, colStats]) => {
              const isObj = typeof colStats === 'object' && colStats !== null
              const mean = isObj ? (colStats.mean ?? colStats.avg) : null
              const median = isObj ? colStats.median : null
              const std = isObj ? (colStats.std_dev ?? colStats.stdDev ?? colStats.std) : null
              return (
                <div key={col} style={{ background: 'var(--surface-0)', borderRadius: 6, padding: '8px 10px', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--brand-primary)', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>{col}</div>
                  {isObj ? (
                    <div style={{ fontSize: 10.5, color: 'var(--text-secondary)', marginTop: 4, display: 'flex', flexDirection: 'column', gap: 2 }}>
                      {mean !== null && mean !== undefined && <div>Mean: <strong>{typeof mean === 'number' ? mean.toFixed(2) : String(mean)}</strong></div>}
                      {median !== null && median !== undefined && <div>Median: <strong>{typeof median === 'number' ? median.toFixed(2) : String(median)}</strong></div>}
                      {std !== null && std !== undefined && <div>StdDev: <strong>{typeof std === 'number' ? std.toFixed(2) : String(std)}</strong></div>}
                    </div>
                  ) : (
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginTop: 2 }}>{String(colStats)}</div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Dataset Quality Metrics */}
      {quality && Object.keys(quality).length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 6, fontWeight: 700 }}>
            Dataset Quality Metrics
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))', gap: 8 }}>
            {Object.entries(quality).filter(([, v]) => typeof v !== 'object').map(([k, v]) => (
              <div key={k} style={{ background: 'var(--surface-0)', borderRadius: 6, padding: '8px 10px', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase' }}>{k.replace(/_/g, ' ')}</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginTop: 2 }}>{String(v)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Outlier Detection */}
      {totalOutliers > 0 && (
        <div style={{ marginBottom: 12, padding: '10px 12px', background: 'var(--surface-0)', borderRadius: 8, border: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: '#f59e0b', textTransform: 'uppercase' }}>⚠️ Detected Outliers</span>
            <span className="badge badge-amber" style={{ fontSize: 10 }}>{totalOutliers} anomaly row(s)</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
            {outliers.summary || `${totalOutliers} data points fall outside expected standard deviation/IQR thresholds.`}
          </div>
        </div>
      )}

      {insights && insights.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 6, fontWeight: 700 }}>
            Key Business Insights
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {insights.map((ins, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, background: 'var(--surface-0)', padding: '6px 10px', borderRadius: 6, border: '1px solid var(--border-subtle)' }}>
                <span style={{ color: '#818cf8', fontWeight: 700 }}>•</span>
                <div style={{ flex: 1 }}><MarkdownView content={ins} /></div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Document Research Result ──────────────────────────────────────────────────
function DocumentResearchResult({ output }: { output: Record<string, unknown> }) {
  const summary = (output.synthesis || output.answer || output.summary) as string | undefined
  const rawSources = (output.sources || output.passages || output.citations) as any[] | undefined
  const rawKeyFindings = (output.key_takeaways || output.key_points || output.key_findings) as string[] | undefined
  const confidenceScore = output.confidence_score as number | undefined
  const confidence = output.confidence as string | undefined

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ background: 'rgba(14,165,233,0.12)', borderRadius: 8, padding: 6, color: '#0ea5e9' }}>
            <FileText size={16} />
          </div>
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Document Research Findings</span>
        </div>
        {confidence && (
          <span style={{
            fontSize: 11,
            fontWeight: 600,
            padding: '2px 8px',
            borderRadius: 12,
            background: confidence === 'high' ? 'rgba(16,185,129,0.12)' : 'rgba(245,158,11,0.12)',
            color: confidence === 'high' ? '#10b981' : '#f59e0b',
            border: `1px solid ${confidence === 'high' ? 'rgba(16,185,129,0.25)' : 'rgba(245,158,11,0.25)'}`,
          }}>
            {confidence === 'high' ? '✓ High Confidence' : '⚡ Grounded Match'} {confidenceScore ? `(${Math.round(confidenceScore * 100)}%)` : ''}
          </span>
        )}
      </div>

      {summary && (
        <div style={{
          marginBottom: 14, padding: '12px 16px', background: 'var(--surface-0)',
          borderRadius: 8, fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.6,
          border: '1px solid var(--border-subtle)',
        }}>
          <MarkdownView content={summary} />
        </div>
      )}

      {rawKeyFindings && rawKeyFindings.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 8, fontWeight: 700 }}>
            Key Findings & Grounded Points
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {rawKeyFindings.map((f, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, background: 'var(--surface-0)', padding: '8px 12px', borderRadius: 6, border: '1px solid var(--border-subtle)' }}>
                <span style={{ color: '#0ea5e9', fontWeight: 700 }}>•</span>
                <div style={{ flex: 1 }}><MarkdownView content={f} /></div>
              </div>
            ))}
          </div>
        </div>
      )}

      {rawSources && rawSources.length > 0 ? (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 8, fontWeight: 700 }}>
            Verified Citations & Sources ({rawSources.length})
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {rawSources.map((s, i) => {
              if (typeof s === 'string') {
                return <div key={i} style={{ fontSize: 11, color: 'var(--text-muted)', padding: '2px 0' }}>📄 {s}</div>
              }
              const docName = s.documentName || s.doc_filename || s.doc_name || s.documentId || `Source ${i + 1}`
              const loc = s.slide ? `Slide ${s.slide}${s.slide_title ? `: ${s.slide_title}` : ''}` : (s.page ? `Page ${s.page}` : (s.section ? s.section : null))
              return (
                <div key={i} style={{ padding: '8px 12px', borderRadius: 6, background: 'var(--surface-0)', border: '1px solid var(--border-subtle)', fontSize: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 3 }}>
                    <span style={{ fontWeight: 600, color: 'var(--primary)', fontSize: 12 }}>📄 {docName}</span>
                    <div style={{ display: 'flex', gap: 6 }}>
                      {loc && (
                        <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, background: 'var(--surface-2)', color: 'var(--text-secondary)', fontWeight: 600 }}>
                          {loc}
                        </span>
                      )}
                      {s.score && (
                        <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, background: 'rgba(16, 185, 129, 0.1)', color: '#10b981', fontWeight: 600 }}>
                          {Math.min(100, Math.round(s.score * 100))}% match
                        </span>
                      )}
                    </div>
                  </div>
                  {s.excerpt && (
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', fontStyle: 'italic', lineHeight: 1.4 }}>
                      "{s.excerpt}"
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      ) : (
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6, fontStyle: 'italic' }}>
          No source citations were returned.
        </div>
      )}
    </div>
  )
}

// ── Report Generation Result ──────────────────────────────────────────────────
function ReportResult({ output }: { output: Record<string, unknown> }) {
  const title = (output.reportTitle || output.title || 'Generated Executive Report') as string
  const format = ((output.format as string) || 'pdf').toLowerCase()
  const sections = output.sections as Array<string | { heading?: string; title?: string; content?: string }> | undefined
  const content = (output.content || output.markdown || output.summary) as string | undefined
  const artifact = output.artifact as Record<string, unknown> | undefined
  const downloads = (output.downloads || {}) as Record<string, string>
  const allArtifacts = (output.all_artifacts || []) as Array<{ name?: string; url?: string; download_url?: string; type?: string }>
  const primaryUrl = (output.report_url || artifact?.download_url || artifact?.url || downloads[format] || (allArtifacts.length > 0 ? (allArtifacts[0].download_url || allArtifacts[0].url) : undefined)) as string | undefined

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ background: 'rgba(16,185,129,0.12)', borderRadius: 8, padding: 6, color: '#10b981' }}>
            <ClipboardList size={16} />
          </div>
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Generated Report</span>
        </div>
        <StatusBadgePill status="completed" />
      </div>

      <Row label="Report Title" value={title} />
      <Row label="Primary Format" value={format.toUpperCase()} />
      {sections && sections.length > 0 && (
        <Row
          label="Sections"
          value={sections.map(s => typeof s === 'string' ? s : (s.heading || s.title || 'Section')).join(', ')}
        />
      )}

      {content && (
        <div style={{
          marginTop: 10, marginBottom: 12, padding: '10px 14px', background: 'var(--surface-0)',
          borderRadius: 8, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6,
          border: '1px solid var(--border-subtle)', maxHeight: 220, overflowY: 'auto'
        }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 6 }}>
            Report Content Preview:
          </div>
          <MarkdownView content={typeof content === 'string' ? (content.length > 800 ? content.slice(0, 800) + '...' : content) : String(content)} />
        </div>
      )}

      {/* Available Download Artifacts */}
      <div style={{ marginTop: 12, paddingTop: 10, borderTop: '1px solid var(--border-subtle)' }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 8 }}>
          📥 Download Generated Artifacts:
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {(() => {
            const seenUrls = new Set<string>()
            const seenKeys = new Set<string>()
            const normalizeFmt = (fmt: string) => {
              const f = fmt.toLowerCase()
              if (f === 'markdown' || f === 'md') return 'MD'
              if (f === 'doc' || f === 'docx') return 'DOCX'
              if (f === 'text' || f === 'txt') return 'TXT'
              return f.toUpperCase()
            }

            const uniqueDownloads: Array<[string, string]> = []
            Object.entries(downloads).forEach(([fmtKey, url]) => {
              if (typeof url !== 'string' || !url) return
              const canonicalFmt = normalizeFmt(fmtKey)
              if (seenUrls.has(url) || seenKeys.has(canonicalFmt)) return
              seenUrls.add(url)
              seenKeys.add(canonicalFmt)
              uniqueDownloads.push([canonicalFmt, url])
            })

            return uniqueDownloads.map(([fmtKey, url]) => (
              <a
                key={fmtKey}
                href={url}
                download
                target="_blank"
                rel="noreferrer"
                className="btn btn-secondary"
                style={{ fontSize: 12, padding: '6px 12px', display: 'inline-flex', alignItems: 'center', gap: 6, textDecoration: 'none' }}
              >
                📄 Download {fmtKey}
              </a>
            ))
          })()}
          {Object.keys(downloads).length === 0 && primaryUrl && (
            <a
              href={primaryUrl}
              download
              target="_blank"
              rel="noreferrer"
              className="btn btn-secondary"
              style={{ fontSize: 12, padding: '6px 12px', display: 'inline-flex', alignItems: 'center', gap: 6, textDecoration: 'none' }}
            >
              📄 Download {format.toUpperCase()} Artifact
            </a>
          )}
        </div>
      </div>
    </div>
  )
}

// ── HTTP/Webhook Result ───────────────────────────────────────────────────────
function WebhookResult({ output }: { output: Record<string, unknown> }) {
  const [showHeaders, setShowHeaders] = useState(false)
  const [showDetails, setShowDetails] = useState(false)
  const [copiedBody, setCopiedBody] = useState(false)

  const url = (output.url || output.endpoint) as string | undefined
  const method = ((output.method as string) || 'GET').toUpperCase()
  const statusCode = (output.statusCode ?? output.status_code) as number | undefined
  const success = output.success !== undefined ? Boolean(output.success) : (statusCode ? statusCode >= 200 && statusCode < 300 : undefined)
  const durationMs = (output.durationMs ?? output.duration_ms ?? output.response_time_ms) as number | undefined
  const rawData = output.data ?? output.response_body ?? output.body ?? output.response
  const statusStr = (output.status as string) || (success ? 'completed' : (statusCode ? `HTTP ${statusCode}` : 'http_error'))
  const warnings = (output.warnings as string[]) || []
  const respHeaders = (output.response_headers || output.headers) as Record<string, string> | undefined
  const isAwaitingApproval = Boolean(statusStr === 'awaiting_approval' || output.requires_approval)

  // Safely parse JSON response body if stringified
  let parsedBody: any = rawData
  let isJson = output.is_json ?? (typeof rawData === 'object' && rawData !== null)

  if (typeof rawData === 'string') {
    const trimmed = rawData.trim()
    if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
      try {
        parsedBody = JSON.parse(trimmed)
        isJson = true
      } catch {
        parsedBody = rawData
        isJson = false
      }
    }
  }

  const formattedBody = parsedBody !== undefined && parsedBody !== null
    ? (typeof parsedBody === 'object' ? JSON.stringify(parsedBody, null, 2) : String(parsedBody))
    : ''

  const handleCopyBody = () => {
    navigator.clipboard.writeText(formattedBody)
    setCopiedBody(true)
    setTimeout(() => setCopiedBody(false), 2000)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* 1. Header Bar: Status, Target, Duration */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '12px 16px',
        background: 'var(--surface-1)',
        borderRadius: 8,
        border: '1px solid var(--border-subtle)',
        flexWrap: 'wrap',
        gap: 10,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {isAwaitingApproval ? (
            <span className="badge badge-amber" style={{ fontSize: 12, fontWeight: 700, padding: '4px 10px' }}>
              🟡 Awaiting Approval
            </span>
          ) : statusCode ? (
            <span
              className={`badge ${success ? 'badge-emerald' : 'badge-rose'}`}
              style={{ fontSize: 12, fontWeight: 800, padding: '4px 10px' }}
            >
              HTTP {statusCode} {statusCode === 200 ? 'OK' : (statusCode === 404 ? 'Not Found' : (success ? 'Success' : 'Error'))}
            </span>
          ) : (
            <StatusBadgePill status={success ? 'success' : 'failed'} />
          )}

          {method && (
            <span style={{
              padding: '3px 8px',
              borderRadius: 4,
              fontSize: 11,
              fontWeight: 800,
              background: method === 'GET' ? 'rgba(16,185,129,0.15)' : (method === 'POST' ? 'rgba(99,102,241,0.15)' : 'rgba(245,158,11,0.15)'),
              color: method === 'GET' ? '#10b981' : (method === 'POST' ? '#818cf8' : '#f59e0b'),
              letterSpacing: '0.04em',
            }}>
              {method}
            </span>
          )}

          {url && (
            <span style={{ fontSize: 12, color: 'var(--text-secondary)', wordBreak: 'break-all' }}>
              Target: <code style={{ color: 'var(--text-primary)', background: 'var(--surface-2)', padding: '2px 6px', borderRadius: 4 }}>{url}</code>
            </span>
          )}
        </div>

        {durationMs !== undefined && (
          <div style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 600 }}>
            ⏱️ Response Time: <strong style={{ color: 'var(--text-primary)' }}>{durationMs} ms</strong>
          </div>
        )}
      </div>

      {/* Warnings if any */}
      {warnings.length > 0 && (
        <div style={{ padding: '8px 12px', background: 'rgba(244,63,94,0.08)', borderRadius: 6, fontSize: 12, color: '#f43f5e', border: '1px solid rgba(244,63,94,0.2)' }}>
          {warnings.map((w, i) => <div key={i}>⚠️ {w}</div>)}
        </div>
      )}

      {/* 2. Primary Response Body Section */}
      <div style={{
        background: 'var(--surface-0)',
        borderRadius: 8,
        border: '1px solid var(--border-subtle)',
        overflow: 'hidden',
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 14px',
          background: 'var(--surface-1)',
          borderBottom: '1px solid var(--border-subtle)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Response Body {isJson ? '(JSON)' : '(Text)'}
            </span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              ({formattedBody.length} bytes)
            </span>
          </div>

          {formattedBody && (
            <button
              onClick={handleCopyBody}
              className="btn btn-ghost btn-sm"
              style={{ fontSize: 11, padding: '2px 8px', display: 'inline-flex', alignItems: 'center', gap: 4 }}
            >
              {copiedBody ? <Check size={12} color="#10b981" /> : <Copy size={12} />}
              <span>{copiedBody ? 'Copied' : 'Copy Response'}</span>
            </button>
          )}
        </div>

        <pre style={{
          margin: 0,
          padding: 14,
          fontSize: 12,
          lineHeight: 1.55,
          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
          color: '#38bdf8',
          background: '#0b1120',
          overflowX: 'auto',
          maxHeight: 380,
        }}>
          <code>{formattedBody || 'No response body returned.'}</code>
        </pre>
      </div>

      {/* 3. Collapsible Response Headers Section */}
      {respHeaders && Object.keys(respHeaders).length > 0 && (
        <div style={{
          background: 'var(--surface-0)',
          borderRadius: 8,
          border: '1px solid var(--border-subtle)',
          overflow: 'hidden',
        }}>
          <button
            type="button"
            onClick={() => setShowHeaders(!showHeaders)}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '10px 14px',
              background: 'var(--surface-1)',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--text-primary)',
              fontSize: 12,
              fontWeight: 700,
              textAlign: 'left',
            }}
          >
            <span>Response Headers ({Object.keys(respHeaders).length})</span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{showHeaders ? '▲ Hide' : '▼ Show'}</span>
          </button>

          {showHeaders && (
            <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 220, overflowY: 'auto' }}>
              {Object.entries(respHeaders).map(([hk, hv]) => (
                <div key={hk} style={{ display: 'flex', gap: 8, fontSize: 11.5, fontFamily: 'monospace', padding: '3px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                  <span style={{ color: '#818cf8', fontWeight: 600, minWidth: 160 }}>{hk}:</span>
                  <span style={{ color: 'var(--text-secondary)', wordBreak: 'break-all', flex: 1 }}>{hv}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 4. Collapsible Execution / Technical Details */}
      <div style={{
        background: 'var(--surface-0)',
        borderRadius: 8,
        border: '1px solid var(--border-subtle)',
        overflow: 'hidden',
      }}>
        <button
          type="button"
          onClick={() => setShowDetails(!showDetails)}
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '10px 14px',
            background: 'var(--surface-1)',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--text-primary)',
            fontSize: 12,
            fontWeight: 700,
            textAlign: 'left',
          }}
        >
          <span>Execution Details &amp; Telemetry</span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{showDetails ? '▲ Hide' : '▼ Show'}</span>
        </button>

        {showDetails && (
          <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <Row label="HTTP Method" value={method} />
            <Row label="Target URL" value={url} />
            <Row label="Status Code" value={statusCode ? `HTTP ${statusCode}` : 'N/A'} />
            <Row label="Latency" value={durationMs !== undefined ? `${durationMs} ms` : 'N/A'} />
            <Row label="SSRF Check" value="✓ Passed (Private IPs & Localhost Blocked)" />
            <Row label="Content Type" value={respHeaders?.['content-type'] || respHeaders?.['Content-Type'] || (isJson ? 'application/json' : 'text/plain')} />
          </div>
        )}
      </div>
    </div>
  )
}

// ── Security Analysis Result ──────────────────────────────────────────────────
function SecurityResult({ output }: { output: Record<string, unknown> }) {
  const target = (output.target || output.filename || output.file_id || 'Target Source Code') as string
  const rawFindings = (output.findings || []) as Array<any>
  const summary = (output.summary || output.risk_assessment) as string | undefined
  const score = output.security_score as number | undefined
  const recommendations = (output.recommendations || []) as string[]
  const countsBySev = (output.findings_by_severity || {}) as Record<string, number>

  const totalCount = output.findingsCount !== undefined ? Number(output.findingsCount) : rawFindings.length

  // Calculate severity counts if not directly provided
  const criticals = countsBySev.critical ?? rawFindings.filter(f => (typeof f === 'object' ? f.severity?.toLowerCase() === 'critical' : false)).length
  const highs = countsBySev.high ?? rawFindings.filter(f => (typeof f === 'object' ? f.severity?.toLowerCase() === 'high' : false)).length
  const mediums = countsBySev.medium ?? rawFindings.filter(f => (typeof f === 'object' ? f.severity?.toLowerCase() === 'medium' : false)).length
  const lows = countsBySev.low ?? rawFindings.filter(f => (typeof f === 'object' ? f.severity?.toLowerCase() === 'low' : false)).length

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ background: totalCount > 0 ? 'rgba(244,63,94,0.12)' : 'rgba(16,185,129,0.12)', borderRadius: 8, padding: 6, color: totalCount > 0 ? '#f43f5e' : '#10b981' }}>
            <Shield size={16} />
          </div>
          <div>
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Security &amp; Vulnerability Scan</span>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Target: <code>{target}</code></div>
          </div>
        </div>
        <span className={`badge ${totalCount > 0 ? 'badge-rose' : 'badge-emerald'}`} style={{ fontSize: 11, fontWeight: 700 }}>
          {totalCount > 0 ? `🚨 ${totalCount} Finding(s)` : '🛡️ Zero Findings'}
        </span>
      </div>

      {/* Severity Breakdown Pills */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(80px, 1fr))', gap: 6, marginBottom: 12 }}>
        <div style={{ background: 'var(--surface-0)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '6px 8px', textAlign: 'center' }}>
          <div style={{ fontSize: 9.5, color: '#f43f5e', fontWeight: 700, textTransform: 'uppercase' }}>Critical</div>
          <div style={{ fontSize: 14, fontWeight: 800, color: criticals > 0 ? '#f43f5e' : 'var(--text-primary)' }}>{criticals}</div>
        </div>
        <div style={{ background: 'var(--surface-0)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '6px 8px', textAlign: 'center' }}>
          <div style={{ fontSize: 9.5, color: '#f59e0b', fontWeight: 700, textTransform: 'uppercase' }}>High</div>
          <div style={{ fontSize: 14, fontWeight: 800, color: highs > 0 ? '#f59e0b' : 'var(--text-primary)' }}>{highs}</div>
        </div>
        <div style={{ background: 'var(--surface-0)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '6px 8px', textAlign: 'center' }}>
          <div style={{ fontSize: 9.5, color: '#eab308', fontWeight: 700, textTransform: 'uppercase' }}>Medium</div>
          <div style={{ fontSize: 14, fontWeight: 800, color: mediums > 0 ? '#eab308' : 'var(--text-primary)' }}>{mediums}</div>
        </div>
        <div style={{ background: 'var(--surface-0)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '6px 8px', textAlign: 'center' }}>
          <div style={{ fontSize: 9.5, color: '#0ea5e9', fontWeight: 700, textTransform: 'uppercase' }}>Low</div>
          <div style={{ fontSize: 14, fontWeight: 800, color: lows > 0 ? '#0ea5e9' : 'var(--text-primary)' }}>{lows}</div>
        </div>
      </div>

      {summary && (
        <div style={{
          marginBottom: 12, padding: '10px 14px', background: 'var(--surface-0)',
          borderRadius: 8, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6,
          border: '1px solid var(--border-subtle)'
        }}>
          <MarkdownView content={summary} />
        </div>
      )}

      {/* Individual Finding Cards */}
      {rawFindings.length > 0 ? (
        <div style={{ marginBottom: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Detailed Vulnerability Findings ({rawFindings.length}):
          </div>
          {rawFindings.map((f: any, i: number) => {
            if (typeof f === 'string') {
              return (
                <div key={i} style={{ background: 'var(--surface-0)', padding: 10, borderRadius: 6, border: '1px solid var(--border-subtle)', fontSize: 12 }}>
                  ⚠️ {f}
                </div>
              )
            }
            const sev = (f.severity || 'medium').toLowerCase()
            const sevColor = sev === 'critical' ? '#f43f5e' : (sev === 'high' ? '#f97316' : (sev === 'medium' ? '#eab308' : '#0ea5e9'))
            return (
              <div key={i} style={{ background: 'var(--surface-0)', padding: 10, borderRadius: 6, borderLeft: `3px solid ${sevColor}`, border: '1px solid var(--border-subtle)', fontSize: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ padding: '1px 6px', borderRadius: 4, fontSize: 9.5, fontWeight: 800, textTransform: 'uppercase', background: `${sevColor}20`, color: sevColor }}>
                      {f.severity}
                    </span>
                    <strong style={{ color: 'var(--text-primary)' }}>{f.title || f.category}</strong>
                  </div>
                  {f.line && <span style={{ fontSize: 10.5, color: 'var(--text-muted)' }}>Line {f.line}</span>}
                </div>

                {f.evidence && (
                  <div style={{ background: 'var(--surface-base)', padding: '6px 8px', borderRadius: 4, fontFamily: 'monospace', fontSize: 11, color: '#f43f5e', margin: '4px 0' }}>
                    {f.evidence}
                  </div>
                )}

                {f.impact && (
                  <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', marginTop: 4 }}>
                    <strong>Impact:</strong> {f.impact}
                  </div>
                )}

                {f.remediation && (
                  <div style={{ fontSize: 11.5, color: '#10b981', marginTop: 4 }}>
                    <strong>✓ Fix:</strong> {f.remediation}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      ) : (
        <div style={{ padding: '12px 16px', background: 'rgba(16,185,129,0.08)', borderRadius: 8, border: '1px solid rgba(16,185,129,0.2)', color: '#10b981', fontSize: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Check size={16} />
          <span><strong>Static Code Audit Clean:</strong> No suspicious vulnerability patterns, hardcoded secrets, or injection flaws were found in the scanned target.</span>
        </div>
      )}

      {recommendations && recommendations.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 6 }}>
            Recommended Security Hardening Actions
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {recommendations.map((r, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, fontSize: 12, color: 'var(--text-secondary)' }}>
                <span style={{ color: '#10b981', fontWeight: 700 }}>✓</span>
                <span>{r}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Database/BI Result ────────────────────────────────────────────────────────
function DatabaseResult({ output }: { output: Record<string, unknown> }) {
  const query = (output.query || output.executed_sql || output.sql) as string | undefined
  const rowCount = (output.row_count ?? output.rowCount ?? output.rows_affected) as number | undefined
  const columns = (output.columns || output.fields || []) as string[]
  const summary = (output.summary || output.message) as string | undefined
  const executionTime = (output.execution_time_ms ?? output.executionTime ?? output.duration_ms) as number | undefined
  const rows = (output.rows || output.data || output.results || output.records) as any[] | undefined

  const tableCols = columns.length > 0
    ? columns
    : (rows && rows.length > 0 && typeof rows[0] === 'object' && rows[0] !== null ? Object.keys(rows[0]) : [])

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ background: 'rgba(6,182,212,0.12)', borderRadius: 8, padding: 6, color: '#06b6d4' }}>
            <Database size={16} />
          </div>
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Database Query Execution</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {rowCount !== undefined && (
            <span className="badge badge-indigo" style={{ fontSize: 11, fontWeight: 700 }}>
              {rowCount} row(s) affected
            </span>
          )}
          <StatusBadgePill status="completed" />
        </div>
      </div>

      {executionTime !== undefined && <Row label="Execution Time" value={`${executionTime} ms`} />}
      {rowCount !== undefined && <Row label="Rows Returned" value={String(rowCount)} />}
      {summary && <Row label="Executive Summary" value={summary} />}

      {query && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 4 }}>
            Executed SQL
          </div>
          <pre style={{
            background: 'var(--surface-0)', borderRadius: 6, padding: 10,
            fontSize: 11, color: '#38bdf8', overflowX: 'auto',
            fontFamily: 'JetBrains Mono, monospace', border: '1px solid var(--border-subtle)',
          }}>
            {query}
          </pre>
        </div>
      )}

      {/* Results Data Table */}
      {rows && Array.isArray(rows) && rows.length > 0 && tableCols.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 6, fontWeight: 700 }}>
            Query Results ({rows.length} rows)
          </div>
          <div style={{ overflowX: 'auto', maxHeight: 250, border: '1px solid var(--border-subtle)', borderRadius: 6 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11.5, textAlign: 'left' }}>
              <thead>
                <tr style={{ background: 'var(--surface-0)', borderBottom: '1px solid var(--border-subtle)' }}>
                  {tableCols.map((c, i) => (
                    <th key={i} style={{ padding: '6px 10px', color: 'var(--text-secondary)', fontWeight: 700, whiteSpace: 'nowrap' }}>{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, 50).map((r, rIdx) => (
                  <tr key={rIdx} style={{ borderBottom: '1px solid var(--border-subtle)', background: rIdx % 2 === 0 ? 'transparent' : 'var(--surface-0)' }}>
                    {tableCols.map((c, cIdx) => (
                      <td key={cIdx} style={{ padding: '5px 10px', color: 'var(--text-primary)', whiteSpace: 'nowrap' }}>
                        {typeof r === 'object' && r !== null ? String(r[c] ?? '') : String(r)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {rows.length > 50 && (
            <div style={{ fontSize: 10.5, color: 'var(--text-muted)', marginTop: 4, textAlign: 'right' }}>
              Showing first 50 rows of {rows.length}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Task Manager Result ───────────────────────────────────────────────────────
function TaskManagerResult({ output }: { output: Record<string, unknown> }) {
  const tasks = (output.tasks || output.task_cards || output.task_list || (output.task ? [output.task] : [])) as Array<any>
  const summary = (output.summary || output.message || output.objective) as string | undefined
  const totalTasks = typeof output.total_tasks === 'number' ? output.total_tasks : tasks.length
  const status = (output.status || 'completed') as string
  const isFailed = status.toLowerCase() === 'failed' || Boolean(output.error)

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ background: 'rgba(99,102,241,0.12)', borderRadius: 8, padding: 6, color: '#818cf8' }}>
            <CheckSquare size={16} />
          </div>
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Task Manager</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span className="badge badge-indigo" style={{ fontSize: 11, fontWeight: 700 }}>
            {totalTasks} Task{totalTasks === 1 ? '' : 's'}
          </span>
          <StatusBadgePill status={isFailed ? 'failed' : status} />
        </div>
      </div>

      {summary && (
        <div style={{
          marginBottom: 12, padding: '10px 14px', background: 'var(--surface-0)',
          borderRadius: 8, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6,
          border: '1px solid var(--border-subtle)',
        }}>
          <MarkdownView content={summary} />
        </div>
      )}

      {isFailed && Boolean(output.error) && (
        <div style={{ marginBottom: 12, padding: '10px 14px', background: 'rgba(244,63,94,0.08)', borderRadius: 8, border: '1px solid rgba(244,63,94,0.25)', color: '#f43f5e', fontSize: 12 }}>
          <strong>Task Execution Failed:</strong> {String(output.error)}
        </div>
      )}

      {tasks.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {tasks.map((task, idx) => {
            const taskTitle = task.name || task.title || task.description || task.task_key || `Task #${idx + 1}`
            const taskStatus = (task.status || 'PENDING').toUpperCase()
            const priority = (task.priority || 'medium').toLowerCase()
            const assignee = task.assigned_agent_id || task.assignee || task.assigned_to || task.role || 'System Worker'
            const deadline = task.deadline || task.due_date || (task.timeout_seconds ? `${task.timeout_seconds}s limit` : null)
            const transitions = task.state_transitions || task.transitions || (task.previous_status ? `${task.previous_status} → ${taskStatus}` : null)
            const prioColor = priority === 'high' || priority === 1 ? '#f43f5e' : (priority === 'medium' || priority === 2 ? '#f59e0b' : '#38bdf8')

            return (
              <div
                key={idx}
                style={{
                  padding: '12px 14px',
                  borderRadius: 8,
                  background: 'var(--surface-0)',
                  border: '1px solid var(--border-subtle)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 8,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)' }}>#{idx + 1}</span>
                    <strong style={{ fontSize: 13, color: 'var(--text-primary)' }}>{taskTitle}</strong>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{
                      fontSize: 10,
                      fontWeight: 800,
                      padding: '2px 6px',
                      borderRadius: 4,
                      background: `${prioColor}20`,
                      color: prioColor,
                      textTransform: 'uppercase',
                    }}>
                      {typeof task.priority === 'number' ? `P${task.priority}` : priority}
                    </span>
                    <span style={{
                      fontSize: 10.5,
                      fontWeight: 700,
                      padding: '2px 8px',
                      borderRadius: 10,
                      background: taskStatus === 'COMPLETED' ? 'rgba(16,185,129,0.12)' : (taskStatus === 'RUNNING' || taskStatus === 'IN_PROGRESS' ? 'rgba(99,102,241,0.15)' : 'rgba(148,163,184,0.12)'),
                      color: taskStatus === 'COMPLETED' ? '#10b981' : (taskStatus === 'RUNNING' || taskStatus === 'IN_PROGRESS' ? '#818cf8' : '#94a3b8'),
                    }}>
                      {taskStatus}
                    </span>
                  </div>
                </div>

                {task.description && task.description !== taskTitle && (
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                    {task.description}
                  </div>
                )}

                <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap', fontSize: 11, color: 'var(--text-muted)', paddingTop: 4, borderTop: '1px solid var(--border-subtle)' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <User size={12} /> Assignee: <strong style={{ color: 'var(--text-primary)' }}>{assignee}</strong>
                  </span>
                  {deadline && (
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <Calendar size={12} /> Deadline: <strong style={{ color: 'var(--text-primary)' }}>{deadline}</strong>
                    </span>
                  )}
                  {transitions && (
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--brand-primary)' }}>
                      <ArrowRight size={12} /> State: {transitions}
                    </span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      ) : !isFailed && (
        <div style={{ padding: '12px 14px', background: 'var(--surface-0)', borderRadius: 8, border: '1px solid var(--border-subtle)', fontSize: 12, color: 'var(--text-secondary)' }}>
          No individual task items defined in payload.
        </div>
      )}
    </div>
  )
}

// ── Chat Assistant Result ─────────────────────────────────────────────────────
function ChatResult({ output }: { output: Record<string, unknown> }) {
  const query = (output.query || output.message || output.prompt || output.user_message) as string | undefined
  const response = (output.response || output.answer || output.reply || output.synthesis || output.text) as string | undefined
  const messages = (output.messages || output.history) as Array<{ role: string; content: string }> | undefined
  const sources = (output.sources || output.citations) as Array<any> | undefined

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ background: 'rgba(99,102,241,0.12)', borderRadius: 8, padding: 6, color: '#818cf8' }}>
            <MessageSquare size={16} />
          </div>
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Chat Assistant Response</span>
        </div>
        <StatusBadgePill status="completed" />
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {messages && Array.isArray(messages) && messages.length > 0 ? (
          messages.map((m, idx) => {
            const isUser = m.role === 'user'
            return (
              <div
                key={idx}
                style={{
                  display: 'flex',
                  justifyContent: isUser ? 'flex-end' : 'flex-start',
                  gap: 8,
                }}
              >
                {!isUser && (
                  <div style={{ background: 'rgba(99,102,241,0.15)', borderRadius: '50%', width: 26, height: 26, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#818cf8', flexShrink: 0, marginTop: 2 }}>
                    <Bot size={14} />
                  </div>
                )}
                <div style={{
                  maxWidth: '82%',
                  padding: '10px 14px',
                  borderRadius: isUser ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
                  background: isUser ? 'var(--brand-primary, #6366f1)' : 'var(--surface-0)',
                  color: isUser ? '#ffffff' : 'var(--text-primary)',
                  fontSize: 12.5,
                  lineHeight: 1.6,
                  border: isUser ? 'none' : '1px solid var(--border-subtle)',
                }}>
                  <MarkdownView content={m.content} />
                </div>
                {isUser && (
                  <div style={{ background: 'var(--surface-2)', borderRadius: '50%', width: 26, height: 26, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)', flexShrink: 0, marginTop: 2 }}>
                    <User size={14} />
                  </div>
                )}
              </div>
            )
          })
        ) : (
          <>
            {query && (
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                <div style={{
                  maxWidth: '80%',
                  padding: '10px 14px',
                  borderRadius: '12px 12px 2px 12px',
                  background: '#6366f1',
                  color: '#ffffff',
                  fontSize: 12.5,
                  lineHeight: 1.5,
                }}>
                  {query}
                </div>
                <div style={{ background: 'var(--surface-2)', borderRadius: '50%', width: 26, height: 26, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)', flexShrink: 0 }}>
                  <User size={14} />
                </div>
              </div>
            )}

            {response && (
              <div style={{ display: 'flex', justifyContent: 'flex-start', gap: 8 }}>
                <div style={{ background: 'rgba(99,102,241,0.15)', borderRadius: '50%', width: 26, height: 26, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#818cf8', flexShrink: 0 }}>
                  <Bot size={14} />
                </div>
                <div style={{
                  flex: 1,
                  maxWidth: '88%',
                  padding: '12px 16px',
                  borderRadius: '12px 12px 12px 2px',
                  background: 'var(--surface-0)',
                  color: 'var(--text-primary)',
                  fontSize: 13,
                  lineHeight: 1.6,
                  border: '1px solid var(--border-subtle)',
                }}>
                  <MarkdownView content={response} />
                </div>
              </div>
            )}
          </>
        )}

        {sources && sources.length > 0 && (
          <div style={{ marginTop: 6, padding: '8px 12px', background: 'var(--surface-0)', borderRadius: 6, border: '1px solid var(--border-subtle)', fontSize: 11, color: 'var(--text-muted)' }}>
            <strong>Citations:</strong> {sources.map((s, i) => (typeof s === 'string' ? s : (s.name || s.documentName || `Source ${i + 1}`))).join(' • ')}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Supervisor & Planner Result ───────────────────────────────────────────────
function SupervisorPlannerResult({ output }: { output: Record<string, unknown> }) {
  const objective = (output.objective || output.goal || output.plan_objective || output.title) as string | undefined
  const stages = (output.stages || output.tasks || output.plan_tasks || output.dag || (output.plan && (output.plan as any).tasks) || []) as Array<any>
  const completedStages = output.completed_stages as number | undefined
  const currentStage = output.current_stage as string | undefined

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ background: 'rgba(168,85,247,0.12)', borderRadius: 8, padding: 6, color: '#a855f7' }}>
            <GitBranch size={16} />
          </div>
          <div>
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Supervisor &amp; Planner DAG</span>
          </div>
        </div>
        <span className="badge badge-indigo" style={{ fontSize: 11, fontWeight: 700 }}>
          {stages.length} Stage{stages.length === 1 ? '' : 's'}
        </span>
      </div>

      {objective && (
        <div style={{
          marginBottom: 12, padding: '10px 14px', background: 'var(--surface-0)',
          borderRadius: 8, fontSize: 12.5, color: 'var(--text-primary)', lineHeight: 1.5,
          border: '1px solid var(--border-subtle)',
        }}>
          <strong style={{ color: '#a855f7' }}>Orchestration Goal:</strong> {objective}
        </div>
      )}

      {/* DAG Stages Execution Order */}
      {stages.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 700 }}>
            Execution Graph Stages ({stages.length})
          </div>
          {stages.map((st, idx) => {
            const stageName = st.name || st.title || st.task_key || `Stage ${idx + 1}`
            const agent = st.assigned_agent_id || st.agent || st.agent_type || st.role || 'Agent'
            const status = (st.status || 'PENDING').toLowerCase()
            const deps = st.dependencies || st.depends_on || []
            const depList = Array.isArray(deps) ? deps : [deps]
            const isDone = status === 'completed' || status === 'success'
            const isRunning = status === 'running' || status === 'in_progress'

            return (
              <div
                key={idx}
                style={{
                  padding: '10px 12px',
                  borderRadius: 8,
                  background: 'var(--surface-0)',
                  border: `1px solid ${isRunning ? 'rgba(168,85,247,0.4)' : isDone ? 'rgba(16,185,129,0.3)' : 'var(--border-subtle)'}`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 10,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1 }}>
                  <div style={{
                    width: 24,
                    height: 24,
                    borderRadius: '50%',
                    background: isDone ? 'rgba(16,185,129,0.15)' : (isRunning ? 'rgba(168,85,247,0.15)' : 'var(--surface-2)'),
                    color: isDone ? '#10b981' : (isRunning ? '#a855f7' : 'var(--text-muted)'),
                    fontSize: 11,
                    fontWeight: 800,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}>
                    {isDone ? '✓' : idx + 1}
                  </div>
                  <div>
                    <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--text-primary)' }}>
                      {stageName}
                    </div>
                    <div style={{ display: 'flex', gap: 10, fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                      <span>Agent: <strong style={{ color: 'var(--text-secondary)' }}>{agent}</strong></span>
                      {depList.length > 0 && (
                        <span>Depends on: <strong style={{ color: '#818cf8' }}>{depList.join(', ')}</strong></span>
                      )}
                    </div>
                  </div>
                </div>

                <StatusBadgePill status={status} />
              </div>
            )
          })}
        </div>
      ) : (
        <div style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic', padding: 8 }}>
          No stage definitions returned in plan.
        </div>
      )}
    </div>
  )
}

// ── Generic / Fallback Result (Executive Card Style) ─────────────────────────
function GenericResult({ output }: { output: Record<string, unknown> }) {
  const summary = (output.result_summary || output.summary || output.message || output.overview || output.description || output.text) as string | undefined
  const status = (output.status || (output.success !== undefined ? (output.success ? 'completed' : 'failed') : undefined)) as string | undefined
  const agentType = (output.agent_type || output.agent_name || output.action) as string | undefined
  const isFailed = status?.toLowerCase() === 'failed' || Boolean(output.error)

  // Collect numeric/scalar metrics
  const metricEntries = Object.entries(output).filter(([k, v]) => {
    if (['summary', 'result_summary', 'message', 'text', 'description', 'status', 'agent_type', 'agent_name', 'action', 'id', 'public_id'].includes(k)) return false
    return typeof v === 'number' || typeof v === 'boolean' || (typeof v === 'string' && v.length < 25 && !v.includes('\n'))
  })

  // Collect array/bullet insights
  const arrayEntries = Object.entries(output).filter(([, v]) => Array.isArray(v) && v.length > 0 && typeof v[0] === 'string') as [string, string[]][]

  // Collect nested objects (e.g. stage results)
  const nestedObjects = Object.entries(output).filter(([k, v]) => {
    if (['input_data', 'output_data', 'context', 'processed_inputs', 'error_data'].includes(k)) return false
    return typeof v === 'object' && v !== null && !Array.isArray(v) && Object.keys(v).length > 0
  }) as [string, Record<string, unknown>][]

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ background: isFailed ? 'rgba(244,63,94,0.12)' : 'rgba(99,102,241,0.12)', borderRadius: 8, padding: 6, color: isFailed ? '#f43f5e' : '#818cf8' }}>
            <Cpu size={16} />
          </div>
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
            {agentType ? `${String(agentType).replace(/_/g, ' ').toUpperCase()} Summary` : 'Execution Summary'}
          </span>
        </div>
        {status && <StatusBadgePill status={status} />}
      </div>

      {isFailed && Boolean(output.error) && (
        <div style={{ marginBottom: 12, padding: '10px 14px', background: 'rgba(244,63,94,0.08)', borderRadius: 8, border: '1px solid rgba(244,63,94,0.25)', color: '#f43f5e', fontSize: 12 }}>
          <strong>Execution Error:</strong> {String(output.error)}
        </div>
      )}

      {summary && (
        <div style={{
          marginBottom: 12, padding: '10px 14px', background: 'var(--surface-0)',
          borderRadius: 8, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6,
          border: '1px solid var(--border-subtle)',
        }}>
          <MarkdownView content={summary} />
        </div>
      )}

      {/* Metric Cards Grid */}
      {metricEntries.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 6 }}>
            Execution Metrics &amp; Attributes
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))', gap: 8 }}>
            {metricEntries.map(([k, v]) => (
              <div key={k} style={{ background: 'var(--surface-0)', borderRadius: 6, padding: '8px 10px', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase' }}>{k.replace(/_/g, ' ')}</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginTop: 2 }}>{String(v)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Bulleted Insights / Items */}
      {arrayEntries.map(([groupName, items]) => (
        <div key={groupName} style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 6 }}>
            {groupName.replace(/_/g, ' ')}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {items.map((item, idx) => (
              <div key={idx} style={{ display: 'flex', gap: 8, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, background: 'var(--surface-0)', padding: '6px 10px', borderRadius: 6, border: '1px solid var(--border-subtle)' }}>
                <span style={{ color: '#818cf8', fontWeight: 700 }}>•</span>
                <div style={{ flex: 1 }}><MarkdownView content={item} /></div>
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* Nested Stage Sections */}
      {nestedObjects.map(([stageKey, stageData]) => (
        <div key={stageKey} style={{ marginTop: 10, padding: '10px 12px', background: 'var(--surface-0)', borderRadius: 8, border: '1px solid var(--border-subtle)' }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--brand-primary)', textTransform: 'uppercase', marginBottom: 8 }}>
            Stage: {stageKey.replace(/_/g, ' ')}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 6 }}>
            {Object.entries(stageData).filter(([, v]) => typeof v !== 'object').map(([k, v]) => (
              <div key={k} style={{ background: 'var(--surface-1)', padding: '6px 8px', borderRadius: 4, border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase' }}>{k.replace(/_/g, ' ')}</div>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-primary)', marginTop: 2 }}>{String(v)}</div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Agent Type Detection ───────────────────────────────────────────────────────
function detectAgentType(output: Record<string, unknown>, hint?: string): string {
  const normHint = (hint || '').toLowerCase()

  // Exact / domain-specific agent hints first (prevent substring collisions like 'analysis' in 'security_analysis')
  if (normHint.includes('security')) return 'security_analysis'
  if (normHint.includes('webhook') || normHint.includes('http')) return 'http_webhook'
  if (normHint.includes('report')) return 'report_generation'
  if (normHint.includes('email') || normHint.includes('mail')) return 'email'
  if (normHint.includes('document') || normHint.includes('research') || normHint.includes('doc')) return 'document_research'
  if (normHint.includes('database') || normHint.includes('bi') || normHint.includes('sql')) return 'database_bi'
  if (normHint.includes('task_manager') || normHint.includes('task_mgmt')) return 'task_manager'
  if (normHint.includes('chat_assistant') || normHint.includes('chat')) return 'chat_assistant'
  if (normHint.includes('supervisor') || normHint.includes('planner')) return 'supervisor_planner'
  if (
    normHint.includes('data_analysis') ||
    normHint.includes('analytics') ||
    normHint === 'analysis' ||
    (normHint.includes('data') && !normHint.includes('database'))
  ) return 'data_analysis'

  // Pattern detection from output payload keys (prioritize domain-specific schemas first)
  if (output.security_score !== undefined || output.vulnerabilities || output.scannedTarget || (output.findings && !output.statistics)) return 'security_analysis'
  if (output.status_code || output.response_body || output.webhook_url || output.statusCode) return 'http_webhook'
  if (output.stages || output.execution_order || output.dag || (output.plan && (output.plan as any).tasks)) return 'supervisor_planner'
  if (output.tasks && Array.isArray(output.tasks) && output.tasks.length > 0 && (output.tasks[0].task_key || output.tasks[0].assigned_agent_id || output.tasks[0].status || output.tasks[0].priority)) return 'task_manager'
  if (output.messages && Array.isArray(output.messages)) return 'chat_assistant'
  if (output.reportTitle || output.report_url || output.all_artifacts || (output.sections && output.markdown)) return 'report_generation'
  if (output.mode && (output.to || output.subject || output.body)) return 'email'
  if (output.key_findings || (output.sources && (output.summary || output.content)) || output.synthesis || output.citations) return 'document_research'
  if (output.row_count !== undefined || output.rowCount !== undefined || output.query || output.executed_sql) return 'database_bi'
  if (output.statistics || output.dataQuality || output.numericMetrics || (output.insights && Array.isArray(output.insights))) return 'data_analysis'

  return 'generic'
}

// ── Main Component ─────────────────────────────────────────────────────────────
export function AgentResultRenderer({ output, agentType }: AgentResultProps) {
  if (!output || Object.keys(output).length === 0) return null

  const resolved = detectAgentType(output, agentType)
  const json = JSON.stringify(output, null, 2)

  // Technical metadata extracted safely
  const messageId = typeof output.messageId === 'string' ? output.messageId : undefined
  const duration = typeof output.execution_duration_ms === 'number'
    ? output.execution_duration_ms
    : typeof output.durationMs === 'number'
      ? output.durationMs
      : typeof output.duration_ms === 'number'
        ? output.duration_ms
        : undefined
  const provider = typeof output.provider === 'string'
    ? output.provider
    : typeof output.provider_used === 'string'
      ? output.provider_used
      : undefined

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* 1. Primary Human-Readable Presentation (Card Format) */}
      <div style={{ background: 'var(--surface-1)', borderRadius: 8, padding: 14, border: '1px solid var(--border-subtle)' }}>
        {resolved === 'email' && <EmailResult output={output} />}
        {resolved === 'data_analysis' && <DataAnalysisResult output={output} />}
        {resolved === 'report_generation' && <ReportResult output={output} />}
        {resolved === 'http_webhook' && <WebhookResult output={output} />}
        {resolved === 'security_analysis' && <SecurityResult output={output} />}
        {resolved === 'database_bi' && <DatabaseResult output={output} />}
        {resolved === 'document_research' && <DocumentResearchResult output={output} />}
        {resolved === 'task_manager' && <TaskManagerResult output={output} />}
        {resolved === 'chat_assistant' && <ChatResult output={output} />}
        {resolved === 'supervisor_planner' && <SupervisorPlannerResult output={output} />}
        {resolved === 'generic' && <GenericResult output={output} />}
      </div>

      {/* 2. Technical Details & Raw Payload (Collapsed Accordion) */}
      <details style={{
        background: 'var(--surface-0)', borderRadius: 8, border: '1px solid var(--border-subtle)',
        overflow: 'hidden',
      }}>
        <summary style={{
          padding: '8px 14px', fontSize: 11, fontWeight: 500, color: 'var(--text-muted)',
          cursor: 'pointer', userSelect: 'none', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <span>⚙️ Technical Metadata & Raw JSON (Advanced)</span>
          <CopyBtn text={json} />
        </summary>
        <div style={{ padding: '10px 14px 14px', borderTop: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div>
            {messageId ? <Row label="Message ID" value={<span className="mono">{messageId}</span>} /> : null}
            {provider ? <Row label="Provider" value={provider} /> : null}
            {duration !== undefined ? <Row label="Duration" value={`${duration} ms`} /> : null}
            <Row label="Agent Type" value={resolved} />
          </div>
          <div>
            <pre style={{
              background: 'rgba(0,0,0,0.35)', borderRadius: 6, padding: 10,
              fontSize: 11, color: '#38bdf8', overflowX: 'auto', maxHeight: 200,
              fontFamily: 'JetBrains Mono, monospace', margin: 0,
            }}>
              {json}
            </pre>
          </div>
        </div>
      </details>
    </div>
  )
}

export default AgentResultRenderer
