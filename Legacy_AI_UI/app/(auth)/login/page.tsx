'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Eye, EyeOff, Sparkles, Shield, Zap, ArrowRight, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { Logo } from '@/components/landing/logo'
import { useAuth } from '@/contexts/auth-context'
import { loginSchema } from '@/lib/validations/auth'
import { getDashboardPath } from '@/lib/auth-cookies'
import { API_BASE_URL } from '@/lib/config'

const features = [
  {
    icon: Sparkles,
    title: 'Intelligent Routing',
    description: 'Auto-route tasks to the best-fit agent',
  },
  {
    icon: Shield,
    title: 'Guardrails Built-in',
    description: 'Safety rules enforced at every invocation',
  },
  {
    icon: Zap,
    title: 'Real-time Execution',
    description: 'Monitor runs, logs, and cost live',
  },
]

function GoogleIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden>
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
    </svg>
  )
}

function GitHubIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden>
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.012 8.012 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
    </svg>
  )
}

export default function LoginPage() {
  const router = useRouter()
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [rememberMe, setRememberMe] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const getRedirectTarget = (fallback: string, role?: string): string => {
    if (typeof window === 'undefined') return fallback
    const from = new URLSearchParams(window.location.search).get('from')
    if (from && from.startsWith('/') && !from.startsWith('//')) {
      const isSuperAdmin = role === 'super_admin' || role === 'super admin'
      if (isSuperAdmin && from.startsWith('/client')) {
        return fallback
      }
      return from
    }
    return fallback
  }


  const handleOAuth = (provider: 'google' | 'github') => {
    setError('')
    const from = new URLSearchParams(window.location.search).get('from')
    if (from?.startsWith('/') && !from.startsWith('//')) sessionStorage.setItem('auth_redirect', from)
    window.location.href = `${API_BASE_URL}/auth/oauth/${provider}`
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const result = loginSchema.safeParse({ email, password })
      if (!result.success) {
        setError(result.error.issues[0].message)
        return
      }
      const user = await login(email, password, rememberMe)
      window.location.href = getRedirectTarget(getDashboardPath(user.role), user.role)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen w-full bg-background">
      {/* Left hero — desktop only. Flat, theme-aware ambient language mirroring the landing hero. */}
      <div className="hidden lg:flex lg:w-[52%] relative flex-col overflow-hidden border-r border-border">

        {/* soft violet glow only — clean panel, no busy section texture */}
        <div className="pointer-events-none absolute -top-24 -left-16 size-[34rem] rounded-full bg-violet-500/15 blur-[120px]" />
        <div className="pointer-events-none absolute -bottom-32 right-[8%] size-[26rem] rounded-full bg-violet-500/10 blur-[120px]" />

        <div className="relative z-10 flex flex-col h-full p-10 xl:p-14">
          {/* Logo — shared landing brand mark */}
          <Link href="/" aria-label="ONE-AI home">
            <Logo />
          </Link>

          {/* Hero copy */}
          <div className="mt-auto mb-14 max-w-lg">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card/60 px-3 py-1 text-xs font-medium text-muted-foreground backdrop-blur-xl mb-6">
              The enterprise AI agent platform
            </span>

            <h1 className="text-[38px] xl:text-[46px] font-extrabold leading-[1.08] tracking-tight text-foreground">
              Manage your{' '}
              <span className="text-violet-600 dark:text-violet-400">AI agents</span>{' '}
              at enterprise scale
            </h1>

            <p className="mt-4 text-[15px] text-muted-foreground leading-relaxed">
              Deploy, monitor, and orchestrate intelligent agents with built-in guardrails and real-time observability.
            </p>

            <div className="mt-8 flex flex-col gap-3">
              {features.map(({ icon: Icon, title, description }) => (
                <div
                  key={title}
                  className="glass-card flex items-center gap-4 rounded-2xl border border-border bg-card/60 px-4 py-3 backdrop-blur-2xl backdrop-saturate-150"
                >
                  <span className="flex size-9 items-center justify-center rounded-xl bg-violet-500/12 shrink-0">
                    <Icon className="w-4.5 h-4.5 text-violet-600 dark:text-violet-400" />
                  </span>
                  <div>
                    <p className="text-[14px] font-semibold text-foreground">{title}</p>
                    <p className="text-[12.5px] text-muted-foreground mt-0.5">{description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Right form panel */}
      <div className="flex-1 flex flex-col justify-center items-center p-6 sm:p-10">
        {/* Mobile logo */}
        <Link href="/" aria-label="ONE-AI home" className="flex lg:hidden mb-10">
          <Logo />
        </Link>

        <div className="w-full max-w-[400px]">
          <div className="mb-8">
            <h2 className="text-[26px] font-bold text-foreground tracking-tight">Welcome back</h2>
            <p className="text-[14px] text-muted-foreground mt-1">Sign in to your ONE-AI account</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div
                className={
                  error.toLowerCase().includes('pending approval') ||
                  error.toLowerCase().includes('registration successful') ||
                  error.toLowerCase().includes('confirmed by')
                    ? "p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/50 text-[13px] text-emerald-700 dark:text-emerald-300 font-medium flex items-center gap-2"
                    : "p-3 rounded-xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800/50 text-[13px] text-red-600 dark:text-red-400"
                }
              >
                {error}
              </div>
            )}

            <div>
              <label className="text-[12.5px] font-semibold text-foreground/80 block mb-1.5 tracking-wide">
                Email address
              </label>
              <Input
                type="email"
                placeholder="you@company.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                disabled={loading}
                autoComplete="email"
              />
            </div>

            <div>
              <label className="text-[12.5px] font-semibold text-foreground/80 block mb-1.5 tracking-wide">
                Password
              </label>
              <div className="relative">
                <Input
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  disabled={loading}
                  autoComplete="current-password"
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between pt-0.5">
              <label className="flex items-center gap-2 text-[13px] text-foreground/80 cursor-pointer select-none">
                <Checkbox
                  checked={rememberMe}
                  onChange={setRememberMe}
                  aria-label="Remember me"
                />
                Remember me
              </label>
              <Link
                href="/forgot-password"
                className="text-[13px] text-violet-600 dark:text-violet-400 hover:text-violet-500 dark:hover:text-violet-300 font-medium transition-colors"
              >
                Forgot password?
              </Link>
            </div>

            <Button
              type="submit"
              variant="primary"
              className="w-full h-10 text-[14px] font-semibold mt-1 group"
              disabled={loading}
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Signing in...
                </>
              ) : (
                <>
                  Sign in
                  <ArrowRight className="w-4 h-4 ml-1 group-hover:translate-x-0.5 transition-transform" />
                </>
              )}
            </Button>
          </form>

          <div className="my-5 flex items-center gap-3">
            <div className="flex-1 h-px bg-border" />
            <span className="text-[12px] text-muted-foreground">or continue with</span>
            <div className="flex-1 h-px bg-border" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Button
              variant="outline"
              type="button"
              className="w-full h-9 gap-2 text-[13px]"
              onClick={() => handleOAuth('google')}
              disabled={loading}
            >
              <GoogleIcon />
              Google
            </Button>
            <Button
              variant="outline"
              type="button"
              className="w-full h-9 gap-2 text-[13px]"
              onClick={() => handleOAuth('github')}
              disabled={loading}
            >
              <GitHubIcon />
              GitHub
            </Button>
          </div>

          <p className="mt-8 text-center text-[13.5px] text-muted-foreground">
            Don&apos;t have an account?{' '}
            <Link
              href="/register"
              onClick={() => {
                const from = new URLSearchParams(window.location.search).get('from')
                if (from?.startsWith('/') && !from.startsWith('//')) sessionStorage.setItem('auth_redirect', from)
              }}
              className="text-violet-600 dark:text-violet-400 hover:text-violet-500 dark:hover:text-violet-300 font-semibold transition-colors"
            >
              Create one →
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
