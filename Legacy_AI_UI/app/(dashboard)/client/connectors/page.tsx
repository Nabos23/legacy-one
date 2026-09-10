import Link from 'next/link'
import { ArrowRight, MessageCircle, PlugZap } from 'lucide-react'
import { ConnectorGrid } from '@/components/connectors/connector-grid'

export default function ConnectorsPage() {
  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Page header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-1">
          <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-violet-500/10">
            <PlugZap className="w-5 h-5 text-violet-600 dark:text-violet-400" />
          </div>
          <h1 className="text-[22px] font-bold text-[var(--text-1)]">Connectors</h1>
        </div>
        <p className="text-[13px] text-[var(--text-3)] ml-12">
          Connect your tools and services to make them available to your agents.
        </p>
      </div>

      {/* Distinct from the outbound "Slack" connector below (agent calls
          Slack's API) -- this is our own Slack App, chatted with inbound. */}
      <Link
        href="/client/connectors/slack-app"
        className="mb-8 flex items-center gap-3 rounded-2xl border border-[var(--border)] bg-[var(--surface-2)] px-4 py-3 hover:border-violet-300 transition-colors group"
      >
        <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-violet-500/10 shrink-0">
          <MessageCircle className="w-4.5 h-4.5 text-violet-600 dark:text-violet-400" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[14px] font-semibold text-[var(--text-1)]">Slack App — chat with an agent from Slack</p>
          <p className="text-[12px] text-[var(--text-3)]">Manage connected Slack workspaces and which agent answers each one.</p>
        </div>
        <ArrowRight className="w-4 h-4 text-[var(--text-3)] group-hover:text-violet-500 transition-colors shrink-0" />
      </Link>

      <ConnectorGrid />
    </div>
  )
}
