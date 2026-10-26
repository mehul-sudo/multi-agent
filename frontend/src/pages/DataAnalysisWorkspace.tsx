import React, { useState } from 'react'
import { motion } from 'framer-motion'
import {
  BarChart3, Upload, TrendingUp, AlertTriangle, CheckCircle,
  Copy, Check, FileSpreadsheet, Download, RefreshCw, Layers,
  ChevronRight, Database
} from 'lucide-react'
import { uploadsApi, agentsApi } from '../lib/api'
import { SectionHeader, StatusBadge } from '../components/ui'
import { MarkdownView } from '../components/MarkdownView'

const PRESET_DATASET = [
  { month: 'Jan', revenue: 120, cost: 75, users: 450 },
  { month: 'Feb', revenue: 155, cost: 85, users: 590 },
  { month: 'Mar', revenue: 190, cost: 105, users: 740 },
  { month: 'Apr', revenue: 240, cost: 120, users: 980 },
  { month: 'May', revenue: 310, cost: 145, users: 1250 },
  { month: 'Jun', revenue: 420, cost: 180, users: 1720 },
]

export default function DataAnalysisWorkspacePage() {
  const [inputMode, setInputMode] = useState<'preset' | 'file' | 'numbers'>('preset')
  const [numbersInput, setNumbersInput] = useState('120, 155, 190, 240, 310, 420')
  const [targetColumn, setTargetColumn] = useState('')
  const [uploadedFileId, setUploadedFileId] = useState<string | null>(null)
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null)
  const [detectedColumns, setDetectedColumns] = useState<string[]>([])
  const [selectedColumn, setSelectedColumn] = useState<string>('')
  const [uploading, setUploading] = useState(false)

  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<any>(null)
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
      if ((res as any).preview?.columns) {
        setDetectedColumns((res as any).preview.columns)
      }
      setInputMode('file')
    } catch (err: any) {
      setError(err.message || 'Dataset upload failed.')
    } finally {
      setUploading(false)
    }
  }

  const handleRun = async () => {
    setRunning(true)
    setError('')
    setResult(null)

    try {
      let payload: any = {}
      if (inputMode === 'file' && uploadedFileId) {
        payload = {
          file_id: uploadedFileId,
          query: 'Perform comprehensive descriptive statistics, percentiles, correlation, and outlier audit.'
        }
        if (targetColumn && targetColumn !== 'auto') {
          payload.aggregate_column = targetColumn
        }
      } else if (inputMode === 'numbers') {
        payload = { numbers: numbersInput.trim() }
      } else {
        payload = {
          rows: PRESET_DATASET,
          aggregate_column: targetColumn && targetColumn !== 'auto' ? targetColumn : 'revenue'
        }
      }

      const res = await agentsApi.runAgent('data_analysis', payload)
      if (!res.success) {
        setError(res.error || 'Data analysis failed.')
      } else {
        setResult(res)
        const stats = res?.output?.statistics || {}
        const cols = Object.keys(stats)
        if (cols.length > 0 && !selectedColumn) {
          setSelectedColumn(cols[0])
        }
      }
    } catch (err: any) {
      setError(err.message || 'Data analysis execution failed.')
    } finally {
      setRunning(false)
    }
  }

  const out = result?.output || {}
  const stats = out.statistics || {}
  const quality = out.dataQuality || {}
  const outliers = out.outliers || {}
  const catDist = out.categoricalDistributions || {}
  const insights = out.insights || []
  const summary = out.summary || ''
  const numericCols = Object.keys(stats)

  const activeCol = (selectedColumn && stats[selectedColumn])
    ? selectedColumn
    : (targetColumn && stats[targetColumn] ? targetColumn : (numericCols[0] || 'value'))
  const activeMetrics = stats[activeCol] || Object.values(stats)[0] || {}

  const copyText = (txt: string) => {
    navigator.clipboard.writeText(txt)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div style={{ padding: '24px', maxWidth: 1400, margin: '0 auto' }}>
      <SectionHeader
        title="Data Analysis & Metrics Workspace"
        subtitle="Upload enterprise datasets (CSV, XLSX) or enter figures. Automatically computes statistical aggregations, trend variances, and anomalies."
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(380px, 460px) 1fr', gap: 24, alignItems: 'start', marginTop: 24 }}>
        {/* Left Column: Data Input Controls */}
        <div className="card" style={{ padding: 20 }}>
          <h3 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 16px', display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-primary)' }}>
            <FileSpreadsheet size={18} color="var(--primary)" />
            Dataset Source
          </h3>

          {/* Mode Tabs */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
            <button
              onClick={() => setInputMode('preset')}
              className={`btn btn-sm ${inputMode === 'preset' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ flex: 1 }}
            >
              Enterprise Preset
            </button>
            <button
              onClick={() => setInputMode('file')}
              className={`btn btn-sm ${inputMode === 'file' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ flex: 1 }}
            >
              Upload CSV/XLSX
            </button>
            <button
              onClick={() => setInputMode('numbers')}
              className={`btn btn-sm ${inputMode === 'numbers' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ flex: 1 }}
            >
              Direct Numbers
            </button>
          </div>

          {inputMode === 'file' && (
            <div style={{ marginBottom: 16 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 8 }}>
                Upload CSV or Excel File
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
                    {uploading ? 'Processing Dataset…' : 'Click to select CSV or XLSX'}
                  </p>
                  <input
                    type="file"
                    accept=".csv,.xlsx,.xls"
                    style={{ display: 'none' }}
                    onChange={handleFileUpload}
                    disabled={uploading}
                  />
                </label>
              </div>

              {uploadedFileName && (
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
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Ready for analysis</span>
                </div>
              )}
            </div>
          )}

          {inputMode === 'preset' && (
            <div style={{ marginBottom: 16 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                Preset: Monthly Corporate Performance (Q1-Q2)
              </label>
              <div style={{
                padding: 12,
                borderRadius: 8,
                background: 'var(--surface-0)',
                border: '1px solid var(--border-subtle)',
                fontSize: 11,
                fontFamily: 'monospace',
                maxHeight: 140,
                overflowY: 'auto',
                color: 'var(--text-secondary)',
              }}>
                {PRESET_DATASET.map((r, i) => (
                  <div key={i}>
                    {r.month}: Revenue=${r.revenue}k, Cost=${r.cost}k, Users={r.users}
                  </div>
                ))}
              </div>
            </div>
          )}

          {inputMode === 'numbers' && (
            <div style={{ marginBottom: 16 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                Comma-Separated Figures
              </label>
              <input
                type="text"
                value={numbersInput}
                onChange={(e) => setNumbersInput(e.target.value)}
                placeholder="120, 155, 190, 240, 310, 420"
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
          )}

          {/* Target Column Selection */}
          {inputMode !== 'numbers' && (
            <div style={{ marginBottom: 16 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                Focus Column (Optional / Auto-Detect)
              </label>
              {detectedColumns.length > 0 ? (
                <select
                  value={targetColumn}
                  onChange={(e) => setTargetColumn(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '9px 12px',
                    borderRadius: 8,
                    background: 'var(--surface-0)',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--text-primary)',
                    fontSize: 13,
                  }}
                >
                  <option value="">Auto-analyze all columns</option>
                  {detectedColumns.map((col) => (
                    <option key={col} value={col}>
                      {col}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  value={targetColumn}
                  onChange={(e) => setTargetColumn(e.target.value)}
                  placeholder="e.g., revenue, cost (or leave empty to auto-detect)"
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
              )}
            </div>
          )}

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
              <AlertTriangle size={14} /> {error}
            </div>
          )}

          <button
            onClick={handleRun}
            disabled={running}
            className="btn btn-primary"
            style={{ width: '100%', padding: '10px 16px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
          >
            {running ? (
              <>
                <span className="spinner" style={{ width: 14, height: 14 }} />
                Data Analysis Agent Calculating…
              </>
            ) : (
              <>
                <BarChart3 size={15} />
                Run Statistical Analysis
              </>
            )}
          </button>
        </div>

        {/* Right Column: Computed Metrics & Statistical Visualizations */}
        <div className="card" style={{ padding: 24, minHeight: 400 }}>
          {result ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              {/* Top Banner */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: 14 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <StatusBadge status="success" label="Calculations Complete" />
                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    Inspected Metric: <strong style={{ color: 'var(--text-primary)' }}>{activeCol}</strong>
                  </span>
                </div>
                <button
                  onClick={() => copyText(summary || JSON.stringify(out, null, 2))}
                  className="btn btn-ghost btn-sm"
                  style={{ display: 'flex', alignItems: 'center', gap: 4 }}
                >
                  {copied ? <Check size={13} color="var(--accent-emerald)" /> : <Copy size={13} />}
                  {copied ? 'Copied' : 'Copy Summary'}
                </button>
              </div>

              {/* Data Quality & Metric Totals Bar */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 10 }}>
                <div style={{ background: 'var(--surface-1)', padding: 12, borderRadius: 8, textAlign: 'center', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Quality Score</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: '#10b981', marginTop: 2 }}>
                    {quality.quality_score ?? 100}%
                  </div>
                </div>
                <div style={{ background: 'var(--surface-1)', padding: 12, borderRadius: 8, textAlign: 'center', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Total Records</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', marginTop: 2 }}>
                    {quality.total_rows?.toLocaleString?.() ?? (out.metadata?.row_count ?? (activeMetrics.count ?? 0))}
                  </div>
                </div>
                <div style={{ background: 'var(--surface-1)', padding: 12, borderRadius: 8, textAlign: 'center', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Total Columns</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', marginTop: 2 }}>
                    {quality.total_columns ?? numericCols.length}
                  </div>
                </div>
                <div style={{ background: 'var(--surface-1)', padding: 12, borderRadius: 8, textAlign: 'center', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Duplicates</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: quality.duplicate_rows > 0 ? '#f43f5e' : 'var(--text-primary)', marginTop: 2 }}>
                    {quality.duplicate_rows ?? 0}
                  </div>
                </div>
              </div>

              {/* Analytical Summary Narrative */}
              {summary && (
                <div style={{
                  padding: 16,
                  borderRadius: 10,
                  background: 'var(--surface-0)',
                  border: '1px solid var(--border-subtle)',
                  fontSize: 13,
                  lineHeight: 1.6,
                  color: 'var(--text-primary)',
                }}>
                  <MarkdownView content={summary} />
                </div>
              )}

              {/* Column Selector Tabs if multiple numeric columns */}
              {numericCols.length > 1 && (
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
                    Select Metric Column:
                  </div>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {numericCols.map((col) => (
                      <button
                        key={col}
                        onClick={() => setSelectedColumn(col)}
                        className={`btn btn-sm ${activeCol === col ? 'btn-primary' : 'btn-secondary'}`}
                        style={{ fontSize: 11, padding: '4px 10px' }}
                      >
                        {col}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Metric Cards Grid for active column */}
              <div>
                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Statistics for Column: <span style={{ color: 'var(--primary)' }}>{activeCol}</span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 10 }}>
                  {[
                    { label: 'Mean (Average)', value: activeMetrics.mean },
                    { label: 'Median', value: activeMetrics.median },
                    { label: 'Std Deviation', value: activeMetrics.std_dev },
                    { label: 'Variance', value: activeMetrics.variance },
                    { label: 'Min', value: activeMetrics.min },
                    { label: 'Max', value: activeMetrics.max },
                    { label: 'IQR (Spread)', value: activeMetrics.iqr ?? activeMetrics.range },
                    { label: 'Total Sum', value: activeMetrics.sum },
                  ].map((stat, i) => (
                    <div
                      key={i}
                      style={{
                        padding: '12px 10px',
                        borderRadius: 8,
                        background: 'var(--surface-0)',
                        border: '1px solid var(--border-subtle)',
                        textAlign: 'center',
                      }}
                    >
                      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4, fontWeight: 600 }}>
                        {stat.label}
                      </div>
                      <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>
                        {typeof stat.value === 'number'
                          ? stat.value.toLocaleString(undefined, { maximumFractionDigits: 2 })
                          : (stat.value ?? '—')}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Full Multi-Column Descriptive Statistics Table */}
              {numericCols.length > 0 && (
                <div style={{ border: '1px solid var(--border-subtle)', borderRadius: 8, overflow: 'hidden' }}>
                  <div style={{ background: 'var(--surface-1)', padding: '10px 14px', fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)' }}>
                    📊 Multi-Column Descriptive Comparison &amp; Percentiles:
                  </div>
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', fontSize: 11, borderCollapse: 'collapse' }}>
                      <thead>
                        <tr style={{ background: 'var(--surface-base)', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                          <th style={{ padding: '8px 10px', textAlign: 'left' }}>Column</th>
                          <th style={{ padding: '8px 8px', textAlign: 'right' }}>Mean</th>
                          <th style={{ padding: '8px 8px', textAlign: 'right' }}>Median</th>
                          <th style={{ padding: '8px 8px', textAlign: 'right' }}>Min</th>
                          <th style={{ padding: '8px 8px', textAlign: 'right' }}>Max</th>
                          <th style={{ padding: '8px 8px', textAlign: 'right' }}>P25</th>
                          <th style={{ padding: '8px 8px', textAlign: 'right' }}>P75</th>
                          <th style={{ padding: '8px 8px', textAlign: 'right' }}>IQR</th>
                          <th style={{ padding: '8px 8px', textAlign: 'right' }}>StdDev</th>
                        </tr>
                      </thead>
                      <tbody>
                        {numericCols.map((col, idx) => {
                          const s = stats[col] || {}
                          return (
                            <tr
                              key={col}
                              onClick={() => setSelectedColumn(col)}
                              style={{
                                borderBottom: '1px solid var(--border-subtle)',
                                background: activeCol === col ? 'rgba(99, 102, 241, 0.08)' : (idx % 2 === 0 ? 'transparent' : 'var(--surface-1)'),
                                cursor: 'pointer',
                              }}
                            >
                              <td style={{ padding: '8px 10px', fontWeight: 600, color: activeCol === col ? 'var(--primary)' : '#f59e0b' }}>
                                {col}
                              </td>
                              <td style={{ padding: '8px 8px', textAlign: 'right', color: 'var(--text-primary)' }}>{s.mean ?? '—'}</td>
                              <td style={{ padding: '8px 8px', textAlign: 'right', color: 'var(--text-primary)' }}>{s.median ?? '—'}</td>
                              <td style={{ padding: '8px 8px', textAlign: 'right', color: 'var(--text-secondary)' }}>{s.min ?? '—'}</td>
                              <td style={{ padding: '8px 8px', textAlign: 'right', color: 'var(--text-secondary)' }}>{s.max ?? '—'}</td>
                              <td style={{ padding: '8px 8px', textAlign: 'right', color: 'var(--text-muted)' }}>{s.p25 ?? '—'}</td>
                              <td style={{ padding: '8px 8px', textAlign: 'right', color: 'var(--text-muted)' }}>{s.p75 ?? '—'}</td>
                              <td style={{ padding: '8px 8px', textAlign: 'right', color: 'var(--text-primary)' }}>{s.iqr ?? '—'}</td>
                              <td style={{ padding: '8px 8px', textAlign: 'right', color: 'var(--text-secondary)' }}>{s.std_dev ?? '—'}</td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Actionable Insights */}
              {insights.length > 0 && (
                <div style={{
                  padding: 14,
                  borderRadius: 8,
                  background: 'var(--surface-0)',
                  border: '1px solid var(--border-subtle)',
                }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <TrendingUp size={15} color="var(--accent-emerald)" />
                    Analytical Insights &amp; Findings
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {insights.map((item: string, idx: number) => (
                      <div key={idx} style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                        <span style={{ color: 'var(--accent-emerald)', fontWeight: 700 }}>•</span>
                        <span>{item}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Anomaly / Outliers Alert */}
              {Object.keys(outliers).length > 0 && (
                <div style={{
                  padding: 14,
                  borderRadius: 10,
                  background: 'rgba(245, 158, 11, 0.1)',
                  border: '1px solid var(--accent-amber)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 700, fontSize: 13, color: 'var(--accent-amber)', marginBottom: 6 }}>
                    <AlertTriangle size={15} />
                    Statistical Outliers Detected via IQR
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-primary)' }}>
                    {Object.entries(outliers).map(([col, items]: [string, any]) => (
                      <div key={col} style={{ marginTop: 2 }}>
                        • <strong>{col}:</strong> {Array.isArray(items) ? `${items.length} outlier data point(s)` : JSON.stringify(items)}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
              <BarChart3 size={36} style={{ marginBottom: 12, opacity: 0.5 }} />
              <p style={{ margin: 0, fontSize: 14 }}>
                Select a dataset or upload a CSV on the left, then click "Run Statistical Analysis" to view calculated statistics and insights.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
