'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Plus, CalendarClock, Trash2, Pause, Play, ChevronRight, AlertTriangle, Bot, Network } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScheduleStatusBadge } from '@/components/schedules/schedule-status-badge'
import { Pagination } from '@/components/ui/pagination'
import { schedulesApi } from '@/lib/api'
import { useToast } from '@/hooks/use-toast'
import { cn } from '@/lib/utils'
import type { SchedulePublic } from '@/types'

const POLL_INTERVAL_MS = 30_000

function recurrenceSummary(schedule: SchedulePublic): string {
  const { recurrence } = schedule
  switch (recurrence.kind) {
    case 'once': return 'Runs once'
    case 'daily': return `Daily at ${recurrence.time_of_day}`
    case 'weekly': return `Weekly at ${recurrence.time_of_day}`
    case 'monthly': return `Monthly at ${recurrence.time_of_day}`
    case 'always': return `Every ${recurrence.interval_minutes} min`
    case 'custom': return recurrence.custom_cron || 'Custom schedule'
    default: return 'Scheduled'
  }
}

export default function SchedulesPage() {
  const router = useRouter()
  const { toast } = useToast()
  const [schedules, setSchedules] = useState<SchedulePublic[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    const run = () =>
      schedulesApi.list({ page, pageSize })
        .then(data => { if (active) { setSchedules(data.items); setTotal(data.total) } })
        .catch(() => { if (active) toast.error('Failed to load schedules') })
        .finally(() => { if (active) setLoading(false) })
    run()
    const id = setInterval(run, POLL_INTERVAL_MS)
    return () => { active = false; clearInterval(id) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, pageSize])

  const handlePageSizeChange = (size: number) => {
    setPageSize(size)
    setPage(1)
  }

  const handlePauseResume = async (e: React.MouseEvent, schedule: SchedulePublic) => {
    e.stopPropagation()
    try {
      const updated = schedule.status === 'paused'
        ? await schedulesApi.resume(schedule.id)
        : await schedulesApi.pause(schedule.id)
      setSchedules(prev => prev.map(s => (s.id === updated.id ? updated : s)))
      toast.success(schedule.status === 'paused' ? 'Schedule resumed' : 'Schedule paused')
    } catch {
      toast.error('Failed to update schedule')
    }
  }

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    if (!confirm('Delete this schedule?')) return
    try {
      await schedulesApi.delete(id)
      setSchedules(prev => prev.filter(s => s.id !== id))
      setTotal(prev => Math.max(0, prev - 1))
      toast.success('Schedule deleted')
    } catch {
      toast.error('Failed to delete schedule')
    }
  }

  return (
    <div className="flex flex-col min-h-0 flex-1 p-6 max-w-5xl mx-auto w-full">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-[22px] font-bold text-[var(--text-1)] tracking-tight">Schedules</h1>
          <p className="text-[13px] text-[var(--text-3)] mt-1">Run an agent automatically, once or on a recurring basis</p>
        </div>
        <Button
          onClick={() => router.push('/client/schedules/create')}
          className="pl-3 pr-1.5 bg-violet-600 hover:bg-violet-700 text-white rounded-xl shadow-md shadow-violet-500/20"
        >
          <span className="mr-1 flex size-5 items-center justify-center rounded-full bg-white/20">
            <Plus className="w-3 h-3" />
          </span>
          New Schedule
        </Button>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-24 rounded-2xl bg-[var(--surface-2)] animate-pulse border border-[var(--border)]" />
          ))}
        </div>
      ) : schedules.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center py-24 text-[var(--text-2)]">
          <div className="w-16 h-16 rounded-2xl bg-violet-50 dark:bg-violet-500/10 border border-violet-100 dark:border-violet-500/20 flex items-center justify-center text-violet-500 mb-4">
            <CalendarClock className="w-8 h-8" />
          </div>
          <p className="text-[16px] font-bold text-[var(--text-1)] mb-2">No schedules yet</p>
          <p className="text-[13px] text-[var(--text-3)] mb-6 text-center max-w-xs">
            Schedule an agent to run automatically, without anyone needing to chat with it.
          </p>
          <Button
            onClick={() => router.push('/client/schedules/create')}
            className="pl-3 pr-1.5 bg-violet-600 hover:bg-violet-700 text-white rounded-xl"
          >
            <span className="mr-1 flex size-5 items-center justify-center rounded-full bg-white/20">
              <Plus className="w-3 h-3" />
            </span>
            Create your first schedule
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          {schedules.map(schedule => (
            <div
              key={schedule.id}
              onClick={() => router.push(`/client/schedules/${schedule.id}`)}
              className="group flex items-center gap-4 p-5 rounded-2xl border border-[var(--border)] bg-[var(--surface)] hover:border-violet-200 dark:hover:border-violet-500/30 hover:shadow-md transition-[border-color,box-shadow] cursor-pointer"
            >
              <div className={cn(
                "w-11 h-11 rounded-xl border flex items-center justify-center shrink-0",
                schedule.target_type === 'orchestration' || schedule.orchestration_id
                  ? "bg-indigo-50 dark:bg-indigo-500/10 border-indigo-100 dark:border-indigo-500/20 text-indigo-600"
                  : "bg-violet-50 dark:bg-violet-500/10 border-violet-100 dark:border-violet-500/20 text-violet-600"
              )}>
                {schedule.target_type === 'orchestration' || schedule.orchestration_id ? (
                  <Network className="w-5 h-5" />
                ) : (
                  <Bot className="w-5 h-5" />
                )}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <p className="text-[15px] font-semibold text-[var(--text-1)] truncate">{schedule.name}</p>
                  <Badge variant="neutral" className="text-[10px] shrink-0">
                    {schedule.target_type === 'orchestration' || schedule.orchestration_id ? 'Orchestration' : 'Agent'}
                  </Badge>
                  <ScheduleStatusBadge status={schedule.status} />
                  {schedule.needs_attention && (
                    <Badge variant="danger" className="text-[10px] shrink-0 gap-1">
                      <AlertTriangle className="w-3 h-3" /> Needs attention
                    </Badge>
                  )}
                </div>
                {schedule.description && (
                  <p className="text-[12px] text-[var(--text-3)] truncate">{schedule.description}</p>
                )}
                <p className="text-[11px] text-[var(--text-3)] mt-1">
                  {recurrenceSummary(schedule)}
                  {schedule.status === 'active' && ` · Next run ${new Date(schedule.next_run_at).toLocaleString()}`}
                  {schedule.last_run_status && ` · Last run: ${schedule.last_run_status}`}
                </p>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                {(schedule.status === 'active' || schedule.status === 'paused') && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={e => handlePauseResume(e, schedule)}
                    className="rounded-lg text-[12px] gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    {schedule.status === 'paused' ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
                    {schedule.status === 'paused' ? 'Resume' : 'Pause'}
                  </Button>
                )}
                <button
                  onClick={e => handleDelete(e, schedule.id)}
                  className="p-2 rounded-lg hover:bg-red-50 dark:hover:bg-red-500/10 text-[var(--text-3)] hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
                <ChevronRight className="w-4 h-4 text-[var(--text-3)] group-hover:text-violet-500 transition-colors" />
              </div>
            </div>
          ))}
        </div>
      )}

      {total > pageSize && (
        <Pagination
          page={page}
          pageSize={pageSize}
          total={total}
          onPageChange={setPage}
          onPageSizeChange={handlePageSizeChange}
          pageSizeOptions={[5, 10, 20, 50]}
        />
      )}
    </div>
  )
}
