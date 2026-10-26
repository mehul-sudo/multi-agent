import React, { useState } from 'react'
import { motion } from 'framer-motion'
import {
  Mail, Send, CheckCircle2, AlertTriangle, ShieldCheck,
  RefreshCw, Copy, Check, Clock, User
} from 'lucide-react'
import { agentsApi } from '../lib/api'
import { SectionHeader, StatusBadge } from '../components/ui'

export default function MessagingWorkspacePage() {
  const [to, setTo] = useState('mehulpankajmaha@gmail.com')
  const [subject, setSubject] = useState('Enterprise Notification: All Systems Operational')
  const [body, setBody] = useState(
    'This notification was dispatched in real-time by the Enterprise Multi-Agent System.\n\nAll 8 specialized domain agents are active and responding within normal SLA limits.'
  )
  const [provider, setProvider] = useState<'resend' | 'smtp'>('resend')
  const [mode, setMode] = useState<'send' | 'draft'>('send')

  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState('')

  const handleSend = async () => {
    if (!to.trim() || !subject.trim()) return
    setRunning(true)
    setError('')
    setResult(null)

    try {
      const payload = {
        to,
        subject,
        body,
        provider,
        email_provider: provider,
        mode,
      }

      const res = await agentsApi.runAgent('email', payload)
      setResult(res)
    } catch (err: any) {
      setError(err.message || 'Email dispatch failed.')
    } finally {
      setRunning(false)
    }
  }

  return (
    <div style={{ padding: '24px', maxWidth: 1400, margin: '0 auto' }}>
      <SectionHeader
        title="Messaging & Email Workspace"
        subtitle="Compose and dispatch verified notifications worldwide via Resend or Gmail SMTP with optional human-in-the-loop approval gates."
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(380px, 480px) 1fr', gap: 24, alignItems: 'start', marginTop: 24 }}>
        {/* Left Column: Email Composer Form */}
        <div className="card" style={{ padding: 20 }}>
          <h3 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 16px', display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-primary)' }}>
            <Mail size={18} color="var(--primary)" />
            Compose Enterprise Dispatch
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                Recipient Email
              </label>
              <input
                type="email"
                value={to}
                onChange={(e) => setTo(e.target.value)}
                placeholder="recipient@enterprise.com"
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  borderRadius: 8,
                  background: 'var(--surface-0)',
                  border: '1px solid var(--border-subtle)',
                  color: 'var(--text-primary)',
                  fontSize: 13,
                }}
              />
            </div>

            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                Subject
              </label>
              <input
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="Enterprise Notification Subject"
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  borderRadius: 8,
                  background: 'var(--surface-0)',
                  border: '1px solid var(--border-subtle)',
                  color: 'var(--text-primary)',
                  fontSize: 13,
                }}
              />
            </div>

            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                Email Engine Provider
              </label>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  onClick={() => setProvider('resend')}
                  className={`btn btn-sm ${provider === 'resend' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ flex: 1 }}
                >
                  ⚡ Resend Cloud API
                </button>
                <button
                  onClick={() => setProvider('smtp')}
                  className={`btn btn-sm ${provider === 'smtp' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ flex: 1 }}
                >
                  🌐 Gmail SMTP (Any Email)
                </button>
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>
                {provider === 'resend' ? (
                  <span>⚡ Resend Free Sandbox only sends to <code>mehulpankajmaha@gmail.com</code>. Choose <strong>Gmail SMTP</strong> to deliver to any recipient worldwide.</span>
                ) : (
                  <span>🌐 Gmail SMTP delivers to <strong>ANY recipient</strong> (Gmail, Yahoo, Outlook, work emails) without domain limits.</span>
                )}
              </div>
            </div>

            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '10px 12px',
              borderRadius: 8,
              background: 'var(--surface-0)',
              border: '1px solid var(--border-subtle)',
            }}>
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
                  Execution Mode
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  {mode === 'send' ? 'Live Dispatch (Requires Backend Human Approval)' : 'Draft Preview (Local Only)'}
                </div>
              </div>
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value as 'send' | 'draft')}
                style={{
                  padding: '6px 10px',
                  borderRadius: 6,
                  background: 'var(--surface-1)',
                  border: '1px solid var(--border-subtle)',
                  color: 'var(--text-primary)',
                  fontSize: 12,
                }}
              >
                <option value="send">Live Dispatch</option>
                <option value="draft">Draft Preview</option>
              </select>
            </div>

            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                Message Body
              </label>
              <textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                rows={6}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  borderRadius: 8,
                  background: 'var(--surface-0)',
                  border: '1px solid var(--border-subtle)',
                  color: 'var(--text-primary)',
                  fontSize: 12,
                  resize: 'vertical',
                }}
              />
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
              onClick={handleSend}
              disabled={running || !to.trim()}
              className="btn btn-primary"
              style={{ width: '100%', padding: '10px 16px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
            >
              {running ? (
                <>
                  <span className="spinner" style={{ width: 14, height: 14 }} />
                  Dispatching Email…
                </>
              ) : (
                <>
                  <Send size={15} />
                  Dispatch Email Message
                </>
              )}
            </button>
          </div>
        </div>

        {/* Right Column: Dispatch Status & Log */}
        <div className="card" style={{ padding: 24, minHeight: 400 }}>
          {result ? (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18, borderBottom: '1px solid var(--border-subtle)', paddingBottom: 14 }}>
                <StatusBadge
                  status={result.success ? 'success' : result.requires_approval ? 'warning' : 'failed'}
                  label={result.success ? 'Delivered' : result.requires_approval ? 'Approval Required' : 'Failed'}
                />
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  Engine: {provider === 'resend' ? 'Resend Cloud API' : 'Gmail SMTP'}
                </span>
              </div>

              <div style={{
                padding: 16,
                borderRadius: 10,
                background: 'var(--surface-0)',
                border: '1px solid var(--border-subtle)',
                marginBottom: 16,
              }}>
                <h4 style={{ fontSize: 13, fontWeight: 700, margin: '0 0 8px', color: 'var(--text-primary)' }}>
                  Execution Outcome
                </h4>
                <p style={{ margin: 0, fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                  {result.output?.message || result.output?.status || (result.success ? 'Message successfully accepted by mail transport engine.' : 'Operation completed.')}
                </p>
              </div>

              {result.output?.email_id && (
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
                  <strong>Message ID:</strong> <code>{result.output.email_id}</code>
                </div>
              )}

              {result.requires_approval && (
                <div style={{
                  padding: 14,
                  borderRadius: 8,
                  background: 'rgba(245, 158, 11, 0.1)',
                  border: '1px solid var(--accent-amber)',
                  fontSize: 12,
                  color: 'var(--text-primary)',
                }}>
                  <strong>Notice:</strong> This email dispatch triggered the Human Approval Gate and has been posted to the <strong>Approvals</strong> page for authorization.
                </div>
              )}
            </div>
          ) : (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
              <Mail size={36} style={{ marginBottom: 12, opacity: 0.5 }} />
              <p style={{ margin: 0, fontSize: 14 }}>
                Enter the recipient address and message on the left to dispatch enterprise notifications.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
