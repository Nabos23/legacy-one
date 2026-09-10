'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Menu, Moon, Sun, X } from 'lucide-react'
import { useTheme } from '@/contexts/theme-context'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { Logo } from './logo'

const LINKS = [
  { label: 'Features', href: '#features' },
  { label: 'Connectors', href: '#connectors' },
  { label: 'How it works', href: '#how-it-works' },
  { label: 'Platform', href: '#showcase' },
  { label: 'Pricing', href: '#pricing' },
  { label: 'FAQ', href: '#faq' },
]

export function Nav() {
  const { theme, toggleTheme } = useTheme()
  const [scrolled, setScrolled] = useState(false)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState('')

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  // Highlight the nav link for the section currently in view.
  useEffect(() => {
    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) setActive(e.target.id)
        })
      },
      { rootMargin: '-45% 0px -50% 0px' },
    )
    LINKS.forEach((l) => {
      const el = document.getElementById(l.href.slice(1))
      if (el) obs.observe(el)
    })
    return () => obs.disconnect()
  }, [])

  // Lock body scroll while the mobile menu is open.
  useEffect(() => {
    document.body.style.overflow = open ? 'hidden' : ''
    return () => {
      document.body.style.overflow = ''
    }
  }, [open])

  return (
    <motion.header
      initial={{ y: -24, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      className="fixed inset-x-0 top-0 z-50 flex justify-center px-4 pt-3"
    >
      <nav
        className={cn(
          'flex w-full max-w-5xl items-center justify-between rounded-2xl px-4 py-2.5 transition-[background-color,border-color,backdrop-filter] duration-300',
          scrolled || open
            ? 'glass-card border border-border bg-card/55 backdrop-blur-2xl backdrop-saturate-150'
            : 'border border-transparent bg-transparent',
        )}
      >
        <Link href="/" aria-label="ONE-AI home" onClick={() => setOpen(false)}>
          <Logo />
        </Link>

        {/* desktop links */}
        <div className="hidden items-center gap-1 md:flex">
          {LINKS.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className={cn(
                'rounded-lg px-3 py-1.5 text-sm font-medium transition-colors hover:bg-muted hover:text-foreground',
                active === l.href.slice(1)
                  ? 'bg-muted text-foreground'
                  : 'text-muted-foreground',
              )}
            >
              {l.label}
            </a>
          ))}
        </div>

        {/* desktop actions */}
        <div className="hidden items-center gap-1.5 md:flex">
          <Button variant="ghost" size="icon-sm" onClick={toggleTheme} aria-label="Toggle theme">
            {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          </Button>
          <Button variant="ghost" size="sm" nativeButton={false} render={<Link href="/login" />}>
            Log in
          </Button>
          <Button variant="primary" size="sm" nativeButton={false} render={<Link href="/register" />}>
            Get started
          </Button>
        </div>

        {/* mobile actions */}
        <div className="flex items-center gap-1.5 md:hidden">
          <Button variant="ghost" size="icon-sm" onClick={toggleTheme} aria-label="Toggle theme">
            {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? 'Close menu' : 'Open menu'}
            aria-expanded={open}
          >
            {open ? <X size={18} /> : <Menu size={18} />}
          </Button>
        </div>
      </nav>

      {/* mobile dropdown panel */}
      <AnimatePresence>
        {open && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 -z-10 bg-background/40 backdrop-blur-sm md:hidden"
              onClick={() => setOpen(false)}
            />
            <motion.div
              initial={{ opacity: 0, y: -12, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -12, scale: 0.98 }}
              transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
              className="absolute inset-x-4 top-[4.5rem] origin-top rounded-2xl border border-border bg-card/80 p-3 backdrop-blur-2xl backdrop-saturate-150 shadow-[0_20px_50px_-20px_rgba(0,0,0,0.3)] md:hidden"
            >
              <div className="flex flex-col">
                {LINKS.map((l) => (
                  <a
                    key={l.href}
                    href={l.href}
                    onClick={() => setOpen(false)}
                    className="rounded-xl px-4 py-3 text-sm font-medium text-foreground/90 transition-colors hover:bg-muted"
                  >
                    {l.label}
                  </a>
                ))}
              </div>
              <div className="mt-2 flex flex-col gap-2 border-t border-border pt-3">
                <Button
                  variant="outline"
                  size="lg"
                  className="h-10 w-full"
                  nativeButton={false} render={<Link href="/login" />}
                  onClick={() => setOpen(false)}
                >
                  Log in
                </Button>
                <Button
                  variant="primary"
                  size="lg"
                  className="h-10 w-full"
                  nativeButton={false} render={<Link href="/register" />}
                  onClick={() => setOpen(false)}
                >
                  Get started
                </Button>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </motion.header>
  )
}
