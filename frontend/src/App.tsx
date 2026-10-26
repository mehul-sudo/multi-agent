import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import AppLayout from './components/layout/AppLayout'
import LoginPage from './pages/Login'
import OverviewPage from './pages/Overview'
import AgentsPage from './pages/Agents'
import WorkflowsPage from './pages/Workflows'
import WorkflowDetailPage from './pages/WorkflowDetail'
import ExecutionsPage from './pages/Executions'
import ApprovalsPage from './pages/Approvals'
import ResultsPage from './pages/Results'
import SettingsPage from './pages/Settings'

// Dedicated Enterprise Workspaces
import ChatAssistantPage from './pages/ChatAssistant'
import TaskManagerPage from './pages/TaskManager'
import DocumentsWorkspacePage from './pages/DocumentsWorkspace'
import DataAnalysisWorkspacePage from './pages/DataAnalysisWorkspace'
import ReportsWorkspacePage from './pages/ReportsWorkspace'
import MessagingWorkspacePage from './pages/MessagingWorkspace'
import DatabaseBIWorkspacePage from './pages/DatabaseBIWorkspace'
import SecurityWorkspacePage from './pages/SecurityWorkspace'

// ─── Error Boundary ───────────────────────────────────────────────────────────
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: any) {
    super(props)
    this.state = { hasError: false, error: null }
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[ErrorBoundary] Caught error:', error, info)
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          minHeight: '100vh', background: 'var(--surface-0)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 16, padding: 32,
        }}>
          <div style={{ fontSize: 32 }}>⚠️</div>
          <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)' }}>
            Something went wrong
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-muted)', maxWidth: 480, textAlign: 'center' }}>
            {this.state.error?.message || 'An unexpected error occurred in this page.'}
          </div>
          <button
            className="btn btn-primary"
            onClick={() => { this.setState({ hasError: false, error: null }); window.location.href = '/' }}
          >
            Return to Dashboard
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div style={{
        minHeight: '100vh',
        background: 'var(--surface-0)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexDirection: 'column',
        gap: 16,
      }}>
        <div style={{
          width: 48, height: 48, borderRadius: 12,
          background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
          </svg>
        </div>
        <div className="spinner" />
        <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>Restoring session…</p>
      </div>
    )
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}

function PublicOnly({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()
  if (isLoading) return null
  if (isAuthenticated) return <Navigate to="/" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public */}
            <Route path="/login" element={<PublicOnly><LoginPage /></PublicOnly>} />

            {/* Protected Enterprise Platform */}
            <Route
              path="/"
              element={
                <RequireAuth>
                  <AppLayout />
                </RequireAuth>
              }
            >
              {/* OVERVIEW */}
              <Route index element={<OverviewPage />} />

              {/* WORKSPACE */}
              <Route path="chat" element={<ChatAssistantPage key="chat" />} />
              <Route path="tasks" element={<TaskManagerPage />} />
              <Route path="documents" element={<DocumentsWorkspacePage />} />
              <Route path="data-analysis" element={<DataAnalysisWorkspacePage />} />
              <Route path="reports" element={<ReportsWorkspacePage />} />
              <Route path="messaging" element={<MessagingWorkspacePage />} />

              {/* AUTOMATION */}
              <Route path="agents" element={<AgentsPage />} />
              <Route path="workflows" element={<WorkflowsPage />} />
              <Route path="workflows/:id" element={<WorkflowDetailPage />} />
              <Route path="executions" element={<ExecutionsPage />} />
              <Route path="approvals" element={<ApprovalsPage />} />

              {/* INSIGHTS */}
              <Route path="database-bi" element={<DatabaseBIWorkspacePage />} />
              <Route path="security" element={<SecurityWorkspacePage />} />

              {/* SYSTEM */}
              <Route path="results" element={<ResultsPage />} />
              <Route path="settings" element={<SettingsPage />} />
            </Route>

            {/* Catch-all */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ErrorBoundary>
  )
}
