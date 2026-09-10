'use client'

import {
  createContext,
  useContext,
  useState,
  ReactNode,
  useEffect,
  useCallback,
  useMemo,
} from 'react'

type SidebarVariant = 'client' | 'admin'

interface SidebarContextType {
  isCollapsed: boolean
  isMobileOpen: boolean
  isOpen: boolean
  variant: SidebarVariant
  toggleCollapse: () => void
  toggleMobile: () => void
  toggle: () => void
  toggleSidebar: () => void
  setCollapsed: (v: boolean) => void
}

const SidebarContext = createContext<SidebarContextType | null>(null)
const SidebarVariantContext = createContext<SidebarVariant>('client')

function SidebarContextProvider({
  variant,
  children,
}: {
  variant: SidebarVariant
  children: ReactNode
}) {
  // The persisted desktop preference. On mobile the sidebar is an off-canvas
  // drawer that must always render expanded (full width + labels), so the
  // collapse concept only applies to the ≥1024px rail.
  const [rawCollapsed, setRawCollapsed] = useState(false)
  const [isMobile, setIsMobile] = useState(false)
  const [isMobileOpen, setIsMobileOpen] = useState(false)

  useEffect(() => {
    const saved = localStorage.getItem('sidebar-collapsed')
    if (saved !== null) {
      try {
        setRawCollapsed(JSON.parse(saved))
      } catch {
        /* ignore */
      }
    }

    const mq = window.matchMedia('(max-width: 1023px)')
    const apply = () => {
      setIsMobile(mq.matches)
      // Leaving mobile width should also dismiss the off-canvas drawer so it
      // doesn't linger as an overlay on the desktop layout.
      if (!mq.matches) setIsMobileOpen(false)
    }
    apply()
    mq.addEventListener('change', apply)
    return () => mq.removeEventListener('change', apply)
  }, [])

  const isCollapsed = isMobile ? false : rawCollapsed

  const setCollapsed = useCallback((v: boolean) => {
    setRawCollapsed(v)
    localStorage.setItem('sidebar-collapsed', JSON.stringify(v))
  }, [])

  const toggleCollapse = useCallback(() => {
    setRawCollapsed(prev => {
      const next = !prev
      localStorage.setItem('sidebar-collapsed', JSON.stringify(next))
      return next
    })
  }, [])

  const toggleMobile = useCallback(() => {
    setIsMobileOpen(prev => !prev)
  }, [])

  const value = useMemo(
    () => ({
      isCollapsed,
      isMobileOpen,
      isOpen: isMobileOpen,
      variant,
      toggleCollapse,
      toggleMobile,
      toggle: toggleMobile,
      toggleSidebar: toggleCollapse,
      setCollapsed,
    }),
    [isCollapsed, isMobileOpen, variant, toggleCollapse, toggleMobile, setCollapsed]
  )

  return (
    <SidebarContext.Provider value={value}>{children}</SidebarContext.Provider>
  )
}

export function SidebarProvider({ children }: { children: ReactNode }) {
  return <SidebarContextProvider variant="client">{children}</SidebarContextProvider>
}

export function SidebarVariantProvider({
  variant,
  children,
}: {
  variant: SidebarVariant
  children: ReactNode
}) {
  return (
    <SidebarVariantContext.Provider value={variant}>
      <SidebarContextProvider variant={variant}>{children}</SidebarContextProvider>
    </SidebarVariantContext.Provider>
  )
}

export function useSidebar() {
  const context = useContext(SidebarContext)
  if (!context) {
    throw new Error('useSidebar must be used within SidebarProvider')
  }
  return context
}

export function useSidebarVariant() {
  return useContext(SidebarVariantContext)
}
