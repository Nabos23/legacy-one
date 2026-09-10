import { Badge } from '@/components/ui/badge'
import type { SchedulePublic, ScheduleRunPublic } from '@/types'

export function ScheduleStatusBadge({ status }: { status: SchedulePublic['status'] }) {
  if (status === 'active') return <Badge variant="success">Active</Badge>
  if (status === 'paused') return <Badge variant="warning">Paused</Badge>
  if (status === 'running') return <Badge variant="info">Running</Badge>
  if (status === 'completed') return <Badge variant="neutral">Completed</Badge>
  return <Badge variant="danger">Terminated</Badge>
}

export function ScheduleRunStatusBadge({ status }: { status: ScheduleRunPublic['status'] }) {
  if (status === 'success') return <Badge variant="success">Success</Badge>
  if (status === 'failed') return <Badge variant="danger">Failed</Badge>
  return <Badge variant="info">Running</Badge>
}
