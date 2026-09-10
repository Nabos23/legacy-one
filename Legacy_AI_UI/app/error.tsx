'use client'

import { AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div className="flex h-screen items-center justify-center bg-[var(--bg)]">
      <div className="text-center max-w-md mx-auto px-6">
        <AlertTriangle className="w-12 h-12 text-red-500 mx-auto mb-4" />
        <h1 className="text-2xl font-bold text-[var(--text-1)] mb-2">
          Something went wrong
        </h1>
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded-lg p-4 mb-6 text-left">
          <p className="text-sm font-mono text-[var(--text-2)] break-all">
            {error.message}
          </p>
        </div>
        <Button
          onClick={reset}
          className="bg-violet-600 hover:bg-violet-700 text-white"
        >
          Try again
        </Button>
      </div>
    </div>
  )
}
