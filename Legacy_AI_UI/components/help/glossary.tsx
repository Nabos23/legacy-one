import { BookMarked } from 'lucide-react'
import { SettingsCard, SettingsCardHeader } from '@/components/settings/settings-card'
import type { GlossaryTerm } from '@/lib/help-content'

export function Glossary({ terms }: { terms: GlossaryTerm[] }) {
  return (
    <SettingsCard>
      <SettingsCardHeader
        icon={BookMarked}
        title="Glossary"
        description="Core vocabulary used across the platform"
      />
      <div className="grid sm:grid-cols-2 gap-3">
        {terms.map(t => (
          <div key={t.term} className="p-3.5 rounded-xl bg-[var(--surface-2)] border border-[var(--border)]">
            <p className="text-[13.5px] font-semibold text-[var(--text-1)] mb-1">{t.term}</p>
            <p className="text-[12.5px] leading-relaxed text-[var(--text-3)]">{t.definition}</p>
          </div>
        ))}
      </div>
    </SettingsCard>
  )
}
