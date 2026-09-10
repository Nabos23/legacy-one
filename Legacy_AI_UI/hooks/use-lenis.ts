'use client'

import { useEffect } from 'react'

/**
 * Initializes Lenis smooth scrolling and keeps GSAP ScrollTrigger in sync.
 * No-ops under prefers-reduced-motion so accessibility / motion preferences win.
 */
export function useLenis() {
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

    let lenis: { raf: (t: number) => void; destroy: () => void; on: (e: string, cb: () => void) => void } | undefined
    let rafId = 0
    let cancelled = false

    Promise.all([import('lenis'), import('gsap'), import('gsap/ScrollTrigger')]).then(
      ([{ default: Lenis }, { gsap }, { ScrollTrigger }]) => {
        if (cancelled) return
        gsap.registerPlugin(ScrollTrigger)

        lenis = new Lenis({
          duration: 1.1,
          easing: (t: number) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
          smoothWheel: true,
        }) as unknown as typeof lenis

        lenis!.on('scroll', ScrollTrigger.update)

        const raf = (time: number) => {
          lenis!.raf(time)
          rafId = requestAnimationFrame(raf)
        }
        rafId = requestAnimationFrame(raf)
      },
    )

    return () => {
      cancelled = true
      cancelAnimationFrame(rafId)
      lenis?.destroy()
    }
  }, [])
}
