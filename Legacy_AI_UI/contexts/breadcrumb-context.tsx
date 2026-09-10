'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

interface BreadcrumbActions {
  setLabel: (segment: string, label: string) => void
  clearLabel: (segment: string) => void
}

// Split into two contexts on purpose: actions never change identity across
// renders, labels do (every time any page registers/clears one). A component
// that only calls setLabel/clearLabel (useBreadcrumbLabel) must subscribe to
// the stable one only — otherwise its effect's dependency array would see a
// "new" context value on every label change and re-fire, clearing then
// re-setting its own label forever (infinite update loop).
const BreadcrumbActionsContext = createContext<BreadcrumbActions | null>(null)
const BreadcrumbLabelsContext = createContext<Record<string, string>>({})

export function BreadcrumbProvider({ children }: { children: React.ReactNode }) {
  const [labels, setLabels] = useState<Record<string, string>>({})

  const setLabel = useCallback((segment: string, label: string) => {
    setLabels(prev => (prev[segment] === label ? prev : { ...prev, [segment]: label }))
  }, [])

  const clearLabel = useCallback((segment: string) => {
    setLabels(prev => {
      if (!(segment in prev)) return prev
      const next = { ...prev }
      delete next[segment]
      return next
    })
  }, [])

  const actions = useMemo(() => ({ setLabel, clearLabel }), [setLabel, clearLabel])

  return (
    <BreadcrumbActionsContext.Provider value={actions}>
      <BreadcrumbLabelsContext.Provider value={labels}>
        {children}
      </BreadcrumbLabelsContext.Provider>
    </BreadcrumbActionsContext.Provider>
  )
}

export function useBreadcrumbLabels(): Record<string, string> {
  return useContext(BreadcrumbLabelsContext)
}

/** Register a display label for a raw URL segment (e.g. an id) while this
 * component is mounted — the top breadcrumb shows this instead of the raw
 * segment. Call once the entity's name has loaded; pass undefined/empty to
 * skip (e.g. while still loading). */
export function useBreadcrumbLabel(segment: string | undefined, label: string | undefined) {
  const actions = useContext(BreadcrumbActionsContext)
  useEffect(() => {
    if (!actions || !segment || !label) return
    actions.setLabel(segment, label)
    return () => actions.clearLabel(segment)
  }, [actions, segment, label])
}
