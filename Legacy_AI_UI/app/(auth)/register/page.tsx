'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Eye, EyeOff, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Logo } from '@/components/landing/logo'
import { authApi } from '@/lib/api'
import { getDashboardPath, setAuthCookie } from '@/lib/auth-cookies'
import { Select } from '@/components/ui/select'
import { useOrganizations } from '@/hooks/use-organizations'
import { FormField } from '@/components/ui/form-field'

export default function RegisterPage() {
  const router = useRouter()
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: '',
    organization_id: '',
  })
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)

  const { data: orgPage, loading: loadingOrgs } = useOrganizations(1, undefined, 1000, {}, true)
  const organizations = orgPage?.items || []

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target
    setFormData(prev => ({ ...prev, [name]: value }))
    setFieldErrors(prev => (prev[name] ? { ...prev, [name]: '' } : prev))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setFieldErrors({})

    if (!formData.name.trim()) {
      setFieldErrors({ name: 'Name is required' })
      return
    }
    if (formData.password !== formData.confirmPassword) {
      setFieldErrors({ confirmPassword: 'Passwords do not match' })
      return
    }
    if (formData.password.length < 8) {
      setFieldErrors({ password: 'Password must be at least 8 characters' })
      return
    }
    if (!/[A-Z]/.test(formData.password)) {
      setFieldErrors({ password: 'Password must contain at least one uppercase letter' })
      return
    }
    if (!/[a-z]/.test(formData.password)) {
      setFieldErrors({ password: 'Password must contain at least one lowercase letter' })
      return
    }
    if (!/[0-9]/.test(formData.password)) {
      setFieldErrors({ password: 'Password must contain at least one digit' })
      return
    }
    if (!/[!@#$%^&*(),.?":{}|<>]/.test(formData.password)) {
      setFieldErrors({ password: 'Password must contain at least one special character' })
      return
    }

    setLoading(true)
    try {
      const response = await authApi.register({
        name: formData.name,
        email: formData.email,
        password: formData.password,
        organization_id: formData.organization_id || undefined,
      })
      localStorage.setItem('access_token', response.access_token)
      setAuthCookie(response.access_token)
      const from = new URLSearchParams(window.location.search).get('from')
      const savedFrom = sessionStorage.getItem('auth_redirect')
      sessionStorage.removeItem('auth_redirect')
      const target = from || savedFrom
      window.location.href = target?.startsWith('/') && !target.startsWith('//') ? target : getDashboardPath(response.user.role)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative min-h-screen flex items-center justify-center overflow-hidden p-4">
      <div className="pointer-events-none absolute -top-24 -left-16 size-[34rem] rounded-full bg-violet-500/15 blur-[120px]" />
      <div className="pointer-events-none absolute -bottom-32 right-[8%] size-[26rem] rounded-full bg-violet-500/10 blur-[120px]" />

      <div className="glass-card relative z-10 w-full max-w-[440px] rounded-3xl border border-border bg-card/60 p-8 backdrop-blur-2xl backdrop-saturate-150">
        <Link href="/" aria-label="ONE-AI home" className="mb-6 inline-flex">
          <Logo />
        </Link>
        <div className="mb-8">
          <h1 className="text-[24px] font-bold text-foreground">Create your account</h1>
          <p className="text-[14px] text-muted-foreground mt-1">
            Join ONE-AI to manage your AI agents
          </p>
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

          <FormField label="Full Name" htmlFor="name" required error={fieldErrors.name}>
            <Input
              id="name"
              type="text"
              name="name"
              placeholder="Full Name"
              value={formData.name}
              onChange={handleChange}
              disabled={loading}
              required
            />
          </FormField>

          <FormField label="Work Email" htmlFor="email" required error={fieldErrors.email}>
            <Input
              id="email"
              type="email"
              name="email"
              placeholder="Work Email"
              value={formData.email}
              onChange={handleChange}
              disabled={loading}
              required
            />
          </FormField>

          <FormField
            label="Password"
            htmlFor="password"
            required
            error={fieldErrors.password}
            hint="Min 8 chars, upper, lower, digit, special"
          >
            <Input
              id="password"
              type={showPassword ? "text" : "password"}
              name="password"
              placeholder="Password"
              value={formData.password}
              onChange={handleChange}
              disabled={loading}
              required
              rightElement={
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="hover:text-[var(--text-1)] transition-colors focus:outline-none"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              }
            />
          </FormField>

          <FormField label="Confirm Password" htmlFor="confirmPassword" required error={fieldErrors.confirmPassword}>
            <Input
              id="confirmPassword"
              type={showConfirmPassword ? "text" : "password"}
              name="confirmPassword"
              placeholder="Confirm Password"
              value={formData.confirmPassword}
              onChange={handleChange}
              disabled={loading}
              required
              rightElement={
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="hover:text-[var(--text-1)] transition-colors focus:outline-none"
                  tabIndex={-1}
                >
                  {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              }
            />
          </FormField>

          <FormField
            label="Organization"
            htmlFor="organization_id"
            error={fieldErrors.organization_id}
            hint="If organization isn't in the list choose none"
          >
            <Select
              searchable
              searchPlaceholder="Search organization..."
              value={formData.organization_id}
              onValueChange={(value) => {
                setFormData(prev => ({ ...prev, organization_id: value }))
                setFieldErrors(prev => (prev.organization_id ? { ...prev, organization_id: '' } : prev))
              }}
              options={[
                { value: '', label: 'None' },
                ...organizations.map(org => ({
                  value: org.id || '',
                  label: org.name,
                })),
              ]}
              disabled={loading || loadingOrgs}
              placeholder="Select Organization"
            />
          </FormField>

          <Button
            type="submit"
            variant="primary"
            className="w-full mt-2"
            disabled={loading}
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Creating account...
              </>
            ) : 'Create Account'}
          </Button>
        </form>

        <div className="mt-6 text-center text-[13px] text-muted-foreground">
          Already have an account?{' '}
          <Link href="/login" className="text-violet-600 dark:text-violet-400 hover:text-violet-500 dark:hover:text-violet-300 font-medium transition-colors">
            Sign in
          </Link>
        </div>
      </div>
    </div>
  )
}
