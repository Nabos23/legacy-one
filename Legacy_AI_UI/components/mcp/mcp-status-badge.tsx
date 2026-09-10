import { Badge } from '@/components/ui/badge'

export function McpStatusBadge({ status }: { status: string }) {
  if (status === 'connected') return <Badge variant="success">Connected</Badge>
  if (status === 'error')     return <Badge variant="danger">Error</Badge>
  return <Badge variant="warning">Pending</Badge>
}

export function McpTransportBadge({ transport, authType }: { transport?: string; authType?: string }) {
  if (authType === 'oauth') return <Badge variant="primary">OAuth</Badge>
  switch (transport) {
    case 'stdio':           return <Badge variant="neutral">stdio</Badge>
    case 'streamable_http': return <Badge variant="info">HTTP</Badge>
    case 'sse':             return <Badge variant="info">SSE</Badge>
    case 'websocket':       return <Badge variant="warning">WebSocket</Badge>
    default:                return <Badge variant="neutral">{transport ?? '—'}</Badge>
  }
}
