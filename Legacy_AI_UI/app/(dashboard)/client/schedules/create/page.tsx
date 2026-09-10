'use client'

import { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  ArrowLeft, ArrowRight, Bot, CheckCircle2, Edit3, Loader2, Network, Rocket, Sparkles, Trash2, XCircle,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { SearchInput } from '@/components/ui/search-input'
import { Textarea } from '@/components/ui/textarea'
import { Select } from '@/components/ui/select'
import { FormField } from '@/components/ui/form-field'
import { PageHeader } from '@/components/ui/page-header'
import { Stepper } from '@/components/ui/stepper'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/hooks/use-toast'
import { useAuth } from '@/contexts/auth-context'
import { agentsApi, orchestrationsApi, schedulesApi } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { AgentPublic, Clarification, OrchestrationPublic, RecurrenceConfig, RecurrenceKind, ScheduleCreate } from '@/types'

const STEPS = ['Target', 'Task', 'Clarifications', 'Recurrence', 'Review']

const WEEKDAYS = [
  { value: 1, label: 'Mon' }, { value: 2, label: 'Tue' }, { value: 3, label: 'Wed' },
  { value: 4, label: 'Thu' }, { value: 5, label: 'Fri' }, { value: 6, label: 'Sat' }, { value: 7, label: 'Sun' },
]

const RECURRENCE_OPTIONS = [
  { value: 'once', label: 'Once, at a specific time' },
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
  { value: 'always', label: 'Every N minutes' },
  { value: 'custom', label: 'Custom cron expression' },
]

interface FormData {
  targetType: 'agent' | 'orchestration'
  agentId: string
  orchestrationId: string
  name: string
  description: string
  message: string
  clarifications: Clarification[]
  recurrenceKind: RecurrenceKind
  timeOfDay: string
  dayOfWeek: number[]
  dayOfMonth: number
  lastDayOfMonth: boolean
  intervalMinutes: number
  customCron: string
  runAt: string
  timezone: string
  maxConsecutiveFailures: number
}

const DEFAULT_TZ = typeof Intl !== 'undefined' ? Intl.DateTimeFormat().resolvedOptions().timeZone : 'UTC'

export default function CreateSchedulePage() {
  const router = useRouter()
  const { toast } = useToast()
  const { user } = useAuth()

  const [step, setStep] = useState(0)
  const [loading, setLoading] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const [agents, setAgents] = useState<AgentPublic[]>([])
  const [agentSearch, setAgentSearch] = useState('')

  const [orchestrations, setOrchestrations] = useState<OrchestrationPublic[]>([])
  const [orchestrationSearch, setOrchestrationSearch] = useState('')

  const [questionsLoading, setQuestionsLoading] = useState(false)
  const [questions, setQuestions] = useState<string[]>([])
  const [questionsFetchedFor, setQuestionsFetchedFor] = useState<string | null>(null)
  const [isCapable, setIsCapable] = useState(true)
  const [invalidReason, setInvalidReason] = useState<string | null>(null)

  const [formData, setFormData] = useState<FormData>({
    targetType: 'agent',
    agentId: '',
    orchestrationId: '',
    name: '',
    description: '',
    message: '',
    clarifications: [],
    recurrenceKind: 'daily',
    timeOfDay: '09:00',
    dayOfWeek: [1],
    dayOfMonth: 1,
    lastDayOfMonth: false,
    intervalMinutes: 15,
    customCron: '',
    runAt: '',
    timezone: DEFAULT_TZ,
    maxConsecutiveFailures: 3,
  })

  const update = (patch: Partial<FormData>) => setFormData(prev => ({ ...prev, ...patch }))

  useEffect(() => {
    if (!user?.organization_id) return
    agentsApi.listByOrg(user.organization_id, 1, 100, undefined, { isActive: true }).then(d => setAgents(d.items))
    orchestrationsApi.list().then(d => setOrchestrations(d.items)).catch(() => {})
  }, [user])

  const filteredAgents = useMemo(
    () => agents.filter(a => a.name.toLowerCase().includes(agentSearch.toLowerCase())),
    [agents, agentSearch]
  )

  const filteredOrchestrations = useMemo(
    () => orchestrations.filter(o => o.name.toLowerCase().includes(orchestrationSearch.toLowerCase())),
    [orchestrations, orchestrationSearch]
  )

  const selectedAgent = agents.find(a => a.id === formData.agentId)
  const selectedOrchestration = orchestrations.find(o => o.id === formData.orchestrationId)
  const answeredClarifications = formData.clarifications.filter(c => c.answer.trim())

  const validateStep = (): boolean => {
    const next: Record<string, string> = {}
    if (step === 0) {
      if (formData.targetType === 'agent' && !formData.agentId) {
        next.targetId = 'Select an agent to schedule.'
      }
      if (formData.targetType === 'orchestration' && !formData.orchestrationId) {
        next.targetId = 'Select an orchestration to schedule.'
      }
    }
    if (step === 1) {
      if (!formData.name.trim()) next.name = 'Give this schedule a name.'
      if (!formData.message.trim()) next.message = 'Describe the task to perform.'
    }
    if (step === 2 && !isCapable) {
      next.step2 = 'The selected Target does not have the capability to run this task.'
    }
    if (step === 3) {
      if (formData.recurrenceKind === 'weekly' && formData.dayOfWeek.length === 0) next.dayOfWeek = 'Pick at least one day.'
      if (formData.recurrenceKind === 'always' && formData.intervalMinutes < 5) next.intervalMinutes = 'Minimum interval is 5 minutes.'
      if (formData.recurrenceKind === 'custom' && !formData.customCron.trim()) next.customCron = 'Enter a cron expression.'
      if (formData.recurrenceKind === 'once' && !formData.runAt) next.runAt = 'Pick a date and time.'
    }
    setErrors(next)
    return Object.keys(next).length === 0
  }

  const fetchQuestions = async () => {
    if (questionsFetchedFor === formData.message) return
    setQuestionsLoading(true)
    try {
      const target = {
        target_type: formData.targetType,
        agent_id: formData.targetType === 'agent' ? formData.agentId : undefined,
        orchestration_id: formData.targetType === 'orchestration' ? formData.orchestrationId : undefined,
      }
      const res = await schedulesApi.previewQuestions(target, formData.message)
      const capable = res.is_capable ?? true
      setIsCapable(capable)
      setInvalidReason(res.invalid_reason || null)
      setQuestions(res.questions)
      update({ clarifications: res.questions.map(q => ({ question: q, answer: '' })) })
      setQuestionsFetchedFor(formData.message)
    } catch {
      toast.error('Could not generate clarifying questions — you can still continue.')
      setQuestions([])
      setIsCapable(true)
    } finally {
      setQuestionsLoading(false)
    }
  }

  const handleNext = async () => {
    if (!validateStep()) return
    if (step === 1) {
      setStep(2)
      await fetchQuestions()
      return
    }
    if (step === 2 && !isCapable) return
    setStep(s => Math.min(s + 1, STEPS.length - 1))
  }

  const buildRecurrence = (): RecurrenceConfig => {
    switch (formData.recurrenceKind) {
      case 'once':
        return { kind: 'once', run_at: new Date(formData.runAt).toISOString() }
      case 'weekly':
        return { kind: 'weekly', time_of_day: formData.timeOfDay, day_of_week: formData.dayOfWeek }
      case 'monthly':
        return { kind: 'monthly', time_of_day: formData.timeOfDay, day_of_month: formData.lastDayOfMonth ? -1 : formData.dayOfMonth }
      case 'always':
        return { kind: 'always', interval_minutes: formData.intervalMinutes }
      case 'custom':
        return { kind: 'custom', custom_cron: formData.customCron }
      case 'daily':
      default:
        return { kind: 'daily', time_of_day: formData.timeOfDay }
    }
  }

  const handleCreate = async () => {
    setLoading(true)
    try {
      const payload: ScheduleCreate = {
        name: formData.name,
        description: formData.description || undefined,
        target_type: formData.targetType,
        agent_id: formData.targetType === 'agent' ? formData.agentId : undefined,
        orchestration_id: formData.targetType === 'orchestration' ? formData.orchestrationId : undefined,
        message: formData.message,
        clarifications: answeredClarifications,
        recurrence: buildRecurrence(),
        timezone: formData.timezone,
        max_consecutive_failures: formData.maxConsecutiveFailures,
      }
      const created = await schedulesApi.create(payload)
      toast.success('Schedule created')
      router.push(`/client/schedules/${created.id}`)
    } catch (err: any) {
      toast.error(err?.message || 'Failed to create schedule')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col min-h-0 flex-1 p-6 max-w-3xl mx-auto w-full">
      {/* Top Header Actions */}
      <div className="flex items-center justify-between mb-2">
        <Button
          variant="ghost"
          size="xs"
          onClick={() => router.push('/client/schedules')}
          className="text-[12px] text-[var(--text-3)] hover:text-[var(--text-1)]"
        >
          <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Back to Schedules
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="text-red-600 hover:text-red-700 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10 border-red-200 dark:border-red-500/20 font-medium"
          onClick={() => {
            if (confirm('Discard this schedule draft?')) {
              router.push('/client/schedules')
            }
          }}
        >
          <Trash2 className="w-3.5 h-3.5 mr-1.5 text-red-600 dark:text-red-400" />
          Discard Schedule
        </Button>
      </div>

      <PageHeader
        eyebrow="New Schedule"
        title="Schedule an Agent or Orchestration"
        description="Run an agent or multi-agent orchestration automatically, once or on a recurring basis."
      />
      <div className="mb-8">
        <Stepper steps={STEPS} currentStep={step} />
      </div>

      {/* Step 0 — Target Selection */}
      {step === 0 && (
        <div className="space-y-4">
          <SearchInput
            placeholder="Search agents…"
            value={agentSearch}
            onChange={e => setAgentSearch(e.target.value)}
          />
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {filteredAgents.map(agent => (
              <button
                key={agent.id}
                onClick={() => update({ agentId: agent.id! })}
                className={cn(
                  'w-full flex items-center gap-3 p-3 rounded-xl border text-left transition-colors',
                  formData.agentId === agent.id
                    ? 'border-violet-400 bg-violet-50 dark:bg-violet-500/10'
                    : 'border-[var(--border)] hover:border-violet-200 dark:hover:border-violet-500/30'
                )}
              >
                <div className="w-9 h-9 rounded-lg bg-violet-50 dark:bg-violet-500/10 border border-violet-100 dark:border-violet-500/20 flex items-center justify-center text-violet-600 shrink-0">
                  <Bot className="w-4 h-4" />
                </div>
                <div className="min-w-0">
                  <p className="text-[14px] font-medium text-[var(--text-1)] truncate">{agent.name}</p>
                  {agent.description && <p className="text-[12px] text-[var(--text-3)] truncate">{agent.description}</p>}
                </div>
              </button>
            ))}
            {filteredAgents.length === 0 && (
              <p className="text-[13px] text-[var(--text-3)] text-center py-8">No agents found.</p>
            )}
          </div>
          {errors.agentId && <p className="text-[12px] text-red-500">{errors.agentId}</p>}
        </div>
      )}

      {/* Step 1 — Task */}
      {step === 1 && (
        <div className="space-y-4">
          <FormField label="Schedule name" error={errors.name}>
            <Input value={formData.name} onChange={e => update({ name: e.target.value })} placeholder="e.g. Daily ticket summary" />
          </FormField>
          <FormField label="Description (optional)">
            <Input value={formData.description} onChange={e => update({ description: e.target.value })} placeholder="What is this schedule for?" />
          </FormField>
          <FormField label="Task" error={errors.message}>
            <Textarea
              value={formData.message}
              onChange={e => update({ message: e.target.value })}
              placeholder="Describe exactly what should be executed each time this runs…"
              rows={5}
            />
          </FormField>
        </div>
      )}

      {/* Step 2 — Clarifications */}
      {step === 2 && (
        <div className="space-y-4">
          {questionsLoading ? (
            <div className="flex items-center gap-2 text-[13px] text-[var(--text-3)] py-8 justify-center">
              <Loader2 className="w-4 h-4 animate-spin" /> Checking target capabilities and task details…
            </div>
          ) : !isCapable ? (
            <div className="flex items-start gap-3 p-4 rounded-xl border border-red-200 dark:border-red-500/20 bg-red-50 dark:bg-red-500/10">
              <XCircle className="w-5 h-5 text-red-600 dark:text-red-400 shrink-0 mt-0.5" />
              <div>
                <p className="text-[14px] font-semibold text-red-700 dark:text-red-400">
                  Unsupported Capability
                </p>
                <p className="text-[13px] text-red-600 dark:text-red-300 mt-1">
                  {invalidReason || `The selected ${formData.targetType === 'orchestration' ? 'Orchestration' : 'Agent'} doesn't have the capability to run this specific task.`}
                </p>
              </div>
            </div>
          ) : questions.length === 0 ? (
            <div className="flex items-center gap-3 p-4 rounded-xl border border-green-200 dark:border-green-500/20 bg-green-50 dark:bg-green-500/10">
              <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400 shrink-0" />
              <p className="text-[13px] text-[var(--text-1)]">Your task is already clear — nothing to clarify.</p>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2 text-[12px] text-[var(--text-3)]">
                <Sparkles className="w-3.5 h-3.5" />
                Answer these so it doesn&apos;t have to guess when running unattended.
              </div>
              {formData.clarifications.map((c, i) => (
                <FormField key={i} label={c.question}>
                  <Input
                    value={c.answer}
                    onChange={e => {
                      const next = [...formData.clarifications]
                      next[i] = { ...next[i], answer: e.target.value }
                      update({ clarifications: next })
                    }}
                    placeholder="Your answer…"
                  />
                </FormField>
              ))}
            </>
          )}
        </div>
      )}

      {/* Step 3 — Recurrence */}
      {step === 3 && (
        <div className="space-y-4">
          <FormField label="How often should this run?">
            <Select
              value={formData.recurrenceKind}
              onValueChange={v => update({ recurrenceKind: v as RecurrenceKind })}
              options={RECURRENCE_OPTIONS}
            />
          </FormField>

          {formData.recurrenceKind === 'once' && (
            <FormField label="Run at" error={errors.runAt}>
              <Input type="datetime-local" value={formData.runAt} onChange={e => update({ runAt: e.target.value })} />
            </FormField>
          )}

          {(formData.recurrenceKind === 'daily' || formData.recurrenceKind === 'weekly' || formData.recurrenceKind === 'monthly') && (
            <FormField label="Time of day">
              <Input type="time" value={formData.timeOfDay} onChange={e => update({ timeOfDay: e.target.value })} />
            </FormField>
          )}

          {formData.recurrenceKind === 'weekly' && (
            <FormField label="Days of week" error={errors.dayOfWeek}>
              <div className="flex flex-wrap gap-2">
                {WEEKDAYS.map(d => (
                  <button
                    key={d.value}
                    onClick={() => update({
                      dayOfWeek: formData.dayOfWeek.includes(d.value)
                        ? formData.dayOfWeek.filter(x => x !== d.value)
                        : [...formData.dayOfWeek, d.value],
                    })}
                    className={cn(
                      'px-3 py-1.5 rounded-lg text-[12px] font-medium border transition-colors',
                      formData.dayOfWeek.includes(d.value)
                        ? 'bg-violet-600 text-white border-violet-600'
                        : 'bg-[var(--bg-surface)] text-[var(--text-2)] border-[var(--border-subtle)] hover:bg-[var(--bg-surface-hover)]'
                    )}
                  >
                    {d.label}
                  </button>
                ))}
              </div>
            </FormField>
          )}

          {formData.recurrenceKind === 'monthly' && (
            <div className="flex items-end gap-3">
              <div className="flex-1">
                <FormField label="Day of month">
                  <Input
                    type="number" min={1} max={31}
                    value={formData.dayOfMonth}
                    disabled={formData.lastDayOfMonth}
                    onChange={e => update({ dayOfMonth: Number(e.target.value) })}
                  />
                </FormField>
              </div>
              <label className="flex items-center gap-2 text-[13px] text-[var(--text-2)] cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.lastDayOfMonth}
                  onChange={e => update({ lastDayOfMonth: e.target.checked })}
                  className="rounded border-[var(--border-subtle)] text-violet-600 focus:ring-violet-500"
                />
                Run on the last day of each month
              </label>
            </div>
          )}

          {formData.recurrenceKind === 'always' && (
            <FormField label="Every N minutes (minimum 5)" error={errors.intervalMinutes}>
              <Input
                type="number"
                min={5}
                max={1440}
                value={formData.intervalMinutes}
                onChange={e => update({ intervalMinutes: parseInt(e.target.value, 10) || 15 })}
              />
            </FormField>
          )}

          {formData.recurrenceKind === 'custom' && (
            <FormField label="Cron expression" error={errors.customCron}>
              <Input
                value={formData.customCron}
                onChange={e => update({ customCron: e.target.value })}
                placeholder="0 9 * * 1-5"
              />
            </FormField>
          )}

          {formData.recurrenceKind !== 'once' && (
            <FormField label="Timezone" hint='Detected from your browser — times above and "Next run" always match this zone.'>
              <Input value={formData.timezone} disabled />
            </FormField>
          )}
        </div>
      )}

      {/* Step 4 — Review */}
      {step === 4 && (
        <div className="space-y-5">
          <div className="glass border border-violet-500/20 p-4 rounded-[var(--radius-lg)] flex items-center gap-3">
            <CheckCircle2 className="w-5 h-5 text-violet-600 dark:text-violet-400" />
            <span className="text-[14px] font-medium">Ready to schedule</span>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="glass p-5 rounded-[var(--radius-lg)]">
              <div className="flex justify-between mb-3">
                <h4 className="font-medium">Target</h4>
                <Button variant="ghost" size="xs" onClick={() => setStep(0)}>Edit</Button>
              </div>
              <div className="flex items-center gap-2">
                {formData.targetType === 'orchestration' ? (
                  <>
                    <Network className="w-4 h-4 text-indigo-500 shrink-0" />
                    <p className="text-[14px] font-medium">{selectedOrchestration?.name ?? 'Orchestration'}</p>
                    <Badge variant="neutral" className="text-[10px]">Orchestration</Badge>
                  </>
                ) : (
                  <>
                    <Bot className="w-4 h-4 text-violet-500 shrink-0" />
                    <p className="text-[14px] font-medium">{selectedAgent?.name ?? 'Agent'}</p>
                    <Badge variant="neutral" className="text-[10px]">Agent</Badge>
                  </>
                )}
              </div>
            </div>
            <div className="glass p-5 rounded-[var(--radius-lg)]">
              <div className="flex justify-between mb-3">
                <h4 className="font-medium">Task</h4>
                <Button variant="ghost" size="xs" onClick={() => setStep(1)}>Edit</Button>
              </div>
              <p className="text-[14px]">{formData.name}</p>
              <p className="text-[12px] text-[var(--text-3)] mt-1 line-clamp-3">{formData.message}</p>
            </div>
            <div className="glass p-5 rounded-[var(--radius-lg)]">
              <div className="flex justify-between mb-3">
                <h4 className="font-medium">Clarifications ({answeredClarifications.length})</h4>
                <Button variant="ghost" size="xs" onClick={() => setStep(2)}>Edit</Button>
              </div>
              {answeredClarifications.length === 0 ? (
                <span className="text-[13px] text-[var(--text-3)]">None</span>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {answeredClarifications.map((c, i) => (
                    <Badge key={i} variant="neutral">{c.question}</Badge>
                  ))}
                </div>
              )}
            </div>
            <div className="glass p-5 rounded-[var(--radius-lg)]">
              <div className="flex justify-between mb-3">
                <h4 className="font-medium">Recurrence</h4>
                <Button variant="ghost" size="xs" onClick={() => setStep(3)}>Edit</Button>
              </div>
              <p className="text-[14px] capitalize">{formData.recurrenceKind}</p>
              <p className="text-[12px] text-[var(--text-3)] mt-1">{formData.timezone}</p>
            </div>
          </div>
          <Button variant="primary" size="lg" className="w-full" onClick={handleCreate} disabled={loading}>
            {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Rocket className="w-4 h-4 mr-2" />}
            Create Schedule
          </Button>
        </div>
      )}

      {step < 4 && (
        <div className="flex items-center justify-between mt-8 pt-4 border-t border-[var(--border-subtle)]">
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => setStep(s => Math.max(s - 1, 0))} disabled={step === 0}>
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="text-red-600 hover:text-red-700 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-500/10"
              onClick={() => {
                if (confirm('Discard this schedule draft?')) {
                  router.push('/client/schedules')
                }
              }}
            >
              <Trash2 className="w-4 h-4 mr-1.5" />
              Discard Schedule
            </Button>
          </div>
          <Button variant="primary" size="sm" onClick={handleNext} disabled={loading || questionsLoading || (step === 2 && !isCapable)}>
            Next
            <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
        </div>
      )}
    </div>
  )
}
