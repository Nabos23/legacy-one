'use client'

import Link from 'next/link'
import { Globe, Moon, Sun } from 'lucide-react'
import { useTheme } from '@/contexts/theme-context'
import { Button } from '@/components/ui/button'
import { GitHubLogo, TwitterLogo } from '@/components/connectors/connector-logo'
import { Logo } from './logo'

const GROUPS = [
  {
    title: 'Product',
    links: [
      { label: 'Features', href: '#features' },
      { label: 'How it works', href: '#how-it-works' },
      { label: 'Pricing', href: '#pricing' },
      { label: 'FAQ', href: '#faq' },
    ],
  },
  {
    title: 'Platform',
    links: [
      { label: 'Agents', href: '#showcase' },
      { label: 'Tracing', href: '#showcase' },
      { label: 'Playground', href: '#showcase' },
    ],
  },
  {
    title: 'Account',
    links: [
      { label: 'Log in', href: '/login' },
      { label: 'Get started', href: '/register' },
    ],
  },
]

const SOCIALS = [
  { icon: GitHubLogo, href: '#', label: 'GitHub' },
  { icon: TwitterLogo, href: '#', label: 'X' },
  { icon: Globe, href: '#', label: 'Website' },
]

export function Footer() {
  const { theme, toggleTheme } = useTheme()

  return (
    <footer className="relative w-full border-t border-border bg-card/40 backdrop-blur-2xl backdrop-saturate-150">
      <div className="mx-auto max-w-6xl">
        <div className="grid gap-10 px-4 py-14 sm:px-6 md:grid-cols-[1.4fr_1fr_1fr_1fr] md:px-8">
          {/* brand column */}
          <div>
            <Logo />
            <p className="mt-4 max-w-xs text-sm text-muted-foreground">
              The enterprise control plane to build, observe and govern AI agents at scale.
            </p>
          </div>

          {GROUPS.map((g) => (
            <div key={g.title}>
              <h4 className="text-sm font-semibold text-foreground">{g.title}</h4>
              <ul className="mt-4 space-y-2.5">
                {g.links.map((l) => (
                  <li key={l.label}>
                    <Link
                      href={l.href}
                      className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                    >
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* mini CTA strip */}
        <div className="flex flex-col items-center justify-between gap-4 border-t border-border px-4 py-6 sm:px-6 md:flex-row md:px-8">
          <p className="text-center text-sm font-medium text-foreground md:text-left">
            Ready to ship your first agent?
          </p>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" nativeButton={false} render={<Link href="/login" />}>
              Log in
            </Button>
            <Button variant="primary" size="sm" nativeButton={false} render={<Link href="/register" />}>
              Get started free
            </Button>
          </div>
        </div>

        {/* bottom bar */}
        <div className="flex flex-col items-center justify-between gap-3 border-t border-border px-4 py-5 sm:px-6 md:flex-row md:px-8">
          <p className="text-xs text-muted-foreground">© 2026 ONE-AI. All rights reserved.</p>
          <div className="flex items-center gap-1">
            {SOCIALS.map((s) => (
              <a
                key={s.label}
                href={s.href}
                aria-label={s.label}
                className="flex size-8 items-center justify-center rounded-lg text-muted-foreground opacity-70 grayscale transition-[background-color,opacity,filter] hover:bg-muted hover:opacity-100 hover:grayscale-0"
              >
                {s.label === 'Website' ? <Globe size={16} /> : <s.icon size={16} />}
              </a>
            ))}
            <span className="mx-1 h-4 w-px bg-border" />
            <Button variant="ghost" size="icon-sm" onClick={toggleTheme} aria-label="Toggle theme">
              {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            </Button>
          </div>
        </div>
      </div>
    </footer>
  )
}
