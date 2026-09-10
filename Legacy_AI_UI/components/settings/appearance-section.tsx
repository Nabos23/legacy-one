'use client'

import { useEffect, useState } from 'react'
import { LayoutGrid, Home, Globe2 } from 'lucide-react'
import { Select, type SelectOption } from '@/components/ui/select'
import { SettingsCard, SettingsCardHeader } from './settings-card'
import {
  getStoredDensity, setStoredDensity, type Density,
  getStoredTimezone, setStoredTimezone, TIMEZONE_OPTIONS,
  getStoredLanding, setStoredLanding,
} from '@/lib/preferences'
import { useToast } from '@/hooks/use-toast'
import { cn } from '@/lib/utils'

interface AppearanceSectionProps {
  /** Valid default-landing sub-paths for this dashboard area (client vs. admin), with labels. */
  landingOptions: SelectOption[]
}

/** Density, timezone, and default-landing-page preferences — all local to this browser. */
export function AppearanceSection({ landingOptions }: AppearanceSectionProps) {
  const { toast } = useToast()
  const [density, setDensity] = useState<Density>('comfortable')
  const [timezone, setTimezone] = useState('')
  const [landing, setLanding] = useState('dashboard')

  useEffect(() => {
    setDensity(getStoredDensity())
    setTimezone(getStoredTimezone())
    setLanding(getStoredLanding(landingOptions.map(o => o.value)) ?? 'dashboard')
  }, [landingOptions])

  const handleDensityChange = (next: Density) => {
    setDensity(next)
    setStoredDensity(next)
    toast.success(next === 'compact' ? 'Compact layout applied' : 'Comfortable layout applied')
  }

  const handleTimezoneChange = (tz: string) => {
    setTimezone(tz)
    setStoredTimezone(tz)
    toast.success('Timezone updated')
  }

  const handleLandingChange = (path: string) => {
    setLanding(path)
    setStoredLanding(path)
    toast.success('Default landing page updated')
  }

  return (
    <SettingsCard>
      <SettingsCardHeader
        icon={LayoutGrid}
        title="Appearance & Defaults"
        description="How the app looks and where it takes you on login"
      />

      <div className="space-y-5">
        <div>
          <label className="text-[13.5px] font-medium block mb-2 text-[var(--text-1)]">Layout density</label>
          <div className="inline-flex p-1 rounded-xl bg-[var(--surface-2)] border border-[var(--border)]">
            {(['comfortable', 'compact'] as const).map(d => (
              <button
                key={d}
                type="button"
                onClick={() => handleDensityChange(d)}
                className={cn(
                  'px-3.5 py-1.5 rounded-lg text-[13px] font-medium capitalize transition-colors',
                  density === d
                    ? 'bg-[var(--surface)] text-[var(--text-1)] shadow-sm'
                    : 'text-[var(--text-3)] hover:text-[var(--text-1)]',
                )}
              >
                {d}
              </button>
            ))}
          </div>
          <p className="text-[12px] text-[var(--text-3)] mt-1.5">
            Compact tightens spacing across cards, lists, and tables.
          </p>
        </div>

        <div>
          <label className="text-[13.5px] font-medium mb-2 flex items-center gap-1.5 text-[var(--text-1)]">
            <Globe2 className="w-3.5 h-3.5" /> Timezone
          </label>
          <Select
            value={timezone}
            onValueChange={handleTimezoneChange}
            options={TIMEZONE_OPTIONS as unknown as SelectOption[]}
          />
          <p className="text-[12px] text-[var(--text-3)] mt-1.5">
            Used to display dates across traces, sessions, and activity.
          </p>
        </div>

        <div>
          <label className="text-[13.5px] font-medium mb-2 flex items-center gap-1.5 text-[var(--text-1)]">
            <Home className="w-3.5 h-3.5" /> Default landing page
          </label>
          <Select value={landing} onValueChange={handleLandingChange} options={landingOptions} />
          <p className="text-[12px] text-[var(--text-3)] mt-1.5">
            Where you land right after signing in.
          </p>
        </div>
      </div>
    </SettingsCard>
  )
}
