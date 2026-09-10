'use client'

import { useState } from 'react'
import { Plus, HelpCircle } from 'lucide-react'
import { SettingsCard, SettingsCardHeader } from '@/components/settings/settings-card'
import type { HelpFaq } from '@/lib/help-content'
import { cn } from '@/lib/utils'

export function HelpFaqSection({ faqs }: { faqs: HelpFaq[] }) {
  const [open, setOpen] = useState<number | null>(0)

  return (
    <SettingsCard>
      <SettingsCardHeader
        icon={HelpCircle}
        title="Frequently Asked Questions"
        description="Answers to what people usually get stuck on"
      />
      <div className="space-y-2">
        {faqs.map((f, i) => {
          const isOpen = open === i
          return (
            <div
              key={f.q}
              className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] overflow-hidden"
            >
              <button
                type="button"
                onClick={() => setOpen(isOpen ? null : i)}
                aria-expanded={isOpen}
                className="flex w-full items-center gap-3 p-3.5 text-left"
              >
                <span className="flex-1 text-[13.5px] font-medium text-[var(--text-1)]">{f.q}</span>
                <Plus
                  className={cn(
                    'w-4 h-4 text-violet-500 transition-transform shrink-0',
                    isOpen && 'rotate-45',
                  )}
                />
              </button>
              <div
                className={cn(
                  'grid transition-[grid-template-rows] duration-200 ease-out',
                  isOpen ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]',
                )}
              >
                <div className="overflow-hidden">
                  <p className="px-3.5 pb-3.5 text-[13px] leading-relaxed text-[var(--text-2)]">{f.a}</p>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </SettingsCard>
  )
}
