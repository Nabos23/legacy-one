'use client'

import { useEffect, useState } from 'react'
import { usePathname } from 'next/navigation'
import { ShieldAlert, XCircle } from 'lucide-react'
import { Sidebar } from './sidebar'
import { TopNav } from './top-nav'
import { useSidebar } from '@/hooks/use-sidebar'
import { useAuth } from '@/contexts/auth-context'
import { BreadcrumbProvider } from '@/contexts/breadcrumb-context'
import { Button } from '@/components/ui/button'
import { FullscreenLoader } from '@/components/ui/loader'
import { cn } from '@/lib/utils'
import { getStoredDensity, DENSITY_CHANGE_EVENT, type Density } from '@/lib/preferences'
import { API_FORBIDDEN_EVENT } from '@/lib/api/client'

interface DashboardLayoutProps {
  children: React.ReactNode
  variant: 'admin' | 'client'
}

const PUBLIC_DASHBOARD_PATHS = ['/client/agents/build']

const ROUTE_PERMISSIONS: Record<string, string | string[]> = {
  // Admin base & sub-routes
  '/admin/organizations': ['view_org', 'create_org'],
  '/admin/organizations/create': 'create_org',
  '/admin/users': ['view_user', 'create_user', 'edit_user', 'delete_user'],
  '/admin/users/create': 'create_user',
  '/admin/agents': ['view_agent', 'create_agent'],
  '/admin/agents/create': 'create_agent',
  '/admin/tool-registry': ['view_tool_registry', 'create_tool'],
  '/admin/tool-registry/create': 'create_tool',
  '/admin/mcp-servers': ['view_tool', 'create_tool'],
  '/admin/mcp-servers/create': 'create_tool',
  '/admin/widgets': ['view_widget', 'create_widget'],
  '/admin/widgets/create': 'create_widget',
  '/admin/playground': 'create_chat_session',
  '/admin/tracing': 'view_trace',
  '/admin/settings': 'edit_org',
  '/admin/connectors': 'access_admin_panel',

  // Client base & sub-routes
  '/client/users': ['view_user', 'create_user', 'edit_user'],
  '/client/users/create': 'create_user',
  '/client/teams': ['view_team', 'create_team'],
  '/client/teams/create': 'create_team',
  '/client/permissions': 'edit_role_permissions',
  '/client/agents': ['view_agent', 'create_agent'],
  '/client/agents/create': 'create_agent',
  '/client/tools': ['view_tool', 'create_tool'],
  '/client/tools/create': 'create_tool',
  '/client/mcp-servers': ['view_tool', 'create_tool'],
  '/client/mcp-servers/create': 'create_tool',
  '/client/db-connections': ['view_db_connection', 'create_db_connection'],
  '/client/db-connections/create': 'create_db_connection',
  '/client/orchestrations': ['view_agent', 'create_agent'],
  '/client/orchestrations/create': 'create_agent',
  '/client/schedules': ['view_schedule', 'create_schedule'],
  '/client/schedules/create': 'create_schedule',
  '/client/widgets': ['view_widget', 'create_widget'],
  '/client/widgets/create': 'create_widget',
  '/client/playground': 'create_chat_session',
  '/client/tracing': 'view_trace',
}

function hasPermissionForPath(pathname: string, permissions: Record<string, boolean>): boolean {
  if (permissions.is_super_admin || permissions.is_org_admin) return true

  // Dynamic edit routes
  if (pathname.startsWith('/client/agents/') && pathname.endsWith('/edit')) {
    return Boolean(permissions.create_agent || permissions.edit_agent)
  }
  if (pathname.startsWith('/admin/agents/') && pathname.endsWith('/edit')) {
    return Boolean(permissions.create_agent || permissions.edit_agent)
  }
  if (pathname.startsWith('/client/tools/') && pathname.endsWith('/edit')) {
    return Boolean(permissions.create_tool || permissions.edit_tool)
  }
  if (pathname.startsWith('/admin/tool-registry/') && pathname.endsWith('/edit')) {
    return Boolean(permissions.create_tool || permissions.edit_tool)
  }
  if (pathname.startsWith('/client/teams/') && pathname.endsWith('/edit')) {
    return Boolean(permissions.create_team || permissions.edit_team)
  }

  // Exact path check
  if (ROUTE_PERMISSIONS[pathname]) {
    const required = ROUTE_PERMISSIONS[pathname]
    const requiredList = Array.isArray(required) ? required : [required]
    if (!requiredList.some(flag => permissions[flag])) {
      return false
    }
  }

  // Ancestor path segment check
  const segments = pathname.split('/').filter(Boolean)
  let currentPath = ''
  for (const segment of segments) {
    currentPath += '/' + segment
    const required = ROUTE_PERMISSIONS[currentPath]
    if (!required) continue
    const requiredList = Array.isArray(required) ? required : [required]
    if (!requiredList.some(flag => permissions[flag])) {
      return false
    }
  }
  return true
}

export function DashboardLayout({ children, variant }: DashboardLayoutProps) {
  const { isCollapsed } = useSidebar()
  const pathname = usePathname()
  const { user, permissions, loading, isAuthenticated } = useAuth()
  const isFullBleed = pathname.endsWith('/playground')
    || pathname.endsWith('/projects')
    || pathname.endsWith('/agents/build')
    || /\/orchestrations\/[^/]+\/chat$/.test(pathname)
    || /\/orchestrations\/[^/]+$/.test(pathname)
  const [density, setDensity] = useState<Density>('comfortable')
  useEffect(() => {
    setDensity(getStoredDensity())
    const onChange = (e: Event) => setDensity((e as CustomEvent<Density>).detail)
    window.addEventListener(DENSITY_CHANGE_EVENT, onChange)
    return () => window.removeEventListener(DENSITY_CHANGE_EVENT, onChange)
  }, [])

  // A 403 from any API call (not just a route the ROUTE_PERMISSIONS map knows
  // about) also surfaces the Access Denied screen below, instead of the page
  // silently failing to load its data.
  const [apiForbidden, setApiForbidden] = useState(false)
  useEffect(() => {
    const onForbidden = () => setApiForbidden(true)
    window.addEventListener(API_FORBIDDEN_EVENT, onForbidden)
    return () => window.removeEventListener(API_FORBIDDEN_EVENT, onForbidden)
  }, [])
  useEffect(() => {
    setApiForbidden(false)
  }, [pathname])

  const isAdminUser = !!permissions.is_super_admin || user?.role === 'super_admin'
  const isPublicUnauthed = !isAuthenticated && PUBLIC_DASHBOARD_PATHS.includes(pathname)

  useEffect(() => {
    if (loading) return
    if (!isAuthenticated && !isPublicUnauthed) {
      window.location.href = `/login?from=${encodeURIComponent(pathname)}`
      return
    }
  }, [loading, isAuthenticated, isPublicUnauthed, pathname])

  if (loading || (!isAuthenticated && !isPublicUnauthed)) {
    return <FullscreenLoader />
  }

  if (isPublicUnauthed) {
    return <>{children}</>
  }

  if (apiForbidden || (!loading && (!hasPermissionForPath(pathname, permissions) || (variant === 'admin' && !isAdminUser)))) {
    return (
      <div data-density={density} className="flex h-screen overflow-hidden bg-[var(--bg)] relative">
        <Sidebar variant={variant} />
        <div className={cn(
          'relative flex flex-col flex-1 min-w-0 overflow-hidden',
          'transition-[margin] duration-[220ms] ease-[cubic-bezier(0.16,1,0.3,1)]',
          isCollapsed ? 'lg:ml-[68px]' : 'lg:ml-[252px]'
        )}>
          <TopNav variant={variant} />
          <main className="flex-1 overflow-y-auto flex items-center justify-center p-6">
            <div className="text-center max-w-md glass p-8 rounded-2xl border border-red-500/20 shadow-2xl">
              <div className="w-14 h-14 rounded-full bg-red-500/15 border border-red-500/30 flex items-center justify-center mx-auto mb-4">
                <XCircle className="w-8 h-8 text-red-500" />
              </div>
              <h1 className="text-2xl font-bold mb-2">Access Denied</h1>
              <p className="text-[14px] text-[var(--text-3)] mb-6">
                You do not have the required permissions to access this page (<code className="text-red-400 bg-red-500/10 px-1.5 py-0.5 rounded text-xs">{pathname}</code>). Please contact your administrator.
              </p>
              <Button variant="primary" onClick={() => window.location.href = variant === 'admin' ? '/admin/dashboard' : '/client/dashboard'}>
                Go to Dashboard
              </Button>
            </div>
          </main>
        </div>
      </div>
    )
  }

  return (
    <BreadcrumbProvider>
      <div data-density={density} className="flex h-screen overflow-hidden bg-[var(--bg)] relative">
        {!isFullBleed && (
          <div className="absolute inset-0 overflow-hidden pointer-events-none select-none" aria-hidden>
            <div className="absolute top-[-15%] left-[15%] w-[700px] h-[700px] rounded-full
              bg-violet-500/[0.04] dark:bg-violet-500/[0.07]
              blur-[130px] motion-safe:animate-pulse [animation-duration:8s]" />
            <div className="absolute bottom-[-10%] right-[5%] w-[550px] h-[550px] rounded-full
              bg-indigo-500/[0.03] dark:bg-indigo-400/[0.05]
              blur-[110px] motion-safe:animate-pulse [animation-duration:12s] [animation-delay:2s]" />
            <div className="absolute top-[40%] right-[25%] w-[350px] h-[350px] rounded-full
              bg-cyan-500/[0.02] dark:bg-cyan-400/[0.04]
              blur-[90px] motion-safe:animate-pulse [animation-duration:10s] [animation-delay:4s]" />
          </div>
        )}

        <Sidebar variant={variant} />

        <div
          className={cn(
            'relative flex flex-col flex-1 min-w-0 min-h-0 overflow-hidden',
            'transition-[margin] duration-[220ms] ease-[cubic-bezier(0.16,1,0.3,1)]',
            isCollapsed ? 'lg:ml-[68px]' : 'lg:ml-[252px]'
          )}
        >
          <TopNav variant={variant} />
          <main className={cn(
            'flex-1 min-h-0 flex flex-col',
            isFullBleed ? 'overflow-hidden' : 'overflow-y-auto scrollbar-none'
          )}>
            {isFullBleed ? (
              children
            ) : (
              <div className="p-6 max-w-[1600px] w-full">{children}</div>
            )}
          </main>
        </div>
      </div>
    </BreadcrumbProvider>
  )
}
