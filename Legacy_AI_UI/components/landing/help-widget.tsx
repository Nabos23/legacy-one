'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { AnimatePresence, motion } from 'motion/react'
import { Bot } from 'lucide-react'

const EASE = [0.16, 1, 0.3, 1] as const

export function HelpWidget() {
  const [showPill, setShowPill] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => setShowPill(true), 1600)
    return () => clearTimeout(t)
  }, [])

  return (
    <Link
      href="/client/agents/build"
      data-testid="help-widget"
      aria-label="Create an agent with AI"
      className="group fixed bottom-16 right-4 z-[70] flex flex-col items-end sm:bottom-10 sm:right-6"
    >
      <AnimatePresence>
        {showPill && (
          <motion.span
            key="pill"
            initial={{ opacity: 0, y: 8, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 6, scale: 0.9 }}
            transition={{ duration: 0.3, ease: EASE }}
            className="mb-2.5 rounded-md border border-border bg-card/95 px-3 py-1.5 text-xs font-medium text-foreground shadow-md backdrop-blur-xl transition-colors group-hover:border-primary/40"
          >
            Create agent
          </motion.span>
        )}
      </AnimatePresence>

      <motion.span
        animate={{ y: [0, -3, 0] }}
        transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
        whileHover={{ scale: 1.04, y: -3, transition: { duration: 0.15, ease: EASE } }}
        whileTap={{ scale: 0.96 }}
        className="flex size-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg shadow-primary/20 ring-1 ring-black/5 transition-shadow group-hover:shadow-xl group-hover:shadow-primary/30 dark:ring-white/10"
      >
        <Bot size={22} strokeWidth={1.75} />
      </motion.span>
    </Link>
  )
}
