'use client'

import { useEffect } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { useToastContext } from '@/contexts/toast-context'

export function ConnectorCallbackHandler() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const { addToast } = useToastContext()

  useEffect(() => {
    const connected = searchParams.get('connected')
    const error = searchParams.get('error')

    if (connected === '1') {
      addToast({ type: 'success', message: 'Connector connected successfully!' })
      router.replace('/client/connectors')
    } else if (error) {
      addToast({ type: 'error', message: `Connection failed: ${decodeURIComponent(error)}` })
      router.replace('/client/connectors')
    }
  }, [searchParams, router, addToast])

  return null
}
