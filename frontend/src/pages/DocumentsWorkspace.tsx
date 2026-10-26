import React, { useState } from 'react'
import { motion } from 'framer-motion'
import {
  FileText, Upload, Sparkles, Search, CheckCircle, AlertCircle,
  Copy, Check, BookOpen, Quote, Download
} from 'lucide-react'
import { uploadsApi, agentsApi } from '../lib/api'
import { SectionHeader, StatusBadge } from '../components/ui'
import { MarkdownView } from '../components/MarkdownView'

export default function DocumentsWorkspacePage() {
  const [query, setQuery] = useState('What are the key record retention and compliance rules?')
  const [mode, setMode] = useState<'file' | 'custom' | 'web'>('file')
  const [docContent, setDocContent] = useState(
    'SEC Compliance Rule 17a-4 mandates financial transaction records, audit logs, and ledger books must be preserved for at least 7 years in immutable format.\n\nGeneral application diagnostic logs expire after 90 days in cold storage.\n\nEmployee telemetry data is automatically deleted after 30 days.'
  )
  const [uploadedFileId, setUploadedFileId] = useState<string | null>(null)
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)

  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [qaHistory, setQaHistory] = useState<Array<{ query: string; result: any }>>([])
  const [followUpQuery, setFollowUpQuery] = useState('')
  const [expandedExcerpts, setExpandedExcerpts] = useState<Record<number, boolean>>({})
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setError('')
    try {
      const res = await uploadsApi.upload(file)
      setUploadedFileId(res.file_id)
      setUploadedFileName(res.filename)
      setMode('file')
    } catch (err: any) {
      setError(err.message || 'File upload failed.')
    } finally {
      setUploading(false)
    }
  }

  const handleRun = async () => {
    if (!query.trim()) return
    setError('')

    setRunning(true)
    setResult(null)

    try {
      let payload: any = { query, mode }
      if (mode === 'file') {
        if (!uploadedFileId) {
          setError('Please upload or select a document (PDF, DOCX, PPTX, TXT) first.')
          setRunning(false)
          return
        }
        payload.file_id = uploadedFileId
      } else if (mode === 'custom') {
        if (!docContent.trim()) {
          setError('Please paste or write document text to research.')
          setRunning(false)
          return
        }
        payload.documents = [docContent]
      } else {
        payload.query = query
        payload.mode = 'web'
        payload.web_search = true
      }

      const res = await agentsApi.runAgent('document_research', payload)
      setResult(res)
      setQaHistory([{ query, result: res }])
    } catch (err: any) {
      setError(err.message || 'Document research execution failed.')
    } finally {
      setRunning(false)
    }
  }

  const handleFollowUp = async (e?: React.FormEvent, customQ?: string) => {
    if (e) e.preventDefault()
    const q = (customQ || followUpQuery).trim()
    if (!q || running) return
    setError('')
    setFollowUpQuery('')
    setRunning(true)

    try {
      let payload: any = { query: q, mode }
      if (mode === 'file' && uploadedFileId) {
        payload.file_id = uploadedFileId
      } else if (mode === 'custom' && docContent.trim()) {
        payload.documents = [docContent]
      } else if (mode === 'web') {
        payload.mode = 'web'
        payload.web_search = true
      }
      const res = await agentsApi.runAgent('document_research', payload)
      setResult(res)
      setQaHistory(prev => [...prev, { query: q, result: res }])
    } catch (err: any) {
      setError(err.message || 'Follow-up query failed.')
    } finally {
      setRunning(false)
    }
  }

  const toggleExcerpt = (idx: number) => {
    setExpandedExcerpts(prev => ({ ...prev, [idx]: !prev[idx] }))
  }

  const copyText = (txt: string) => {
    navigator.clipboard.writeText(txt)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div style={{ padding: '24px', maxWidth: 1400, margin: '0 auto' }}>
      <SectionHeader
        title="Documents & Knowledge Workspace"
        subtitle="Upload enterprise policies, manuals, PowerPoint presentations, or PDF reports. Ask questions naturally with grounded fact retrieval and citations."
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(380px, 480px) 1fr', gap: 24, alignItems: 'start', marginTop: 24 }}>
        {/* Left Column: Upload & Input Form */}
        <div className="card" style={{ padding: 20 }}>
          <h3 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 16px', display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-primary)' }}>
            <FileText size={18} color="var(--primary)" />
            Document Source
          </h3>

          {/* Mode Selector */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
            <button
              onClick={() => setMode('file')}
              className={`btn btn-sm ${mode === 'file' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ flex: 1 }}
            >
              Upload Document
            </button>
            <button
              onClick={() => setMode('custom')}
              className={`btn btn-sm ${mode === 'custom' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ flex: 1 }}
            >
              Paste Text
            </button>
            <button
              onClick={() => setMode('web')}
              className={`btn btn-sm ${mode === 'web' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ flex: 1 }}
            >
              Public Knowledge
            </button>
          </div>

          {mode === 'file' && (
            <div style={{ marginBottom: 16 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 8 }}>
                Upload PDF, DOCX, PPTX, TXT, or MD
              </label>
              <div style={{
                border: '2px dashed var(--border-subtle)',
                borderRadius: 10,
                padding: '24px 16px',
                textAlign: 'center',
                background: 'var(--surface-0)',
                cursor: 'pointer',
              }}>
                <label style={{ cursor: 'pointer' }}>
                  <Upload size={24} style={{ color: 'var(--text-muted)', marginBottom: 8 }} />
                  <p style={{ margin: 0, fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
                    {uploading ? 'Processing File…' : 'Click to browse files'}
                  </p>
                  <p style={{ margin: '4px 0 0', fontSize: 11, color: 'var(--text-muted)' }}>
                    Supports enterprise PDFs, Word docs, PowerPoint (.pptx), Markdown, text files
                  </p>
                  <input
                    type="file"
                    accept=".pdf,.docx,.doc,.pptx,.txt,.md"
                    style={{ display: 'none' }}
                    onChange={handleFileUpload}
                    disabled={uploading}
                  />
                </label>
              </div>

              {uploadedFileName ? (
                <div style={{
                  marginTop: 10,
                  padding: '8px 12px',
                  borderRadius: 6,
                  background: 'var(--surface-2)',
                  fontSize: 12,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}>
                  <span style={{ fontWeight: 600, color: 'var(--accent-emerald)' }}>✓ {uploadedFileName}</span>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Active</span>
                </div>
              ) : (
                <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', background: 'var(--surface-1)', borderRadius: 6, fontSize: 11, border: '1px solid var(--border-subtle)' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>💡 Or start with standard policy handbook</span>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    style={{ fontSize: 11, padding: '3px 8px' }}
                    onClick={() => {
                      setMode('custom')
                    }}
                  >
                    View Preloaded Policy
                  </button>
                </div>
              )}
            </div>
          )}

          {mode === 'custom' && (
            <div style={{ marginBottom: 16 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                Document Text
              </label>
              <textarea
                value={docContent}
                onChange={(e) => setDocContent(e.target.value)}
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
          )}

          {/* Research Query Box */}
          <div style={{ marginBottom: 16 }}>
            <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
              Natural Language Question / Topic
            </label>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g., What are the retention requirements for financial records?"
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
            {/* Quick Preset Query Chips */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
              {[
                { label: 'Retention Rules', q: 'What are the key record retention and compliance rules?' },
                { label: 'Telemetry & Logs', q: 'When are employee telemetry and diagnostic logs deleted?' },
                { label: 'Multi-Agent Safety', q: 'What operations require human verification or authorization?' },
                { label: '🌐 Live AI News', q: 'Latest AI regulation guidelines and enterprise compliance standards', targetMode: 'web' }
              ].map((p, idx) => (
                <button
                  key={idx}
                  type="button"
                  className="btn btn-ghost btn-sm"
                  style={{ fontSize: 11, padding: '2px 8px', borderRadius: 12, border: '1px solid var(--border-subtle)' }}
                  onClick={() => {
                    setQuery(p.q)
                    if (p.targetMode) setMode(p.targetMode as any)
                  }}
                >
                  {p.label}
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
              marginBottom: 12,
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}>
              <AlertCircle size={14} /> {error}
            </div>
          )}

          <button
            onClick={handleRun}
            disabled={running || !query.trim()}
            className="btn btn-primary"
            style={{ width: '100%', padding: '10px 16px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
          >
            {running ? (
              <>
                <span className="spinner" style={{ width: 14, height: 14 }} />
                Research Agent Analyzing…
              </>
            ) : (
              <>
                <Search size={15} />
                Ask Document Research Agent
              </>
            )}
          </button>
        </div>

        {/* Right Column: Grounded Result */}
        <div className="card" style={{ padding: 24, minHeight: 450, display: 'flex', flexDirection: 'column' }}>
          {result ? (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
              {/* Document Header & Metadata */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 16,
                borderBottom: '1px solid var(--border-subtle)',
                paddingBottom: 14,
                flexWrap: 'wrap',
                gap: 10,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{ background: 'rgba(14,165,233,0.12)', borderRadius: 8, padding: 6, color: '#0ea5e9' }}>
                    <FileText size={18} />
                  </div>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
                        {uploadedFileName || result.output?.document_title || 'Document Research'}
                      </span>
                      <StatusBadge status="success" label="Grounded" />
                    </div>
                    <div style={{ display: 'flex', gap: 12, marginTop: 3, fontSize: 11, color: 'var(--text-muted)' }}>
                      <span>Target: <strong style={{ color: 'var(--text-secondary)' }}>{result.output?.query_target ? String(result.output.query_target).replace(/_/g, ' ') : 'General Analysis'}</strong></span>
                      {result.output?.target_page && <span>Page: <strong>{result.output.target_page}</strong></span>}
                      {result.output?.target_slide && <span>Slide: <strong>{result.output.target_slide}</strong></span>}
                      {result.output?.total_passages_analyzed && (
                        <span>Indexed: <strong>{result.output.total_passages_analyzed} passages</strong></span>
                      )}
                      <span>Confidence: <strong style={{ color: 'var(--accent-emerald)' }}>{result.output?.confidence_score ? `${Math.round(result.output.confidence_score * 100)}%` : '95%'}</strong></span>
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <button
                    onClick={() => copyText(result.output?.synthesis || result.output?.answer || '')}
                    className="btn btn-ghost btn-sm"
                    style={{ display: 'flex', alignItems: 'center', gap: 4 }}
                  >
                    {copied ? <Check size={13} color="var(--accent-emerald)" /> : <Copy size={13} />}
                    {copied ? 'Copied!' : 'Copy Answer'}
                  </button>
                </div>
              </div>

              {/* Synthesized Answer with clean typography */}
              <div style={{ marginBottom: 20 }}>
                <h4 style={{ fontSize: 12, fontWeight: 700, margin: '0 0 10px', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Research Response &amp; Analysis
                </h4>
                <div style={{
                  padding: 20,
                  borderRadius: 10,
                  background: 'var(--surface-0)',
                  border: '1px solid var(--border-subtle)',
                  fontSize: 13.5,
                  lineHeight: 1.7,
                  color: 'var(--text-primary)',
                }}>
                  <MarkdownView content={result.output?.synthesis || result.output?.answer || 'No explicit synthesis returned.'} />
                </div>
              </div>

              {/* Key Takeaways (if present and distinct) */}
              {(() => {
                const takeaways = (result.output?.key_takeaways && result.output.key_takeaways.length > 0)
                  ? result.output.key_takeaways
                  : (result.output?.key_points || [])
                return takeaways.length > 0 ? (
                  <div style={{ marginBottom: 20 }}>
                    <h4 style={{ fontSize: 12, fontWeight: 700, margin: '0 0 8px', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      Key Takeaways &amp; Findings
                    </h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {takeaways.map((item: string, idx: number) => (
                        <div
                          key={idx}
                          style={{
                            padding: '8px 12px',
                            borderRadius: 6,
                            background: 'var(--surface-0)',
                            border: '1px solid var(--border-subtle)',
                            fontSize: 12.5,
                            color: 'var(--text-primary)',
                            display: 'flex',
                            alignItems: 'flex-start',
                            gap: 8,
                          }}
                        >
                          <CheckCircle size={14} color="var(--accent-emerald)" style={{ flexShrink: 0, marginTop: 3 }} />
                          <div style={{ lineHeight: 1.5, flex: 1 }}>
                            <MarkdownView content={item} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null
              })()}

              {/* Citations & Verified Sources (Compact & Clean with preview toggle) */}
              {(() => {
                const citationsList = (result.output?.sources && result.output.sources.length > 0)
                  ? result.output.sources
                  : (result.output?.passages || result.output?.citations || [])
                return citationsList.length > 0 ? (
                  <div style={{ marginBottom: 24 }}>
                    <h4 style={{ fontSize: 12, fontWeight: 700, margin: '0 0 10px', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      Verified Citations ({citationsList.length})
                    </h4>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 8 }}>
                      {citationsList.map((p: any, idx: number) => {
                        const docTitle = p.documentName || p.doc_name || p.name || uploadedFileName || `Source #${idx + 1}`
                        const excerpt = p.excerpt || p.text || p.content || (typeof p === 'string' ? p : '')
                        const loc = p.page ? `Page ${p.page}` : (p.slide ? `Slide ${p.slide}` : (p.paragraph ? `Para ${p.paragraph}` : null))
                        const isExpanded = expandedExcerpts[idx]
                        return (
                          <div
                            key={idx}
                            style={{
                              padding: '10px 12px',
                              borderRadius: 8,
                              background: 'var(--surface-0)',
                              border: '1px solid var(--border-subtle)',
                              fontSize: 12,
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
                              <span style={{ fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 170 }}>
                                📄 {docTitle} {loc ? `— ${loc}` : ''}
                              </span>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                {p.score && (
                                  <span style={{ fontSize: 10, padding: '1px 5px', borderRadius: 4, background: 'rgba(16, 185, 129, 0.1)', color: 'var(--accent-emerald)', fontWeight: 600 }}>
                                    {Math.min(100, Math.round(p.score * 100))}% match
                                  </span>
                                )}
                                {excerpt && (
                                  <button
                                    type="button"
                                    onClick={() => toggleExcerpt(idx)}
                                    className="btn btn-ghost"
                                    style={{ fontSize: 10, padding: '2px 6px', color: 'var(--primary)', cursor: 'pointer' }}
                                  >
                                    {isExpanded ? '▲ Hide' : '▼ Preview'}
                                  </button>
                                )}
                              </div>
                            </div>

                            {isExpanded && excerpt && (
                              <div style={{
                                marginTop: 8,
                                padding: '8px 10px',
                                borderRadius: 6,
                                background: 'var(--surface-1)',
                                border: '1px solid var(--border-subtle)',
                                fontSize: 11,
                                color: 'var(--text-secondary)',
                                fontStyle: 'italic',
                                lineHeight: 1.45,
                                maxHeight: 150,
                                overflowY: 'auto',
                              }}>
                                "{excerpt}"
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </div>
                ) : null
              })()}

              {/* Follow-up Question Section (Support same document follow-up) */}
              <div style={{
                marginTop: 'auto',
                paddingTop: 16,
                borderTop: '1px solid var(--border-subtle)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    Ask Follow-up Question
                  </span>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    Context preserved for <strong>{uploadedFileName || 'current document'}</strong>
                  </span>
                </div>

                <form onSubmit={handleFollowUp} style={{ display: 'flex', gap: 8 }}>
                  <input
                    type="text"
                    value={followUpQuery}
                    onChange={(e) => setFollowUpQuery(e.target.value)}
                    placeholder="Ask a follow-up (e.g. 'Explain page 14', 'What are the main risks?', 'Summarize in 3 bullet points')..."
                    disabled={running}
                    style={{
                      flex: 1,
                      padding: '10px 14px',
                      borderRadius: 8,
                      background: 'var(--surface-0)',
                      border: '1px solid var(--border-subtle)',
                      color: 'var(--text-primary)',
                      fontSize: 13,
                    }}
                  />
                  <button
                    type="submit"
                    disabled={running || !followUpQuery.trim()}
                    className="btn btn-primary"
                    style={{ padding: '0 18px', display: 'flex', alignItems: 'center', gap: 6 }}
                  >
                    {running ? <span className="spinner" style={{ width: 14, height: 14 }} /> : <Search size={14} />}
                    <span>Ask Follow-up</span>
                  </button>
                </form>

                {/* Quick Follow-up Suggestions */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
                  {[
                    'Explain key concepts in simple terms',
                    'Summarize the primary takeaways',
                    'What are the limitations or risks discussed?'
                  ].map((sug, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => handleFollowUp(undefined, sug)}
                      disabled={running}
                      className="btn btn-ghost btn-sm"
                      style={{ fontSize: 11, padding: '2px 8px', borderRadius: 12, border: '1px solid var(--border-subtle)' }}
                    >
                      💡 {sug}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div style={{ padding: 60, textAlign: 'center', color: 'var(--text-muted)', margin: 'auto' }}>
              <BookOpen size={40} style={{ marginBottom: 12, opacity: 0.4 }} />
              <p style={{ margin: '0 0 6px', fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
                No Document Selected Yet
              </p>
              <p style={{ margin: 0, fontSize: 12, color: 'var(--text-muted)', maxWidth: 400 }}>
                Upload an enterprise document on the left or enter a query to get grounded, citation-backed answers.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
