import { useState } from 'react'

interface CodeEditorProps {
  value: string
  onChange: (val: string) => void
  label?: string
  placeholder?: string
  minHeight?: number
  error?: string
  charLimit?: number
}

export function CodeEditor({
  value,
  onChange,
  label,
  placeholder,
  minHeight = 200,
  error,
  charLimit,
}: CodeEditorProps) {
  const charCount = value.length
  const isOverLimit = charLimit && charCount > charLimit * 0.9

  return (
    <div className="space-y-2">
      {label && <label className="text-[14px] font-medium">{label}</label>}
      <div className="relative">
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          style={{ minHeight: `${minHeight}px` }}
          className="w-full bg-[var(--surface-3)] font-mono text-[13px] text-[var(--text-1)] border border-[var(--border)] rounded-[var(--radius-md)] p-4 resize-y transition-shadow duration-150 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:ring-offset-0"
        />
        {charLimit && (
          <div
            className={`absolute top-3 right-3 text-[11px] font-medium ${
              isOverLimit ? 'text-red-400' : 'text-[var(--text-3)]'
            }`}
          >
            {charCount}/{charLimit}
          </div>
        )}
      </div>
      {error && <p className="text-[12px] text-red-600 dark:text-red-400">{error}</p>}
    </div>
  )
}
