import { NextRequest, NextResponse } from 'next/server'

const PROTECTED = ['/admin', '/client']
const AUTH_PATHS = ['/login', '/register', '/forgot-password']
const PUBLIC_EXCEPTIONS = ['/client/agents/build']

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

export function proxy(req: NextRequest) {
  const token = req.cookies.get('access_token')?.value
  const role = req.cookies.get('user_role')?.value
  const permissionsRaw = req.cookies.get('user_permissions')?.value
  const { pathname } = req.nextUrl

  if (PROTECTED.some(p => pathname.startsWith(p)) && !PUBLIC_EXCEPTIONS.some(p => pathname.startsWith(p)) && !token) {
    const url = req.nextUrl.clone()
    url.pathname = '/login'
    url.searchParams.set('from', pathname)
    return NextResponse.redirect(url)
  }

  if (AUTH_PATHS.some(p => pathname.startsWith(p)) && token) {
    const from = req.nextUrl.searchParams.get('from')
    const isAdmin = role === 'super_admin' || role === 'super admin'
    if (from && from.startsWith('/') && !from.startsWith('//')) {
      if (isAdmin && from.startsWith('/client')) {
        return NextResponse.redirect(new URL('/admin/dashboard', req.url))
      }
      return NextResponse.redirect(new URL(from, req.url))
    }
    const target = isAdmin ? '/admin/dashboard' : '/client/dashboard'
    return NextResponse.redirect(new URL(target, req.url))
  }

  // For authenticated requests to protected paths, let Next.js render the page wrapper so that
  // DashboardLayout displays the inline "Access Denied" screen on missing permissions.
  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|api).*)'],
}
