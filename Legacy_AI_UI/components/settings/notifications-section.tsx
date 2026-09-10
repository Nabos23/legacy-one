'use client'

import { useEffect, useState } from 'react'
import { Bell, Save } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Toggle } from '@/components/ui/toggle'
import { SettingsCard, SettingsCardHeader } from './settings-card'
import { useTheme } from '@/contexts/theme-context'
import { useToast } from '@/hooks/use-toast'

/** Personal notification + appearance preferences, persisted per-browser under `storageKey`. */
export function NotificationsSection({ storageKey }: { storageKey: string }) {
  const { theme, toggleTheme } = useTheme()
  const { toast } = useToast()

  const [emailNotif, setEmailNotif] = useState(true)
  const [desktopNotif, setDesktopNotif] = useState(false)
  const [weeklyDigest, setWeeklyDigest] = useState(true)
  const [agentAlerts, setAgentAlerts] = useState(true)

  // Hydrate preferences from localStorage after mount (avoids SSR hydration mismatch).
  useEffect(() => {
    try {
      const raw = localStorage.getItem(storageKey)
      if (!raw) return
      const p = JSON.parse(raw)
      if (typeof p.emailNotif === 'boolean') setEmailNotif(p.emailNotif)
      if (typeof p.desktopNotif === 'boolean') setDesktopNotif(p.desktopNotif)
      if (typeof p.weeklyDigest === 'boolean') setWeeklyDigest(p.weeklyDigest)
      if (typeof p.agentAlerts === 'boolean') setAgentAlerts(p.agentAlerts)
    } catch {
      /* ignore malformed prefs */
    }
  }, [storageKey])

  const savePreferences = () => {
    try {
      localStorage.setItem(
        storageKey,
        JSON.stringify({ emailNotif, desktopNotif, weeklyDigest, agentAlerts })
      )
      toast.success('Preferences saved')
    } catch {
      toast.error('Could not save preferences in this browser')
    }
  }

  return (
    <SettingsCard>
      <SettingsCardHeader
        icon={Bell}
        title="Preferences"
        description="Choose how ONE-AI keeps you in the loop"
      />
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-[13.5px] text-[var(--text-1)]">Dark Mode</span>
          <Toggle checked={theme === 'dark'} onChange={toggleTheme} aria-label="Dark Mode" />
        </div>
        <Separator />
        <div className="flex items-center justify-between">
          <div>
            <span className="text-[13.5px] text-[var(--text-1)] block">Email Notifications</span>
            <span className="text-[12px] text-[var(--text-3)]">Product updates and important account activity</span>
          </div>
          <Toggle checked={emailNotif} onChange={setEmailNotif} aria-label="Email Notifications" />
        </div>
        <div className="flex items-center justify-between">
          <div>
            <span className="text-[13.5px] text-[var(--text-1)] block">Desktop Notifications</span>
            <span className="text-[12px] text-[var(--text-3)]">Browser push while the app is open</span>
          </div>
          <Toggle checked={desktopNotif} onChange={setDesktopNotif} aria-label="Desktop Notifications" />
        </div>
        <div className="flex items-center justify-between">
          <div>
            <span className="text-[13.5px] text-[var(--text-1)] block">Agent Alerts</span>
            <span className="text-[12px] text-[var(--text-3)]">Notify me when an agent errors or a connector disconnects</span>
          </div>
          <Toggle checked={agentAlerts} onChange={setAgentAlerts} aria-label="Agent Alerts" />
        </div>
        <div className="flex items-center justify-between">
          <div>
            <span className="text-[13.5px] text-[var(--text-1)] block">Weekly Digest</span>
            <span className="text-[12px] text-[var(--text-3)]">A summary of agent activity every Monday</span>
          </div>
          <Toggle checked={weeklyDigest} onChange={setWeeklyDigest} aria-label="Weekly Digest" />
        </div>
      </div>
      <p className="text-[11px] text-[var(--text-3)]/70 mt-5">
        Saved to this browser only — preferences don&rsquo;t yet sync across devices.
      </p>
      <div className="mt-2 pt-4 border-t border-[var(--border)] flex justify-end">
        <Button variant="primary" size="sm" onClick={savePreferences}>
          <Save className="w-4 h-4 mr-2" />
          Save Preferences
        </Button>
      </div>
    </SettingsCard>
  )
}
