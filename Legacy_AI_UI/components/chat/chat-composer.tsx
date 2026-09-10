'use client'

import { useEffect, useState } from 'react'
import { ArrowUp, Globe, Settings, FolderCode, Mic, Square, Paperclip } from 'lucide-react'
import { cn } from '@/lib/utils'

const WAVE_BARS = Array.from({ length: 22 }, (_, i) => {
  // Deterministic pseudo-random heights so the waveform looks organic, not uniform.
  const seed = Math.sin(i * 12.9898) * 43758.5453
  return 0.35 + (seed - Math.floor(seed)) * 0.65
})

function formatTimer(totalSeconds: number) {
  const m = Math.floor(totalSeconds / 60)
  const s = totalSeconds % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export interface ChatComposerProps {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  placeholder?: string
  disabled?: boolean
  sendDisabled?: boolean
  onAttachClick?: () => void
  attachDisabled?: boolean
  attachTitle?: string
  tone?: 'default' | 'warning'
  className?: string
  textareaRef?: React.Ref<HTMLTextAreaElement>
  /** Show the send button even when the text value is empty (e.g. attachments queued with no caption). */
  hasContent?: boolean
}

export function ChatComposer({
  value,
  onChange,
  onSend,
  placeholder = 'Type your message here...',
  disabled = false,
  sendDisabled = false,
  onAttachClick,
  attachDisabled = false,
  attachTitle = 'Attach a file (PDF, Office, text, code, or image)',
  tone = 'default',
  className,
  textareaRef,
  hasContent,
}: ChatComposerProps) {
  const [webSearchActive, setWebSearchActive] = useState(false)
  const [thinkActive, setThinkActive] = useState(false)
  const [canvasActive, setCanvasActive] = useState(false)
  const [recording, setRecording] = useState(false)
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    if (!recording) return
    const id = setInterval(() => setSeconds(s => s + 1), 1000)
    return () => clearInterval(id)
  }, [recording])

  const startRecording = () => {
    if (disabled) return
    setSeconds(0)
    setRecording(true)
  }

  const stopRecording = () => {
    setRecording(false)
  }

  const hasText = hasContent ?? value.trim().length > 0
  const isWarning = tone === 'warning'

  return (
    <div
      className={cn(
        'rounded-3xl border px-4 py-3 transition-all shadow-[var(--elevation-1)]',
        recording
          ? 'bg-[var(--surface-2)] border-red-400/70 dark:border-red-500/50 ring-2 ring-red-500/15'
          : cn(
              'bg-[var(--surface-2)] focus-within:bg-[var(--surface)] focus-within:ring-2',
              isWarning
                ? 'border-amber-300 dark:border-amber-500/40 focus-within:ring-amber-500/20 focus-within:border-amber-400'
                : 'border-[var(--border)] focus-within:ring-violet-500/20 focus-within:border-violet-300 dark:focus-within:border-violet-500/40',
            ),
        className,
      )}
    >
      {recording ? (
        <div className="flex flex-col items-center gap-2 py-1">
          <div className="flex items-center gap-2 text-[12px] font-mono text-[var(--text-2)]">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            {formatTimer(seconds)}
          </div>
          <div className="flex items-end gap-[3px] h-6">
            {WAVE_BARS.map((base, i) => (
              <span
                key={i}
                className="w-[2px] rounded-full bg-[var(--text-3)] voice-wave-bar"
                style={{ height: `${base * 24}px`, animationDelay: `${i * 70}ms` }}
              />
            ))}
          </div>
        </div>
      ) : (
        <textarea
          ref={textareaRef}
          value={value}
          disabled={disabled}
          onChange={e => onChange(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend() } }}
          placeholder={canvasActive ? 'Create on canvas...' : placeholder}
          rows={1}
          className="w-full bg-transparent text-[14px] text-[var(--text-1)] placeholder:text-[var(--text-3)] resize-none outline-none min-h-[22px] max-h-[180px] py-0.5 custom-scrollbar overflow-y-auto disabled:cursor-not-allowed"
        />
      )}

      <div className="flex items-center justify-between mt-2">
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={onAttachClick}
            disabled={attachDisabled || recording}
            title={attachTitle}
            className={cn(
              'w-8 h-8 rounded-full flex items-center justify-center transition-colors shrink-0',
              attachDisabled || recording
                ? 'text-[var(--text-3)] cursor-not-allowed'
                : 'text-[var(--text-3)] hover:text-[var(--text-1)] hover:bg-black/[0.05] dark:hover:bg-white/[0.07]',
            )}
          >
            <Paperclip className="w-4 h-4" />
          </button>

          <button
            type="button"
            onClick={() => setWebSearchActive(v => !v)}
            disabled={recording}
            title="Search the web"
            className={cn(
              'w-8 h-8 rounded-full flex items-center justify-center transition-colors shrink-0',
              webSearchActive
                ? 'text-cyan-500 bg-cyan-500/10'
                : 'text-[var(--text-3)] hover:text-[var(--text-1)] hover:bg-black/[0.05] dark:hover:bg-white/[0.07]',
            )}
          >
            <Globe className="w-4 h-4" />
          </button>

          <div className="w-px h-4 bg-[var(--border)] mx-0.5" />

          <button
            type="button"
            onClick={() => setThinkActive(v => !v)}
            disabled={recording}
            title="Think before responding"
            className={cn(
              'h-8 rounded-full flex items-center justify-center gap-1.5 transition-all shrink-0 px-2.5',
              thinkActive
                ? 'text-violet-500 bg-violet-500/10 border border-violet-500/40'
                : 'text-[var(--text-3)] hover:text-[var(--text-1)] hover:bg-black/[0.05] dark:hover:bg-white/[0.07]',
            )}
          >
            <Settings className="w-4 h-4" />
            {thinkActive && <span className="text-[12px] font-medium">Think</span>}
          </button>

          <div className="w-px h-4 bg-[var(--border)] mx-0.5" />

          <button
            type="button"
            onClick={() => setCanvasActive(v => !v)}
            disabled={recording}
            title="Create on canvas"
            className={cn(
              'h-8 rounded-full flex items-center justify-center gap-1.5 transition-all shrink-0 px-2.5',
              canvasActive
                ? 'text-amber-500 bg-amber-500/10 border border-amber-500/40'
                : 'text-[var(--text-3)] hover:text-[var(--text-1)] hover:bg-black/[0.05] dark:hover:bg-white/[0.07]',
            )}
          >
            <FolderCode className="w-4 h-4" />
            {canvasActive && <span className="text-[12px] font-medium">Canvas</span>}
          </button>
        </div>

        {recording ? (
          <button
            type="button"
            onClick={stopRecording}
            title="Stop recording"
            className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-white text-red-600 border border-red-300 hover:bg-red-50"
          >
            <Square className="w-3.5 h-3.5 fill-current" />
          </button>
        ) : hasText ? (
          <button
            type="button"
            onClick={onSend}
            disabled={sendDisabled || disabled}
            className={cn(
              'w-8 h-8 rounded-full flex items-center justify-center transition-colors shrink-0',
              !sendDisabled && !disabled
                ? isWarning ? 'bg-amber-500 hover:bg-amber-600 text-white' : 'bg-violet-600 hover:bg-violet-700 text-white'
                : 'bg-black/[0.05] dark:bg-white/[0.07] text-[var(--text-3)] cursor-not-allowed',
            )}
          >
            <ArrowUp className="w-4 h-4" />
          </button>
        ) : (
          <button
            type="button"
            onClick={startRecording}
            disabled={disabled}
            title="Voice input"
            className={cn(
              'w-8 h-8 rounded-full flex items-center justify-center transition-colors shrink-0',
              !disabled
                ? 'bg-[var(--surface-3)] border border-[var(--border)] text-[var(--text-2)] hover:bg-[var(--surface)]'
                : 'bg-black/[0.05] dark:bg-white/[0.07] text-[var(--text-3)] cursor-not-allowed',
            )}
          >
            <Mic className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  )
}
