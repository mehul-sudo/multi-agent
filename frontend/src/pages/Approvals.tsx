import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Shield, CheckCircle2, XCircle, RefreshCw, Clock, AlertTriangle, Mail, Paperclip } from 'lucide-react'
import { approvalsApi, type ApprovalRequest } from '../lib/api'
import { useAsync } from '../hooks/useAsync'
import { SectionHeader, EmptyState, ErrorState, Modal, FormGroup, RiskBadge, StatusBadge } from '../components/ui'
import { MarkdownView } from '../components/MarkdownView'

// Safely render any value — prevents "Objects not valid as React child" crash
const safeStr = (v: any): string => {
  if (v == null) return ''
  if (typeof v === 'string') return v
  if (typeof v === 'number' || typeof v === 'boolean') return String(v)
  return JSON.stringify(v, null, 2)
}

// Helper to detect and extract email data from an ApprovalRequest
function getEmailApprovalData(approval: ApprovalRequest): {
  to: string[]
  subject: string
  body: string
  html?: string
  mode: string
  attachments: string[]
  attachmentFilename?: string
  attachmentFormat?: string
  attachmentStatus?: string
  sourceReportName?: string
} | null {
  const pOut = (typeof approval.proposed_output === 'object' && approval.proposed_output !== null)
    ? (approval.proposed_output as Record<string, unknown>)
    : {}
  const iSum = (typeof approval.input_summary === 'object' && approval.input_summary !== null)
    ? (approval.input_summary as Record<string, unknown>)
    : {}

  const merged: Record<string, unknown> = { ...iSum, ...pOut }
  const action = (approval.requested_action || '').toLowerCase()
  const agent = (approval.requested_by_agent || '').toLowerCase()

  const isEmail =
    action.includes('email') ||
    action.includes('mail') ||
    agent.includes('email') ||
    Boolean(merged.to || merged.recipients || (merged.subject && (merged.body || merged.html)))

  if (!isEmail) return null

  // Extract recipients
  let recipients: string[] = []
  const rawTo = merged.to || merged.recipients || merged.target_recipients
  if (Array.isArray(rawTo)) {
    recipients = rawTo.map(String)
  } else if (typeof rawTo === 'string' && rawTo.trim()) {
    recipients = rawTo.split(',').map((s) => s.trim()).filter(Boolean)
  }

  // Extract subject
  const subject = String(merged.subject || 'Enterprise Multi-Agent Operational Briefing')

  // Extract body
  const body = String(merged.body || merged.message || merged.content || '')

  // Extract HTML preview
  const html = (typeof merged.html === 'string' ? merged.html : (typeof merged.html_preview === 'string' ? merged.html_preview : undefined))

  // Extract attachments
  let attachments: string[] = []
  if (Array.isArray(merged.attachments)) {
    attachments = merged.attachments.map(String)
  }

  const mode = String(merged.mode || 'send')
  const attachmentFilename = (merged.attachment_filename || (attachments.length > 0 ? attachments[0].split(/[/\\]/).pop() : undefined)) as string | undefined
  const attachmentFormat = (merged.attachment_format || (attachmentFilename ? attachmentFilename.split('.').pop() : undefined)) as string | undefined
  const attachmentStatus = (merged.attachment_status || (attachments.length > 0 ? 'attached' : 'none')) as string
  const sourceReportName = merged.source_report_name as string | undefined

  return {
    to: recipients,
    subject,
    body,
    html,
    mode,
    attachments,
    attachmentFilename,
    attachmentFormat,
    attachmentStatus,
    sourceReportName,
  }
}

// Dedicated executive preview for Email approvals
function EmailApprovalPreview({ approval }: { approval: ApprovalRequest }) {
  const emailData = getEmailApprovalData(approval)
  const [activeTab, setActiveTab] = useState<'message' | 'html' | 'raw'>('message')

  if (!emailData) return <FormattedOutput data={approval.proposed_output} />

  const { to, subject, body, html, mode, attachments, attachmentFilename, attachmentFormat } = emailData

  return (
    <div style={{
      background: 'var(--surface-1)',
      borderRadius: 8,
      border: '1px solid var(--border-subtle)',
      overflow: 'hidden',
    }}>
      {/* Top Banner: Outbound Email Dispatch Header */}
      <div style={{
        padding: '12px 14px',
        background: 'var(--surface-2)',
        borderBottom: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 8,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            background: 'rgba(99,102,241,0.15)',
            color: '#818cf8',
            borderRadius: 6,
            padding: 6,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <Mail size={16} />
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
              Outbound Email Dispatch Preview
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              Review the exact formatted message and recipients before dispatching
            </div>
          </div>
        </div>

        <span style={{
          fontSize: 10.5,
          fontWeight: 700,
          padding: '2px 8px',
          borderRadius: 12,
          background: mode === 'send' ? 'rgba(16,185,129,0.15)' : 'rgba(245,158,11,0.15)',
          color: mode === 'send' ? '#10b981' : '#f59e0b',
          textTransform: 'uppercase',
        }}>
          {mode === 'send' ? '🚀 Send Mode' : '📝 Draft Mode'}
        </span>
      </div>

      {/* Meta Fields (To, Subject, Attachments) */}
      <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', gap: 10 }}>
        {/* Recipient(s) */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 12 }}>
          <span style={{ fontWeight: 600, color: 'var(--text-muted)', width: 85, flexShrink: 0 }}>
            To:
          </span>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {to.length > 0 ? (
              to.map((r, i) => (
                <span
                  key={i}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    background: 'rgba(99,102,241,0.1)',
                    border: '1px solid rgba(99,102,241,0.25)',
                    color: '#818cf8',
                    padding: '2px 8px',
                    borderRadius: 12,
                    fontSize: 11.5,
                    fontFamily: 'JetBrains Mono, monospace',
                  }}
                >
                  <Mail size={11} />
                  {r}
                </span>
              ))
            ) : (
              <span style={{ color: 'var(--text-muted)', fontStyle: 'italic', fontSize: 11 }}>
                No explicit recipient specified
              </span>
            )}
          </div>
        </div>

        {/* Subject */}
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, fontSize: 12 }}>
          <span style={{ fontWeight: 600, color: 'var(--text-muted)', width: 85, flexShrink: 0 }}>
            Subject:
          </span>
          <strong style={{ color: 'var(--text-primary)', fontSize: 13, wordBreak: 'break-word' }}>
            {subject}
          </strong>
        </div>

        {/* Attachments */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 12 }}>
          <span style={{ fontWeight: 600, color: 'var(--text-muted)', width: 85, flexShrink: 0 }}>
            Attachment:
          </span>
          {attachments.length > 0 || attachmentFilename ? (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {(attachments.length > 0 ? attachments : [attachmentFilename!]).map((att, idx) => {
                const name = att.split(/[/\\]/).pop() || att
                const ext = attachmentFormat || (name.includes('.') ? name.split('.').pop()?.toUpperCase() : 'DOC')
                return (
                  <span
                    key={idx}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 5,
                      background: 'rgba(16,185,129,0.1)',
                      border: '1px solid rgba(16,185,129,0.25)',
                      color: '#10b981',
                      padding: '2px 8px',
                      borderRadius: 12,
                      fontSize: 11,
                      fontWeight: 600,
                    }}
                  >
                    <Paperclip size={11} />
                    {name} ({ext})
                  </span>
                )
              })}
            </div>
          ) : (
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              fontSize: 11,
              color: 'var(--text-muted)',
              background: 'var(--surface-0)',
              padding: '2px 8px',
              borderRadius: 4,
              border: '1px solid var(--border-subtle)',
            }}>
              Direct findings in email body · No attachments (Mode A)
            </span>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div style={{
        display: 'flex',
        borderBottom: '1px solid var(--border-subtle)',
        background: 'var(--surface-0)',
      }}>
        <button
          type="button"
          onClick={() => setActiveTab('message')}
          style={{
            padding: '8px 14px',
            fontSize: 11.5,
            fontWeight: 600,
            border: 'none',
            background: 'none',
            cursor: 'pointer',
            borderBottom: activeTab === 'message' ? '2px solid #6366f1' : '2px solid transparent',
            color: activeTab === 'message' ? '#818cf8' : 'var(--text-muted)',
          }}
        >
          ✉️ Email Message Body
        </button>
        {html && (
          <button
            type="button"
            onClick={() => setActiveTab('html')}
            style={{
              padding: '8px 14px',
              fontSize: 11.5,
              fontWeight: 600,
              border: 'none',
              background: 'none',
              cursor: 'pointer',
              borderBottom: activeTab === 'html' ? '2px solid #6366f1' : '2px solid transparent',
              color: activeTab === 'html' ? '#818cf8' : 'var(--text-muted)',
            }}
          >
            🎨 Rich HTML Preview
          </button>
        )}
        <button
          type="button"
          onClick={() => setActiveTab('raw')}
          style={{
            padding: '8px 14px',
            fontSize: 11.5,
            fontWeight: 600,
            border: 'none',
            background: 'none',
            cursor: 'pointer',
            marginLeft: 'auto',
            borderBottom: activeTab === 'raw' ? '2px solid #6366f1' : '2px solid transparent',
            color: activeTab === 'raw' ? '#818cf8' : 'var(--text-muted)',
          }}
        >
          ⚙️ Raw JSON
        </button>
      </div>

      {/* Tab Panels */}
      <div style={{ padding: 12 }}>
        {activeTab === 'message' && (
          <div style={{
            background: 'var(--surface-0)',
            borderRadius: 6,
            padding: '12px 14px',
            border: '1px solid var(--border-subtle)',
            fontSize: 12.5,
            lineHeight: 1.6,
            color: 'var(--text-secondary)',
          }}>
            {body ? (
              <MarkdownView content={body} />
            ) : (
              <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>
                No message body provided.
              </span>
            )}
          </div>
        )}

        {activeTab === 'html' && html && (
          <div style={{
            background: '#ffffff',
            borderRadius: 6,
            border: '1px solid var(--border-subtle)',
            overflow: 'hidden',
          }}>
            <iframe
              title="Email HTML Preview"
              srcDoc={html}
              style={{
                width: '100%',
                height: 380,
                border: 'none',
                display: 'block',
              }}
              sandbox="allow-same-origin"
            />
          </div>
        )}

        {activeTab === 'raw' && (
          <pre style={{
            background: 'var(--surface-0)',
            borderRadius: 6,
            padding: 10,
            fontSize: 11,
            color: '#38bdf8',
            overflow: 'auto',
            maxHeight: 220,
            margin: 0,
            fontFamily: 'JetBrains Mono, monospace',
          }}>
            {JSON.stringify(approval.proposed_output || approval.input_summary, null, 2)}
          </pre>
        )}
      </div>
    </div>
  )
}

// Formatted Output Viewer component for human-readable parameters & result outputs
function FormattedOutput({ data }: { data: any }) {
  const [showRaw, setShowRaw] = useState(false)

  let parsed: any = data
  if (typeof data === 'string') {
    try {
      parsed = JSON.parse(data)
    } catch {
      parsed = data
    }
  }

  if (typeof parsed !== 'object' || parsed === null) {
    return (
      <div style={{
        background: 'var(--surface-1)', borderRadius: 8, padding: '10px 12px',
        fontSize: 12, color: 'var(--text-secondary)', border: '1px solid var(--border-subtle)',
      }}>
        {String(parsed)}
      </div>
    )
  }

  // Filter out internal and massive html dump fields from generic key list
  const entries = Object.entries(parsed).filter(([k]) => !['html', 'html_preview', '_backend_approval_verified'].includes(k))

  return (
    <div style={{
      background: 'var(--surface-1)',
      borderRadius: 8,
      padding: '12px 14px',
      border: '1px solid var(--border-subtle)',
    }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {entries.map(([key, val]) => {
          let displayVal = val
          if (Array.isArray(val)) displayVal = val.join(', ')
          else if (typeof val === 'object' && val !== null) displayVal = JSON.stringify(val)

          return (
            <div key={key} style={{ display: 'flex', alignItems: 'baseline', gap: 10, fontSize: 12 }}>
              <span style={{ fontWeight: 600, color: 'var(--text-muted)', width: 110, flexShrink: 0, textTransform: 'capitalize' }}>
                {key.replace(/_/g, ' ')}
              </span>
              <span style={{ color: 'var(--text-primary)', wordBreak: 'break-word', fontFamily: (key.toLowerCase().includes('id') || key.toLowerCase().includes('code')) ? 'JetBrains Mono, monospace' : 'inherit' }}>
                {String(displayVal)}
              </span>
            </div>
          )
        })}
      </div>

      <div style={{ marginTop: 8, textAlign: 'right' }}>
        <button
          onClick={() => setShowRaw(!showRaw)}
          style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: 10, cursor: 'pointer', textDecoration: 'underline' }}
        >
          {showRaw ? 'Hide Raw JSON' : 'Show Raw JSON'}
        </button>
      </div>

      {showRaw && (
        <pre style={{
          marginTop: 8,
          padding: 8,
          borderRadius: 6,
          background: 'var(--surface-0)',
          fontSize: 10,
          color: 'var(--text-secondary)',
          overflow: 'auto',
          maxHeight: 120,
          margin: 0,
        }}>
          {JSON.stringify(parsed, null, 2)}
        </pre>
      )}
    </div>
  )
}

function ApprovalCard({ approval, onAction }: { approval: ApprovalRequest; onAction: () => void }) {
  const [approving, setApproving] = useState(false)
  const [rejecting, setRejecting] = useState(false)
  const [comments, setComments] = useState('')
  const [reason, setReason] = useState('')
  const [showApprove, setShowApprove] = useState(false)
  const [showReject, setShowReject] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const isPending = approval.status?.toLowerCase() === 'pending'

  const handleApprove = async () => {
    setLoading(true); setError('')
    try { await approvalsApi.approve(approval.id, comments); setShowApprove(false); onAction() }
    catch (e) { setError((e as Error).message) }
    finally { setLoading(false) }
  }

  const handleReject = async () => {
    if (!reason) { setError('Rejection reason is required'); return }
    setLoading(true); setError('')
    try { await approvalsApi.reject(approval.id, reason); setShowReject(false); onAction() }
    catch (e) { setError((e as Error).message) }
    finally { setLoading(false) }
  }

  const riskGlow = {
    high: 'rgba(244,63,94,0.08)',
    medium: 'rgba(245,158,11,0.06)',
    low: 'rgba(16,185,129,0.06)',
  }[approval.risk_level?.toLowerCase()] || 'transparent'

  return (
    <>
      <motion.div
        className="card"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        style={{
          padding: 20,
          boxShadow: `var(--shadow-sm), inset 0 0 40px ${riskGlow}`,
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 16 }}>
          <div style={{
            width: 38, height: 38, borderRadius: 9,
            background: 'rgba(245,158,11,0.1)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0,
          }}>
            <Shield size={17} style={{ color: '#f59e0b' }} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
                {safeStr(approval.requested_action)}
              </span>
              <RiskBadge level={safeStr(approval.risk_level)} />
              <StatusBadge status={safeStr(approval.status)} />
            </div>
            {approval.requested_by_agent && (
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                Requested by agent: <strong style={{ color: 'var(--text-secondary)' }}>{safeStr(approval.requested_by_agent)}</strong>
              </div>
            )}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
            <Clock size={11} />
            {new Date(approval.created_at).toLocaleDateString()}
          </div>
        </div>

        {/* Explanation */}
        {approval.explanation && (
          <div style={{
            background: 'var(--surface-1)',
            borderRadius: 8, padding: '12px 14px', marginBottom: 14,
            fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6,
          }}>
            {safeStr(approval.explanation)}
          </div>
        )}


        {/* Proposed output preview */}
        {(approval.proposed_output || approval.input_summary) && (
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>
              {getEmailApprovalData(approval) ? 'Proposed Email Action Details' : 'Action Details & Parameters'}
            </div>
            {getEmailApprovalData(approval) ? (
              <EmailApprovalPreview approval={approval} />
            ) : (
              <FormattedOutput data={approval.proposed_output || approval.input_summary} />
            )}
          </div>
        )}


        {/* Actions */}
        {isPending && (
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-success" style={{ flex: 1, justifyContent: 'center', fontSize: 12 }} onClick={() => setShowApprove(true)}>
              <CheckCircle2 size={13} /> Approve
            </button>
            <button className="btn btn-danger" style={{ flex: 1, justifyContent: 'center', fontSize: 12 }} onClick={() => setShowReject(true)}>
              <XCircle size={13} /> Reject
            </button>
          </div>
        )}

        {!isPending && approval.comments && (
          <div className="alert alert-success" style={{ fontSize: 12 }}>Comments: {safeStr(approval.comments)}</div>
        )}
        {!isPending && approval.rejection_reason && (
          <div className="alert alert-error" style={{ fontSize: 12 }}>Rejection reason: {safeStr(approval.rejection_reason)}</div>
        )}
      </motion.div>

      {/* Approve Modal */}
      <Modal
        open={showApprove}
        onClose={() => setShowApprove(false)}
        title="Approve Action"
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setShowApprove(false)}>Cancel</button>
            <button className="btn btn-success" onClick={handleApprove} disabled={loading}>
              {loading ? <div className="spinner" style={{ width: 14, height: 14 }} /> : <CheckCircle2 size={13} />}
              Confirm Approval
            </button>
          </>
        }
      >
        {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16 }}>
          You are approving: <strong style={{ color: 'var(--text-primary)' }}>{safeStr(approval.requested_action)}</strong>
        </p>
        <FormGroup label="Comments (optional)">
          <textarea className="input" rows={3} placeholder="Add your approval notes..." value={comments} onChange={(e) => setComments(e.target.value)} />
        </FormGroup>
      </Modal>

      {/* Reject Modal */}
      <Modal
        open={showReject}
        onClose={() => setShowReject(false)}
        title="Reject Action"
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setShowReject(false)}>Cancel</button>
            <button className="btn btn-danger" onClick={handleReject} disabled={loading}>
              {loading ? <div className="spinner" style={{ width: 14, height: 14 }} /> : <XCircle size={13} />}
              Confirm Rejection
            </button>
          </>
        }
      >
        {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16 }}>
          You are rejecting: <strong style={{ color: 'var(--text-primary)' }}>{safeStr(approval.requested_action)}</strong>
        </p>
        <FormGroup label="Rejection Reason" required>
          <textarea className="input" rows={3} placeholder="Explain why this action is being rejected..." value={reason} onChange={(e) => setReason(e.target.value)} required />
        </FormGroup>
      </Modal>
    </>
  )
}

export default function ApprovalsPage() {
  const { data: approvals, isLoading, error, refetch } = useAsync(
    () => approvalsApi.listPending(),
    [],
    true
  )

  const pending = approvals?.filter(a => a.status?.toLowerCase() === 'pending') || []
  const resolved = approvals?.filter(a => a.status?.toLowerCase() !== 'pending') || []

  return (
    <div className="page-container animate-fadeIn">
      <SectionHeader
        title="Approval Center"
        subtitle="Human-in-the-loop governance for high-risk AI actions"
        actions={
          <button className="btn btn-secondary" onClick={refetch} style={{ fontSize: 12 }}>
            <RefreshCw size={13} />
            Refresh
          </button>
        }
      />

      {error && <ErrorState message={error} onRetry={refetch} />}

      {/* Pending count badge */}
      {pending.length > 0 && (
        <div className="alert alert-warning">
          <AlertTriangle size={14} style={{ flexShrink: 0 }} />
          <span><strong>{pending.length}</strong> pending approval{pending.length !== 1 ? 's' : ''} require your review</span>
        </div>
      )}

      {isLoading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {[...Array(2)].map((_, i) => (
            <div key={i} className="card" style={{ height: 160 }}>
              <div className="skeleton" style={{ height: '100%', borderRadius: 12 }} />
            </div>
          ))}
        </div>
      ) : approvals?.length === 0 ? (
        <EmptyState
          icon={<Shield size={40} />}
          title="No approval requests"
          description="There are currently no approval requests assigned to you. They will appear here when AI agents require human authorization."
        />
      ) : (
        <>
          {/* Pending */}
          {pending.length > 0 && (
            <div>
              <div className="section-title">Pending Review</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {pending.map((a) => (
                  <ApprovalCard key={a.id} approval={a} onAction={refetch} />
                ))}
              </div>
            </div>
          )}

          {/* Resolved */}
          {resolved.length > 0 && (
            <div>
              <div className="section-title">Resolved</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {resolved.map((a) => (
                  <ApprovalCard key={a.id} approval={a} onAction={refetch} />
                ))}
              </div>
            </div>
          )}
        </>
      )}

      <div style={{ fontSize: 11, color: 'var(--text-muted)', textAlign: 'center' }}>
        Data from <code className="mono">/api/v1/approvals/pending</code>
      </div>
    </div>
  )
}
