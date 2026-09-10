'use client'

import { useState, useEffect } from 'react'
import { connectorsApi } from '@/lib/api'
import type { ConnectorRegistryItem } from '@/types/connectors'

export function useConnectors() {
  const [data, setData] = useState<ConnectorRegistryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    connectorsApi
      .getRegistry()
      .then(setData)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Failed to load connectors'))
      .finally(() => setLoading(false))
  }, [])

  return { data, loading, error }
}
