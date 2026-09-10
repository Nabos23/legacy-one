import { getClient, replayIntegration } from '@sentry/nextjs'

export function attachReplay(): void {
  const client = getClient()
  if (!client) return
  client.addIntegration(
    replayIntegration({
      mutationLimit: 1500,
      mutationBreadcrumbLimit: 500,
      blockAllMedia: false,
      block: ['.sentry-block'],
      ignore: ['.sentry-ignore'],
    }),
  )
}
