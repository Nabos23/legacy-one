'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Loader2 } from 'lucide-react'
import { useAuth } from '@/contexts/auth-context'
import { getDashboardPath } from '@/lib/auth-cookies'

export default function OAuthCallbackPage() {
  const { completeOAuthLogin } = useAuth()
  const [error, setError] = useState('')

  useEffect(() => {
    const params = new URLSearchParams(window.location.hash.slice(1))
    const token = params.get('access_token')
    const providerError = params.get('error')

    if (providerError || !token) {
      setError(providerError || 'The sign-in response was invalid. Please try again.')
      return
    }
    window.history.replaceState(null, '', window.location.pathname)
    completeOAuthLogin(token)
      .then(user => {
        const from = sessionStorage.getItem('auth_redirect')
        sessionStorage.removeItem('auth_redirect')
        window.location.href = from?.startsWith('/') && !from.startsWith('//') ? from : getDashboardPath(user.role)
      })
      .catch(err => setError(err instanceof Error ? err.message : 'Sign-in failed.'))
  }, [completeOAuthLogin])

  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-6">
      <div className="w-full max-w-sm rounded-2xl border border-border bg-card p-8 text-center">
        {error ? (
          <>
            <h1 className="text-lg font-semibold text-foreground">Couldn&apos;t sign you in</h1>
            <p className="mt-2 text-sm text-muted-foreground">{error}</p>
            <Link href="/login" className="mt-5 inline-block text-sm font-medium text-violet-600 hover:text-violet-500">
              Back to sign in
            </Link>
          </>
        ) : (
          <>
            <Loader2 className="mx-auto size-6 animate-spin text-violet-600" />
            <p className="mt-3 text-sm text-muted-foreground">Finishing sign in…</p>
          </>
        )}
      </div>
    </main>
  )
}
