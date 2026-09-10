import { captureRouterTransitionStart, init } from '@sentry/nextjs'

init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || process.env.NODE_ENV,
  tracesSampleRate: 0.1,
  replaysSessionSampleRate: 0,
  replaysOnErrorSampleRate: 1.0,
})

function loadReplay() {
  import('@/lib/monitoring/replay')
    .then(({ attachReplay }) => attachReplay())
    .catch(err => {
      if (process.env.NODE_ENV !== 'production') {
        console.warn('[sentry] session replay not attached:', err)
      }
    })
}

if (typeof window !== 'undefined' && process.env.NEXT_PUBLIC_SENTRY_DSN) {
  const idle = (window as Window & typeof globalThis).requestIdleCallback
  if (typeof idle === 'function') {
    idle(loadReplay, { timeout: 5000 })
  } else {
    setTimeout(loadReplay, 3000)
  }
}

export const onRouterTransitionStart = captureRouterTransitionStart
