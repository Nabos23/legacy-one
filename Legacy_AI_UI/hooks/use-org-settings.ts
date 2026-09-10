'use client'

import { useState, useEffect, useCallback } from 'react'
import { settingsApi } from '@/lib/api'
import { useAuth } from '@/contexts/auth-context'
import type { OrgSettings, OrgSettingsUpdate } from '@/types'

/**
 * Loads and persists the current user's organization settings.
 * Scoped to the authenticated user's organization_id.
 */
export function useOrgSettings() {
  const { user } = useAuth()
  const orgId = user?.organization_id

  const [data, setData] = useState<OrgSettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback(async () => {
    if (!orgId) {
      setLoading(false)
      return
    }
    try {
      setLoading(true)
      setData(await settingsApi.get(orgId))
      setError(null)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load settings')
    } finally {
      setLoading(false)
    }
  }, [orgId])

  useEffect(() => {
    refetch()
  }, [refetch])

  const save = useCallback(
    async (updates: OrgSettingsUpdate) => {
      if (!orgId) throw new Error('No organization in scope')
      setSaving(true)
      try {
        const updated = await settingsApi.update(orgId, updates)
        setData(updated)
        return updated
      } finally {
        setSaving(false)
      }
    },
    [orgId]
  )

  return { data, loading, saving, error, save, refetch, orgId }
}
