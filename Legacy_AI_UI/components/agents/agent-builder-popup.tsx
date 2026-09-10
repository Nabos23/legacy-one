'use client'

import { createPortal } from 'react-dom'
import { motion } from 'motion/react'
import { AlertTriangle, Bot, Building2, Check, Database, Loader2, PlugZap, SkipForward, Sparkles, User as UserIcon, Users, Wrench, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { IconTile } from '@/components/ui/icon-tile'
import { Loader } from '@/components/ui/loader'
import { cn } from '@/lib/utils'
import type { AgentBlueprint, BuilderQuestion } from '@/lib/api'
import type { DbConnectionPublic, TeamPublic } from '@/types'

const EASE = [0.16, 1, 0.3, 1] as const

export type OwnerScope = 'user' | 'team' | 'organization'
export type BuilderStep = 'question' | 'missing-tools' | 'integrations' | 'scope' | 'team' | 'create' | 'creating'

export const SCOPE_OPTIONS: { value: OwnerScope; label: string; icon: typeof UserIcon }[] = [
  { value: 'user', label: 'Personal', icon: UserIcon },
  { value: 'team', label: 'Team', icon: Users },
  { value: 'organization', label: 'Organization', icon: Building2 },
]

const EYEBROW: Record<BuilderStep, string> = {
  question: 'One more detail',
  'missing-tools': "We don't have everything yet",
  integrations: 'Connect services (optional)',
  scope: 'Who can use this?',
  team: 'Choose a team',
  create: 'Ready to build',
  creating: 'Building your agent',
}

interface AgentBuilderPopupProps {
  blueprint: AgentBlueprint
  step: BuilderStep
  busy: boolean
  onClose: () => void

  question?: BuilderQuestion
  selectedValue?: string
  onChooseOption: (questionId: string, value: string, label: string) => void

  selectedSubstitutes: string[]
  onToggleSubstitute: (value: string) => void
  onContinueAfterMissingTools: () => void
  onDeclineCreate: () => void

  connected: Record<string, boolean>
  onConnectConnector: (id: string) => void
  skippedConnectorIds: string[]
  onSkipConnector: (id: string) => void
  dbConnections: DbConnectionPublic[] | null
  dbConnectionsLoading: boolean
  selectedDbConnId: string | null
  onSelectDbConnection: (id: string, label: string) => void
  onCreateDbConnection: () => void
  dbSkipped: boolean
  onSkipDb: () => void
  onUndoSkipDb: () => void

  scopeSelectedValue: OwnerScope | null
  onChooseScope: (value: OwnerScope, label: string) => void

  teams: TeamPublic[] | null
  teamsLoading: boolean
  teamId: string | null
  onChooseTeam: (id: string, name: string) => void

  onCreate: () => void
  creatingStage: string
}

export function AgentBuilderPopup({
  blueprint, step, busy, onClose,
  question, selectedValue, onChooseOption,
  selectedSubstitutes, onToggleSubstitute, onContinueAfterMissingTools, onDeclineCreate,
  connected, onConnectConnector, skippedConnectorIds, onSkipConnector, dbConnections, dbConnectionsLoading, selectedDbConnId, onSelectDbConnection, onCreateDbConnection, dbSkipped, onSkipDb, onUndoSkipDb,
  scopeSelectedValue, onChooseScope,
  teams, teamsLoading, teamId, onChooseTeam,
  onCreate, creatingStage,
}: AgentBuilderPopupProps) {
  const answering = busy && step === 'question' && !!selectedValue
  const showDescription = step === 'question' || step === 'missing-tools' || step === 'integrations'
  const badges = [
    ...blueprint.connector_names.map(name => ({ label: name, icon: PlugZap })),
    ...blueprint.mcp_names.map(name => ({ label: name, icon: Wrench })),
    ...(blueprint.requires_db_connection ? [{ label: 'Database', icon: Database }] : []),
  ]

  return createPortal(
    <>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.25, ease: EASE }}
        onClick={onClose}
        className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
      />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <motion.div
          role="dialog"
          aria-modal="true"
          aria-label={`${blueprint.name} — ${EYEBROW[step]}`}
          initial={{ opacity: 0, scale: 0.85, y: 28 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.9, y: 16 }}
          transition={{ type: 'spring', stiffness: 300, damping: 24 }}
          className="glass-card relative w-full max-w-md overflow-hidden rounded-3xl border border-violet-500/20 bg-card/95 p-8 text-center shadow-[0_24px_64px_-16px_rgba(124,58,237,0.45)] backdrop-blur-2xl backdrop-saturate-150"
        >
          <div className="pointer-events-none absolute -top-16 -left-16 -z-10 size-56 rounded-full bg-violet-500/20 blur-[80px]" aria-hidden />
          <div className="pointer-events-none absolute -bottom-16 -right-16 -z-10 size-56 rounded-full bg-indigo-500/20 blur-[80px]" aria-hidden />

          <button
            onClick={onClose}
            aria-label="Close"
            className="absolute right-4 top-4 flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <X className="size-4" />
          </button>

          <motion.div
            key={`icon-${step}`}
            initial={{ scale: 0.7, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: 'spring', stiffness: 260, damping: 18 }}
            className="relative mx-auto mb-5 flex size-16 items-center justify-center"
          >
            <div className="absolute inset-0 -z-10 animate-glowPulse rounded-2xl" aria-hidden />
            <div className="flex size-16 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-600 to-indigo-600 text-white shadow-[0_12px_28px_-8px_rgba(124,58,237,0.6)]">
              <Bot className="size-8" />
            </div>
            {step !== 'creating' && (
              <motion.div
                animate={{ y: [0, -4, 0], rotate: [0, 8, 0] }}
                transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut' }}
                className="absolute -right-2 -top-2 flex size-6 items-center justify-center rounded-full bg-amber-400 text-amber-950 shadow-[0_4px_12px_-2px_rgba(251,191,36,0.7)]"
              >
                <Sparkles className="size-3.5" />
              </motion.div>
            )}
          </motion.div>

          <motion.p
            key={`eyebrow-${step}`}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, ease: EASE }}
            className="text-xs font-semibold uppercase tracking-wide text-violet-500"
          >
            {EYEBROW[step]}
          </motion.p>
          <h2 className="mt-1 text-2xl font-bold text-foreground">{blueprint.name}</h2>
          {showDescription && <p className="mt-2 text-sm text-[var(--text-3)]">{blueprint.description}</p>}

          <motion.div
            key={`body-${step}`}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.3, ease: EASE }}
            className="mt-6"
          >
            {step === 'question' && question && (
              <>
                <p className="text-sm font-medium text-foreground">{question.text}</p>
                <div className="mt-3 flex flex-wrap justify-center gap-2">
                  {question.options.map((option, i) => {
                    const isSelected = selectedValue === option.value
                    const disabled = busy || !!selectedValue
                    return (
                      <motion.button
                        key={option.value}
                        type="button"
                        initial={{ opacity: 0, y: 6, scale: 0.9 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        transition={{ delay: i * 0.05, duration: 0.25, ease: EASE }}
                        whileHover={disabled ? undefined : { scale: 1.04 }}
                        whileTap={disabled ? undefined : { scale: 0.96 }}
                        onClick={() => onChooseOption(question.id, option.value, option.label)}
                        disabled={disabled}
                        className={cn(
                          'flex items-center gap-1.5 rounded-full border px-4 py-2 text-sm font-medium transition-colors duration-150 disabled:cursor-not-allowed',
                          isSelected
                            ? 'border-emerald-500 bg-emerald-500 text-white'
                            : 'border-violet-500/25 bg-violet-500/[0.06] text-[var(--text-1)] hover:border-violet-500/50 hover:bg-violet-500/10 disabled:opacity-40'
                        )}
                      >
                        {isSelected && <Check className="size-3.5" />}
                        {option.label}
                      </motion.button>
                    )
                  })}
                </div>
                {answering && (
                  <div className="mt-3 flex items-center justify-center gap-1.5 text-xs text-[var(--text-3)]">
                    <Loader2 className="size-3.5 animate-spin" />Updating the blueprint…
                  </div>
                )}
              </>
            )}

            {step === 'missing-tools' && (
              <div className="space-y-4 text-left">
                <div className="rounded-xl border border-amber-500/25 bg-amber-500/5 p-3">
                  <p className="flex items-center gap-1.5 text-xs font-semibold text-amber-500">
                    <AlertTriangle className="size-3.5" />Not in our tools yet
                  </p>
                  <p className="mt-1 text-sm text-[var(--text-1)]">{blueprint.unmatched_capabilities.join(', ')}</p>
                </div>
                {blueprint.available_options.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-[var(--text-3)]">Pick a replacement (optional) — here&apos;s what we have:</p>
                    <div className="custom-scrollbar mt-2 flex max-h-48 flex-wrap justify-center gap-2 overflow-y-auto">
                      {blueprint.available_options.map(option => {
                        const isSelected = selectedSubstitutes.includes(option.value)
                        return (
                          <button
                            key={option.value}
                            type="button"
                            title={option.description || undefined}
                            onClick={() => onToggleSubstitute(option.value)}
                            disabled={busy}
                            className={cn(
                              'flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-40',
                              isSelected
                                ? 'border-emerald-500 bg-emerald-500 text-white'
                                : 'border-violet-500/25 bg-violet-500/[0.06] text-[var(--text-1)] hover:border-violet-500/50 hover:bg-violet-500/10'
                            )}
                          >
                            {isSelected && <Check className="size-3" />}
                            {option.label}
                          </button>
                        )
                      })}
                    </div>
                  </div>
                )}
                <div className="flex gap-2 pt-2">
                  <Button variant="outline" className="flex-1" onClick={onDeclineCreate} disabled={busy}>Don&apos;t create</Button>
                  <Button variant="primary" className="flex-1" onClick={onContinueAfterMissingTools} disabled={busy}>Create anyway</Button>
                </div>
              </div>
            )}

            {step === 'integrations' && (
              <div className="space-y-2 text-left">
                {blueprint.connector_ids.map((id, index) => {
                  const name = blueprint.connector_names[index] || 'service'
                  const isConnected = !!connected[id]
                  const isSkipped = !isConnected && skippedConnectorIds.includes(id)
                  return (
                    <div
                      key={id}
                      className={cn(
                        'flex items-center justify-between gap-3 rounded-xl border p-3',
                        isConnected ? 'border-emerald-500/25 bg-emerald-500/5' : isSkipped ? 'border-[var(--border-2)] bg-[var(--surface-2)]' : 'border-violet-500/25 bg-violet-500/[0.04]'
                      )}
                    >
                      <div className="flex items-center gap-3">
                        <IconTile icon={isConnected ? Check : isSkipped ? SkipForward : PlugZap} size="sm" />
                        <div>
                          <p className="text-sm font-medium leading-tight">{name}</p>
                          <p className="text-xs text-[var(--text-3)]">{isConnected ? 'Connected' : isSkipped ? 'Skipped — connect later from Connectors' : 'Optional — connect now or skip for later'}</p>
                        </div>
                      </div>
                      {!isConnected && (
                        isSkipped ? (
                          <Button size="sm" variant="outline" onClick={() => onConnectConnector(id)} disabled={busy}>Connect</Button>
                        ) : (
                          <div className="flex shrink-0 gap-2">
                            <Button size="sm" variant="ghost" onClick={() => onSkipConnector(id)} disabled={busy}>Skip</Button>
                            <Button size="sm" variant="primary" onClick={() => onConnectConnector(id)} disabled={busy}>Connect</Button>
                          </div>
                        )
                      )}
                    </div>
                  )
                })}
                {blueprint.requires_db_connection && (() => {
                  const selected = dbConnections?.find(c => c.id === selectedDbConnId)
                  if (selected) {
                    return (
                      <div className="flex items-center justify-between gap-3 rounded-xl border border-emerald-500/25 bg-emerald-500/5 p-3">
                        <div className="flex items-center gap-3">
                          <IconTile icon={Check} size="sm" />
                          <div>
                            <p className="text-sm font-medium leading-tight">Database connection</p>
                            <p className="text-xs text-[var(--text-3)]">{selected.name?.trim() || 'Connected'}</p>
                          </div>
                        </div>
                      </div>
                    )
                  }
                  if (dbSkipped) {
                    return (
                      <div className="flex items-center justify-between gap-3 rounded-xl border border-[var(--border-2)] bg-[var(--surface-2)] p-3">
                        <div className="flex items-center gap-3">
                          <IconTile icon={SkipForward} size="sm" />
                          <div>
                            <p className="text-sm font-medium leading-tight">Database connection</p>
                            <p className="text-xs text-[var(--text-3)]">Skipped — connect later from Database Connections</p>
                          </div>
                        </div>
                        <Button size="sm" variant="outline" onClick={onUndoSkipDb} disabled={busy}>Connect</Button>
                      </div>
                    )
                  }
                  return (
                    <div className="space-y-2">
                      <p className="text-xs font-medium text-[var(--text-3)]">Database connection — optional, lets this agent query your data</p>
                      {dbConnectionsLoading ? (
                        <div className="flex items-center justify-center gap-2 rounded-xl border border-violet-500/25 bg-violet-500/[0.04] py-3 text-sm text-[var(--text-3)]">
                          <Loader2 className="size-3.5 animate-spin" />Loading…
                        </div>
                      ) : (
                        <>
                          {(dbConnections ?? []).map(conn => (
                            <div key={conn.id} className="flex items-center justify-between gap-3 rounded-xl border border-violet-500/25 bg-violet-500/[0.04] p-3">
                              <div className="flex min-w-0 items-center gap-3">
                                <IconTile icon={Database} size="sm" />
                                <div className="min-w-0">
                                  <p className="truncate text-sm font-medium leading-tight">{conn.name?.trim() || 'Database connection'}</p>
                                  <p className="truncate text-xs text-[var(--text-3)]">{conn.connection_type || 'Existing connection'}</p>
                                </div>
                              </div>
                              <Button size="sm" variant="primary" onClick={() => onSelectDbConnection(conn.id!, conn.name?.trim() || 'Database connection')} disabled={busy}>Use this</Button>
                            </div>
                          ))}
                          <Button size="sm" variant="outline" className="w-full" onClick={onCreateDbConnection} disabled={busy}>
                            {(dbConnections?.length ?? 0) > 0 ? 'Connect a different database' : 'Connect a database'}
                          </Button>
                          <Button size="sm" variant="ghost" className="w-full" onClick={onSkipDb} disabled={busy}>
                            <SkipForward className="mr-1.5 size-3.5" />Skip for now
                          </Button>
                        </>
                      )}
                    </div>
                  )
                })()}
              </div>
            )}

            {step === 'scope' && (
              <>
                <p className="text-sm font-medium text-foreground">Who should be able to use this agent?</p>
                <div className="mt-3 flex flex-wrap justify-center gap-2">
                  {SCOPE_OPTIONS.map((opt, i) => {
                    const isSelected = scopeSelectedValue === opt.value
                    const disabled = busy || scopeSelectedValue !== null
                    return (
                      <motion.button
                        key={opt.value}
                        type="button"
                        initial={{ opacity: 0, y: 6, scale: 0.9 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        transition={{ delay: i * 0.05, duration: 0.25, ease: EASE }}
                        whileHover={disabled ? undefined : { scale: 1.04 }}
                        whileTap={disabled ? undefined : { scale: 0.96 }}
                        onClick={() => onChooseScope(opt.value, opt.label)}
                        disabled={disabled}
                        className={cn(
                          'flex items-center gap-1.5 rounded-full border px-4 py-2 text-sm font-medium transition-colors duration-150 disabled:cursor-not-allowed',
                          isSelected
                            ? 'border-emerald-500 bg-emerald-500 text-white'
                            : 'border-violet-500/25 bg-violet-500/[0.06] text-[var(--text-1)] hover:border-violet-500/50 hover:bg-violet-500/10 disabled:opacity-40'
                        )}
                      >
                        {isSelected ? <Check className="size-3.5" /> : <opt.icon className="size-3.5" />}
                        {opt.label}
                      </motion.button>
                    )
                  })}
                </div>
              </>
            )}

            {step === 'team' && (
              <>
                <p className="text-sm font-medium text-foreground">Which team should have access?</p>
                {teamsLoading ? (
                  <div className="mt-3 flex items-center justify-center gap-2 text-sm text-[var(--text-3)]">
                    <Loader2 className="size-3.5 animate-spin" />Loading teams…
                  </div>
                ) : (
                  <div className="mt-3 flex flex-wrap justify-center gap-2">
                    {(teams ?? []).map((team, i) => {
                      const isSelected = teamId === team.id
                      return (
                        <motion.button
                          key={team.id}
                          type="button"
                          initial={{ opacity: 0, y: 6, scale: 0.9 }}
                          animate={{ opacity: 1, y: 0, scale: 1 }}
                          transition={{ delay: i * 0.05, duration: 0.25, ease: EASE }}
                          whileHover={teamId ? undefined : { scale: 1.04 }}
                          whileTap={teamId ? undefined : { scale: 0.96 }}
                          onClick={() => onChooseTeam(team.id!, team.name)}
                          disabled={!!teamId}
                          className={cn(
                            'flex items-center gap-1.5 rounded-full border px-4 py-2 text-sm font-medium transition-colors duration-150 disabled:cursor-not-allowed',
                            isSelected
                              ? 'border-emerald-500 bg-emerald-500 text-white'
                              : 'border-violet-500/25 bg-violet-500/[0.06] text-[var(--text-1)] hover:border-violet-500/50 hover:bg-violet-500/10 disabled:opacity-40'
                          )}
                        >
                          {isSelected && <Check className="size-3.5" />}
                          {team.name}
                        </motion.button>
                      )
                    })}
                  </div>
                )}
              </>
            )}

            {step === 'create' && (
              <>
                {badges.length > 0 && (
                  <div className="flex flex-wrap justify-center gap-2">
                    {badges.map((badge, i) => (
                      <motion.span
                        key={`${badge.label}-${i}`}
                        initial={{ opacity: 0, y: 6, scale: 0.9 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        transition={{ delay: i * 0.05, duration: 0.25, ease: EASE }}
                        className="flex items-center gap-1.5 rounded-full border border-violet-500/25 bg-violet-500/[0.06] px-3 py-1.5 text-xs font-medium text-[var(--text-1)]"
                      >
                        <badge.icon className="size-3.5 text-violet-500" />
                        {badge.label}
                      </motion.span>
                    ))}
                  </div>
                )}
                <Button variant="primary" onClick={onCreate} disabled={busy} className="mt-6 w-full shadow-[0_8px_20px_-8px_rgba(124,58,237,0.55)]">
                  <Sparkles className="mr-2 size-4" />Create agent
                </Button>
              </>
            )}

            {step === 'creating' && (
              <div className="flex flex-col items-center gap-3">
                <Loader size={72} />
                <p className="text-sm font-semibold">{creatingStage}</p>
                <p className="text-xs text-[var(--text-3)]">This only takes a few seconds…</p>
              </div>
            )}
          </motion.div>
        </motion.div>
      </div>
    </>,
    document.body,
  )
}
