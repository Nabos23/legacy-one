'use client'

import { useEffect, useRef } from 'react'

/**
 * Runs a GSAP setup function scoped to a container ref via gsap.context(),
 * registering ScrollTrigger and cleaning everything up on unmount.
 * No-ops when the user prefers reduced motion.
 *
 * Usage:
 *   const scope = useGsapScroll((gsap, ScrollTrigger, el) => {
 *     gsap.from(el.querySelectorAll('.item'), { ... })
 *   })
 *   return <section ref={scope}>...</section>
 */
export function useGsapScroll<T extends HTMLElement = HTMLDivElement>(
  setup: (
    gsap: typeof import('gsap').gsap,
    ScrollTrigger: typeof import('gsap/ScrollTrigger').ScrollTrigger,
    el: T,
  ) => void,
  deps: unknown[] = [],
) {
  const ref = useRef<T | null>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce) return

    let ctx: { revert: () => void } | undefined

    let cancelled = false
    Promise.all([import('gsap'), import('gsap/ScrollTrigger')]).then(
      ([{ gsap }, { ScrollTrigger }]) => {
        if (cancelled || !ref.current) return
        gsap.registerPlugin(ScrollTrigger)
        ctx = gsap.context(() => setup(gsap, ScrollTrigger, ref.current as T), ref.current!)
      },
    )

    return () => {
      cancelled = true
      ctx?.revert()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return ref
}
