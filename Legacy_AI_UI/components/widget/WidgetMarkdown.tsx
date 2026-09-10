'use client'

import { Fragment, useState } from 'react'
import { Copy, Check } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

/**
 * Fork of components/ui/markdown.tsx for the public, unauthenticated embed
 * page -- same fenced-code/table/list/blockquote/inline parsing, minus the
 * dashboard-only "download PDF report" special case (which depends on the
 * authenticated api client and doesn't apply to widget visitors).
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

const INLINE = /(`[^`]+`)|(\*\*[^*]+\*\*)|(__[^_]+__)|(\*[^*\n]+\*)|(_[^_\n]+_)|(!\[[^\]]*\]\([^)]+\))|(\[[^\]]+\]\([^)]+\))/

function renderInline(text: string): React.ReactNode {
  const nodes: React.ReactNode[] = []
  let remaining = text
  let key = 0

  while (remaining.length) {
    const match = remaining.match(INLINE)
    if (!match || match.index === undefined) {
      nodes.push(remaining)
      break
    }
    const index = match.index
    if (index > 0) nodes.push(remaining.slice(0, index))
    const token = match[0]
    const k = key++
    if (token.startsWith('`')) {
      nodes.push(
        <code key={k} className="font-mono text-[0.85em] bg-black/[0.06] dark:bg-white/[0.1] rounded px-1 py-0.5">
          {token.slice(1, -1)}
        </code>,
      )
    } else if (token.startsWith('**') || token.startsWith('__')) {
      nodes.push(<strong key={k} className="font-semibold">{token.slice(2, -2)}</strong>)
    } else if (token.startsWith('![')) {
      const im = token.match(/!\[([^\]]*)\]\(([^)]+)\)/)!
      nodes.push(
        // eslint-disable-next-line @next/next/no-img-element
        <img key={k} src={im[2]} alt={im[1]} loading="lazy" className="max-w-full rounded-lg my-1" />,
      )
    } else if (token.startsWith('[')) {
      const lm = token.match(/\[([^\]]+)\]\(([^)]+)\)/)!
      nodes.push(
        <a key={k} href={lm[2]} target="_blank" rel="noopener noreferrer" className="text-violet-500 hover:underline">
          {lm[1]}
        </a>,
      )
    } else {
      nodes.push(<em key={k} className="italic">{token.slice(1, -1)}</em>)
    }
    remaining = remaining.slice(index + token.length)
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
      push(<p className={cn(cls, 'mt-1')}>{renderInline(h[2])}</p>)
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
    push(<p className="whitespace-pre-wrap">{renderInline(para.join('\n'))}</p>)
  }

  return <>{blocks}</>
}

export function WidgetMarkdown({ content, className }: { content: string; className?: string }) {
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
    <div className={cn('leading-relaxed space-y-2 break-words', className)}>
      {parts.map((p, i) =>
        p.type === 'code'
          ? <CodeBlock key={i} language={p.lang} body={p.body} />
          : <MarkdownBlocks key={i} text={p.text} />,
      )}
    </div>
  )
}
