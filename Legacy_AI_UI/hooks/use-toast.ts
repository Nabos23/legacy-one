'use client'

import { useToastContext } from '@/contexts/toast-context'

export function useToast() {
  const { toasts, addToast, removeToast } = useToastContext()

  const toast = {
    success: (message: string, title?: string) =>
      addToast({ type: 'success', message, title }),
    error: (message: string, title?: string) =>
      addToast({ type: 'error', message, title }),
    warning: (message: string, title?: string) =>
      addToast({ type: 'warning', message, title }),
    info: (message: string, title?: string) =>
      addToast({ type: 'info', message, title }),
  }

  return { toasts, toast, removeToast, addToast }
}
