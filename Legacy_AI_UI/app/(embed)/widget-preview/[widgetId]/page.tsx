'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { API_BASE_URL } from '@/lib/config'

declare global {
  interface Window {
    OneAIWidget?: {
      init: (opts: { widgetId: string; apiUrl: string; chatUrl: string; previewToken?: string }) => { open: () => void }
    }
  }
}

/**
 * A blank page that installs the widget exactly as the dashboard's embed
 * snippet does, then opens it automatically -- a working "test this widget"
 * target, distinct from the widget's own iframe page (which never calls the
 * API on its own and can't be opened standalone). This page's origin is
 * always trusted by the backend (see backend/widget/origins.py), so it works
 * without the org needing to allowlist their own dashboard domain first.
 *
 * Accepts ?preview_token=... and passes it through to OneAIWidget.init so the
 * backend serves the DRAFT config instead of the published one -- letting
 * admins preview unpublished changes end-to-end. Read via window.location
 * (not useSearchParams) so this page needs no Suspense boundary and the token
 * never influences prerendering.
 */
export default function WidgetPreviewPage() {
  const params = useParams<{ widgetId: string }>()
  const [isDraftPreview, setIsDraftPreview] = useState(false)

  useEffect(() => {
    const previewToken = new URLSearchParams(window.location.search).get('preview_token')
    setIsDraftPreview(!!previewToken)
    const script = document.createElement('script')
    script.src = `${window.location.origin}/widget.js`
    script.onload = () => {
      const instance = window.OneAIWidget?.init({
        widgetId: params.widgetId,
        apiUrl: API_BASE_URL,
        chatUrl: window.location.origin,
        previewToken: previewToken ?? undefined,
      })
      instance?.open()
    }
    document.body.appendChild(script)
    return () => { document.body.removeChild(script) }
  }, [params.widgetId])

  return (
    <div style={{ fontFamily: 'sans-serif', padding: '2rem', color: '#444' }}>
      <p>This page has the widget installed exactly as the embed snippet installs it on a real site.</p>
      {isDraftPreview && <p style={{ fontSize: 13, color: '#888' }}>Previewing the draft (unpublished) configuration.</p>}
    </div>
  )
}
