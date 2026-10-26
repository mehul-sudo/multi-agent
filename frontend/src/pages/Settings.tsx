import React from 'react'
import { Settings, User, Key, Database, Cpu, Shield, Info, Zap, Globe, Mail, Lock, Check, Copy, Trash2 } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { SectionHeader, NotAvailable } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { integrationStatusApi, authApi, type IntegrationMode } from '../lib/api'

function SettingSection({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="card" style={{ overflow: 'hidden' }}>
      <div style={{
        padding: '16px 20px',
        borderBottom: '1px solid var(--border-subtle)',
        display: 'flex', alignItems: 'center', gap: 10,
      }}>
        <div style={{ color: 'var(--text-muted)' }}>{icon}</div>
        <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--text-primary)' }}>{title}</div>
      </div>
      <div style={{ padding: '20px 24px' }}>{children}</div>
    </div>
  )
}

function FieldRow({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--border-subtle)' }}>
      <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{label}</span>
      <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', fontFamily: mono ? 'JetBrains Mono, monospace' : undefined }}>
        {value}
      </span>
    </div>
  )
}

function IntegrationBadge({ status, detail }: { status: IntegrationMode | string | undefined; detail?: string }) {
  if (!status) {
    return <span className="badge badge-gray">Checking…</span>
  }
  const sUpper = String(status).toUpperCase()
  const cfg: Record<string, { cls: string; label: string }> = {
    LIVE:           { cls: 'badge-emerald', label: '🟢 LIVE' },
    CONFIGURED:     { cls: 'badge-emerald', label: '🟢 CONFIGURED' },
    ACTIVE:         { cls: 'badge-emerald', label: '🟢 ACTIVE' },
    MOCK:           { cls: 'badge-amber',   label: '🟡 MOCK' },
    NOT_CONFIGURED: { cls: 'badge-rose',    label: '🔴 NOT CONFIGURED' },
  }
  const { cls, label } = cfg[sUpper] || (
    sUpper.includes('SYNC') || sUpper.includes('LOCAL') || sUpper.includes('CELERY') || sUpper.includes('REDIS') || sUpper.includes('ASYNC')
      ? { cls: 'badge-emerald', label: '🟢 CONFIGURED' }
      : { cls: 'badge-gray', label: status }
  )
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 2 }}>
      <span className={`badge ${cls}`}>{label}</span>
      {detail && <span style={{ fontSize: 10, color: 'var(--text-muted)', maxWidth: 240, textAlign: 'right' }}>{detail}</span>}
    </div>
  )
}

function IntegrationRow({ label, icon, status, detail }: {
  label: string; icon: React.ReactNode; status?: IntegrationMode; detail?: string
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 0', borderBottom: '1px solid var(--border-subtle)' }}>
      <div style={{ color: 'var(--text-muted)', flexShrink: 0 }}>{icon}</div>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{label}</div>
      </div>
      <IntegrationBadge status={status} detail={detail} />
    </div>
  )
}

export default function SettingsPage() {
  const { user } = useAuth()
  const { data: integrations, isLoading: intLoading, error: intError, refetch } = useAsync(
    () => integrationStatusApi.get(), [], true
  )

  return (
    <div className="page-container animate-fadeIn">
      <SectionHeader
        title="Settings"
        subtitle="Account profile, integrations, and platform configuration"
      />

      {/* Account */}
      <SettingSection title="Account Profile" icon={<User size={15} />}>
        <FieldRow label="Username" value={user?.username || '—'} />
        <FieldRow label="Email" value={user?.email || '—'} />
        <FieldRow label="Role" value={user?.role || '—'} />
        <FieldRow label="User ID" value={user?.public_id?.slice(0, 16) + '…' || '—'} mono />
        <div className="alert alert-info" style={{ marginTop: 16, fontSize: 12 }}>
          <Info size={13} style={{ flexShrink: 0, marginTop: 1 }} />
          Profile editing is managed via the backend admin panel. The frontend does not currently expose a profile update endpoint.
        </div>
      </SettingSection>

      {/* Backend Connection */}
      <SettingSection title="Backend Connection" icon={<Database size={15} />}>
        <FieldRow label="API Base URL" value="http://localhost:5000/api" mono />
        <FieldRow label="API Version" value="v1 + legacy" />
        <FieldRow label="Authentication" value="JWT Bearer Token" />
        <FieldRow label="Proxy" value="Vite dev proxy → :5000" />
        {integrations?.database && (
          <div style={{ marginTop: 12 }}>
            <IntegrationRow
              label={`Database (${integrations.database.type || 'SQLite'})`}
              icon={<Database size={14} />}
              status={integrations.database.status}
              detail={integrations.database.connected ? 'Connected and responding' : 'Connection failed'}
            />
          </div>
        )}
      </SettingSection>

      {/* Live Integration Status */}
      <SettingSection title="Integration Status" icon={<Zap size={15} />}>
        {intLoading && (
          <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: '12px 0' }}>Loading integration status from backend…</div>
        )}
        {intError && (
          <div className="alert alert-error" style={{ fontSize: 12 }}>
            <Info size={13} style={{ flexShrink: 0 }} />
            Could not fetch integration status: {intError}
          </div>
        )}
        {integrations && (
          <>
            <IntegrationRow
              label="Email Agent"
              icon={<Mail size={14} />}
              status={integrations.email?.status}
              detail={integrations.email?.detail}
            />
            <IntegrationRow
              label="LLM Engine"
              icon={<Cpu size={14} />}
              status={integrations.llm?.status}
              detail={integrations.llm?.detail}
            />
            <IntegrationRow
              label="Task Queue (Celery/Redis)"
              icon={<Zap size={14} />}
              status={integrations.task_queue?.status}
              detail={integrations.task_queue?.detail}
            />
            <IntegrationRow
              label="HTTP/Webhook Agent"
              icon={<Globe size={14} />}
              status={integrations.webhook?.status}
              detail={integrations.webhook?.detail}
            />

            {/* LLM Provider breakdown */}
            {integrations.llm?.providers && (
              <div style={{ marginTop: 16 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  LLM Provider Keys
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {Object.entries(integrations.llm.providers).map(([name, info]) => (
                    <div key={name} style={{
                      padding: '8px 14px', borderRadius: 8, border: '1px solid var(--border-subtle)',
                      display: 'flex', gap: 8, alignItems: 'center',
                      background: info.configured ? 'rgba(16,185,129,0.05)' : 'rgba(244,63,94,0.05)',
                    }}>
                      <span className={`badge ${info.configured ? 'badge-emerald' : 'badge-rose'}`} style={{ fontSize: 10 }}>
                        {info.configured ? '✓ Configured' : '✗ Missing'}
                      </span>
                      <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', textTransform: 'capitalize' }}>{name}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="alert alert-info" style={{ marginTop: 16, fontSize: 12 }}>
              <Info size={13} style={{ flexShrink: 0, marginTop: 1 }} />
              <div>
                Integration status is read live from backend configuration. You can also configure credentials directly below without restarting the server!
              </div>
            </div>
          </>
        )}
      </SettingSection>

      {/* Live Connector Configuration Form */}
      <SettingSection title="Configure Real Connectors (Gmail SMTP / LLM / Webhook)" icon={<Key size={15} />}>
        <ConnectorConfigForm onUpdated={refetch} />
      </SettingSection>

      {/* Security */}
      <SettingSection title="Security & Authentication" icon={<Shield size={15} />}>
        <FieldRow label="Token Type" value="JWT (RS256 / HS256)" />
        <FieldRow label="Access Token TTL" value="Configurable via JWT_ACCESS_TOKEN_EXPIRES" />
        <FieldRow label="Refresh Token" value="Supported via /api/auth/refresh" />
        <FieldRow label="Token Blocklist" value="Redis-backed (logout invalidates token)" />
        <FieldRow label="Rate Limiting" value="Configured per-route in backend" />
        
        <div style={{ marginTop: 20, display: 'flex', flexDirection: 'column', gap: 24 }}>
          {/* Change Password */}
          <ChangePasswordForm />

          {/* 2-Factor Authentication */}
          <TwoFactorAuthCard />

          {/* Personal API Keys */}
          <ApiKeyManagementCard />
        </div>
      </SettingSection>
    </div>
  )
}

function ConnectorConfigForm({ onUpdated }: { onUpdated: () => void }) {
  const [smtpHost, setSmtpHost] = React.useState('smtp.gmail.com')
  const [smtpPort, setSmtpPort] = React.useState('587')
  const [smtpUser, setSmtpUser] = React.useState('')
  const [smtpPassword, setSmtpPassword] = React.useState('')
  const [emailProvider, setEmailProvider] = React.useState('resend')
  const [resendKey, setResendKey] = React.useState(() => localStorage.getItem('resend_api_key') || '')
  const [openaiKey, setOpenaiKey] = React.useState('')
  const [geminiKey, setGeminiKey] = React.useState('')
  const [anthropicKey, setAnthropicKey] = React.useState('')
  const [slackUrl, setSlackUrl] = React.useState('')
  const [celeryBrokerUrl, setCeleryBrokerUrl] = React.useState('redis://localhost:6379/0')

  const [saving, setSaving] = React.useState(false)
  const [saveMsg, setSaveMsg] = React.useState<string | null>(null)
  const [saveErr, setSaveErr] = React.useState<string | null>(null)

  const [testingEmail, setTestingEmail] = React.useState(false)
  const [testEmailTo, setTestEmailTo] = React.useState('mehulpankajmaha@gmail.com')
  const [testMsg, setTestMsg] = React.useState<string | null>(null)
  const [testErr, setTestErr] = React.useState<string | null>(null)

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setSaveMsg(null)
    setSaveErr(null)
    try {
      if (resendKey) {
        localStorage.setItem('resend_api_key', resendKey)
      }
      const payload: Record<string, string> = {
        email_provider: emailProvider,
        smtp_host: smtpHost,
        smtp_port: smtpPort,
      }
      if (resendKey) {
        payload.resend_api_key = resendKey
        payload.resend_test_recipient = testEmailTo || 'mehulpankajmaha@gmail.com'
      }
      if (smtpUser) payload.smtp_user = smtpUser
      if (smtpPassword) payload.smtp_password = smtpPassword
      if (openaiKey) payload.openai_api_key = openaiKey
      if (geminiKey) payload.gemini_api_key = geminiKey
      if (anthropicKey) payload.anthropic_api_key = anthropicKey
      if (slackUrl) payload.slack_webhook_url = slackUrl
      if (celeryBrokerUrl) payload.celery_broker_url = celeryBrokerUrl

      const res = await integrationStatusApi.configure(payload)
      setSaveMsg(res.message || 'Connectors updated successfully!')
      onUpdated()
    } catch (err) {
      setSaveErr((err as Error).message || 'Failed to update credentials')
    } finally {
      setSaving(false)
    }
  }

  const handleTestEmail = async () => {
    setTestingEmail(true)
    setTestMsg(null)
    setTestErr(null)
    try {
      const target = testEmailTo || smtpUser || (emailProvider === 'resend' ? 'mehulpankajmaha@gmail.com' : '')
      if (!target) {
        setTestErr('Please specify a recipient email address in the box below.')
        setTestingEmail(false)
        return
      }

      // Auto-save form configuration first so server state is synchronized
      const payload: Record<string, string> = {
        email_provider: emailProvider,
        smtp_host: smtpHost,
        smtp_port: smtpPort,
      }
      if (resendKey) payload.resend_api_key = resendKey
      if (smtpUser) payload.smtp_user = smtpUser
      if (smtpPassword) payload.smtp_password = smtpPassword
      if (openaiKey) payload.openai_api_key = openaiKey
      if (geminiKey) payload.gemini_api_key = geminiKey
      if (anthropicKey) payload.anthropic_api_key = anthropicKey
      if (slackUrl) payload.slack_webhook_url = slackUrl

      try {
        await integrationStatusApi.configure(payload)
        onUpdated()
      } catch {
        // Continue even if background save had a minor warning
      }

      const res = await integrationStatusApi.testEmail(target, {
        email_provider: emailProvider,
        resend_api_key: resendKey,
        smtp_user: smtpUser,
        smtp_password: smtpPassword,
      })
      setTestMsg(res.message || `Test email sent successfully to ${target}!`)
    } catch (err) {
      setTestErr((err as Error).message || 'Test email failed. Please verify credentials.')
    } finally {
      setTestingEmail(false)
    }
  }

  return (
    <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {saveMsg && <div className="alert alert-success" style={{ fontSize: 13 }}>{saveMsg}</div>}
      {saveErr && <div className="alert alert-error" style={{ fontSize: 13 }}>{saveErr}</div>}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <div>
          <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
            Email Provider
          </label>
          <select
            className="input"
            value={emailProvider}
            onChange={(e) => setEmailProvider(e.target.value)}
          >
            <option value="smtp">Real Gmail / SMTP (Requires App Password)</option>
            <option value="resend">Resend API (1-Click Google Sign In at resend.com - Super Easy!)</option>
            <option value="sendgrid">SendGrid API</option>
            <option value="mock">Safe Local Mock</option>
          </select>
        </div>

        {emailProvider === 'resend' ? (
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
              Resend API Key (Free 3,000 emails/mo at resend.com)
            </label>
            <input
              type="password"
              className="input"
              value={resendKey}
              onChange={(e) => setResendKey(e.target.value)}
              placeholder="re_123456789..."
            />
          </div>
        ) : (
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
              SMTP Host & Port
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                className="input"
                value={smtpHost}
                onChange={(e) => setSmtpHost(e.target.value)}
                placeholder="smtp.gmail.com"
                style={{ flex: 3 }}
              />
              <input
                className="input"
                value={smtpPort}
                onChange={(e) => setSmtpPort(e.target.value)}
                placeholder="587"
                style={{ flex: 1 }}
              />
            </div>
          </div>
        )}

        {emailProvider === 'smtp' && (
          <>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                Gmail / SMTP Email Address
              </label>
              <input
                className="input"
                value={smtpUser}
                onChange={(e) => setSmtpUser(e.target.value)}
                placeholder="you@gmail.com"
              />
            </div>

            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                Google App Password (16 characters)
              </label>
              <input
                type="password"
                className="input"
                value={smtpPassword}
                onChange={(e) => setSmtpPassword(e.target.value)}
                placeholder="xxxx xxxx xxxx xxxx"
              />
            </div>
          </>
        )}

        <div>
          <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
            OpenAI API Key (Optional)
          </label>
          <input
            type="password"
            className="input"
            value={openaiKey}
            onChange={(e) => setOpenaiKey(e.target.value)}
            placeholder="sk-..."
          />
        </div>

        <div>
          <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
            Google Gemini API Key (Free at aistudio.google.com)
          </label>
          <input
            type="password"
            className="input"
            value={geminiKey}
            onChange={(e) => setGeminiKey(e.target.value)}
            placeholder="AIzaSy..."
          />
        </div>

        <div>
          <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
            Anthropic Claude API Key (Optional)
          </label>
          <input
            type="password"
            className="input"
            value={anthropicKey}
            onChange={(e) => setAnthropicKey(e.target.value)}
            placeholder="sk-ant-..."
          />
        </div>

        <div>
          <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
            Slack / Discord Webhook URL (Optional)
          </label>
          <input
            className="input"
            value={slackUrl}
            onChange={(e) => setSlackUrl(e.target.value)}
            placeholder="https://hooks.slack.com/services/..."
          />
        </div>

        <div>
          <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
            Celery / Redis Broker URL (Optional)
          </label>
          <input
            className="input"
            value={celeryBrokerUrl}
            onChange={(e) => setCeleryBrokerUrl(e.target.value)}
            placeholder="redis://localhost:6379/0"
          />
          <span style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginTop: 3 }}>
            Default: In-Memory / Eager Queue is active & configured for ultra-fast local execution.
          </span>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginTop: 8 }}>
        <button type="submit" className="btn btn-primary" disabled={saving}>
          {saving ? 'Saving…' : 'Save Connector Credentials'}
        </button>
      </div>

      {/* Test Email Section */}
      <div style={{
        marginTop: 12,
        paddingTop: 16,
        borderTop: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
      }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
          Test Live Email Delivery
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <input
            className="input"
            value={testEmailTo}
            onChange={(e) => setTestEmailTo(e.target.value)}
            placeholder="Send test email to (e.g. mehulmahajan9898@gmail.com)"
            style={{ maxWidth: 380 }}
          />
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleTestEmail}
            disabled={testingEmail}
            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <Mail size={14} />
            {testingEmail ? 'Sending Test…' : 'Send Real Test Email'}
          </button>
        </div>
        {emailProvider === 'resend' && (
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            💡 <strong>Sandbox Note:</strong> In developer test mode (<code>onboarding@resend.dev</code>), Resend delivers emails directly to your registered account email.
          </div>
        )}
        {testMsg && <div className="alert alert-success" style={{ fontSize: 12 }}>{testMsg}</div>}
        {testErr && <div className="alert alert-error" style={{ fontSize: 12 }}>{testErr}</div>}
      </div>
    </form>
  )
}

function ChangePasswordForm() {
  const [currentPassword, setCurrentPassword] = React.useState('')
  const [newPassword, setNewPassword] = React.useState('')
  const [confirmPassword, setConfirmPassword] = React.useState('')
  const [loading, setLoading] = React.useState(false)
  const [msg, setMsg] = React.useState<string | null>(null)
  const [err, setErr] = React.useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setMsg(null)
    setErr(null)

    if (newPassword.length < 8) {
      setErr('New password must be at least 8 characters long.')
      return
    }
    if (newPassword !== confirmPassword) {
      setErr('New password and confirmation do not match.')
      return
    }

    setLoading(true)
    try {
      const res = await authApi.changePassword(currentPassword, newPassword)
      setMsg(res.message || 'Password changed successfully!')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (e) {
      setErr((e as Error).message || 'Failed to change password.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      background: 'var(--surface-1)',
      borderRadius: 10,
      padding: '16px 20px',
      border: '1px solid var(--border-subtle)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <Lock size={15} style={{ color: 'var(--accent-indigo)' }} />
        <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--text-primary)' }}>Change Account Password</div>
      </div>

      {msg && <div className="alert alert-success" style={{ fontSize: 12, marginBottom: 12 }}>{msg}</div>}
      {err && <div className="alert alert-error" style={{ fontSize: 12, marginBottom: 12 }}>{err}</div>}

      <form onSubmit={handleSubmit} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12, alignItems: 'flex-end' }}>
        <div>
          <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
            Current Password
          </label>
          <input
            type="password"
            className="input"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            required
            placeholder="••••••••"
          />
        </div>
        <div>
          <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
            New Password (min 8 chars)
          </label>
          <input
            type="password"
            className="input"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            placeholder="••••••••"
          />
        </div>
        <div>
          <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
            Confirm New Password
          </label>
          <input
            type="password"
            className="input"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            placeholder="••••••••"
          />
        </div>
        <div>
          <button type="submit" className="btn btn-secondary" disabled={loading} style={{ width: '100%', height: 38 }}>
            {loading ? 'Updating…' : 'Update Password'}
          </button>
        </div>
      </form>
    </div>
  )
}

function TwoFactorAuthCard() {
  const [enabled, setEnabled] = React.useState(false)
  const [loading, setLoading] = React.useState(false)
  const [secret, setSecret] = React.useState<string | null>(null)
  const [msg, setMsg] = React.useState<string | null>(null)

  React.useEffect(() => {
    authApi.get2FA().then((res) => {
      if (res?.enabled) {
        setEnabled(true)
        setSecret(res.secret_hint || null)
      }
    }).catch(() => {})
  }, [])

  const handleToggle = async () => {
    setLoading(true)
    setMsg(null)
    try {
      const res = await authApi.toggle2FA()
      setEnabled(res.enabled)
      setSecret(res.secret || null)
      setMsg(res.message)
    } catch {
      // fallback
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      background: 'var(--surface-1)',
      borderRadius: 10,
      padding: '16px 20px',
      border: '1px solid var(--border-subtle)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Shield size={15} style={{ color: enabled ? '#10b981' : 'var(--text-muted)' }} />
            <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--text-primary)' }}>
              Two-Factor Authentication (2FA)
            </div>
            <span className={`badge ${enabled ? 'badge-emerald' : 'badge-gray'}`} style={{ fontSize: 10 }}>
              {enabled ? 'Active / Protected' : 'Disabled'}
            </span>
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
            Secure your account with Time-based One-Time Passwords (TOTP / Google Authenticator).
          </div>
        </div>

        <button
          className={`btn ${enabled ? 'btn-danger' : 'btn-primary'}`}
          style={{ fontSize: 12, padding: '6px 14px' }}
          onClick={handleToggle}
          disabled={loading}
        >
          {loading ? 'Processing…' : enabled ? 'Disable 2FA' : 'Enable 2FA'}
        </button>
      </div>

      {msg && <div className="alert alert-info" style={{ fontSize: 12, marginTop: 12 }}>{msg}</div>}

      {enabled && secret && (
        <div style={{
          marginTop: 12,
          padding: '10px 14px',
          background: 'rgba(16,185,129,0.08)',
          borderRadius: 8,
          border: '1px solid rgba(16,185,129,0.2)',
          fontSize: 12,
          color: 'var(--text-primary)',
        }}>
          <div><strong>Authenticator Setup Key:</strong> <code className="mono">{secret}</code></div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
            Add this key to Google Authenticator, Authy, or 1Password.
          </div>
        </div>
      )}
    </div>
  )
}

function ApiKeyManagementCard() {
  const [keys, setKeys] = React.useState<Array<{ public_id: string; name: string; created_at: string }>>([])
  const [newKeyName, setNewKeyName] = React.useState('')
  const [generatedKey, setGeneratedKey] = React.useState<string | null>(null)
  const [copied, setCopied] = React.useState(false)
  const [loading, setLoading] = React.useState(false)

  const loadKeys = () => {
    authApi.listApiKeys().then((list) => setKeys(list)).catch(() => {})
  }

  React.useEffect(() => {
    loadKeys()
  }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setGeneratedKey(null)
    setCopied(false)
    try {
      const res = await authApi.createApiKey(newKeyName.trim() || undefined)
      setGeneratedKey(res.key)
      setNewKeyName('')
      loadKeys()
    } catch {
      //
    } finally {
      setLoading(false)
    }
  }

  const handleRevoke = async (id: string) => {
    if (!confirm('Are you sure you want to revoke this API key? Any scripts using it will stop working.')) return
    try {
      await authApi.revokeApiKey(id)
      loadKeys()
    } catch {}
  }

  const handleCopy = () => {
    if (generatedKey) {
      navigator.clipboard.writeText(generatedKey)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div style={{
      background: 'var(--surface-1)',
      borderRadius: 10,
      padding: '16px 20px',
      border: '1px solid var(--border-subtle)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <Key size={15} style={{ color: 'var(--accent-indigo)' }} />
        <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--text-primary)' }}>Personal API Keys</div>
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 14 }}>
        Generate API keys for programmatic access to multi-agent automation via REST APIs.
      </div>

      {generatedKey && (
        <div className="alert alert-success" style={{ marginBottom: 14, flexDirection: 'column', alignItems: 'flex-start', gap: 6 }}>
          <div style={{ fontWeight: 600, fontSize: 12 }}>New API Key Created:</div>
          <div style={{ display: 'flex', gap: 8, width: '100%', alignItems: 'center' }}>
            <input className="input mono" style={{ fontSize: 12, flex: 1 }} readOnly value={generatedKey} />
            <button className="btn btn-secondary" style={{ padding: '6px 10px', fontSize: 12 }} onClick={handleCopy}>
              {copied ? <Check size={13} style={{ color: '#10b981' }} /> : <Copy size={13} />}
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            Make sure to copy this key now. It will not be shown again.
          </div>
        </div>
      )}

      <form onSubmit={handleCreate} style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
        <input
          className="input"
          style={{ maxWidth: 300, fontSize: 12 }}
          placeholder="Key description (e.g. CI/CD Pipeline)"
          value={newKeyName}
          onChange={(e) => setNewKeyName(e.target.value)}
        />
        <button type="submit" className="btn btn-primary" style={{ fontSize: 12 }} disabled={loading}>
          {loading ? 'Generating…' : 'Generate API Key'}
        </button>
      </form>

      {keys.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {keys.map((k) => (
            <div key={k.public_id} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '8px 12px', background: 'var(--surface-0)', borderRadius: 6,
              border: '1px solid var(--border-subtle)',
            }}>
              <div>
                <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{k.name}</span>
                <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 10 }}>
                  {k.public_id?.slice(0, 16)}…
                </span>
              </div>
              <button
                className="btn btn-ghost"
                style={{ padding: '4px 8px', color: 'var(--accent-rose)' }}
                onClick={() => handleRevoke(k.public_id)}
                title="Revoke key"
              >
                <Trash2 size={13} />
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>
          No personal API keys generated yet.
        </div>
      )}
    </div>
  )
}

