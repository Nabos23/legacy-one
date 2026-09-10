'use client'

import Link from 'next/link'
import { CheckCircle2, MessageCircle } from 'lucide-react'
import { Logo } from '@/components/landing/logo'

/** Landing page right after the Slack OAuth install completes (see
 * backend/connector_apps/slack/routes.py's oauth_callback redirect target).
 * The account-linking step happens separately, via the "finish setup" link
 * DMed to the installer -- see app/(integrations)/integrations/slack/link. */
export default function SlackInstalledPage() {
  return (
    <div className="flex min-h-screen w-full items-center justify-center p-6 bg-background">
      <div className="w-full max-w-[440px] text-center">
        <Link href="/" aria-label="ONE-AI home" className="inline-flex mb-8">
          <Logo />
        </Link>

        <div className="mx-auto mb-5 flex size-14 items-center justify-center rounded-full bg-emerald-500/12">
          <CheckCircle2 className="w-7 h-7 text-emerald-600 dark:text-emerald-400" />
        </div>

        <h1 className="text-[22px] font-bold text-foreground tracking-tight">One-AI is installed!</h1>
        <p className="mt-2 text-[14.5px] text-muted-foreground leading-relaxed">
          One more step — check your Slack DMs for a message from One-AI with a link to finish setup.
          That&apos;s where you&apos;ll connect this workspace to your One-AI account and pick which agent answers.
        </p>

        <div className="mt-6 flex items-center justify-center gap-2 rounded-xl border border-border bg-card/60 px-4 py-3 text-[13px] text-muted-foreground">
          <MessageCircle className="w-4 h-4 shrink-0 text-violet-600 dark:text-violet-400" />
          Look for a direct message from the One-AI app in your Slack sidebar.
        </div>

        <p className="mt-8 text-[13px] text-muted-foreground">
          Already have the link?{' '}
          <Link href="/login" className="text-violet-600 dark:text-violet-400 hover:underline font-medium">
            Log in
          </Link>{' '}
          and click it from your Slack DM.
        </p>
      </div>
    </div>
  )
}
