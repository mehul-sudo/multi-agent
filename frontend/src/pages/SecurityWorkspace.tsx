import React, { useState } from 'react'
import { motion } from 'framer-motion'
import {
  ShieldAlert, Play, AlertCircle, CheckCircle2,
  Copy, Check, ShieldCheck, Terminal, Bug
} from 'lucide-react'
import { agentsApi } from '../lib/api'
import { SectionHeader, StatusBadge } from '../components/ui'
import { MarkdownView } from '../components/MarkdownView'

const SAMPLE_VULNERABLE_SNIPPET = `// User Authentication Controller
function login(req, res) {
  const username = req.body.username;
  const password = req.body.password;

  // Potential Vulnerability #1: SQL Injection
  const sql = "SELECT * FROM users WHERE username = '" + username + "' AND password = '" + password + "'";
  
  // Potential Vulnerability #2: Hardcoded Secret
  const aws_secret_key = "AKIA1234567890EXAMPLEKEY";

  return db.query(sql);
}`

export default function SecurityWorkspacePage() {
  const [content, setContent] = useState(SAMPLE_VULNERABLE_SNIPPET)
  const [scanType, setScanType] = useState('sast')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState('')

  const handleScan = async () => {
    if (!content.trim()) return
    setRunning(true)
    setError('')
    setResult(null)

    try {
      const payload = {
        content,
        scan_type: scanType,
      }
      const res = await agentsApi.runAgent('security_analysis', payload)
      setResult(res)
    } catch (err: any) {
      setError(err.message || 'Security scan failed.')
    } finally {
      setRunning(false)
    }
  }

  const findings = result?.output?.findings || result?.output?.vulnerabilities || []

  return (
    <div style={{ padding: '24px', maxWidth: 1400, margin: '0 auto' }}>
      <SectionHeader
        title="Security & Vulnerability Analysis Workspace"
        subtitle="Static application security testing (SAST), hardcoded credentials scanner, SQL injection detection, and injection guardrails."
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(380px, 460px) 1fr', gap: 24, alignItems: 'start', marginTop: 24 }}>
        {/* Left Column: Code / Config Input */}
        <div className="card" style={{ padding: 20 }}>
          <h3 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 16px', display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-primary)' }}>
            <ShieldAlert size={18} color="var(--accent-rose)" />
            Code & Config Payload
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                Source Code or Config to Scan
              </label>
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                rows={10}
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
              onClick={handleScan}
              disabled={running || !content.trim()}
              className="btn btn-primary"
              style={{ width: '100%', padding: '10px 16px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
            >
              {running ? (
                <>
                  <span className="spinner" style={{ width: 14, height: 14 }} />
                  Security Scanner Auditing…
                </>
              ) : (
                <>
                  <ShieldAlert size={15} />
                  Run Vulnerability Audit
                </>
              )}
            </button>
          </div>
        </div>

        {/* Right Column: Scan Findings & Triage */}
        <div className="card" style={{ padding: 24, minHeight: 400 }}>
          {result ? (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18, borderBottom: '1px solid var(--border-subtle)', paddingBottom: 14 }}>
                <StatusBadge
                  status={findings.length === 0 ? 'success' : 'failed'}
                  label={findings.length === 0 ? 'Clean (0 Findings)' : `${findings.length} Vulnerability Detected`}
                />
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  SAST Rule Engine: Active
                </span>
              </div>

              {/* Summary text */}
              <div style={{
                padding: 16,
                borderRadius: 8,
                background: 'var(--surface-0)',
                border: '1px solid var(--border-subtle)',
                marginBottom: 18,
                fontSize: 13,
                lineHeight: 1.6,
                color: 'var(--text-primary)',
              }}>
                <MarkdownView content={result.output?.summary || (findings.length > 0 ? 'Security vulnerabilities detected in code payload.' : 'No vulnerabilities detected.')} />
              </div>

              {/* Findings list */}
              {findings.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {findings.map((f: any, idx: number) => {
                    const severity = (f.severity || 'medium').toLowerCase()
                    const badgeColor = severity === 'critical' || severity === 'high' ? 'var(--accent-rose)' : 'var(--accent-amber)'
                    return (
                      <div
                        key={idx}
                        style={{
                          padding: 14,
                          borderRadius: 8,
                          background: 'var(--surface-0)',
                          border: '1px solid var(--border-subtle)',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
                            {f.type || f.rule || f.title || 'Security Finding'}
                          </span>
                          <span style={{
                            fontSize: 10,
                            fontWeight: 700,
                            padding: '2px 8px',
                            borderRadius: 4,
                            background: `${badgeColor}20`,
                            color: badgeColor,
                            textTransform: 'uppercase',
                          }}>
                            {severity}
                          </span>
                        </div>
                        <p style={{ margin: '0 0 6px', fontSize: 12, color: 'var(--text-secondary)' }}>
                          {f.description || f.message || JSON.stringify(f)}
                        </p>
                        {f.remediation && (
                          <div style={{ fontSize: 11, color: 'var(--accent-emerald)', fontWeight: 600 }}>
                            💡 Fix: {f.remediation}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          ) : (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
              <ShieldAlert size={36} style={{ marginBottom: 12, opacity: 0.5 }} />
              <p style={{ margin: 0, fontSize: 14 }}>
                Paste code or configuration on the left and click "Run Vulnerability Audit" to scan for security risks.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
