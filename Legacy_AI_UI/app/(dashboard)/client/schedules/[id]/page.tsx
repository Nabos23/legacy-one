'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { ArrowLeft, Bot, Edit3, Network, Pause, Pencil, Play, Trash2, AlertTriangle, ChevronDown, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Dialog } from '@/components/ui/dialog'
import { PageHeader } from '@/components/ui/page-header'
import { ScheduleStatusBadge, ScheduleRunStatusBadge } from '@/components/schedules/schedule-status-badge'
import { agentsApi, orchestrationsApi, schedulesApi } from '@/lib/api'
import { useToast } from '@/hooks/use-toast'
import { Markdown } from '@/components/ui/markdown'
import { AgentAvatar } from '@/components/dashboard/agent-avatar'
import type { AgentPublic, OrchestrationPublic, SchedulePublic, ScheduleRunPublic, ScheduleUpdate } from '@/types'

const POLL_INTERVAL_MS = 15_000

function recurrenceDescription(schedule: SchedulePublic): string {
  const { recurrence } = schedule
  switch (recurrence.kind) {
    case 'once': return `Once, at ${new Date(recurrence.run_at || '').toLocaleString()}`
    case 'daily': return `Daily at ${recurrence.time_of_day}`
    case 'weekly': return `Weekly at ${recurrence.time_of_day} (days: ${(recurrence.day_of_week || []).join(', ')})`
    case 'monthly': return `Monthly at ${recurrence.time_of_day}, day ${recurrence.day_of_month === -1 ? 'last' : recurrence.day_of_month}`
    case 'always': return `Every ${recurrence.interval_minutes} minutes`
    case 'custom': return recurrence.custom_cron || 'Custom'
    default: return '—'
  }
}

export default function ScheduleDetailPage() {
  const params = useParams<{ id: string }>()
  const router = useRouter()
  const { toast } = useToast()

  const [schedule, setSchedule] = useState<SchedulePublic | null>(null)
  const [agent, setAgent] = useState<AgentPublic | null>(null)
  const [orchestration, setOrchestration] = useState<OrchestrationPublic | null>(null)
  const [runs, setRuns] = useState<ScheduleRunPublic[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null)

  const [editModalOpen, setEditModalOpen] = useState(false)
  const [editForm, setEditForm] = useState({
    name: '',
    description: '',
    message: '',
    timeOfDay: '09:00',
    timezone: 'UTC',
  })

  useEffect(() => {
    if (!params?.id) return
    let active = true
    const run = () => {
      schedulesApi.get(params.id).then(data => { if (active) setSchedule(data) }).catch(() => {})
      schedulesApi.listRuns(params.id, { limit: 25 }).then(data => { if (active) setRuns(data) }).catch(() => {})
    }
    run()
    setLoading(false)
    const id = setInterval(run, POLL_INTERVAL_MS)
    return () => { active = false; clearInterval(id) }
  }, [params?.id])

  useEffect(() => {
    if (!schedule) return
    if (schedule.target_type === 'orchestration' || schedule.orchestration_id) {
      if (schedule.orchestration_id) {
        orchestrationsApi.get(schedule.orchestration_id).then(setOrchestration).catch(() => {})
      }
    } else if (schedule.agent_id) {
      agentsApi.get(schedule.agent_id).then(setAgent).catch(() => {})
    }
  }, [schedule])

  const openEditModal = () => {
    if (!schedule) return
    setEditForm({
      name: schedule.name || '',
      description: schedule.description || '',
      message: schedule.message || '',
      timeOfDay: schedule.recurrence?.time_of_day || '09:00',
      timezone: schedule.timezone || 'UTC',
    })
    setEditModalOpen(true)
  }

  const handleSaveSchedule = async () => {
    if (!schedule) return
    setBusy(true)
    try {
      const patchPayload: ScheduleUpdate = {
        name: editForm.name,
        description: editForm.description || undefined,
        message: editForm.message,
        timezone: editForm.timezone,
      }
      if (schedule.recurrence) {
        patchPayload.recurrence = {
          ...schedule.recurrence,
          time_of_day: editForm.timeOfDay,
        }
      }
      const updated = await schedulesApi.update(schedule.id, patchPayload)
      setSchedule(updated)
      toast.success('Schedule updated successfully')
      setEditModalOpen(false)
    } catch (err: any) {
      toast.error(err?.message || 'Failed to update schedule')
    } finally {
      setBusy(false)
    }
  }

  const handlePauseResume = async () => {
    if (!schedule) return
    setBusy(true)
    try {
      const updated = schedule.status === 'paused'
        ? await schedulesApi.resume(schedule.id)
        : await schedulesApi.pause(schedule.id)
      setSchedule(updated)
      toast.success(schedule.status === 'paused' ? 'Schedule resumed' : 'Schedule paused')
    } catch {
      toast.error('Failed to update schedule')
    } finally {
      setBusy(false)
    }
  }

  const handleDelete = async () => {
    if (!schedule) return
    if (!confirm('Discard and delete this schedule?')) return
    setBusy(true)
    try {
      await schedulesApi.delete(schedule.id)
      toast.success('Schedule discarded')
      router.push('/client/schedules')
    } catch {
      toast.error('Failed to discard schedule')
      setBusy(false)
    }
  }

  if (loading || !schedule) {
    return (
      <div className="flex flex-col min-h-0 flex-1 p-6 max-w-4xl mx-auto w-full">
        <div className="h-24 rounded-2xl bg-[var(--surface-2)] animate-pulse border border-[var(--border)]" />
      </div>
    )
  }

  const isOrch = schedule.target_type === 'orchestration' || Boolean(schedule.orchestration_id)

  return (
    <div className="flex flex-col min-h-0 flex-1 p-6 max-w-4xl mx-auto w-full">
      <Button variant="ghost" size="sm" onClick={() => router.push('/client/schedules')} className="w-fit mb-4 -ml-2">
        <ArrowLeft className="w-4 h-4 mr-2" /> Back to Schedules
      </Button>

      <PageHeader
        title={schedule.name}
        description={schedule.description || undefined}
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={openEditModal} disabled={busy}>
              <Pencil className="w-3.5 h-3.5 mr-1.5" /> Edit Schedule
            </Button>
            {(schedule.status === 'active' || schedule.status === 'paused') && (
              <Button variant="outline" size="sm" onClick={handlePauseResume} disabled={busy}>
                {schedule.status === 'paused' ? <Play className="w-3.5 h-3.5 mr-1.5" /> : <Pause className="w-3.5 h-3.5 mr-1.5" />}
                {schedule.status === 'paused' ? 'Resume' : 'Pause'}
              </Button>
            )}
            <Button variant="destructive" size="sm" onClick={handleDelete} disabled={busy}>
              <Trash2 className="w-3.5 h-3.5 mr-1.5" /> Discard Schedule
            </Button>
          </div>
        }
      />

      <div className="flex items-center gap-2 mb-6">
        <ScheduleStatusBadge status={schedule.status} />
        {schedule.needs_attention && (
          <Badge variant="danger" className="gap-1">
            <AlertTriangle className="w-3 h-3" /> Needs attention — check connectors used
          </Badge>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-8">
        <div className="glass p-5 rounded-[var(--radius-lg)]">
          <div className="flex items-center justify-between mb-3">
            <h4 className="font-medium">Target</h4>
            {isOrch && schedule.orchestration_id && (
              <Button
                variant="ghost"
                size="xs"
                onClick={() => router.push(`/client/orchestrations/${schedule.orchestration_id}`)}
                className="text-indigo-600 dark:text-indigo-400 text-[11px] h-6 px-1.5"
              >
                <Edit3 className="w-3 h-3 mr-1" /> Edit
              </Button>
            )}
          </div>
          <div className="flex items-center gap-2 text-[14px]">
            {isOrch ? (
              <>
                <Network className="w-4 h-4 text-indigo-500" />
                <span className="font-medium">{orchestration?.name ?? schedule.orchestration_id}</span>
                <Badge variant="neutral" className="text-[10px]">Orchestration</Badge>
              </>
            ) : (
              <>
                <Bot className="w-4 h-4 text-violet-500" />
                <span className="font-medium">{agent?.name ?? schedule.agent_id}</span>
                <Badge variant="neutral" className="text-[10px]">Agent</Badge>
              </>
            )}
          </div>
        </div>
        <div className="glass p-5 rounded-[var(--radius-lg)]">
          <h4 className="font-medium mb-3">Recurrence</h4>
          <p className="text-[14px]">{recurrenceDescription(schedule)}</p>
          <p className="text-[12px] text-[var(--text-3)] mt-1">{schedule.timezone}</p>
        </div>
        <div className="glass p-5 rounded-[var(--radius-lg)] lg:col-span-2">
          <h4 className="font-medium mb-3">Task</h4>
          <p className="text-[13px] text-[var(--text-2)] whitespace-pre-wrap">{schedule.message}</p>
        </div>
        {schedule.clarifications.length > 0 && (
          <div className="glass p-5 rounded-[var(--radius-lg)] lg:col-span-2">
            <h4 className="font-medium mb-3">Clarifications</h4>
            <div className="space-y-2">
              {schedule.clarifications.map((c, i) => (
                <div key={i} className="text-[13px]">
                  <span className="text-[var(--text-3)]">{c.question}</span>{' — '}
                  <span className="text-[var(--text-1)] font-medium">{c.answer}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        <div className="glass p-5 rounded-[var(--radius-lg)]">
          <h4 className="font-medium mb-3">Status</h4>
          <p className="text-[13px] text-[var(--text-2)]">Next run: {schedule.status === 'active' ? new Date(schedule.next_run_at).toLocaleString() : '—'}</p>
          <p className="text-[13px] text-[var(--text-2)] mt-1">Last run: {schedule.last_run_at ? new Date(schedule.last_run_at).toLocaleString() : 'Never'} {schedule.last_run_status && `(${schedule.last_run_status})`}</p>
          {schedule.last_run_error && <p className="text-[12px] text-red-500 mt-1">{schedule.last_run_error}</p>}
        </div>
        <div className="glass p-5 rounded-[var(--radius-lg)]">
          <h4 className="font-medium mb-3">Reliability</h4>
          <p className="text-[13px] text-[var(--text-2)]">Total runs: {schedule.run_count}</p>
          <p className="text-[13px] text-[var(--text-2)] mt-1">Consecutive failures: {schedule.consecutive_failure_count} / {schedule.max_consecutive_failures}</p>
        </div>
      </div>

      <h3 className="text-[16px] font-bold text-[var(--text-1)] mb-3">Run history</h3>
      {runs.length === 0 ? (
        <p className="text-[13px] text-[var(--text-3)] py-8 text-center">No runs yet.</p>
      ) : (
        <div className="space-y-2">
          {runs.map(run => {
            const expanded = expandedRunId === run.run_id
            return (
              <div key={run.run_id} className="rounded-xl border border-[var(--border)] bg-[var(--surface)] overflow-hidden">
                <button
                  type="button"
                  onClick={() => setExpandedRunId(expanded ? null : run.run_id)}
                  className="w-full text-left p-4 cursor-pointer hover:bg-[var(--surface-2)] transition-colors"
                >
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      {expanded ? <ChevronDown className="w-3.5 h-3.5 text-[var(--text-3)]" /> : <ChevronRight className="w-3.5 h-3.5 text-[var(--text-3)]" />}
                      <ScheduleRunStatusBadge status={run.status} />
                      {run.auth_errors.length > 0 && (
                        <Badge variant="warning" className="gap-1">
                          <AlertTriangle className="w-3 h-3" /> Auth error
                        </Badge>
                      )}
                      <span className="text-[12px] text-[var(--text-3)]">{new Date(run.started_at).toLocaleString()}</span>
                    </div>
                    {run.duration_ms != null && (
                      <span className="text-[11px] text-[var(--text-3)]">{(run.duration_ms / 1000).toFixed(1)}s</span>
                    )}
                  </div>
                  {run.reply && <p className="text-[13px] text-[var(--text-2)] line-clamp-2">{run.reply}</p>}
                  {run.error_message && <p className="text-[12px] text-red-500">{run.error_message}</p>}
                </button>
                {expanded && (
                  <div className="px-4 pb-4 space-y-4 border-t border-[var(--border)] pt-4">
                    <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--surface-2)]/40 px-3 py-2 text-[11px] text-[var(--text-3)]">
                      Read-only transcript of execution — this run has finished.
                    </div>

                    <div className="space-y-4">
                      {/* user turn */}
                      <div className="flex gap-3 flex-row-reverse">
                        <div className="max-w-[85%] flex flex-col gap-1 items-end">
                          <div className="px-4 py-3 text-[14px] leading-relaxed bg-violet-600 text-white rounded-2xl rounded-br-sm">
                            <div className="whitespace-pre-wrap">{run.message_sent}</div>
                          </div>
                          <p className="text-[11px] text-[var(--text-3)] px-1">Sent to {isOrch ? 'orchestration' : 'agent'}</p>
                        </div>
                      </div>

                      {/* assistant turn */}
                      <div className="flex gap-3">
                        {isOrch ? (
                          <div className="w-7 h-7 rounded-lg bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-100 dark:border-indigo-500/20 flex items-center justify-center text-indigo-600 shrink-0 mt-0.5">
                            <Network className="w-3.5 h-3.5" />
                          </div>
                        ) : agent ? (
                          <AgentAvatar name={agent.name} avatarType={agent.avatar_type} avatarValue={agent.avatar_value}
                            avatarUrl={agent.avatar_url} size="xs" shape="rounded" className="w-7 h-7 mt-0.5" />
                        ) : (
                          <div className="w-7 h-7 rounded-lg bg-[var(--surface-3)] flex items-center justify-center shrink-0 mt-0.5">
                            <Bot className="w-3.5 h-3.5" />
                          </div>
                        )}
                        <div className="max-w-[85%] flex flex-col gap-1 items-start">
                          {run.reply ? (
                            <div className="px-4 py-3 text-[14px] leading-relaxed bg-[var(--surface-2)] border border-[var(--border)] rounded-2xl rounded-bl-sm text-[var(--text-1)]">
                              <Markdown content={run.reply} />
                            </div>
                          ) : run.status === 'running' ? (
                            <div className="px-4 py-3 text-[13px] leading-relaxed bg-[var(--surface-2)] border border-[var(--border)] rounded-2xl rounded-bl-sm text-[var(--text-3)] italic">
                              Still running…
                            </div>
                          ) : (
                            <div className="px-4 py-3 text-[13px] leading-relaxed bg-[var(--surface-2)] border border-[var(--border)] rounded-2xl rounded-bl-sm text-[var(--text-3)] italic">
                              No reply — run failed before responding.
                            </div>
                          )}
                          <p className="text-[11px] text-[var(--text-3)] px-1">
                            {isOrch ? (orchestration?.name ?? 'Orchestration') : (agent?.name ?? 'Agent')}
                          </p>
                        </div>
                      </div>
                    </div>

                    {run.error_type && (
                      <div>
                        <h5 className="text-[11px] font-medium uppercase text-[var(--text-3)] mb-1">Error type</h5>
                        <p className="text-[13px] text-red-500">{run.error_type}</p>
                      </div>
                    )}
                    {run.auth_errors.length > 0 && (
                      <div>
                        <h5 className="text-[11px] font-medium uppercase text-[var(--text-3)] mb-1">Auth errors</h5>
                        <ul className="text-[13px] text-red-500 list-disc pl-4">
                          {run.auth_errors.map((err, i) => (
                            <li key={i}>{Object.entries(err).map(([k, v]) => `${k}: ${v ?? '—'}`).join(', ')}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    <div className="flex flex-wrap gap-x-6 gap-y-1 text-[12px] text-[var(--text-3)]">
                      <span>Attempt: {run.attempt}</span>
                      <span>Started: {new Date(run.started_at).toLocaleString()}</span>
                      <span>Completed: {run.completed_at ? new Date(run.completed_at).toLocaleString() : '—'}</span>
                      <span title={run.thread_id}>Thread: {run.thread_id}</span>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Edit Schedule Modal */}
      <Dialog
        open={editModalOpen}
        onOpenChange={setEditModalOpen}
        title="Edit Schedule"
        size="lg"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setEditModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" size="sm" onClick={handleSaveSchedule} disabled={busy}>
              Save Changes
            </Button>
          </div>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="text-[13px] font-medium text-[var(--text-2)] mb-1.5 block">Schedule Name</label>
            <Input
              value={editForm.name}
              onChange={e => setEditForm(prev => ({ ...prev, name: e.target.value }))}
              placeholder="Schedule name…"
            />
          </div>
          <div>
            <label className="text-[13px] font-medium text-[var(--text-2)] mb-1.5 block">Description (Optional)</label>
            <Input
              value={editForm.description}
              onChange={e => setEditForm(prev => ({ ...prev, description: e.target.value }))}
              placeholder="Description…"
            />
          </div>
          <div>
            <label className="text-[13px] font-medium text-[var(--text-2)] mb-1.5 block">Task Prompt / Instruction</label>
            <Textarea
              value={editForm.message}
              onChange={e => setEditForm(prev => ({ ...prev, message: e.target.value }))}
              placeholder="Describe what should be executed…"
              rows={4}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-[13px] font-medium text-[var(--text-2)] mb-1.5 block">Time of Day</label>
              <Input
                type="time"
                value={editForm.timeOfDay}
                onChange={e => setEditForm(prev => ({ ...prev, timeOfDay: e.target.value }))}
              />
            </div>
            <div>
              <label className="text-[13px] font-medium text-[var(--text-2)] mb-1.5 block">Timezone</label>
              <Input
                value={editForm.timezone}
                onChange={e => setEditForm(prev => ({ ...prev, timezone: e.target.value }))}
              />
            </div>
          </div>
        </div>
      </Dialog>
    </div>
  )
}
