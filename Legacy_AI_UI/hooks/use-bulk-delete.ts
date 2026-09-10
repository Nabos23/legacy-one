'use client'

import { useState } from 'react'
import { useToast } from '@/hooks/use-toast'

const MAX_CONCURRENT_DELETES = 5

async function runWithConcurrencyLimit<T>(
  items: T[],
  limit: number,
  worker: (item: T) => Promise<unknown>,
): Promise<PromiseSettledResult<unknown>[]> {
  const results: PromiseSettledResult<unknown>[] = new Array(items.length)
  let next = 0

  async function runNext(): Promise<void> {
    const i = next++
    if (i >= items.length) return
    try {
      const value = await worker(items[i])
      results[i] = { status: 'fulfilled', value }
    } catch (reason) {
      results[i] = { status: 'rejected', reason }
    }
    return runNext()
  }

  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, runNext))
  return results
}

export function useBulkDelete(
  deleteFn: (id: string) => Promise<unknown>,
  opts: { entity: string; onDone?: () => void },
) {
  const [busy, setBusy] = useState(false)
  const { toast } = useToast()

  const run = async (ids: string[], clear: () => void) => {
    if (ids.length === 0) return
    setBusy(true)
    try {
      const results = await runWithConcurrencyLimit(ids, MAX_CONCURRENT_DELETES, deleteFn)
      const ok = results.filter(r => r.status === 'fulfilled').length
      const failed = results.length - ok
      if (ok) toast.success(`Deleted ${ok} ${opts.entity}${ok === 1 ? '' : 's'}`)
      if (failed) toast.error(`Failed to delete ${failed} ${opts.entity}${failed === 1 ? '' : 's'}`)
      clear()
      opts.onDone?.()
    } finally {
      setBusy(false)
    }
  }

  return { busy, run }
}
