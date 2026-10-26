import React, { useState } from 'react'
import { Copy, Check, ExternalLink } from 'lucide-react'

interface MarkdownViewProps {
  content?: string | null
  className?: string
  style?: React.CSSProperties
}

/**
 * Enterprise Production Markdown & Typography Renderer.
 * Converts markdown (headers, bold, italics, lists, code blocks, tables, blockquotes, citations)
 * into clean, styled UI components without displaying raw markdown symbols.
 */
export function MarkdownView({ content = '', className, style }: MarkdownViewProps) {
  if (!content) return null

  // Clean broken character replacements (e.g.  -> — or •)
  const cleanContent = (typeof content === 'string' ? content : String(content))
    .replace(/\uFFFD\s*/g, ' — ')
    .replace(/\r\n/g, '\n')

  // Render inline formatting: citations, bold italic, bold, italic, code, math, links
  const renderInline = (text: string): React.ReactNode[] => {
    if (!text) return []

    // Pattern matching inline elements
    // 1. Citations: [Doc.pdf — Page X]
    // 2. Math display/inline: \$\$[^\$]+\$\$ or \$[^\$]+\$
    // 3. Inline code: `...`
    // 4. Bold Italic: ***...*** or ___...___
    // 5. Bold: **...** or __...__
    // 6. Italic: *...* or _..._
    // 7. Links: [text](url)
    const regex = /(\[[^\]]+(?:\.pdf|\.docx|\.pptx|\.txt|Page|Slide|Section|Para)[^\]]*\]|\$\$[^\$]+\$\$|\$[^\$]+\$|`[^`]+`|\*\*\*[^*]+\*\*\*|\*\*[^*]+\*\*|(?<!\*)\*[^*]+\*(?!\*)|(?<!_)_[^_]+_(?!_)|\[[^\]]+\]\([^)]+\))/g

    const parts = text.split(regex)

    return parts.map((part, idx) => {
      if (!part) return null

      // Citation Pill: [SEPM.pdf — Page 1]
      if (part.startsWith('[') && part.endsWith(']') && (part.includes('Page') || part.includes('Slide') || part.includes('.pdf') || part.includes('.pptx') || part.includes('.docx'))) {
        const cleanCitation = part.slice(1, -1)
        return (
          <span
            key={idx}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              padding: '1px 7px',
              margin: '0 2px',
              borderRadius: 12,
              background: 'rgba(99, 102, 241, 0.12)',
              border: '1px solid rgba(99, 102, 241, 0.25)',
              color: '#818cf8',
              fontSize: '0.82em',
              fontWeight: 600,
              verticalAlign: 'baseline',
              whiteSpace: 'nowrap',
            }}
          >
            📄 {cleanCitation}
          </span>
        )
      }

      // LaTeX Math: $$...$$ or $...$
      if ((part.startsWith('$$') && part.endsWith('$$') && part.length > 4) ||
          (part.startsWith('$') && part.endsWith('$') && part.length > 2)) {
        const mathContent = part.startsWith('$$') ? part.slice(2, -2) : part.slice(1, -1)
        const cleanMath = mathContent.replace(/\\text\{([^}]+)\}/g, '$1')
        return (
          <span
            key={idx}
            style={{
              display: 'inline-block',
              fontFamily: 'serif',
              fontStyle: 'italic',
              background: 'rgba(255, 255, 255, 0.05)',
              padding: '2px 8px',
              borderRadius: 4,
              color: '#38bdf8',
              fontWeight: 600,
            }}
          >
            {cleanMath}
          </span>
        )
      }

      // Inline code: `code`
      if (part.startsWith('`') && part.endsWith('`') && part.length >= 2) {
        return (
          <code
            key={idx}
            style={{
              background: 'var(--surface-2, rgba(255, 255, 255, 0.06))',
              color: '#38bdf8',
              padding: '2px 6px',
              borderRadius: 4,
              fontSize: '0.88em',
              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
              border: '1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))',
            }}
          >
            {part.slice(1, -1)}
          </code>
        )
      }

      // Bold Italic: ***text***
      if (part.startsWith('***') && part.endsWith('***') && part.length >= 6) {
        return (
          <strong key={idx} style={{ color: 'var(--text-primary, #f8fafc)', fontWeight: 700, fontStyle: 'italic' }}>
            {part.slice(3, -3)}
          </strong>
        )
      }

      // Bold: **text** or __text__
      if ((part.startsWith('**') && part.endsWith('**') && part.length >= 4) ||
          (part.startsWith('__') && part.endsWith('__') && part.length >= 4)) {
        return (
          <strong key={idx} style={{ color: 'var(--text-primary, #f8fafc)', fontWeight: 700 }}>
            {part.slice(2, -2)}
          </strong>
        )
      }

      // Italic: *text* or _text_
      if ((part.startsWith('*') && part.endsWith('*') && part.length >= 2) ||
          (part.startsWith('_') && part.endsWith('_') && part.length >= 2)) {
        return (
          <em key={idx} style={{ fontStyle: 'italic', color: 'var(--text-secondary, #cbd5e1)' }}>
            {part.slice(1, -1)}
          </em>
        )
      }

      // Link: [text](url)
      if (part.startsWith('[') && part.includes('](') && part.endsWith(')')) {
        const linkMatch = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/)
        if (linkMatch) {
          return (
            <a
              key={idx}
              href={linkMatch[2]}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                color: '#60a5fa',
                textDecoration: 'underline',
                textUnderlineOffset: '2px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 2,
              }}
            >
              {linkMatch[1]}
              <ExternalLink size={10} style={{ display: 'inline', marginLeft: 2 }} />
            </a>
          )
        }
      }

      return part
    })
  }

  // Parse markdown lines & blocks
  const lines = cleanContent.split('\n')
  const elements: React.ReactNode[] = []
  let currentList: React.ReactNode[] = []
  let inCodeBlock = false
  let codeBlockLang = ''
  let codeBlockLines: string[] = []
  let inTable = false
  let tableRows: string[][] = []

  const flushList = () => {
    if (currentList.length > 0) {
      elements.push(
        <ul
          key={`ul-${elements.length}`}
          style={{
            margin: '8px 0',
            paddingLeft: 22,
            listStyleType: 'disc',
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
          }}
        >
          {currentList}
        </ul>
      )
      currentList = []
    }
  }

  const flushTable = () => {
    if (inTable && tableRows.length > 0) {
      const header = tableRows[0]
      const body = tableRows.slice(1)
      elements.push(
        <div key={`tbl-${elements.length}`} style={{ overflowX: 'auto', margin: '12px 0' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, textAlign: 'left' }}>
            {header && (
              <thead>
                <tr style={{ background: 'var(--surface-2, rgba(255,255,255,0.04))', borderBottom: '1px solid var(--border-subtle)' }}>
                  {header.map((cell, cIdx) => (
                    <th key={cIdx} style={{ padding: '8px 12px', fontWeight: 700, color: 'var(--text-primary)' }}>
                      {renderInline(cell.trim())}
                    </th>
                  ))}
                </tr>
              </thead>
            )}
            <tbody>
              {body.map((row, rIdx) => (
                <tr key={rIdx} style={{ borderBottom: '1px solid var(--border-subtle, rgba(255,255,255,0.05))' }}>
                  {row.map((cell, cIdx) => (
                    <td key={cIdx} style={{ padding: '8px 12px', color: 'var(--text-secondary)' }}>
                      {renderInline(cell.trim())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
      inTable = false
      tableRows = []
    }
  }

  const flushCodeBlock = () => {
    if (inCodeBlock) {
      const codeText = codeBlockLines.join('\n')
      elements.push(<CodeBlockViewer key={`code-${elements.length}`} code={codeText} language={codeBlockLang} />)
      inCodeBlock = false
      codeBlockLang = ''
      codeBlockLines = []
    }
  }

  for (let lineIdx = 0; lineIdx < lines.length; lineIdx++) {
    const rawLine = lines[lineIdx]
    const trimmed = rawLine.trim()

    // 1. Code Block fences ```
    if (trimmed.startsWith('```')) {
      flushList()
      flushTable()
      if (inCodeBlock) {
        flushCodeBlock()
      } else {
        inCodeBlock = true
        codeBlockLang = trimmed.slice(3).trim()
        codeBlockLines = []
      }
      continue
    }

    if (inCodeBlock) {
      codeBlockLines.push(rawLine)
      continue
    }

    // 2. Table row
    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      flushList()
      // Check if separator line |---|---|
      if (/^\|[-:\s|]+\|$/.test(trimmed)) {
        continue
      }
      const cells = trimmed.slice(1, -1).split('|')
      inTable = true
      tableRows.push(cells)
      continue
    } else if (inTable) {
      flushTable()
    }

    // 3. Blank line
    if (!trimmed) {
      flushList()
      flushTable()
      continue
    }

    // 4. Horizontal Rule
    if (/^[-*_]{3,}$/.test(trimmed)) {
      flushList()
      flushTable()
      elements.push(
        <hr
          key={lineIdx}
          style={{
            margin: '16px 0',
            border: 'none',
            borderTop: '1px solid var(--border-subtle, rgba(255,255,255,0.1))',
          }}
        />
      )
      continue
    }

    // 5. Blockquote
    if (trimmed.startsWith('> ')) {
      flushList()
      flushTable()
      elements.push(
        <div
          key={lineIdx}
          style={{
            margin: '8px 0',
            padding: '8px 14px',
            borderLeft: '3px solid var(--brand-primary, #6366f1)',
            background: 'rgba(99, 102, 241, 0.05)',
            borderRadius: '0 6px 6px 0',
            color: 'var(--text-secondary)',
            fontSize: '0.94em',
            fontStyle: 'italic',
          }}
        >
          {renderInline(trimmed.slice(2))}
        </div>
      )
      continue
    }

    // 6. Headings
    if (trimmed.startsWith('##### ')) {
      flushList()
      flushTable()
      elements.push(
        <h6 key={lineIdx} style={{ fontSize: 12, fontWeight: 700, margin: '10px 0 4px', color: 'var(--text-primary)' }}>
          {renderInline(trimmed.slice(6))}
        </h6>
      )
    } else if (trimmed.startsWith('#### ')) {
      flushList()
      flushTable()
      elements.push(
        <h5 key={lineIdx} style={{ fontSize: 13, fontWeight: 700, margin: '12px 0 4px', color: '#e2e8f0', letterSpacing: '0.01em' }}>
          {renderInline(trimmed.slice(5))}
        </h5>
      )
    } else if (trimmed.startsWith('### ')) {
      flushList()
      flushTable()
      elements.push(
        <h4 key={lineIdx} style={{ fontSize: 14, fontWeight: 700, margin: '16px 0 6px', color: '#60a5fa', letterSpacing: '0.02em', borderBottom: '1px solid rgba(255,255,255,0.06)', paddingBottom: 4 }}>
          {renderInline(trimmed.slice(4))}
        </h4>
      )
    } else if (trimmed.startsWith('## ')) {
      flushList()
      flushTable()
      elements.push(
        <h3 key={lineIdx} style={{ fontSize: 16, fontWeight: 700, margin: '18px 0 8px', color: '#818cf8', letterSpacing: '0.02em' }}>
          {renderInline(trimmed.slice(3))}
        </h3>
      )
    } else if (trimmed.startsWith('# ')) {
      flushList()
      flushTable()
      elements.push(
        <h2 key={lineIdx} style={{ fontSize: 18, fontWeight: 700, margin: '20px 0 10px', color: 'var(--text-primary)' }}>
          {renderInline(trimmed.slice(2))}
        </h2>
      )
    } else if (trimmed.startsWith('- ') || trimmed.startsWith('* ') || trimmed.startsWith('• ')) {
      const itemText = trimmed.replace(/^[-*•]\s+/, '')
      currentList.push(
        <li key={lineIdx} style={{ margin: '3px 0', lineHeight: 1.6, color: 'var(--text-secondary)' }}>
          {renderInline(itemText)}
        </li>
      )
    } else if (/^\d+\.\s+/.test(trimmed)) {
      flushList()
      flushTable()
      const match = trimmed.match(/^(\d+\.)\s+(.*)$/)
      if (match) {
        elements.push(
          <div key={lineIdx} style={{ margin: '6px 0', display: 'flex', gap: 8, lineHeight: 1.6, color: 'var(--text-secondary)' }}>
            <span style={{ fontWeight: 700, color: 'var(--brand-primary, #6366f1)', minWidth: 22 }}>
              {match[1]}
            </span>
            <span style={{ flex: 1 }}>{renderInline(match[2])}</span>
          </div>
        )
      } else {
        elements.push(
          <p key={lineIdx} style={{ margin: '6px 0', lineHeight: 1.6, color: 'var(--text-secondary)' }}>
            {renderInline(trimmed)}
          </p>
        )
      }
    } else {
      flushList()
      flushTable()
      elements.push(
        <p key={lineIdx} style={{ margin: '6px 0', lineHeight: 1.6, color: 'var(--text-secondary)' }}>
          {renderInline(trimmed)}
        </p>
      )
    }
  }

  flushList()
  flushTable()
  flushCodeBlock()

  return (
    <div className={className} style={{ ...style, lineHeight: 1.65 }}>
      {elements}
    </div>
  )
}

function CodeBlockViewer({ code, language }: { code: string; language?: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div
      style={{
        margin: '12px 0',
        borderRadius: 8,
        background: 'var(--surface-0, #0f172a)',
        border: '1px solid var(--border-subtle, rgba(255,255,255,0.08))',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '6px 12px',
          background: 'rgba(255, 255, 255, 0.03)',
          borderBottom: '1px solid var(--border-subtle, rgba(255,255,255,0.05))',
          fontSize: 11,
          color: 'var(--text-muted, #94a3b8)',
        }}
      >
        <span>{language ? language.toUpperCase() : 'CODE'}</span>
        <button
          onClick={handleCopy}
          className="btn btn-ghost btn-sm"
          style={{ padding: '2px 6px', fontSize: 11, display: 'flex', alignItems: 'center', gap: 4 }}
        >
          {copied ? <Check size={11} color="#10b981" /> : <Copy size={11} />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre
        style={{
          margin: 0,
          padding: 12,
          fontSize: 12,
          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
          overflowX: 'auto',
          lineHeight: 1.5,
          color: '#e2e8f0',
        }}
      >
        <code>{code}</code>
      </pre>
    </div>
  )
}
