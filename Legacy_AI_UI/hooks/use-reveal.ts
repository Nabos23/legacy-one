'use client'

import { useEffect, useRef, useState } from 'react'

/**
 * Lightweight scroll-reveal built on IntersectionObserver.
 * Returns a ref to attach to the element and a boolean that flips true
 * once the element scrolls into view. Respects prefers-reduced-motion
 * by revealing immediately.
 */
export function useReveal<T extends HTMLElement = HTMLDivElement>(
  options: { margin?: string; once?: boolean } = {},
) {
  const { margin = '0px 0px -12% 0px', once = true } = options
  const ref = useRef<T | null>(null)
  const [inView, setInView] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce) {
      setInView(true)
      return
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setInView(true)
            if (once) observer.disconnect()
          } else if (!once) {
            setInView(false)
          }
        }
      },
      { rootMargin: margin, threshold: 0.1 },
    )

    observer.observe(el)
    return () => observer.disconnect()
  }, [margin, once])

  return { ref, inView }
}
