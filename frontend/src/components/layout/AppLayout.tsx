import React, { useState, useEffect } from 'react'
import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import {
  LayoutDashboard, Bot, GitBranch, Play, Shield,
  BarChart3, Settings, LogOut, ChevronRight,
  Activity, Zap, Menu, X, Bell, MessageSquare, Layers,
  FileText, FileCheck, Mail,
  Database, ShieldAlert, CheckCircle2, Clock, ExternalLink
} from 'lucide-react'
import clsx from 'clsx'
import { approvalsApi } from '../../lib/api'

interface NavSection {
  title: string
  items: Array<{
    path: string
    label: string
    icon: any
    badge?: string
  }>
}

const navSections: NavSection[] = [
  {
    title: 'OVERVIEW',
    items: [
      { path: '/', label: 'Overview', icon: LayoutDashboard },
    ],
  },
  {
    title: 'WORKSPACE',
    items: [
      { path: '/chat', label: 'Chat Assistant', icon: MessageSquare },
      { path: '/tasks', label: 'Task Manager', icon: Layers },
      { path: '/documents', label: 'Documents', icon: FileText },
      { path: '/data-analysis', label: 'Data Analysis', icon: BarChart3 },
      { path: '/reports', label: 'Reports', icon: FileCheck },
      { path: '/messaging', label: 'Messaging', icon: Mail },
    ],
  },
  {
    title: 'AUTOMATION',
    items: [
      { path: '/agents', label: 'Agents Studio', icon: Bot },
      { path: '/workflows', label: 'Workflows', icon: GitBranch },
      { path: '/executions', label: 'Executions', icon: Play },
      { path: '/approvals', label: 'Approvals', icon: Shield },
    ],
  },
  {
    title: 'INSIGHTS',
    items: [
      { path: '/database-bi', label: 'Database & BI', icon: Database },
      { path: '/security', label: 'Security Analysis', icon: ShieldAlert },
    ],
  },
  {
    title: 'SYSTEM',
    items: [
      { path: '/results', label: 'Analytics', icon: Activity },
      { path: '/settings', label: 'Settings', icon: Settings },
    ],
  },
]

// ─── Page-Level Error Boundary ────────────────────────────────────────────────
class PageErrorBoundaryInner extends React.Component<
  { children: React.ReactNode; locationKey: string },
  { hasError: boolean; error: Error | null; lastKey: string }
> {
  constructor(props: any) {
    super(props)
    this.state = { hasError: false, error: null, lastKey: props.locationKey }
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }
  static getDerivedStateFromProps(
    props: { locationKey: string },
    state: { hasError: boolean; lastKey: string; error: Error | null }
  ) {
    if (props.locationKey !== state.lastKey) {
      return { hasError: false, error: null, lastKey: props.locationKey }
    }
    return null
  }
  componentDidCatch(error: Error) {
    console.error('[PageErrorBoundary]', error)
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: 40, display: 'flex', flexDirection: 'column',
          alignItems: 'center', gap: 16, minHeight: 400,
          justifyContent: 'center',
        }}>
          <div style={{ fontSize: 28 }}>⚠️</div>
          <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>
            This page crashed
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', maxWidth: 420, textAlign: 'center' }}>
            {this.state.error?.message || 'An unexpected error occurred.'}
          </div>
          <button
            className="btn btn-secondary"
            onClick={() => this.setState({ hasError: false, error: null })}
            style={{ fontSize: 12 }}
          >
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

function PageErrorBoundary({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  return (
    <PageErrorBoundaryInner locationKey={location.pathname}>
      {children}
    </PageErrorBoundaryInner>
  )
}

function LogoMark() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <div style={{
        width: 32, height: 32, borderRadius: 8,
        background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        boxShadow: '0 4px 12px rgba(99,102,241,0.35)',
        flexShrink: 0,
      }}>
        <Zap size={16} color="white" />
      </div>
      <div>
        <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em', lineHeight: 1.2 }}>
          OrchestrAI
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>
          ENTERPRISE
        </div>
      </div>
    </div>
  )
}

export default function AppLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [notifOpen, setNotifOpen] = useState(false)
  const [pendingApprovalsCount, setPendingApprovalsCount] = useState(0)

  useEffect(() => {
    const fetchApprovals = () => {
      approvalsApi.listPending()
        .then((items: any[]) => {
          if (Array.isArray(items)) setPendingApprovalsCount(items.length)
        })
        .catch(() => {})
    }

    fetchApprovals()

    const interval = setInterval(() => {
      fetchApprovals()
    }, 4000)

    return () => {
      clearInterval(interval)
    }
  }, [])

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const sidebarWidth = collapsed ? 64 : 224

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--surface-0)' }}>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 40 }}
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside style={{
        width: sidebarWidth,
        minHeight: '100vh',
        background: 'var(--surface-1)',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        transition: 'width 0.2s ease',
        overflow: 'hidden',
        flexShrink: 0,
        position: 'sticky',
        top: 0,
        height: '100vh',
        zIndex: 30,
      }}>
        {/* Logo */}
        <div style={{
          padding: '16px 14px 14px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
        }}>
          {!collapsed && <LogoMark />}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="btn btn-ghost"
            style={{ padding: '4px 6px', flexShrink: 0 }}
          >
            <ChevronRight
              size={14}
              style={{
                transform: collapsed ? 'rotate(0deg)' : 'rotate(180deg)',
                transition: 'transform 0.2s ease',
                color: 'var(--text-muted)',
              }}
            />
          </button>
        </div>

        {/* Grouped Nav */}
        <nav style={{ flex: 1, padding: '10px 8px', display: 'flex', flexDirection: 'column', gap: 14, overflowY: 'auto' }}>
          {navSections.map((section) => (
            <div key={section.title}>
              {!collapsed && (
                <div style={{
                  fontSize: 10,
                  fontWeight: 700,
                  color: 'var(--text-muted)',
                  letterSpacing: '0.06em',
                  paddingLeft: 10,
                  marginBottom: 4,
                  textTransform: 'uppercase',
                }}>
                  {section.title}
                </div>
              )}

              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {section.items.map(({ path, label, icon: Icon }) => (
                  <NavLink
                    key={path}
                    to={path}
                    end={path === '/'}
                    className={({ isActive }) => clsx('sidebar-link', { active: isActive })}
                    style={{ justifyContent: collapsed ? 'center' : undefined, padding: '7px 10px', fontSize: 12.5 }}
                    data-tooltip={collapsed ? label : undefined}
                  >
                    <Icon size={15} style={{ flexShrink: 0 }} />
                    {!collapsed && <span>{label}</span>}
                    {!collapsed && path === '/approvals' && pendingApprovalsCount > 0 && (
                      <span style={{
                        marginLeft: 'auto',
                        background: 'var(--accent-amber)',
                        color: 'black',
                        fontSize: 10,
                        fontWeight: 700,
                        padding: '1px 6px',
                        borderRadius: 10,
                      }}>
                        {pendingApprovalsCount}
                      </span>
                    )}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* User section */}
        <div style={{
          padding: '10px 8px',
          borderTop: '1px solid var(--border-subtle)',
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
        }}>
          {!collapsed && user && (
            <div style={{
              padding: '6px 8px',
              borderRadius: 6,
              background: 'var(--surface-2)',
              marginBottom: 2,
            }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>
                {user.username}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                <span className="status-dot active" />
                <span>{user.role}</span>
              </div>
            </div>
          )}
          <button
            onClick={handleLogout}
            className="sidebar-link"
            style={{ justifyContent: collapsed ? 'center' : undefined, color: 'var(--accent-rose)', width: '100%', padding: '6px 10px' }}
            data-tooltip={collapsed ? 'Sign out' : undefined}
          >
            <LogOut size={15} />
            {!collapsed && <span style={{ fontSize: 12 }}>Sign out</span>}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Top bar */}
        <header style={{
          height: 54,
          background: 'var(--surface-1)',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          padding: '0 24px',
          gap: 16,
          position: 'sticky',
          top: 0,
          zIndex: 20,
        }}>
          <button
            className="btn btn-ghost"
            style={{ padding: '4px', display: 'none' }}
            onClick={() => setMobileOpen(!mobileOpen)}
          >
            <Menu size={18} />
          </button>

          <div style={{ flex: 1 }} />

          {/* System status indicators */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div
              style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--accent-emerald)', fontWeight: 600 }}
              data-tooltip="All 8 specialized agent engines operational"
            >
              <span className="status-dot active" />
              <span>Multi-Agent Live</span>
            </div>

            {/* Notification Bell */}
            <div style={{ position: 'relative' }}>
              <button
                className="btn btn-ghost"
                style={{ padding: '6px', position: 'relative' }}
                onClick={() => setNotifOpen(!notifOpen)}
              >
                <Bell size={16} />
                {pendingApprovalsCount > 0 && (
                  <span style={{
                    position: 'absolute',
                    top: 2,
                    right: 2,
                    width: 7,
                    height: 7,
                    borderRadius: '50%',
                    background: 'var(--accent-amber)',
                  }} />
                )}
              </button>

              {/* Notification Popover */}
              {notifOpen && (
                <div style={{
                  position: 'absolute',
                  top: '100%',
                  right: 0,
                  marginTop: 8,
                  width: 300,
                  background: 'var(--surface-1)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 10,
                  boxShadow: '0 10px 25px rgba(0,0,0,0.2)',
                  padding: 14,
                  zIndex: 50,
                }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 10, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>Notifications & Alerts</span>
                    <button
                      onClick={() => setNotifOpen(false)}
                      style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 0 }}
                    >
                      <X size={14} />
                    </button>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {pendingApprovalsCount > 0 ? (
                      <div
                        onClick={() => { setNotifOpen(false); navigate('/approvals'); }}
                        style={{
                          padding: 10,
                          borderRadius: 6,
                          background: 'rgba(245, 158, 11, 0.1)',
                          border: '1px solid var(--accent-amber)',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 8,
                        }}
                      >
                        <Shield size={16} color="var(--accent-amber)" />
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
                            {pendingApprovalsCount} Action(s) Awaiting Approval
                          </div>
                          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                            Click to review human authorization gates
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: '6px 0' }}>
                        No pending human approvals required.
                      </div>
                    )}

                  </div>
                </div>
              )}
            </div>

            {/* User avatar */}
            <div style={{
              width: 28, height: 28, borderRadius: '50%',
              background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 11, fontWeight: 700, color: 'white',
            }}>
              {user?.username?.[0]?.toUpperCase() ?? 'U'}
            </div>
          </div>
        </header>

        {/* Page content */}
        <main style={{ flex: 1, overflow: 'auto' }}>
          <PageErrorBoundary>
            <Outlet />
          </PageErrorBoundary>
        </main>
      </div>
    </div>
  )
}
