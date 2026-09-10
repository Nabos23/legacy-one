'use client'

import { motion, type Variants } from 'motion/react'
import { cn } from '@/lib/utils'

const container: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06, delayChildren: 0.05 } },
}
const word: Variants = {
  hidden: { y: '110%' },
  show: { y: '0%', transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] } },
}

export function SectionHeading({
  eyebrow,
  title,
  subtitle,
  className,
}: {
  eyebrow?: string
  title: string
  subtitle?: string
  className?: string
}) {
  return (
    <div className={cn('mx-auto max-w-2xl text-center', className)}>
      {eyebrow && (
        <motion.span
          initial={{ opacity: 0, y: 8 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="block text-sm font-semibold uppercase tracking-[0.18em] text-violet-600 dark:text-violet-400"
        >
          {eyebrow}
        </motion.span>
      )}

      {/* word-by-word clip reveal */}
      <motion.h2
        aria-label={title}
        variants={container}
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: '0px 0px -12% 0px' }}
        className="mt-3 flex flex-wrap justify-center gap-x-2.5 gap-y-1 text-3xl font-extrabold tracking-tight text-foreground sm:text-4xl"
      >
        {title.split(' ').map((w, i) => (
          <span key={`${w}-${i}`} aria-hidden className="overflow-hidden py-0.5">
            <motion.span variants={word} className="inline-block">
              {w}
            </motion.span>
          </span>
        ))}
      </motion.h2>

      {subtitle && (
        <motion.p
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '0px 0px -10% 0px' }}
          transition={{ duration: 0.6, delay: 0.15 }}
          className="mx-auto mt-4 max-w-xl text-muted-foreground"
        >
          {subtitle}
        </motion.p>
      )}
    </div>
  )
}
