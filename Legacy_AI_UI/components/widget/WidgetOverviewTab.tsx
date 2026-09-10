'use client'

import { useEffect, useMemo, useState } from 'react'
import { CalendarDays, MessageCircle, ThumbsUp, UserCheck } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Dialog } from '@/components/ui/dialog'
import { StatsCard } from '@/components/ui/stats-card'
import { widgetsApi } from '@/lib/api/widgets'
import { useToast } from '@/hooks/use-toast'
import type { ConversationEntry, SessionHistoryResponse, WidgetAnalytics, WidgetSessionListItem } from '@/types'

interface WidgetOverviewTabProps {
  widgetId: string
}

function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

/** Tiny inline-SVG bar trend of the last 14 days -- deliberately no chart
 * library, this is a glanceable sparkline, not an analytics suite. */
function SessionsTrend({ data }: { data: WidgetAnalytics['sessions_by_day'] }) {
  const width = 560
  const height = 96
  const gap = 6
  const max = Math.max(1, ...data.map(d => d.count))
  const barWidth = data.length > 0 ? (width - gap * (data.length - 1)) / data.length : width

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${width} ${height + 18}`} className="w-full h-auto" role="img" aria-label="Sessions per day, last 14 days">
        {data.map((d, i) => {
          const barHeight = Math.max(2, (d.count / max) * height)
          const x = i * (barWidth + gap)
          const label = new Date(`${d.date}T00:00:00`).toLocaleDateString(undefined, { day: 'numeric' })
          return (
            <g key={d.date}>
              <title>{`${d.date}: ${d.count} session${d.count === 1 ? '' : 's'}`}</title>
              <rect
                x={x}
                y={height - barHeight}
                width={barWidth}
                height={barHeight}
                rx={3}
                className={d.count > 0 ? 'fill-violet-500/80' : 'fill-[var(--border)]'}
              />
              <text x={x + barWidth / 2} y={height + 13} textAnchor="middle" className="fill-[var(--text-3)] text-[9px]">
                {label}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}

/** Flatten every agent's conversation entries into one timestamp-ordered
 * transcript -- widget sessions can span multiple agents in supervisor mode. */
function flattenTranscript(history: SessionHistoryResponse): ConversationEntry[] {
  const entries = history.agents.flatMap(a => a.conversations)
  return [...entries].sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
}

export function WidgetOverviewTab({ widgetId }: WidgetOverviewTabProps) {
  const { toast } = useToast()
  const [analytics, setAnalytics] = useState<WidgetAnalytics | null>(null)
  const [sessions, setSessions] = useState<WidgetSessionListItem[] | null>(null)
  const [loading, setLoading] = useState(true)

  const [transcriptTarget, setTranscriptTarget] = useState<WidgetSessionListItem | null>(null)
  const [transcript, setTranscript] = useState<SessionHistoryResponse | null>(null)
  const [transcriptLoading, setTranscriptLoading] = useState(false)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true)
      try {
        const [analyticsRes, sessionsRes] = await Promise.all([
          widgetsApi.getAnalytics(widgetId),
          widgetsApi.getSessions(widgetId, 1, 10),
        ])
        if (cancelled) return
        setAnalytics(analyticsRes)
        setSessions(sessionsRes.items)
      } catch {
        if (!cancelled) toast.error('Failed to load widget analytics')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [widgetId])

  const openTranscript = async (session: WidgetSessionListItem) => {
    setTranscriptTarget(session)
    setTranscript(null)
    setTranscriptLoading(true)
    try {
      const history = await widgetsApi.getSessionHistory(widgetId, session.visitor_session_id)
      setTranscript(history)
    } catch {
      toast.error('Failed to load this session’s transcript')
      setTranscriptTarget(null)
    } finally {
      setTranscriptLoading(false)
    }
  }

  const transcriptEntries = useMemo(
    () => (transcript ? flattenTranscript(transcript) : []),
    [transcript],
  )

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="h-28 rounded-[1.5rem] bg-[var(--surface-2)] animate-pulse border border-[var(--border)]" />
          ))}
        </div>
        <div className="h-40 rounded-[var(--radius-lg)] bg-[var(--surface-2)] animate-pulse border border-[var(--border)]" />
      </div>
    )
  }

  const feedbackTotal = (analytics?.feedback_up ?? 0) + (analytics?.feedback_down ?? 0)
  const feedbackRatio = feedbackTotal > 0 ? Math.round(((analytics?.feedback_up ?? 0) / feedbackTotal) * 100) : null

  // No traffic yet: teach the launch path instead of showing a wall of zeros.
  if ((analytics?.total_sessions ?? 0) === 0) {
    return (
      <div className="card-1 p-8 rounded-[var(--radius-lg)] max-w-2xl">
        <p className="text-[16px] font-semibold text-[var(--text-1)] mb-1">No conversations yet — let&apos;s launch this widget</p>
        <p className="text-[13px] text-[var(--text-3)] mb-5">
          Once visitors start chatting, this tab fills with session counts, lead capture, feedback, and full transcripts.
        </p>
        <ol className="space-y-3">
          {[
            { n: 1, title: 'Allow your website', body: 'Add your site’s origin (e.g. https://your-site.com) under Security → Allowed origins — the widget refuses to load anywhere else.' },
            { n: 2, title: 'Install the snippet', body: 'Copy the install code for your stack (HTML, React, WordPress, GTM, …) from the Embed Code tab and paste it into your site.' },
            { n: 3, title: 'Publish', body: 'Visitors only ever see the last published version — hit Publish in the banner above when the design is ready.' },
            { n: 4, title: 'Try it yourself', body: 'Use "Preview draft" in the banner to chat with the widget exactly as a visitor would, before your site goes live.' },
          ].map(step => (
            <li key={step.n} className="flex gap-3">
              <span className="w-6 h-6 shrink-0 rounded-full bg-violet-500/10 text-violet-600 dark:text-violet-400 flex items-center justify-center text-[12px] font-semibold">{step.n}</span>
              <div>
                <p className="text-[13.5px] font-medium text-[var(--text-1)]">{step.title}</p>
                <p className="text-[12.5px] text-[var(--text-3)]">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    )
  }

  return (
    <>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard label="Total sessions" value={analytics?.total_sessions ?? 0} icon={MessageCircle} color="primary" />
        <StatsCard label="Sessions today" value={analytics?.sessions_today ?? 0} icon={CalendarDays} color="info" />
        <StatsCard label="Leads captured" value={analytics?.leads_captured ?? 0} icon={UserCheck} color="success" />
        <StatsCard
          label="Feedback 👍 / 👎"
          value={feedbackTotal > 0 ? `${analytics?.feedback_up ?? 0} / ${analytics?.feedback_down ?? 0} (${feedbackRatio}% 👍)` : '—'}
          icon={ThumbsUp}
          color="warning"
        />
      </div>

      <div className="card-1 p-6 rounded-[var(--radius-lg)] mt-6">
        <p className="text-[14px] font-semibold text-[var(--text-1)] mb-1">Sessions — last 14 days</p>
        <p className="text-[12px] text-[var(--text-3)] mb-4">New visitor sessions per day.</p>
        {analytics && analytics.sessions_by_day.length > 0 ? (
          <SessionsTrend data={analytics.sessions_by_day} />
        ) : (
          <p className="text-[13px] text-[var(--text-3)]">No session data yet.</p>
        )}
      </div>

      <div className="card-1 p-6 rounded-[var(--radius-lg)] mt-6">
        <p className="text-[14px] font-semibold text-[var(--text-1)] mb-1">Recent sessions</p>
        <p className="text-[12px] text-[var(--text-3)] mb-4">The 10 most recent visitor sessions. Click one to read its transcript.</p>
        {!sessions || sessions.length === 0 ? (
          <p className="text-[13px] text-[var(--text-3)]">
            No sessions yet — they&apos;ll appear here once visitors start chatting with the embedded widget.
          </p>
        ) : (
          <div className="space-y-2">
            {sessions.map(s => (
              <button
                key={s.visitor_session_id}
                type="button"
                onClick={() => openTranscript(s)}
                className="w-full text-left flex items-center justify-between gap-3 px-4 py-3 rounded-[var(--radius-md)] border border-[var(--border)] hover:border-violet-300 transition-colors"
              >
                <div className="min-w-0">
                  <p className="text-[13px] font-medium truncate">{s.origin || 'Unknown origin'}</p>
                  <p className="text-[11.5px] text-[var(--text-3)]">Started {formatWhen(s.created_at)}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {s.has_lead && <Badge variant="success">Lead</Badge>}
                  <Badge variant={s.status === 'active' ? 'primary' : 'neutral'}>{s.status}</Badge>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      <Dialog
        open={transcriptTarget !== null}
        onOpenChange={open => { if (!open) { setTranscriptTarget(null); setTranscript(null) } }}
        title="Session transcript"
        size="lg"
      >
        <div className="space-y-1 mb-4">
          <p className="text-[12.5px] text-[var(--text-3)]">
            {transcriptTarget?.origin || 'Unknown origin'} · started {transcriptTarget ? formatWhen(transcriptTarget.created_at) : ''}
          </p>
          {transcriptTarget?.has_lead && transcriptTarget.lead_values && (
            <div className="flex flex-wrap gap-2 pt-1">
              {Object.entries(transcriptTarget.lead_values).map(([k, v]) => (
                <span key={k} className="inline-flex items-center gap-1 bg-violet-100 text-violet-700 dark:bg-violet-900/50 dark:text-violet-300 rounded-full px-2.5 py-1 text-[12px]">
                  <span className="font-medium">{k}:</span> {v}
                </span>
              ))}
            </div>
          )}
        </div>
        {transcriptLoading ? (
          <div className="space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-12 rounded-xl bg-[var(--surface-2)] animate-pulse" />
            ))}
          </div>
        ) : transcriptEntries.length === 0 ? (
          <p className="text-[13px] text-[var(--text-3)]">No messages in this session yet.</p>
        ) : (
          <div className="space-y-4 max-h-[50vh] overflow-y-auto pr-1">
            {transcriptEntries.map((entry, i) =>
              entry.type === 'summary' ? (
                <p key={i} className="text-[12px] text-[var(--text-3)] italic border-l-2 border-[var(--border)] pl-3">
                  Conversation summary: {entry.content}
                </p>
              ) : (
                <div key={i} className="space-y-2">
                  <div className="flex justify-end">
                    <div className="max-w-[80%] rounded-2xl rounded-br-md bg-violet-600 text-white px-3.5 py-2 text-[13px] whitespace-pre-wrap break-words">
                      {entry.human_message}
                    </div>
                  </div>
                  <div className="flex justify-start">
                    <div className="max-w-[80%] rounded-2xl rounded-bl-md bg-[var(--surface-2)] border border-[var(--border)] px-3.5 py-2 text-[13px] text-[var(--text-1)] whitespace-pre-wrap break-words">
                      {entry.agent_message}
                    </div>
                  </div>
                  <p className="text-[10.5px] text-[var(--text-3)] text-center">{formatWhen(entry.timestamp)}</p>
                </div>
              ),
            )}
          </div>
        )}
      </Dialog>
    </>
  )
}
