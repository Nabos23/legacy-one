'use client'

import { Fragment, memo, useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { Copy, Check, Download, X as XIcon } from 'lucide-react'
import { Badge } from './badge'
import { cn } from '@/lib/utils'
import { apiDownload } from '@/lib/api/client'
import { apiFetchBlobUrl } from '@/lib/api/client'

/**
 * Lightweight, dependency-free markdown renderer for chat messages.
 * Supports: fenced code blocks (with copy), headings, bold/italic, inline code,
 * unordered/ordered lists, tables, blockquotes, horizontal rules and links.
 */

function CodeBlock({ language, body }: { language: string; body: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = async () => {
    await navigator.clipboard.writeText(body)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <div className="my-3 rounded-xl overflow-hidden bg-slate-900 border border-slate-800 shadow-sm transition-colors hover:border-slate-700">
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-800 bg-slate-800/50">
        <Badge variant="neutral" className="normal-case text-[11px] tracking-wider font-medium bg-slate-700 text-slate-300 border-none">{language}</Badge>
        <button type="button" onClick={handleCopy} className="text-slate-400 hover:text-white transition-colors p-1.5 rounded-md hover:bg-slate-700">
          {copied ? <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
        </button>
      </div>
      <pre className="p-5 font-mono text-[13px] leading-relaxed text-slate-300 whitespace-pre overflow-x-auto custom-scrollbar">{body}</pre>
    </div>
  )
}

// ── Report/attachment detection ──────────────────────────────────────────
const REPORTS_BASE_PATH = 'chat/reports'

const ATTACHMENT_RE = new RegExp(
  `(?:[a-zA-Z][\\w+.-]*:)?\\/*${REPORTS_BASE_PATH}\\/([a-zA-Z0-9_\\-.]+\\.[a-zA-Z0-9]{2,5})(?:\\/preview)?(?:\\?[^\\s)]*)?\\/?`,
  'i',
)

// Extensions that should render as an inline image + lightbox instead of a
// generic "Download X Report" button.
const IMAGE_EXTS = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg'])

function ReportDownloadButton({ path, label }: { path: string; label?: string }) {
  const [downloading, setDownloading] = useState(false)

  const ext = (path.split('.').pop() || '').toUpperCase()
  const defaultLabel = `Download ${ext} Report`

  const handleClick = async () => {
    setDownloading(true)
    try {
      const filename = path.split('/').pop() || `report.${ext.toLowerCase() || 'pdf'}`
      await apiDownload(path, filename)
    } catch {
      alert('Could not download the report. Please try again.')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={downloading}
      className="inline-flex items-center gap-1.5 my-1 px-3.5 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-700 active:bg-violet-800 text-white text-[13px] font-medium transition-colors disabled:opacity-60 shadow-sm"
    >
      <Download className="w-3.5 h-3.5 shrink-0" />
      {downloading ? 'Downloading...' : (label && label.toLowerCase() !== 'download' ? label : defaultLabel)}
    </button>
  )
}

function ImagePreview({ previewPath, downloadPath, filename }: { previewPath: string; downloadPath: string; filename: string }) {
  const [open, setOpen] = useState(false)
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let active = true
    let url: string | null = null
    setBlobUrl(null)
    setFailed(false)
    apiFetchBlobUrl(previewPath)
      .then(u => { if (active) { url = u; setBlobUrl(u) } else { URL.revokeObjectURL(u) } })
      .catch(() => { if (active) setFailed(true) })
    return () => {
      active = false
      if (url) URL.revokeObjectURL(url)
    }
  }, [previewPath])

  if (failed) {
    return (
      <span className="inline-flex items-center gap-1.5 my-1 px-3 py-1.5 rounded-lg bg-red-50 dark:bg-red-500/[0.08] border border-red-200 dark:border-red-500/20 text-[12px] text-red-600 dark:text-red-400">
        Couldn't load {filename}
      </span>
    )
  }

  if (!blobUrl) {
    // Changed <div> to <span> so it's valid inline HTML inside <p>
    return <span className="block w-[220px] h-[140px] rounded-xl bg-[var(--surface-2)] border border-[var(--border)] animate-pulse my-1" />
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="block my-1 rounded-xl overflow-hidden border border-[var(--border)] hover:border-violet-400/50 transition-colors max-w-[280px] shadow-sm"
        title={filename}
      >
        <img src={blobUrl} alt={filename} className="block w-full h-auto max-h-[280px] object-cover" />
      </button>
      {open && <ImageLightbox previewSrc={blobUrl} downloadPath={downloadPath} filename={filename} onClose={() => setOpen(false)} />}
    </>
  )
}

function ImageLightbox({ previewSrc, downloadPath, filename, onClose }: { previewSrc: string; downloadPath: string; filename: string; onClose: () => void }) {
  const [downloading, setDownloading] = useState(false)
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  // Deliberate: this hits the ORIGINAL consuming route, so an explicit
  // download click here really does delete server-side, same as the
  // ReportDownloadButton. The inline <img> above is fed by previewSrc
  // (the safe /preview route) and is unaffected by this.
  const handleDownload = async (e: React.MouseEvent) => {
    e.stopPropagation()
    setDownloading(true)
    try {
      await apiDownload(downloadPath, filename)
    } catch {
      alert('Could not download the image. Please try again.')
    } finally {
      setDownloading(false)
    }
  }

  if (!mounted) return null

  return createPortal(
    <div className="fixed inset-0 z-[100] bg-transparent flex items-center justify-center p-6 animate-in fade-in duration-150" onClick={onClose}>
      <button type="button" onClick={handleDownload} disabled={downloading} title="Download image"
        className="absolute top-4 right-4 w-9 h-9 rounded-lg bg-black/50 hover:bg-black/65 active:bg-black/75 backdrop-blur-sm text-white flex items-center justify-center transition-colors disabled:opacity-60 shadow-lg">
        <Download className="w-4 h-4" />
      </button>
      <button type="button" onClick={onClose} title="Close"
        className="absolute top-4 right-16 w-9 h-9 rounded-lg bg-black/50 hover:bg-black/65 active:bg-black/75 backdrop-blur-sm text-white flex items-center justify-center transition-colors shadow-lg">
        <XIcon className="w-4 h-4" />
      </button>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={previewSrc} alt={filename} onClick={e => e.stopPropagation()}
        className="max-w-full max-h-full rounded-lg shadow-2xl object-contain animate-in zoom-in-95 duration-150" />
    </div>,
    document.body,
  )
}

const INLINE = /(`[^`]+`)|(\*\*[^*]+\*\*)|(__[^_]+__)|(\*[^*\n]+\*)|(_[^_\n]+_)|(\[[^\]]+\]\([^)]+\))/

// Alias kept so the rest of renderInline doesn't need to change shape.
const BARE_REPORT = ATTACHMENT_RE

function extractReportMatch(text: string): { filename: string; downloadPath: string; previewPath: string; label?: string; isImage: boolean } | null {
  if (!text) return null
  const extOf = (filename: string) => (filename.split('.').pop() || '').toLowerCase()

  const linkMatch = text.match(/^\[([^\]]+)\]\(([^)]+)\)$/)
  if (linkMatch) {
    const label = linkMatch[1]
    const url = linkMatch[2]
    const fileMatch = url.match(ATTACHMENT_RE)
    if (!fileMatch) return null // real link (Xbox Wire, The Verge, etc.) — not a report, render as <a>
    const filename = fileMatch[1]
    return {
      filename,
      downloadPath: `/${REPORTS_BASE_PATH}/${filename}`,
      previewPath: `/${REPORTS_BASE_PATH}/${filename}/preview`,
      label,
      isImage: IMAGE_EXTS.has(extOf(filename)),
    }
  }

  const cleaned = text.replace(/^[*_`~]+|[*_`~]+$/g, '').trim()
  const fileMatch = cleaned.match(ATTACHMENT_RE)
  if (!fileMatch) return null
  const filename = fileMatch[1]
  return {
    filename,
    downloadPath: `/${REPORTS_BASE_PATH}/${filename}`,
    previewPath: `/${REPORTS_BASE_PATH}/${filename}/preview`,
    isImage: IMAGE_EXTS.has(extOf(filename)),
  }
}

function renderInline(text: string): React.ReactNode {
  const nodes: React.ReactNode[] = []
  let remaining = text
  let key = 0

  while (remaining.length) {
    const bareReportMatch = remaining.match(BARE_REPORT)
    const inlineMatch = remaining.match(INLINE)

    const reportIdx = bareReportMatch?.index ?? -1
    const inlineIdx = inlineMatch?.index ?? -1

    // 1. Check if a Markdown link matches a report file first
    if (inlineMatch && inlineIdx !== -1 && inlineMatch[0].startsWith('[')) {
      const reportInfo = extractReportMatch(inlineMatch[0])
      if (reportInfo && (reportIdx === -1 || inlineIdx <= reportIdx)) {
        if (inlineIdx > 0) nodes.push(remaining.slice(0, inlineIdx))
        nodes.push(
          reportInfo.isImage
            ? <ImagePreview key={key++} previewPath={reportInfo.previewPath} downloadPath={reportInfo.downloadPath} filename={reportInfo.filename} />
            : <ReportDownloadButton key={key++} path={reportInfo.downloadPath} label={reportInfo.label} />,
        )
        remaining = remaining.slice(inlineIdx + inlineMatch[0].length)
        continue
      }
    }

    // 2. Check if a bare report-file match comes before or at inline match
    if (bareReportMatch && reportIdx !== -1 && (inlineIdx === -1 || reportIdx <= inlineIdx)) {
      const preceding = remaining.slice(0, reportIdx)
      if (preceding) nodes.push(preceding)

      const reportInfo = extractReportMatch(bareReportMatch[0])
      if (reportInfo) {
        nodes.push(
          reportInfo.isImage
            ? <ImagePreview key={key++} previewPath={reportInfo.previewPath} downloadPath={reportInfo.downloadPath} filename={reportInfo.filename} />
            : <ReportDownloadButton key={key++} path={reportInfo.downloadPath} label={reportInfo.label} />,
        )
      } else {
        nodes.push(bareReportMatch[0])
      }

      remaining = remaining.slice(reportIdx + bareReportMatch[0].length)
      continue
    }

    // 3. Otherwise process general inline markdown tokens
    if (!inlineMatch || inlineIdx === undefined) {
      nodes.push(remaining)
      break
    }

    if (inlineIdx > 0) nodes.push(remaining.slice(0, inlineIdx))
    const token = inlineMatch[0]
    const k = key++

    if (token.startsWith('`')) {
      const codeContent = token.slice(1, -1)
      const reportInfo = extractReportMatch(codeContent)
      if (reportInfo) {
        nodes.push(
          reportInfo.isImage
            ? <ImagePreview key={k} previewPath={reportInfo.previewPath} downloadPath={reportInfo.downloadPath} filename={reportInfo.filename} />
            : <ReportDownloadButton key={k} path={reportInfo.downloadPath} label={reportInfo.label} />,
        )
      } else {
        nodes.push(
          <code key={k} className="font-mono text-[0.85em] bg-black/[0.06] dark:bg-white/[0.1] rounded px-1 py-0.5">
            {codeContent}
          </code>,
        )
      }
    } else if (token.startsWith('**') || token.startsWith('__')) {
      nodes.push(<strong key={k} className="font-semibold">{token.slice(2, -2)}</strong>)
    } else if (token.startsWith('[')) {
      const lm = token.match(/\[([^\]]+)\]\(([^)]+)\)/)!
      const href = lm[2]
      nodes.push(
        <a key={k} href={href} target="_blank" rel="noopener noreferrer" className="text-violet-500 hover:underline">
          {lm[1]}
        </a>,
      )
    } else {
      nodes.push(<em key={k} className="italic">{token.slice(1, -1)}</em>)
    }

    remaining = remaining.slice(inlineIdx + token.length)
  }

  return nodes
}

function isSpecialLine(line: string) {
  return (
    /^(#{1,6})\s+/.test(line) ||
    /^\s*[-*+]\s+/.test(line) ||
    /^\s*\d+\.\s+/.test(line) ||
    /^>\s?/.test(line) ||
    /^(-{3,}|\*{3,}|_{3,})\s*$/.test(line)
  )
}

function splitRow(line: string): string[] {
  return line.replace(/^\s*\|/, '').replace(/\|\s*$/, '').split('|').map(c => c.trim())
}

function MarkdownBlocks({ text }: { text: string }) {
  const lines = text.replace(/\r/g, '').split('\n')
  const blocks: React.ReactNode[] = []
  let i = 0
  let key = 0
  const push = (node: React.ReactNode) => blocks.push(<Fragment key={key++}>{node}</Fragment>)

  while (i < lines.length) {
    const line = lines[i]
    if (!line.trim()) { i++; continue }

    const h = line.match(/^(#{1,6})\s+(.*)$/)
    if (h) {
      const level = h[1].length
      const cls = level <= 1 ? 'text-h3' : level === 2 ? 'text-h4' : 'text-[14px] font-semibold'
      push(<div className={cn(cls, 'mt-1')}>{renderInline(h[2])}</div>)
      i++; continue
    }

    if (/^(-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
      push(<hr className="border-[var(--border)] my-1" />)
      i++; continue
    }

    // Table: header row + separator row.
    if (
      line.includes('|') &&
      i + 1 < lines.length &&
      lines[i + 1].includes('-') &&
      /^[\s:|-]+$/.test(lines[i + 1])
    ) {
      const header = splitRow(line)
      i += 2
      const rows: string[][] = []
      while (i < lines.length && lines[i].includes('|') && lines[i].trim()) {
        rows.push(splitRow(lines[i]))
        i++
      }
      push(
        <div className="overflow-x-auto my-1">
          <table className="w-full text-[13px] border border-[var(--border)] rounded-lg overflow-hidden">
            <thead className="bg-[var(--surface-3)]">
              <tr>
                {header.map((c, idx) => (
                  <th key={idx} className="text-left font-semibold px-3 py-2 border-b border-[var(--border)]">{renderInline(c)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, ri) => (
                <tr key={ri} className="border-b border-[var(--border)] last:border-0">
                  {r.map((c, ci) => (
                    <td key={ci} className="px-3 py-2 align-top">{renderInline(c)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      )
      continue
    }

    if (/^>\s?/.test(line)) {
      const quote: string[] = []
      while (i < lines.length && /^>\s?/.test(lines[i])) {
        quote.push(lines[i].replace(/^>\s?/, ''))
        i++
      }
      push(
        <blockquote className="border-l-2 border-violet-400/50 pl-3 text-[var(--text-2)]">
          {renderInline(quote.join(' '))}
        </blockquote>,
      )
      continue
    }

    if (/^\s*[-*+]\s+/.test(line)) {
      const items: string[] = []
      while (i < lines.length && /^\s*[-*+]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*+]\s+/, ''))
        i++
      }
      push(
        <ul className="list-disc pl-5 space-y-1 marker:text-[var(--text-3)]">
          {items.map((it, idx) => {
            const cb = it.match(/^\[([ xX])\]\s+(.*)$/)
            if (cb) {
              const checked = cb[1].toLowerCase() === 'x'
              return (
                <li key={idx} className="list-none -ml-5 flex items-start gap-2">
                  <span
                    className={cn(
                      'mt-[3px] w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0',
                      checked ? 'bg-violet-600 border-violet-600 text-white' : 'border-[var(--border-2)]',
                    )}
                  >
                    {checked && <Check className="w-2.5 h-2.5" strokeWidth={3} />}
                  </span>
                  <span className={checked ? 'text-[var(--text-3)] line-through' : ''}>{renderInline(cb[2])}</span>
                </li>
              )
            }
            return <li key={idx}>{renderInline(it)}</li>
          })}
        </ul>,
      )
      continue
    }

    if (/^\s*\d+\.\s+/.test(line)) {
      const items: string[] = []
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+\.\s+/, ''))
        i++
      }
      push(
        <ol className="list-decimal pl-5 space-y-1 marker:text-[var(--text-3)]">
          {items.map((it, idx) => <li key={idx}>{renderInline(it)}</li>)}
        </ol>,
      )
      continue
    }

    // Paragraph — gather consecutive plain lines.
    const para = [line]
    i++
    while (i < lines.length && lines[i].trim() && !isSpecialLine(lines[i]) && !lines[i].includes('|')) {
      para.push(lines[i])
      i++
    }
    // Replaced <p> with <div> to prevent invalid HTML nesting (<div> inside <p>) when rendering ImagePreview
    push(<div className="whitespace-pre-wrap">{renderInline(para.join('\n'))}</div>)
  }

  return <>{blocks}</>
}

function MarkdownImpl({ content, className }: { content: string; className?: string }) {
  const parts: Array<{ type: 'md'; text: string } | { type: 'code'; lang: string; body: string }> = []
  const regex = /```(\w*)\n?([\s\S]*?)```/g
  let lastIndex = 0
  let m: RegExpExecArray | null
  while ((m = regex.exec(content))) {
    if (m.index > lastIndex) parts.push({ type: 'md', text: content.slice(lastIndex, m.index) })
    parts.push({ type: 'code', lang: m[1] || 'text', body: m[2] })
    lastIndex = regex.lastIndex
  }
  if (lastIndex < content.length) parts.push({ type: 'md', text: content.slice(lastIndex) })

  return (
    <div className={cn('text-[15px] leading-relaxed space-y-2 break-words', className)}>
      {parts.map((p, i) =>
        p.type === 'code'
          ? <CodeBlock key={i} language={p.lang} body={p.body} />
          : <MarkdownBlocks key={i} text={p.text} />,
      )}
    </div>
  )
}

export const Markdown = memo(MarkdownImpl)
Markdown.displayName = 'Markdown'
