'use client'

import { useState } from 'react'
import { KeyRound } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { SettingsCard, SettingsCardHeader } from './settings-card'
import { useAuth } from '@/contexts/auth-context'
import { useToast } from '@/hooks/use-toast'
import { authApi } from '@/lib/api'
import { passwordSchema } from '@/lib/validations/auth'

/** Password change via the existing OTP reset flow: request a code by email, then submit it with a new password. */
export function SecuritySection() {
  const { user } = useAuth()
  const { toast } = useToast()

  const [pwStage, setPwStage] = useState<'idle' | 'sent'>('idle')
  const [otp, setOtp] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [pwBusy, setPwBusy] = useState(false)

  const resetPwForm = () => {
    setPwStage('idle')
    setOtp('')
    setNewPw('')
    setConfirmPw('')
  }

  const requestCode = async () => {
    if (!user?.email) return
    setPwBusy(true)
    try {
      const res = await authApi.forgotPassword(user.email)
      setPwStage('sent')
      if (res?.otp) setOtp(res.otp) // dev mode returns the code for convenience
      toast.success(`Verification code sent to ${user.email}`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not send verification code')
    } finally {
      setPwBusy(false)
    }
  }

  const submitNewPassword = async () => {
    if (!user?.email) return
    if (!otp.trim()) {
      toast.error('Enter the verification code from your email')
      return
    }
    const parsed = passwordSchema.safeParse(newPw)
    if (!parsed.success) {
      toast.error(parsed.error.issues[0].message)
      return
    }
    if (newPw !== confirmPw) {
      toast.error('Passwords do not match')
      return
    }
    setPwBusy(true)
    try {
      await authApi.resetPassword(user.email, otp.trim(), newPw)
      toast.success('Password updated')
      resetPwForm()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not update password')
    } finally {
      setPwBusy(false)
    }
  }

  return (
    <SettingsCard>
      <SettingsCardHeader
        icon={KeyRound}
        title="Password"
        description="Change the password for your account"
      />

      {pwStage === 'idle' ? (
        <div key="idle" className="animate-fadeIn">
          <p className="text-[13px] text-[var(--text-2)] mb-4">
            We&rsquo;ll email a verification code to{' '}
            <span className="font-medium text-[var(--text-1)]">{user?.email ?? 'your account'}</span>.
            Enter it along with your new password to confirm the change.
          </p>
          <Button variant="secondary" size="sm" onClick={requestCode} disabled={pwBusy || !user?.email}>
            {pwBusy ? 'Sending…' : 'Send verification code'}
          </Button>
        </div>
      ) : (
        <div key="verify" className="animate-fadeIn space-y-4">
          <div>
            <label className="text-[13px] font-medium block mb-2">Verification code</label>
            <Input
              value={otp}
              onChange={e => setOtp(e.target.value)}
              placeholder="Enter the code from your email"
              className="font-mono"
            />
          </div>
          <div>
            <label className="text-[13px] font-medium block mb-2">New password</label>
            <Input
              type="password"
              value={newPw}
              onChange={e => setNewPw(e.target.value)}
              placeholder="At least 8 characters"
            />
            <p className="text-[12px] text-[var(--text-3)] mt-1.5">
              Must include uppercase, lowercase, a number, and a special character.
            </p>
          </div>
          <div>
            <label className="text-[13px] font-medium block mb-2">Confirm new password</label>
            <Input
              type="password"
              value={confirmPw}
              onChange={e => setConfirmPw(e.target.value)}
              placeholder="Re-enter new password"
            />
          </div>
          <div className="flex items-center gap-2 pt-1">
            <Button variant="primary" size="sm" onClick={submitNewPassword} disabled={pwBusy}>
              {pwBusy ? 'Updating…' : 'Update password'}
            </Button>
            <Button variant="ghost" size="sm" onClick={resetPwForm} disabled={pwBusy}>
              Cancel
            </Button>
            <button
              type="button"
              onClick={requestCode}
              disabled={pwBusy}
              className="text-[13px] text-violet-600 hover:text-violet-700 dark:text-violet-400 dark:hover:text-violet-300 transition-colors ml-auto disabled:opacity-50"
            >
              Resend code
            </button>
          </div>
        </div>
      )}
    </SettingsCard>
  )
}
