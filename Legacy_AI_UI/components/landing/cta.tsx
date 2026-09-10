'use client'

import Link from 'next/link'
import { motion } from 'motion/react'
import { ArrowRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Magnetic } from './magnetic'

export function CallToAction() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-24">
      <motion.div
        initial={{ opacity: 0, y: 32 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '0px 0px -10% 0px' }}
        transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
        className="glass-card relative overflow-hidden rounded-3xl border border-border bg-card/50 px-6 py-16 text-center backdrop-blur-2xl backdrop-saturate-150 glow-violet"
      >
        <div className="pointer-events-none absolute inset-0 bg-noise opacity-50" />
        <div className="pointer-events-none absolute -bottom-24 left-1/2 size-[26rem] -translate-x-1/2 rounded-full bg-violet-500/15 blur-[110px]" />
        <div className="relative">
          <h2 className="mx-auto max-w-2xl text-3xl font-extrabold tracking-tight text-foreground sm:text-5xl">
            Ship your first agent today
          </h2>
          <p className="mx-auto mt-4 max-w-lg text-muted-foreground">
            Start free. Scale to a governed fleet when you're ready. No rebuild required.
          </p>
          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Magnetic>
              <Button
                variant="primary"
                size="lg"
                className="group h-11 pl-6 pr-1.5 text-sm"
                nativeButton={false}
                render={<Link href="/register" />}
              >
                Get started free
                <span className="ml-1 flex size-7 items-center justify-center rounded-full bg-white/15 transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:translate-x-0.5">
                  <ArrowRight size={14} />
                </span>
              </Button>
            </Magnetic>
            <Magnetic strength={0.25}>
              <Button
                variant="outline"
                size="lg"
                className="h-11 px-6 text-sm"
                nativeButton={false}
                render={<Link href="/login" />}
              >
                Log in
              </Button>
            </Magnetic>
          </div>
        </div>
      </motion.div>
    </section>
  )
}
