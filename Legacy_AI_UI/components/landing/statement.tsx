'use client'

import { motion, type Variants } from 'motion/react'

const WORDS = ['Build', 'Observe', 'Govern', 'Scale', 'Trace', 'Automate']

const container: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
}
const word: Variants = {
  hidden: { opacity: 0.25 },
  show: { opacity: 1, transition: { duration: 0.5 } },
}

/** Full-bleed typographic statement band. Static (no marquee) so it reads as
 * a deliberate manifesto line rather than the same kinetic-marquee pattern
 * already used for the connector logo wall. */
export function Statement() {
  return (
    <section className="relative w-full overflow-hidden border-y border-border bg-card/60 py-14">
      <motion.div
        variants={container}
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: '0px 0px -20% 0px' }}
        className="mx-auto flex max-w-6xl flex-wrap items-center justify-center gap-x-3 gap-y-2 px-4 text-center"
      >
        {WORDS.map((w, i) => (
          <span key={w} className="flex items-center gap-3">
            <motion.span
              variants={word}
              className="text-3xl font-extrabold tracking-tight text-foreground/90 sm:text-5xl lg:text-6xl"
            >
              {w}
            </motion.span>
            {i < WORDS.length - 1 && (
              <span className="text-2xl font-light text-violet-500 sm:text-4xl" aria-hidden>
                ·
              </span>
            )}
          </span>
        ))}
      </motion.div>
    </section>
  )
}
