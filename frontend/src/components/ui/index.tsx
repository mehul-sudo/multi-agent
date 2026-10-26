// Shared UI components

import React from 'react'
import { Loader2 } from 'lucide-react'
import clsx from 'clsx'

// ─── Loading Spinner ────────────────────────────────────────────────────────
export function Spinner({ size = 18, className = '' }: { size?: number; className?: string }) {
  return (
    <Loader2
      size={size}
      className={clsx('animate-spin text-indigo-400', className)}
      style={{ animation: 'spin 0.7s linear infinite' }}
    />
  )
}

// ─── Page Loading ────────────────────────────────────────────────────────────
export function PageLoader({ message = 'Loading...' }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[300px] gap-4">
      <div className="spinner" />
      <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>{message}</p>
    </div>
  )
}

// ─── Error State ─────────────────────────────────────────────────────────────
export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>
      <div className="empty-state-title">Something went wrong</div>
      <div className="empty-state-desc">{message}</div>
      {onRetry && (
        <button className="btn btn-secondary" onClick={onRetry} style={{ marginTop: 8 }}>
          Try again
        </button>
      )}
    </div>
  )
}

// ─── Empty State ─────────────────────────────────────────────────────────────
export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: React.ReactNode
  title: string
  description?: string
  action?: React.ReactNode
}) {
  return (
    <div className="empty-state">
      {icon && <div className="empty-state-icon">{icon}</div>}
      <div className="empty-state-title">{title}</div>
      {description && <div className="empty-state-desc">{description}</div>}
      {action && <div style={{ marginTop: 12 }}>{action}</div>}
    </div>
  )
}

// ─── Not Available State ─────────────────────────────────────────────────────
export function NotAvailable({ feature, endpoint }: { feature: string; endpoint?: string }) {
  return (
    <div className="alert alert-unavailable" style={{ margin: '16px 0' }}>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ flexShrink: 0, marginTop: 1 }}>
        <circle cx="12" cy="12" r="10" />
        <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
      </svg>
      <div>
        <div style={{ fontWeight: 500, marginBottom: 2 }}>{feature} — Not Available</div>
        {endpoint && (
          <div style={{ fontSize: 12, opacity: 0.7 }}>
            Backend API required: <code className="mono">{endpoint}</code>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Status Badge ─────────────────────────────────────────────────────────────
export function StatusBadge({ status, label, children }: { status: string; label?: string; children?: React.ReactNode }) {
  const s = status?.toUpperCase?.() || status
  const map: Record<string, string> = {
    ACTIVE: 'badge-emerald',
    SUCCESS: 'badge-emerald',
    RUNNING: 'badge-sky',
    SUCCEEDED: 'badge-emerald',
    COMPLETED: 'badge-emerald',
    FAILED: 'badge-rose',
    CANCELLED: 'badge-gray',
    QUEUED: 'badge-amber',
    PENDING: 'badge-amber',
    PAUSED: 'badge-amber',
    BLOCKED: 'badge-rose',
    WAITING_FOR_APPROVAL: 'badge-amber',
    AWAITING_APPROVAL: 'badge-amber',
    WARNING: 'badge-amber',
    INFO: 'badge-sky',
    DRAFT: 'badge-gray',
    ARCHIVED: 'badge-gray',
    DISABLED: 'badge-gray',
    ACTIVE_WORKFLOW: 'badge-emerald',
    APPROVED: 'badge-emerald',
    REJECTED: 'badge-rose',
    HIGH: 'badge-rose',
    MEDIUM: 'badge-amber',
    LOW: 'badge-emerald',
  }
  const cls = map[s] || 'badge-gray'
  const displayLabel = label || children || (
    s === 'WAITING_FOR_APPROVAL' ? 'WAITING FOR APPROVAL' :
    s === 'AWAITING_APPROVAL' ? 'WAITING FOR APPROVAL' :
    s === 'PAUSED' ? 'AWAITING APPROVAL' :
    s === 'PENDING' ? 'QUEUED' :
    s === 'BLOCKED' ? 'BLOCKED' :
    status
  )
  return <span className={`badge ${cls}`}>{displayLabel}</span>
}


// ─── Stat Card ────────────────────────────────────────────────────────────────
export function StatCard({
  label,
  value,
  icon,
  accent = '#6366f1',
  suffix,
  loading,
}: {
  label: string
  value: number | string | null
  icon: React.ReactNode
  accent?: string
  suffix?: string
  loading?: boolean
}) {
  return (
    <div className="card" style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
          {label}
        </span>
        <div style={{
          width: 36, height: 36, borderRadius: 9,
          background: `${accent}18`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: accent,
        }}>
          {icon}
        </div>
      </div>
      {loading ? (
        <div className="skeleton" style={{ height: 32, width: '60%' }} />
      ) : (
        <div style={{ fontSize: 28, fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.03em', lineHeight: 1 }}>
          {value ?? '—'}
          {suffix && <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-muted)', marginLeft: 4 }}>{suffix}</span>}
        </div>
      )}
    </div>
  )
}

// ─── Section Header ───────────────────────────────────────────────────────────
export function SectionHeader({
  title,
  subtitle,
  actions,
}: {
  title: string
  subtitle?: string
  actions?: React.ReactNode
}) {
  return (
    <div className="page-header">
      <div>
        <h1 className="page-title">{title}</h1>
        {subtitle && <p className="page-subtitle">{subtitle}</p>}
      </div>
      {actions && <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>{actions}</div>}
    </div>
  )
}

// ─── Skeleton Rows ─────────────────────────────────────────────────────────────
export function SkeletonRows({ count = 3 }: { count?: number }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <tr key={i}>
          <td colSpan={99} style={{ padding: '12px 16px' }}>
            <div className="skeleton" style={{ height: 16, width: `${60 + (i % 3) * 15}%` }} />
          </td>
        </tr>
      ))}
    </>
  )
}

// ─── Modal ─────────────────────────────────────────────────────────────────────
export function Modal({
  open,
  onClose,
  title,
  children,
  footer,
  maxWidth = 560,
}: {
  open: boolean
  onClose: () => void
  title: string
  children: React.ReactNode
  footer?: React.ReactNode
  maxWidth?: number
}) {
  if (!open) return null

  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal animate-slideUp" style={{ maxWidth }}>
        <div className="modal-header">
          <h2 className="modal-title">{title}</h2>
          <button className="btn btn-ghost" style={{ padding: '4px 8px' }} onClick={onClose}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  )
}

// ─── Form Group ────────────────────────────────────────────────────────────────
export function FormGroup({
  label,
  children,
  hint,
  required,
}: {
  label: React.ReactNode
  children: React.ReactNode
  hint?: string
  required?: boolean
}) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label className="label">
        {label}
        {required && <span style={{ color: 'var(--accent-rose)', marginLeft: 2 }}>*</span>}
      </label>
      {children}
      {hint && <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{hint}</p>}
    </div>
  )
}

// ─── Copy Button ──────────────────────────────────────────────────────────────
export function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = React.useState(false)
  const copy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }
  return (
    <button
      onClick={copy}
      className="btn btn-ghost"
      style={{ padding: '3px 6px', fontSize: 11 }}
      data-tooltip={copied ? 'Copied!' : 'Copy'}
    >
      {copied ? (
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12" /></svg>
      ) : (
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" /></svg>
      )}
    </button>
  )
}

// ─── Risk Level Badge ──────────────────────────────────────────────────────────
export function RiskBadge({ level }: { level: string }) {
  const l = level?.toLowerCase()
  const cls = l === 'high' ? 'badge-rose' : l === 'medium' ? 'badge-amber' : 'badge-emerald'
  return <span className={`badge ${cls}`}>{level}</span>
}
