'use client'

import { useEffect, useState } from 'react'

/**
 * Time-of-day greeting. Starts as a neutral value and resolves after mount so
 * server and client render the same initial markup (no hydration mismatch).
 */
export function useGreeting() {
  const [greeting, setGreeting] = useState('Welcome back')
  useEffect(() => {
    const h = new Date().getHours()
    setGreeting(h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening')
  }, [])
  return greeting
}
