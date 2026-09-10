'use client'

import { useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, CheckCircle2, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Stepper } from '@/components/ui/stepper'
import { Logo } from '@/components/landing/logo'
import { authApi } from '@/lib/api'
import { forgotPasswordSchema } from '@/lib/validations/auth'

export default function ForgotPasswordPage() {
  const [step, setStep] = useState(0)
  const [email, setEmail] = useState('')
  const [otp, setOtp] = useState(['', '', '', '', '', ''])
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const steps = ['Email', 'Verify OTP', 'New Password']

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const result = forgotPasswordSchema.safeParse({ email })
      if (!result.success) {
        setError(result.error.issues[0].message)
        return
      }

      await authApi.forgotPassword(email)
      setStep(1)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send reset email')
    } finally {
      setLoading(false)
    }
  }

  const handleOtpChange = (index: number, value: string) => {
    if (value.length <= 1 && /^\d*$/.test(value)) {
      const newOtp = [...otp]
      newOtp[index] = value
      setOtp(newOtp)

      if (value && index < 5) {
        const next = document.querySelector(`input[data-otp-index="${index + 1}"]`) as HTMLInputElement
        next?.focus()
      }
    }
  }

  const handleOtpKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && !otp[index] && index > 0) {
      const prev = document.querySelector(`input[data-otp-index="${index - 1}"]`) as HTMLInputElement
      prev?.focus()
    }
  }

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (otp.some(digit => !digit)) {
      setError('Please enter all 6 digits')
      return
    }
    setLoading(true)
    try {
      await authApi.verifyOtp(email, otp.join(''))
      setStep(2)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Invalid or expired code')
    } finally {
      setLoading(false)
    }
  }

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    if (!/[A-Z]/.test(newPassword)) {
      setError('Password must contain at least one uppercase letter')
      return
    }
    if (!/[a-z]/.test(newPassword)) {
      setError('Password must contain at least one lowercase letter')
      return
    }
    if (!/[0-9]/.test(newPassword)) {
      setError('Password must contain at least one digit')
      return
    }
    if (!/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?`~]/.test(newPassword)) {
      setError('Password must contain at least one special character')
      return
    }

    setLoading(true)
    try {
      await authApi.resetPassword(email, otp.join(''), newPassword)
      setStep(3)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reset password')
    } finally {
      setLoading(false)
    }
  }

  const handleResendCode = async () => {
    setError('')
    setOtp(['', '', '', '', '', ''])
    setLoading(true)
    try {
      await authApi.forgotPassword(email)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resend code')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative min-h-screen flex items-center justify-center overflow-hidden p-4">
      <div className="pointer-events-none absolute -top-24 -left-16 size-[34rem] rounded-full bg-violet-500/15 blur-[120px]" />
      <div className="pointer-events-none absolute -bottom-32 right-[8%] size-[26rem] rounded-full bg-violet-500/10 blur-[120px]" />

      <div className="glass-card relative z-10 w-full max-w-[420px] rounded-3xl border border-border bg-card/60 p-8 backdrop-blur-2xl backdrop-saturate-150">
        <Link href="/" aria-label="ONE-AI home" className="mb-6 inline-flex">
          <Logo />
        </Link>
        {/* Stepper */}
        {step < 3 && (
          <div className="mb-8">
            <Stepper steps={steps} currentStep={step} />
          </div>
        )}

        {/* Step 0: Email */}
        {step === 0 && (
          <form onSubmit={handleEmailSubmit} className="space-y-4">
            <Link href="/login" className="inline-flex items-center gap-1 text-[13px] text-violet-600 dark:text-violet-400 hover:text-violet-500 dark:hover:text-violet-300 transition-colors mb-4">
              <ArrowLeft className="w-4 h-4" />
              Back to login
            </Link>
            <h2 className="text-[18px] font-semibold mb-4">Reset your password</h2>
            {error && (
              <div className="p-3 rounded-xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800/50 text-[13px] text-red-600 dark:text-red-400">
                {error}
              </div>
            )}
            <Input
              type="email"
              placeholder="Enter your email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={loading}
            />
            <Button
              type="submit"
              variant="primary"
              className="w-full mt-6"
              disabled={loading}
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Sending...
                </>
              ) : 'Send Code'}
            </Button>
          </form>
        )}

        {/* Step 1: OTP */}
        {step === 1 && (
          <form onSubmit={handleVerifyOtp} className="space-y-4">
            <h2 className="text-[18px] font-semibold">Check your email</h2>
            <p className="text-[13px] text-[var(--text-3)]">We&apos;ve sent a 6-digit code to {email}</p>
            {error && (
              <div className="p-3 rounded-xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800/50 text-[13px] text-red-600 dark:text-red-400">
                {error}
              </div>
            )}
            <div className="flex gap-2 justify-center py-4">
              {otp.map((digit, index) => (
                <input
                  key={index}
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  aria-label={`Digit ${index + 1} of 6`}
                  data-otp-index={index}
                  value={digit}
                  onChange={(e) => handleOtpChange(index, e.target.value)}
                  onKeyDown={(e) => handleOtpKeyDown(index, e)}
                  maxLength={1}
                  className="w-12 h-12 rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface)] text-center text-[20px] font-semibold text-[var(--text-1)] transition-colors focus:outline-none focus:border-violet-400 dark:focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20"
                  autoFocus={index === 0}
                />
              ))}
            </div>
            <Button
              type="submit"
              variant="primary"
              className="w-full"
              disabled={loading || otp.some(d => !d)}
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Verifying...
                </>
              ) : 'Verify Code'}
            </Button>
            <Button
              type="button"
              variant="ghost"
              className="w-full"
              onClick={handleResendCode}
            >
              Resend code
            </Button>
          </form>
        )}

        {/* Step 2: New Password */}
        {step === 2 && (
          <form onSubmit={handleResetPassword} className="space-y-4">
            <h2 className="text-[18px] font-semibold">Create new password</h2>
            {error && (
              <div className="p-3 rounded-xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800/50 text-[13px] text-red-600 dark:text-red-400">
                {error}
              </div>
            )}
            <Input
              type="password"
              placeholder="New password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              disabled={loading}
            />
            <Input
              type="password"
              placeholder="Confirm password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              disabled={loading}
            />
            <Button
              type="submit"
              variant="primary"
              className="w-full mt-6"
              disabled={loading}
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Resetting...
                </>
              ) : 'Reset Password'}
            </Button>
          </form>
        )}

        {/* Step 3: Success */}
        {step === 3 && (
          <div className="flex flex-col items-center justify-center py-8 space-y-4">
            <CheckCircle2 className="w-16 h-16 text-green-600 dark:text-green-400" />
            <h2 className="text-[20px] font-semibold">Password reset!</h2>
            <p className="text-[13px] text-[var(--text-3)] text-center">
              Your password has been successfully reset
            </p>
            <Link href="/login" className="w-full">
              <Button variant="primary" className="w-full mt-6">
                Back to sign in
              </Button>
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}
