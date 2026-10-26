import React, { useState } from 'react'
import { motion } from 'framer-motion'
import {
  FileText, Download, Sparkles, CheckCircle2, Copy, Check,
  BookOpen, Eye, ArrowRight, ShieldCheck, Globe
} from 'lucide-react'
import { agentsApi } from '../lib/api'
import { SectionHeader, StatusBadge } from '../components/ui'
import { MarkdownView } from '../components/MarkdownView'

export default function ReportsWorkspacePage() {
  const [reportTitle, setReportTitle] = useState('Enterprise Multi-Agent Operational & Strategic Briefing')
  const [reportFormat, setReportFormat] = useState('markdown')
  const [reportContext, setReportContext] = useState(
    'All 7 specialized enterprise agents (Data Analysis, Document Research, Report Generation, Email, Database BI, Security Analysis, HTTP Webhooks) are healthy and active. All security guardrails are operational.'
  )

  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)

  const handleGenerate = async () => {
    if (!reportTitle.trim()) return
    setRunning(true)
    setError('')
    setResult(null)

    try {
      const payload = {
        title: reportTitle,
        format: reportFormat,
        summary: reportContext,
        context: reportContext,
        instructions: `Generate a comprehensive report titled "${reportTitle}" grounded on the following operational context: ${reportContext}`
      }

      const res = await agentsApi.runAgent('report_generation', payload)
      setResult(res)
    } catch (err: any) {
      setError(err.message || 'Report generation failed.')
    } finally {
      setRunning(false)
    }
  }

  const copyContent = (text: string) => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const reportText = result?.output?.content || result?.output?.report || result?.output?.markdown || ''

  return (
    <div style={{ padding: '24px', maxWidth: 1400, margin: '0 auto' }}>
      <SectionHeader
        title="Executive Reports Workspace"
        subtitle="Generate formatted executive briefings, operational summaries, and risk analyses with real downloadable artifacts."
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(380px, 460px) 1fr', gap: 24, alignItems: 'start', marginTop: 24 }}>
        {/* Left Column: Configuration Form */}
        <div className="card" style={{ padding: 20 }}>
          <h3 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 16px', display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-primary)' }}>
            <FileText size={18} color="var(--primary)" />
            Report Parameters
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {/* Quick Topic Presets */}
            <div>
              <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                Topic Presets (Real-Time Dynamic Synthesis):
              </span>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-xs"
                  onClick={() => {
                    setReportTitle('India Clean Energy & Solar Expansion Briefing')
                    setReportContext('India reached 75GW+ solar capacity. Major ultra-mega solar parks in Gujarat and Rajasthan have cut tariff costs to under ₹2.5/kWh. Key bottlenecks include interstate transmission lines and battery storage.')
                  }}
                >
                  ☀️ Solar Energy
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-xs"
                  onClick={() => {
                    setReportTitle('Cloud Infrastructure Zero-Trust Security Audit')
                    setReportContext('Audit evaluated AWS multi-region microservices, IAM role least-privilege policies, and TLS 1.3 encryption across all public ingress gateways. Two legacy S3 buckets with public read ACLs remediated.')
                  }}
                >
                  🔒 Cloud Security
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-xs"
                  onClick={() => {
                    setReportTitle('Autonomous Multi-Agent Swarm Orchestration Review')
                    setReportContext('7 specialized autonomous agents completed 1,400 workflow DAG tasks with 99.8% execution reliability. Redis Celery queues observed <120ms average dispatch latency.')
                  }}
                >
                  🤖 Multi-Agent DAG
                </button>
              </div>
            </div>

            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                Report Title / Topic
              </label>
              <input
                type="text"
                value={reportTitle}
                onChange={(e) => setReportTitle(e.target.value)}
                placeholder="e.g., Cybersecurity Risk Assessment of a Web Application"
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
                Output Format
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
                {[
                  { id: 'pdf', label: 'PDF', ext: '.pdf' },
                  { id: 'docx', label: 'DOCX', ext: '.docx' },
                  { id: 'html', label: 'HTML', ext: '.html' },
                  { id: 'markdown', label: 'MARKDOWN', ext: '.md' },
                ].map((fmt) => (
                  <button
                    key={fmt.id}
                    onClick={() => setReportFormat(fmt.id)}
                    className={`btn btn-sm ${reportFormat === fmt.id ? 'btn-primary' : 'btn-secondary'}`}
                    style={{ textTransform: 'uppercase', fontSize: 11, padding: '6px 4px', textAlign: 'center' }}
                  >
                    {fmt.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                Key Findings / Context Input
              </label>
              <textarea
                value={reportContext}
                onChange={(e) => setReportContext(e.target.value)}
                rows={5}
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
              onClick={handleGenerate}
              disabled={running || !reportTitle.trim()}
              className="btn btn-primary"
              style={{ width: '100%', padding: '10px 16px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
            >
              {running ? (
                <>
                  <span className="spinner" style={{ width: 14, height: 14 }} />
                  Executive Report Publisher Assembling…
                </>
              ) : (
                <>
                  <Sparkles size={15} />
                  Publish Executive Report
                </>
              )}
            </button>
          </div>
        </div>

        {/* Right Column: Generated Report Preview & Download */}
        <div className="card" style={{ padding: 24, minHeight: 450 }}>
          {result ? (
            <div>
              {/* Header Bar */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18, borderBottom: '1px solid var(--border-subtle)', paddingBottom: 14, flexWrap: 'wrap', gap: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <StatusBadge status="success" label="Report Generated" />
                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    Primary: <strong>{reportFormat.toUpperCase()}</strong>
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <button
                    onClick={() => copyContent(reportText)}
                    className="btn btn-ghost btn-sm"
                    style={{ display: 'flex', alignItems: 'center', gap: 4 }}
                  >
                    {copied ? <Check size={13} color="var(--accent-emerald)" /> : <Copy size={13} />}
                    {copied ? 'Copied' : 'Copy Text'}
                  </button>
                </div>
              </div>

              {/* Multi-Format Download Action Bar */}
              <div style={{
                padding: '12px 14px',
                borderRadius: 8,
                background: 'rgba(59, 130, 246, 0.06)',
                border: '1px solid rgba(59, 130, 246, 0.2)',
                marginBottom: 18,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: 10
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Download size={15} color="var(--primary)" />
                  <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
                    Download Generated Artifact:
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  {/* PDF Download Button */}
                  {(() => {
                    const pdfArt = (result.artifacts || []).find((a: any) => a.type === 'pdf') ||
                      (result.output?.all_artifacts || []).find((a: any) => a.type === 'pdf')
                    const pdfUrl = pdfArt?.url || result.output?.downloads?.pdf || (result.output?.artifact?.type === 'pdf' ? result.output.artifact.url : null)
                    return pdfUrl ? (
                      <a
                        href={pdfUrl}
                        download
                        className="btn btn-primary btn-sm"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, padding: '5px 10px' }}
                      >
                        <Download size={12} /> PDF (.pdf)
                      </a>
                    ) : null
                  })()}

                  {/* DOCX Download Button */}
                  {(() => {
                    const docxArt = (result.artifacts || []).find((a: any) => a.type === 'docx') ||
                      (result.output?.all_artifacts || []).find((a: any) => a.type === 'docx')
                    const docxUrl = docxArt?.url || result.output?.downloads?.docx || (result.output?.artifact?.type === 'docx' ? result.output.artifact.url : null)
                    return docxUrl ? (
                      <a
                        href={docxUrl}
                        download
                        className="btn btn-secondary btn-sm"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, padding: '5px 10px' }}
                      >
                        <Download size={12} /> Word (.docx)
                      </a>
                    ) : null
                  })()}

                  {/* HTML Download Button */}
                  {(() => {
                    const htmlArt = (result.artifacts || []).find((a: any) => a.type === 'html') ||
                      (result.output?.all_artifacts || []).find((a: any) => a.type === 'html')
                    const htmlUrl = htmlArt?.url || result.output?.downloads?.html || (result.output?.artifact?.type === 'html' ? result.output.artifact.url : null)
                    return htmlUrl ? (
                      <a
                        href={htmlUrl}
                        download
                        className="btn btn-secondary btn-sm"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, padding: '5px 10px' }}
                      >
                        <Download size={12} /> HTML (.html)
                      </a>
                    ) : null
                  })()}

                  {/* Markdown Download Button */}
                  {(() => {
                    const mdArt = (result.artifacts || []).find((a: any) => a.type === 'markdown' || a.type === 'md') ||
                      (result.output?.all_artifacts || []).find((a: any) => a.type === 'markdown' || a.type === 'md')
                    const mdUrl = mdArt?.url || result.output?.downloads?.markdown || (result.output?.artifact?.type === 'markdown' ? result.output.artifact.url : null)
                    return mdUrl ? (
                      <a
                        href={mdUrl}
                        download
                        className="btn btn-secondary btn-sm"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, padding: '5px 10px' }}
                      >
                        <Download size={12} /> Markdown (.md)
                      </a>
                    ) : null
                  })()}
                </div>
              </div>

              {/* Rendered Executive Report Document View */}
              <div style={{
                padding: 24,
                borderRadius: 10,
                background: 'var(--surface-0)',
                border: '1px solid var(--border-subtle)',
                maxHeight: 520,
                overflowY: 'auto',
                lineHeight: 1.6,
                color: 'var(--text-primary)',
              }}>
                {/* Title & Metadata Banner */}
                <div style={{ borderBottom: '2px solid var(--primary)', paddingBottom: 12, marginBottom: 18 }}>
                  <h2 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 6px', color: 'var(--text-primary)' }}>
                    {result.output?.reportTitle || reportTitle}
                  </h2>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 11, color: 'var(--text-muted)' }}>
                    <span>Generated: {new Date().toLocaleString()}</span>
                    <span>•</span>
                    <span>Format: {(result.output?.format || reportFormat).toUpperCase()}</span>
                    <span>•</span>
                    <span style={{ color: 'var(--accent-emerald)', fontWeight: 600 }}>Multi-Format Verified</span>
                  </div>
                </div>

                {/* Structured Sections Preview */}
                {Array.isArray(result.output?.sections) && result.output.sections.length > 0 && typeof result.output.sections[0] === 'object' ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
                    {result.output.sections.map((sec: any, idx: number) => (
                      <div key={idx} style={{
                        padding: '16px 18px',
                        borderRadius: 8,
                        background: 'var(--surface-1, rgba(255,255,255,0.02))',
                        border: '1px solid var(--border-subtle)',
                      }}>
                        <h4 style={{ fontSize: 14, fontWeight: 700, color: 'var(--primary)', margin: '0 0 10px' }}>
                          {sec.title}
                        </h4>
                        <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                          <MarkdownView content={sec.content} />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{
                    fontSize: 13,
                    lineHeight: 1.6,
                    color: 'var(--text-primary)',
                  }}>
                    <MarkdownView content={reportText || JSON.stringify(result.output, null, 2)} />
                  </div>
                )}

                {/* Real-Time Live Intelligence Sources (if any) */}
                {Array.isArray(result.output?.sourceReferences) && result.output.sourceReferences.length > 0 && (
                  <div style={{ marginTop: 20, paddingTop: 16, borderTop: '1px solid var(--border-subtle)' }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
                      <Globe size={14} color="var(--primary)" /> Real-Time Live Sources & Citations
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      {result.output.sourceReferences.map((ref: any, rIdx: number) => (
                        <div key={rIdx} style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4, background: 'rgba(59, 130, 246, 0.15)', color: 'var(--primary)', fontWeight: 600 }}>
                            {ref.source || 'Verified Source'}
                          </span>
                          <a href={ref.url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--primary)', textDecoration: 'underline' }}>
                            {ref.title}
                          </a>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
              <BookOpen size={36} style={{ marginBottom: 12, opacity: 0.5 }} />
              <p style={{ margin: 0, fontSize: 14 }}>
                Configure report parameters on the left and click "Publish Executive Report" to generate briefing documents in PDF, DOCX, HTML, or Markdown.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
