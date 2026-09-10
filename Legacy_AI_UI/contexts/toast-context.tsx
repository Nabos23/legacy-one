'use client'

import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from 'react'
import { CheckCircle2, XCircle, AlertTriangle, Info, X } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface Toast {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  title?: string
  message: string
  duration?: number
}

interface ToastContextValue {
  toasts: Toast[]
  addToast: (toast: Omit<Toast, 'id'>) => void
  removeToast: (id: string) => void
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined)

const MAX_TOASTS = 3

const iconMap = {
  success: CheckCircle2,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
}

const borderMap = {
  success: 'border-green-500',
  error: 'border-red-500',
  warning: 'border-amber-500',
  info: 'border-cyan-500',
}

const EXIT_DURATION_MS = 220

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  // Toasts mid-exit-animation — kept in `toasts` (so they still render) but
  // flagged here to play the reverse slide-out before actually being filtered
  // out (AUDIT.md category 4/8 — an entrance with no matching exit is a teleport-out).
  const [removingIds, setRemovingIds] = useState<Set<string>>(new Set())

  const removeToast = useCallback((id: string) => {
    setRemovingIds(prev => new Set(prev).add(id))
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
      setRemovingIds(prev => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    }, EXIT_DURATION_MS)
  }, [])

  const addToast = useCallback(
    (toast: Omit<Toast, 'id'>) => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`
      const duration = toast.duration ?? 4000

      setToasts(prev => [...prev.slice(-(MAX_TOASTS - 1)), { ...toast, id }])

      if (duration > 0) {
        setTimeout(() => removeToast(id), duration)
      }
    },
    [removeToast]
  )

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
      <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2">
        {toasts.map(toast => {
          const Icon = iconMap[toast.type]
          const removing = removingIds.has(toast.id)
          return (
            <div
              key={toast.id}
              className={cn(
                'glass w-[340px] px-4 py-3 border-l-4 animate-slideInRight flex items-start gap-3',
                removing && '[animation-direction:reverse]',
                borderMap[toast.type]
              )}
            >
              <Icon className="w-4 h-4 mt-0.5 shrink-0" />
              <div className="flex-1 min-w-0">
                {toast.title && (
                  <p className="text-[13px] font-semibold">{toast.title}</p>
                )}
                <p className="text-[12px] text-[var(--text-3)]">{toast.message}</p>
              </div>
              <button
                onClick={() => removeToast(toast.id)}
                className="text-[var(--text-3)] hover:text-[var(--text-1)]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToastContext() {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error('useToastContext must be used within ToastProvider')
  }
  return context
}
