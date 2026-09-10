'use client'

import { useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useToastContext } from '@/contexts/toast-context'

export function OAuthCallbackHandler() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { addToast } = useToastContext()

  useEffect(() => {
    const drive = searchParams.get('drive')
    const onedrive = searchParams.get('onedrive')
    const connector = searchParams.get('connector')

    if (drive === 'connected') {
      router.replace('/client/drive')
    } else if (drive === 'error') {
      const reason = searchParams.get('reason')
      router.replace(`/client/drive?error=${encodeURIComponent(reason || 'unknown')}`)
    } else if (onedrive === 'connected') {
      router.replace('/client/onedrive')
    } else if (onedrive === 'error') {
      const reason = searchParams.get('reason')
      router.replace(`/client/onedrive?error=${encodeURIComponent(reason || 'unknown')}`)
    } else if (connector === 'connected') {
      addToast({ type: 'success', message: 'Connector connected successfully!' })
      router.replace('/client/connectors')
    } else if (connector === 'error') {
      const reason = searchParams.get('reason')
      addToast({ type: 'error', message: `Connection failed: ${decodeURIComponent(reason || 'unknown')}` })
      router.replace('/client/connectors')
    }
  }, [router, searchParams, addToast])

  return null
}
