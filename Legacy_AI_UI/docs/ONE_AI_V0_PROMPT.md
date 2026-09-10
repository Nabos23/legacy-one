# ONE-AI — v0.dev Generation Prompt

> Paste each **PART** into v0.dev separately, in order. Confirm the scaffold before continuing to Part 2.

---

## PART 1 — Project Scaffold & Design System

Build a production-grade SaaS platform called **ONE-AI** — an AI Agent Management Platform.

### Tech Stack
- Next.js 15 (App Router, React Server Components by default)
- TypeScript (strict mode)
- Tailwind CSS v4
- shadcn/ui — Button, Input, Select, Textarea, Dialog, Tabs, Badge, Card, Tooltip, Popover, DropdownMenu, Separator
- Recharts (charts)
- Lucide React (icons)
- Geist font (Sans + Mono, Next.js built-in)
- Zod (form validation)

### Folder Structure

Generate every file at its exact path:

```
src/
├── app/
│   ├── (auth)/
│   │   ├── layout.tsx
│   │   ├── login/page.tsx
│   │   ├── register/page.tsx
│   │   └── forgot-password/page.tsx
│   ├── (dashboard)/
│   │   ├── layout.tsx
│   │   ├── admin/
│   │   │   ├── layout.tsx
│   │   │   ├── dashboard/page.tsx + loading.tsx
│   │   │   ├── organizations/page.tsx + loading.tsx + create/page.tsx
│   │   │   ├── users/page.tsx + loading.tsx + create/page.tsx
│   │   │   ├── agents/page.tsx + loading.tsx
│   │   │   └── settings/page.tsx
│   │   └── client/
│   │       ├── layout.tsx
│   │       ├── dashboard/page.tsx + loading.tsx
│   │       ├── agents/page.tsx + loading.tsx + create/page.tsx
│   │       ├── tools/page.tsx + loading.tsx + create/page.tsx
│   │       ├── db-connections/page.tsx + loading.tsx + create/page.tsx
│   │       ├── playground/page.tsx
│   │       ├── analytics/page.tsx + loading.tsx
│   │       ├── settings/page.tsx
│   │       └── help/page.tsx
│   ├── layout.tsx
│   ├── page.tsx
│   ├── not-found.tsx
│   ├── error.tsx
│   └── globals.css
├── components/
│   ├── layout/
│   │   ├── sidebar.tsx
│   │   ├── topnav.tsx
│   │   ├── page-header.tsx
│   │   └── command-palette.tsx
│   ├── ui/
│   │   ├── stats-card.tsx
│   │   ├── data-table.tsx
│   │   ├── empty-state.tsx
│   │   ├── status-indicator.tsx
│   │   ├── stepper.tsx
│   │   ├── code-editor.tsx
│   │   ├── tag-input.tsx
│   │   ├── key-value-editor.tsx
│   │   ├── skeleton.tsx
│   │   └── pagination.tsx
│   └── dashboard/
│       ├── metric-cards.tsx
│       ├── agent-analytics-chart.tsx
│       ├── agent-list-card.tsx
│       ├── agent-execution-status.tsx
│       ├── task-completion-chart.tsx
│       ├── system-alerts-card.tsx
│       └── compute-tracker.tsx
├── hooks/
│   ├── use-agents.ts
│   ├── use-tools.ts
│   ├── use-db-connections.ts
│   ├── use-organizations.ts
│   ├── use-toast.ts
│   └── use-sidebar.ts
├── lib/
│   ├── api/
│   │   ├── client.ts
│   │   ├── auth.ts
│   │   ├── agents.ts
│   │   ├── tools.ts
│   │   ├── db-connections.ts
│   │   ├── organizations.ts
│   │   └── index.ts
│   ├── validations/
│   │   ├── auth.ts
│   │   ├── agent.ts
│   │   ├── tool.ts
│   │   └── organization.ts
│   └── utils.ts
├── contexts/
│   ├── auth-context.tsx
│   ├── theme-context.tsx
│   └── sidebar-context.tsx
├── types/index.ts
├── styles/tokens.css
└── middleware.ts
```

### Naming Conventions

| Thing | Convention | Example |
|---|---|---|
| Files | kebab-case | `stats-card.tsx` |
| Components | PascalCase export | `export default function Sidebar` |
| Hooks | camelCase export | `export function useAgents` |
| Types | PascalCase | `interface AgentPublic` |
| CSS variables | --kebab-case | `--color-primary` |
| Constants | SCREAMING_SNAKE | `const BASE_URL` |

### Server vs Client Components

**Server Components** (no `'use client'`):
- All `layout.tsx` and `loading.tsx` files
- `not-found.tsx`, `error.tsx`
- Pages with no interactivity (render a single Client Component child instead)

**Client Components** (`'use client'` at top):
- Everything in `components/layout/`, `components/ui/`, `components/dashboard/`
- All hooks and contexts
- Any page using `useState`, `useEffect`, event handlers, or browser APIs

**Pattern — push `'use client'` as deep as possible:**
```tsx
// app/(dashboard)/client/agents/page.tsx — stays Server Component
import AgentsTable from '@/components/dashboard/agents-table' // 'use client' lives here
export default function AgentsPage() { return <AgentsTable /> }
```

### Design System — `src/styles/tokens.css`

```css
:root {
  /* Backgrounds */
  --bg:        #090910;
  --surface:   #111118;
  --surface-2: #16161f;
  --surface-3: #1c1c27;

  /* Borders */
  --border:   rgba(255,255,255,0.06);
  --border-2: rgba(255,255,255,0.10);

  /* Brand */
  --primary:      #7c3aed;
  --primary-dim:  #6d28d9;
  --primary-fg:   #ffffff;
  --primary-glow: rgba(124,58,237,0.25);

  /* Semantic */
  --secondary: #06b6d4;
  --success:   #22c55e;
  --warning:   #f59e0b;
  --danger:    #ef4444;

  /* Text */
  --text-1: #f4f4f5;
  --text-2: #a1a1aa;
  --text-3: #52525b;

  /* Spacing */
  --space-1: 4px;  --space-2: 8px;   --space-3: 12px;
  --space-4: 16px; --space-5: 20px;  --space-6: 24px;
  --space-8: 32px; --space-10: 40px; --space-12: 48px;

  /* Radius */
  --radius-sm: 6px; --radius-md: 10px;
  --radius-lg: 14px; --radius-xl: 20px;

  /* Transitions */
  --transition-fast: 150ms linear;
  --transition-base: 250ms cubic-bezier(0.16,1,0.3,1);
  --transition-slow: 400ms cubic-bezier(0.16,1,0.3,1);
}

[data-theme="light"] {
  --bg:       #fafafa;
  --surface:  #ffffff;
  --surface-2:#f4f4f5;
  --surface-3:#e4e4e7;
  --border:   rgba(0,0,0,0.08);
  --text-1:   #09090b;
  --text-2:   #52525b;
  --text-3:   #a1a1aa;
}
```

**Glass panel utility (add as Tailwind `@layer components`):**
```css
.glass {
  background: rgba(255,255,255,0.025);
  border: 1px solid rgba(255,255,255,0.07);
  backdrop-filter: blur(24px) saturate(180%);
  border-radius: var(--radius-lg);
  box-shadow: 0 0 0 1px rgba(255,255,255,0.03), 0 8px 32px rgba(0,0,0,0.4);
}
.glass-hover:hover {
  border-color: rgba(124,58,237,0.35);
  box-shadow: 0 0 0 1px rgba(124,58,237,0.15), 0 8px 32px rgba(0,0,0,0.5);
  transition: all var(--transition-base);
}
```

### Core Files

**`src/lib/utils.ts`**
```ts
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs))
export const truncate = (str: string, len: number) => str.length > len ? str.slice(0, len) + '...' : str
export const getInitials = (name: string) => name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
export const formatDate = (date: string | Date): string => { /* returns "2 days ago" / "just now" */ }
export const avatarColor = (name: string): string => {
  const colors = ['bg-violet-600','bg-cyan-600','bg-green-600','bg-amber-600',
                  'bg-red-600','bg-pink-600','bg-indigo-600','bg-orange-600']
  return colors[name.charCodeAt(0) % colors.length]
}
```

**`src/types/index.ts`**
```ts
export interface Page<T> { items: T[]; total: number; page: number; page_size: number }
export interface UserPublic { id: string; organization_id: string; name: string; email: string; role: 'admin' | 'member'; created_at: string }
export interface TokenResponse { access_token: string; token_type: 'bearer'; user: UserPublic }
export interface OrganizationPublic { id: string; name: string; description?: string; created_at: string; updated_at: string }
export interface AgentPublic { id: string; organization_id: string; name: string; prompt: string; guardrails?: string; description?: string; tool_ids?: string[]; created_by: string; created_at: string }
export interface ToolPublic { id: string; organization_id: string; name?: string; description?: string; user_description: string; db_conn_id?: string; tool_id: string; created_at: string }
export interface DbConnectionPublic { id: string; organization_id: string; tool_id: string; connection_string: string; created_at: string }
```

**`src/middleware.ts`**
```ts
import { NextRequest, NextResponse } from 'next/server'
const PROTECTED = ['/admin', '/client']
const AUTH_PATHS = ['/login', '/register', '/forgot-password']
export function middleware(req: NextRequest) {
  const token = req.cookies.get('access_token')?.value
  const { pathname } = req.nextUrl
  if (PROTECTED.some(p => pathname.startsWith(p)) && !token) {
    const url = req.nextUrl.clone()
    url.pathname = '/login'
    url.searchParams.set('from', pathname)
    return NextResponse.redirect(url)
  }
  if (AUTH_PATHS.some(p => pathname.startsWith(p)) && token)
    return NextResponse.redirect(new URL('/client/dashboard', req.url))
  return NextResponse.next()
}
export const config = { matcher: ['/((?!_next/static|_next/image|favicon.ico|api).*)'] }
```

**`src/lib/api/client.ts`**
```ts
const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
export class ApiError extends Error { constructor(public status: number, public detail: string) { super(detail) } }
const getToken = () => typeof window === 'undefined' ? null : localStorage.getItem('access_token')
async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken()
  const res = await fetch(`${BASE_URL}${path}`, { ...init, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init?.headers } })
  if (res.status === 401) { localStorage.removeItem('access_token'); window.location.href = '/login'; throw new ApiError(401, 'Unauthorized') }
  if (!res.ok) { const body = await res.json().catch(() => ({ detail: res.statusText })); throw new ApiError(res.status, body.detail ?? res.statusText) }
  return res.json() as Promise<T>
}
export const api = { get: <T>(p: string) => apiRequest<T>(p), post: <T>(p: string, b: unknown) => apiRequest<T>(p, { method: 'POST', body: JSON.stringify(b) }), put: <T>(p: string, b: unknown) => apiRequest<T>(p, { method: 'PUT', body: JSON.stringify(b) }), delete: <T>(p: string) => apiRequest<T>(p, { method: 'DELETE' }) }
```

**`src/lib/api/agents.ts`** (same pattern for tools, organizations, auth, db-connections)
```ts
import { api } from './client'
import type { AgentPublic, Page } from '@/types'
export const agentsApi = {
  list:   (page = 1, page_size = 10) => api.get<Page<AgentPublic>>(`/agents?page=${page}&page_size=${page_size}`),
  get:    (id: string) => api.get<AgentPublic>(`/agents/${id}`),
  create: (body: { name: string; prompt: string; guardrails?: string }) => api.post<AgentPublic>('/agents', body),
  update: (id: string, body: Partial<AgentPublic>) => api.put<AgentPublic>(`/agents/${id}`, body),
  delete: (id: string) => api.delete<void>(`/agents/${id}`),
}
```

**`src/lib/validations/agent.ts`**
```ts
import { z } from 'zod'
export const createAgentSchema = z.object({
  name:       z.string().min(2, 'Name must be at least 2 characters'),
  prompt:     z.string().min(10, 'System prompt must be at least 10 characters'),
  guardrails: z.string().optional(),
  tool_ids:   z.array(z.string()).optional(),
})
export type CreateAgentInput = z.infer<typeof createAgentSchema>
```

**`src/hooks/use-agents.ts`** (same pattern for use-tools, use-db-connections, use-organizations)
```ts
'use client'
import { useState, useEffect, useCallback } from 'react'
import { agentsApi } from '@/lib/api'
import type { AgentPublic, Page } from '@/types'
export function useAgents(initialPage = 1) {
  const [data, setData]       = useState<Page<AgentPublic> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState<string | null>(null)
  const [page, setPage]       = useState(initialPage)
  const fetch = useCallback(async () => {
    setLoading(true); setError(null)
    try { setData(await agentsApi.list(page)) }
    catch (e: unknown) { setError(e instanceof Error ? e.message : 'Failed to load') }
    finally { setLoading(false) }
  }, [page])
  useEffect(() => { fetch() }, [fetch])
  return { data, loading, error, page, setPage, refetch: fetch }
}
```

**`src/app/layout.tsx`** (Server Component)
```tsx
import type { Metadata } from 'next'
import { GeistSans } from 'geist/font/sans'
import { GeistMono } from 'geist/font/mono'
import { ThemeProvider } from '@/contexts/theme-context'
import { AuthProvider } from '@/contexts/auth-context'
import { SidebarProvider } from '@/contexts/sidebar-context'
import '@/styles/tokens.css'; import './globals.css'
export const metadata: Metadata = { title: { default: 'ONE-AI', template: '%s | ONE-AI' }, description: 'Enterprise AI Agent Management Platform' }
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${GeistSans.variable} ${GeistMono.variable} font-sans antialiased`}>
        <ThemeProvider><AuthProvider><SidebarProvider>{children}</SidebarProvider></AuthProvider></ThemeProvider>
      </body>
    </html>
  )
}
```

**`src/app/page.tsx`** → `redirect('/login')`

**`src/app/not-found.tsx`**: Full-screen centered — large "404" in violet, "Page not found" heading, subtext, "Go back home" primary button → `/login`

**`src/app/error.tsx`** (`'use client'`): Full-screen centered — AlertTriangle 48px danger, "Something went wrong", `error.message` in mono code block, "Try again" primary button calls `reset()`

---

## PART 2 — Layouts & Shell Components

All components in `src/components/layout/` are `'use client'`.

### `src/app/(auth)/layout.tsx` (Server Component)
Full-screen centered layout, `bg-[#090910]`. Two absolute decorative gradient blobs (pointer-events-none): violet 600px top-left blur-3xl opacity-20, cyan 400px bottom-right blur-3xl opacity-15. Renders `{children}` centered.

### `src/app/(dashboard)/layout.tsx` (Server Component)
```tsx
import Sidebar from '@/components/layout/sidebar'
import TopNav  from '@/components/layout/topnav'
// Sidebar and TopNav are 'use client'; this layout stays Server
export default function DashboardLayout({ children }) {
  return (
    <div className="flex h-screen overflow-hidden bg-[var(--bg)]">
      <Sidebar />
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <TopNav />
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  )
}
```
Note: `playground/page.tsx` wraps content in `-m-6` to fill full viewport height.

### `src/app/(dashboard)/admin/layout.tsx` (Server Component)
```tsx
import { SidebarVariantProvider } from '@/contexts/sidebar-context'
export default function AdminLayout({ children }) {
  return <SidebarVariantProvider variant="admin">{children}</SidebarVariantProvider>
}
```

### `src/app/(dashboard)/client/layout.tsx` — same, `variant="client"`

### `src/components/layout/sidebar.tsx` (`'use client'`)

Uses: `useSidebar()`, `usePathname()`, `cn()`

**Dimensions:** Expanded `w-[248px]` / Collapsed `w-[68px]`. Transition: `transition-[width] duration-[250ms] cubic-bezier(0.16,1,0.3,1)`. Base classes: `bg-[#0c0c13] border-r border-[var(--border)] h-screen fixed left-0 top-0 z-40 flex flex-col`

**Logo header** (`h-[56px]`, `flex items-center px-4`, `border-b`): Violet dot (10px, radial-gradient glow), "ONE-AI" wordmark (fades out when collapsed), ChevronLeft/ChevronRight collapse toggle (ghost 28px, right edge).

**Nav items:**

CLIENT variant — Section "MENU":
- `/client/dashboard` — LayoutDashboard — Dashboard
- `/client/agents` — Bot — Agents
- `/client/tools` — Wrench — Tools
- `/client/db-connections` — Database — DB Connections
- `/client/playground` — Terminal — Playground
- `/client/analytics` — BarChart3 — Analytics

Section "GENERAL":
- `/client/settings` — Settings — Settings
- `/client/help` — HelpCircle — Help

ADMIN variant (flat, no sections):
- `/admin/dashboard` — LayoutDashboard — Dashboard
- `/admin/organizations` — Building2 — Organizations
- `/admin/users` — Users — Users
- `/admin/agents` — Bot — Agents
- `/admin/settings` — Settings — Settings

**Nav item style:**
- Base: `flex items-center gap-3 mx-2 px-3 py-2.5 rounded-[10px] text-[14px] text-[var(--text-2)]`
- Icon: 20px Lucide
- Label: hidden when collapsed (`opacity-0 w-0` transition)
- Hover: `bg-white/5 text-[var(--text-1)]`
- Active: `bg-violet-900/20 text-violet-300 shadow-[inset_3px_0_0_#7c3aed]`
- Collapsed: shadcn Tooltip `side="right"` shows label on hover

**Section labels** (visible only expanded): `text-[10px] font-semibold tracking-[0.1em] text-[var(--text-3)] uppercase px-5 pt-5 pb-2`

**Footer** (`mt-auto`):
- CLI card (visible only expanded, `mx-2 mb-3`): glass panel `p-3 rounded-[12px]`, two decorative blobs (violet + cyan blur opacity-20), "ONE-AI CLI" 13px 500, "Run agents from your terminal" 11px text-3, "Download" ghost xs + Download icon
- Logout (`mx-2 mb-2`, always visible): `flex items-center gap-3 px-3 py-2.5 rounded-[10px]`, LogOut icon 18px `text-red-400`, "Logout" label (expanded only), `hover:bg-red-500/10`

### `src/components/layout/topnav.tsx` (`'use client'`)

Uses: `useAuth()`, `useSidebar()`, `usePathname()`, `<CommandPalette />`

Base: `h-[56px] sticky top-0 z-30 flex items-center justify-between px-6 bg-[rgba(9,9,16,0.85)] backdrop-blur-xl border-b border-[var(--border)]`. Shifts right with sidebar width (transition matches sidebar).

**Left** — Breadcrumb: parse pathname → "Client / Dashboard" style, `text-[13px]`, segments in `text-3`, last segment in `text-1 500`

**Center** — Search trigger: glass pill ~360px, Search icon + placeholder `text-3` + `⌘F` kbd pill. `onClick` opens CommandPalette. `hover:border-violet-500/30`

**Right cluster** (`flex items-center gap-1`):
- Theme toggle (ghost 36px): Moon/Sun icon
- Mail (ghost 36px): cyan dot 6px `absolute top-1.5 right-1.5 border-2 border-[var(--bg)]`
- Notifications (ghost 36px): Bell icon, violet badge "3" `absolute -top-0.5 -right-0.5 text-[10px]`
- User dropdown (shadcn DropdownMenu): trigger = avatar 32px from `dicebear.com/7.x/avataaars/svg?seed={username}` with violet border + green online dot. Dropdown content (glass 220px): avatar + name + email + role badge → Separator → Profile / Settings items → Separator → "Log out" in `text-red-400`

### `src/components/layout/command-palette.tsx` (`'use client'`)

State: `isOpen`, `query`, `selectedIndex`. Keyboard: `⌘F` open, `Esc` close, `↑↓` navigate, `Enter` go.

Overlay: `fixed inset-0 bg-black/60 backdrop-blur-sm z-[100]` fadeIn 150ms. Panel: `fixed top-[20vh] left-1/2 -translate-x-1/2 w-[600px] glass rounded-[16px] shadow-2xl` scaleIn 200ms.

Input row (`px-4 py-3 border-b`): Search icon + `flex-1` transparent input (placeholder: "Search pages, agents, actions...") + `Esc` kbd.

Results: groups labeled "Pages", "Actions", "Recent". Each item: `flex items-center gap-3 px-4 py-2.5 rounded-[8px] mx-2 hover:bg-white/5`, icon 16px + label 14px + path 12px `ml-auto`. Active item highlighted via keyboard nav.

### `src/components/layout/page-header.tsx`
```tsx
interface PageHeaderProps { title: string; description?: string; actions?: React.ReactNode }
// flex items-start justify-between mb-6
// Left: h1 text-[24px] font-bold text-[var(--text-1)] + p 14px text-[var(--text-2)] mt-1
// Right: actions slot
```

### Loading Skeletons

**`src/components/ui/skeleton.tsx`**: Variants: text (`h-4`), rect, circle. Shimmer animation: `bg-gradient` sweep left→right 1.5s infinite (`from-white/[0.03] via-white/[0.07] to-white/[0.03]`).

Each `loading.tsx` mirrors the page grid with Skeleton placeholders at matching sizes.

---

## PART 3 — UI Component Library

All in `src/components/ui/`. All `'use client'`.

### `stats-card.tsx`
```ts
interface StatsCardProps {
  title: string; value: string | number; icon: LucideIcon
  trend?: number; trendLabel?: string
  variant?: 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info'
}
```
Style: `glass glass-hover p-5 rounded-[var(--radius-lg)]`. Top row: title 13px text-3 + variant-colored icon button (ghost 32px). Value: 32px bold with counter animation from 0 on mount (requestAnimationFrame). Bottom: trend Badge (success/danger with ArrowUpRight/ArrowDownRight) + trendLabel 12px text-3.

Icon variant backgrounds: primary=`violet-900/30 text-violet-400`, success=`green-900/30 text-green-400`, warning=`amber-900/30 text-amber-400`, danger=`red-900/30 text-red-400`, info=`cyan-900/30 text-cyan-400`, default=`white/5 text-2`

### `data-table.tsx`
```ts
interface Column<T> { key: string; header: string; render?: (row: T, index: number) => React.ReactNode; className?: string }
interface DataTableProps<T> { columns: Column<T>[]; data: T[]; emptyMessage?: string; isLoading?: boolean }
```
Style: `glass overflow-hidden rounded-[var(--radius-lg)]`. `thead` bg `surface-2`, `th`: 11px uppercase tracking-wider text-3 border-b. `tr`: `hover:bg-white/[0.02]` border-b last:border-0. `td`: px-4 py-3.5 14px text-2. `isLoading`: 5 skeleton rows. Empty: py-16 centered text-3.

### `pagination.tsx`
```ts
interface PaginationProps { page: number; pageSize: number; total: number; onPageChange: (page: number) => void }
```
`flex items-center justify-between px-4 py-3 border-t`. Left: "Showing X–Y of Z" 13px text-3. Right: ChevronLeft/ChevronRight ghost buttons + current page text.

### `empty-state.tsx`
```ts
interface EmptyStateProps { icon: LucideIcon; title: string; description?: string; action?: React.ReactNode }
```
`flex flex-col items-center justify-center py-16 px-4 border border-dashed border-[var(--border-2)] rounded-[var(--radius-lg)]`. Icon 48px text-3, title 16px 600 mt-4, description 14px text-3 mt-2 max-w-[280px] text-center, action mt-6.

### `status-indicator.tsx`
```ts
interface StatusIndicatorProps { status: 'active'|'inactive'|'warning'|'error'|'processing'; label?: string; pulse?: boolean }
```
8px circle + optional label 12px text-3. Colors: active=green-400, inactive=zinc-500, warning=amber-400, error=red-400, processing=cyan-400. `pulse` → `animate-pulse`.

### `stepper.tsx`
```ts
interface StepperProps { steps: string[]; currentStep: number }
```
`flex items-center w-full`. Each step: circle 32px (completed=violet-600 + Check, active=violet border + inner dot + ring pulse, pending=border-2 text-3 + step number). Label 12px centered below (completed=violet-400, active=text-1 500, pending=text-3). Connector line `flex-1 h-px mx-3` (completed=violet-600, pending=border-2).

### `code-editor.tsx`
```ts
interface CodeEditorProps { value: string; onChange: (val: string) => void; label?: string; placeholder?: string; minHeight?: number; error?: string; charLimit?: number }
```
`bg-[var(--surface-3)] font-mono text-[13px] text-green-300 border border-[var(--border)] rounded-[var(--radius-md)] p-4 min-h-[200px] resize-y`. Character counter (top-right, 11px text-3, red when >90%).

### `tag-input.tsx`
```ts
interface TagInputProps { tags: string[]; onChange: (tags: string[]) => void; placeholder?: string; label?: string }
```
Pill container: glass input style `flex flex-wrap gap-1.5 p-2 min-h-[44px]`. Tag pills: `bg-violet-900/50 text-violet-300 rounded-full px-2.5 py-1 text-[12px]` + X button. Inline input `flex-1 min-w-[120px]`. Enter adds, Backspace on empty removes last, duplicates ignored.

### `key-value-editor.tsx`
```ts
interface KVPair { key: string; value: string }
interface KeyValueEditorProps { items: KVPair[]; onChange: (items: KVPair[]) => void; label?: string }
```
Rows: `flex gap-2 items-center` — key Input (flex-1) + ":" separator + value Input (flex-1) + Trash2 ghost xs. "Add field" ghost sm + Plus icon below.

---

## PART 4 — Auth Pages

All auth pages are `'use client'`. Use Server Component boundary for `metadata` export + Client Component for the form.

### Login (`src/app/(auth)/login/page.tsx`)

**Split layout** (`flex min-h-screen`):

**Left panel** (`hidden md:flex w-3/5`, dark gradient bg, `border-r`):
- Top: Logo (violet dot + "ONE-AI" 20px 700)
- Hero (`mt-auto mb-12`): "Manage your AI Agents at enterprise scale" 48px 800, "AI Agents" span with `bg-gradient-to-r from-violet-400 to-cyan-400 bg-clip-text text-transparent`
- Feature bullets (`mt-8 flex flex-col gap-4`): Each = icon in 36px violet-bg rounded + heading 15px 600 + desc 13px text-3
  - Sparkles — "Intelligent Routing" — "Auto-route tasks to the best-fit agent"
  - Shield — "Guardrails Built-in" — "Safety rules enforced at every invocation"
  - Zap — "Real-time Execution" — "Monitor runs, logs, and cost live"

**Right panel** (`flex-1 flex flex-col justify-center items-center p-12`):
- Form card (`glass w-full max-w-[380px] p-8 rounded-[20px]`): "Welcome back" 24px 700, "Sign in to ONE-AI" 14px text-3 mb-8
- Email Input + Password Input (mt-4) + Remember me toggle + "Forgot password?" link
- "Sign in" primary `w-full mt-6`
- Error alert (red) if `error.message`
- Divider "or continue with" (text-[12px] text-3)
- OAuth row: Google SVG + "Google" (secondary w-full) + Github icon + "GitHub" (secondary w-full)
- Footer: "Don't have an account? Create one →" → `/register`

Form logic: `authApi.login(email, password)` → store token in localStorage + cookie → redirect admin→`/admin/dashboard`, member→`/client/dashboard`

### Register (`src/app/(auth)/register/page.tsx`)

Centered glass card `max-w-[440px] p-8`:
- Full Name, Work Email, Organization ID (hint: "Your admin will provide this"), Password (min 8)
- Inline Zod errors on submit
- "Create Account" primary `w-full mt-8`
- Link: "Already have an account? Sign in" → `/login`

### Forgot Password (`src/app/(auth)/forgot-password/page.tsx`)

Centered glass card `max-w-[420px] p-8`. Stepper: ["Email", "Verify OTP", "New Password"].

**Step 0 — Email:** ArrowLeft back link, email Input, "Send Code" primary
**Step 1 — OTP:** "Check your email" heading, 6 individual inputs (48×52px glass, auto-focus next on entry, focus prev on backspace), "Verify Code" primary + "Resend code" ghost
**Step 2 — New Password:** two password inputs, Zod passwords-match + min 8, "Reset Password" primary
**Step 3 — Success:** CheckCircle2 64px green, "Password reset!" heading, "Back to sign in" primary → `/login`

---

## PART 5 — Client Dashboard

### `src/app/(dashboard)/client/dashboard/page.tsx` (Server Component)
`export const metadata = { title: 'Dashboard' }`. Renders `<DashboardContent />` (client component).

### `src/app/(dashboard)/client/dashboard/loading.tsx`
Mirror dashboard grid: 4 metric skeletons (`h-[120px]`) + chart skeleton (`h-[280px]`) + 3 bottom skeletons + table skeleton.

### `src/components/dashboard/metric-cards.tsx`
Four StatsCards using `useAgents()`, `useTools()`, `useDbConnections()`:
- Total Agents · `agentsData?.total ?? 47` · Bot · primary · trend +12
- Active Now · 23 · Activity · success · trend +5
- Total Tools · `toolsData?.total ?? 18` · Wrench · info · trend +2
- DB Connections · `dbData?.total ?? 6` · Database · warning · trend 0

### `src/components/dashboard/agent-analytics-chart.tsx`
Period state: `'7D' | '30D' | '90D'`.

Glass card `p-5`: "Agent Activity" 15px 600 + period pill tabs (active: `bg-violet-900/50 text-violet-300`).

Recharts `AreaChart` height=240, `ResponsiveContainer`. Two `<Area>` series: `executions` (stroke `#7c3aed`, `fill="url(#violetGrad)"`) + `messages` (stroke `#06b6d4`, `fill="url(#cyanGrad)"`). Both `type="monotone" animationDuration=800`. SVG `<defs>` gradients: violetGrad top `rgba(124,58,237,0.3)` → transparent, cyanGrad top `rgba(6,182,212,0.2)` → transparent. Custom dark glass tooltip. XAxis tick 11px text-3. Horizontal gridlines only (`stroke rgba(255,255,255,0.04)`).

Mock data: 7D = 7 points · executions `[12,19,8,24,31,18,27]` · messages `[45,67,32,89,102,71,95]`. 30D and 90D: realistic upward trend with variance.

### `src/components/dashboard/agent-execution-status.tsx`
"Connected Modules" header + "View all →" link. 4 mock rows (flex, dicebear avatar 32px, module name + user name, status Badge):
- Sarah K. · Data Pipeline · Completed
- Marcus T. · API Gateway · In Progress
- Elena V. · ML Classifier · Pending
- James R. · Report Builder · Completed

"Add Module" ghost `w-full mt-3 border border-dashed` + Plus icon.

### `src/components/dashboard/task-completion-chart.tsx`
Recharts `PieChart` donut: 160px, `innerRadius=55 outerRadius=75`. Data: Completed 41% `#22c55e`, In Progress 35% `#7c3aed`, Pending 24% `#3f3f46`. No labels on chart. Center overlay: "41%" 20px 700 + "complete" 11px text-3. Legend below.

### `src/components/dashboard/system-alerts-card.tsx`
"Reminders" + Badge "2". Alert 1 (glass inner, `border-l-4 border-violet-500`): Calendar icon + "System Sync" Badge warning "Today", "02:00 pm – 04:00 pm", "Start Sync" primary sm. Alert 2: AlertCircle amber + "API rate limit at 80%" + "12 min ago".

### `src/components/dashboard/compute-tracker.tsx`
Glass card `relative overflow-hidden`, deep violet overlay (`rgba(30,15,60,0.5)`). "Active Session" header + StatusIndicator active pulse. Timer (ticking via useEffect): "01:24:08" 42px Geist Mono 700 + "Session duration" 12px text-3. Controls: Pause 48px circle `bg-white/10` toggles to Play, Stop 48px `bg-red-500/20`. Resources: CPU 67% violet, MEM 45% cyan, API 38% amber — each with `h-1.5` progress bar.

### `src/components/dashboard/agent-list-card.tsx`
Uses `useAgents()`. Header: "Your Agents" + Badge "23 active" + search Input (glass 240px) + Filter ghost. DataTable columns: Name (initials avatar + name), Status (StatusIndicator + Badge), Prompt (mono 12px truncated 60 chars), Created, Actions (Chat → playground, Edit2, Trash2 → delete confirm modal). `<Pagination />` below.

### Dashboard Layout (inside `DashboardContent` client component)
```tsx
<PageHeader title="Good morning, Sufyan 👋" description="Here's what's happening with your agents today."
  actions={<Button variant="primary" href="/client/agents/create"><Plus /> New Agent</Button>} />

<div className="grid grid-cols-12 gap-5">
  {/* Row 1 — 4 metric cards */}
  <div className="col-span-3"><MetricCards /></div>  {/* × 4 */}

  {/* Row 2 */}
  <div className="col-span-8"><AgentAnalyticsChart /></div>
  <div className="col-span-4"><AgentExecutionStatus /></div>

  {/* Row 3 */}
  <div className="col-span-4"><TaskCompletionChart /></div>
  <div className="col-span-4"><SystemAlertsCard /></div>
  <div className="col-span-4"><ComputeTracker /></div>

  {/* Row 4 */}
  <div className="col-span-12"><AgentListCard /></div>
</div>
```
Staggered animation: `style={{ animationDelay: `${index * 50}ms` }} className="animate-slideUpFade"`

---

## PART 6 — Agents Pages

### `src/app/(dashboard)/client/agents/page.tsx` → renders `<AgentsPageContent />`

`AgentsPageContent` (`'use client'`):
- State: `view ('grid'|'table')`, `search`, `filterStatus`, `deleteTarget`, `page`
- Uses: `useAgents(page)`, `useToast()`
- PageHeader: title="Agents", actions=Link primary → `/client/agents/create` "Create Agent"
- Toolbar: search Input (280px), status Select (All/Active/Inactive), view toggle (LayoutGrid | Table2 icons)

**Card Grid** (`view='grid'`, `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4`):
Each `AgentCard` (`glass glass-hover p-5`): initials avatar 48px + status Badge (top-right absolute), name 16px 600 mt-3, "GPT-4o" cyan badge, prompt excerpt 13px text-3 line-clamp-2, Separator, stats row (Wrench "5 tools" · Clock "Active 2h ago"), action buttons (Chat → playground, Edit2, Trash2).

**Table view**: DataTable — Name | Status | System Prompt | Created | Actions

**Delete Modal** (shadcn Dialog): confirm message with agent name, "Cancel" secondary + "Delete" danger → `agentsApi.delete` → toast → refetch.

### `src/app/(dashboard)/client/agents/create/page.tsx` (`'use client'`)

State: `step (0–3)`, `formData`. Zod validation per step.

PageHeader: "Create Agent" + back link ← Agents. Stepper: ["Identity", "Prompt & Guardrails", "Tools", "Review"]

**Step 0 — Identity** (two-col):
- Left: Name Input + Description Textarea + Avatar color swatches (8 × 32px circles, selected = ring-2 + scale-110)
- Right: Live preview card (avatar + name + "Draft" badge + description)

**Step 1 — Prompt & Guardrails** (full width):
- CodeEditor, `label="System Prompt"`, `charLimit=4000`
- Collapsible "Prompt Templates": 2×2 grid of clickable template cards (Customer Support · Data Analysis · Code Review · General Assistant)
- Guardrails glass card: header + Toggle. InfoBox description. Textarea visible only when toggle on.

**Step 2 — Tools** (two-col):
- Left: search Input + tool cards (Checkbox + Wrench icon + name + registry Badge + description). Mock: SQL Query, Web Search, Email Sender, PDF Reader, REST API Caller, Slack Notifier. "Create new tool +" ghost → `/client/tools/create` (new tab)
- Right (sticky): "Selected Tools" label + count Badge. Selected tool pills (`bg-violet-900/50 text-violet-300` rounded-full + X). Empty dashed border state.

**Step 3 — Review**:
- Banner: glass `border-violet-500/20`, CheckCircle2 violet + "Ready to deploy"
- Summary grid 2-col: Identity card + Prompt card + Tools card (col-span-2), each with "Edit" button top-right
- "Deploy Agent" primary lg `w-full mt-6` (Rocket icon → Loader2 spin when loading → success toast → `/client/agents`)

Navigation row: "← Back" ghost sm + "Next →" primary sm (disabled if validation fails).

---

## PART 7 — Tools & DB Connections Pages

### Tools List (`src/app/(dashboard)/client/tools/page.tsx`)
Client component using `useTools()`. PageHeader "Tools" + "Create Tool" primary → `/client/tools/create`.

DataTable: Name (Wrench cyan + name) | Description (truncate 80) | Registry ID (Badge neutral font-mono) | DB ("Connected" success or "None" neutral) | Created | Actions (Edit2 + Trash2). Pagination + EmptyState (Wrench, "No tools yet"). Delete confirm modal.

### Create Tool (`src/app/(dashboard)/client/tools/create/page.tsx`)
Glass card `max-w-2xl mx-auto p-6`:
- Textarea: User Description (required, `min 10`, hint: "Written for the AI")
- Input: Tool Registry ID (required, `leftIcon=Hash`, hint: "Find in the ONE-AI Tool Registry docs")
- Input: Display Name (optional, "Defaults to registry name")
- Textarea: Internal Description
- Select: DB Connection (None + connected DBs, hint: "Required only for database-type tools")

Row `justify-end`: Cancel secondary + "Register Tool" primary.

### DB Connections List (`src/app/(dashboard)/client/db-connections/page.tsx`)
Uses `useDbConnections()`. PageHeader "DB Connections" + "Add Connection" primary.

DataTable: Connection (Database cyan + masked string `first-20-chars***@...` font-mono 12px) | Tool (linked name or "Unlinked") | Created | Actions (Eye/EyeOff toggle — show full string in tooltip only, never plain DOM + Trash2 danger).

EmptyState icon=Database. Delete modal with warning: "Removing this connection may break tools that depend on it."

### Create DB Connection (`src/app/(dashboard)/client/db-connections/create/page.tsx`)
Glass card `max-w-xl mx-auto p-6`:
- Input: Tool ID (required, `leftIcon=Wrench`)
- Input: Connection String (required, `type="password"`, `leftIcon=Lock`, placeholder: `postgresql://user:pass@host:5432/dbname`, hint: "Stored encrypted — never exposed in API responses")
- InfoBox (`border-l-4 border-cyan-500`): Info icon + "Connection strings are encrypted at rest using AES-256."

Row `justify-end`: Cancel secondary + "Save Connection" primary (Lock icon).

---

## PART 8 — Playground Page

### `src/app/(dashboard)/client/playground/page.tsx` (`'use client'`)
Uses `-m-6` wrapper to cancel parent padding. State: `selectedAgentId`, `messages[]`, `inputValue`, `isTyping`.

**Outer div:** `flex h-[calc(100vh-56px)] -m-6`

**Left panel** (`w-[280px] bg-[#0c0c13] border-r flex flex-col`):
- Header: "Agents" 14px 600 + count Badge
- Search Input (glass sm, `placeholder="Search agents..."`)
- Agent list (`flex-1 overflow-y-auto`): Each item = avatar 36px (initials + avatarColor) + name 14px 500 + last-active 11px text-3 + StatusIndicator ml-auto. Active: `bg-violet-900/30 border border-violet-500/20`. Mock agents: Nexus-7 (active, 2m) · DataSift (active, 1h) · ClarityBot (inactive, 2d) · QueryMaster (active, 30m) · CodeReview (active, just now)

**Right panel** (`flex-1 flex flex-col`):

Chat topbar (`flex items-center justify-between px-5 py-3 border-b flex-shrink-0`): avatar 32px + name 15px 600 + StatusIndicator + "Online" 12px | Settings ghost sm + MoreVertical ghost sm

Message thread (`flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-4`):
- Date separator: "Today" glass pill centered
- Agent message: avatar 28px + bubble `bg-white/[0.04] border rounded-[14px] rounded-tl-[4px] px-4 py-3 max-w-[70%]` 14px text-1 leading-[1.6] + timestamp 11px text-3
- User message: `flex-row-reverse`, bubble `bg-gradient-to-br from-violet-600 to-violet-700 rounded-[14px] rounded-tr-[4px]` text-white
- Code block: `bg-[var(--surface-3)]` + header bar (language badge + Copy button → Check after click) + `p-4 font-mono text-[13px] text-green-300 whitespace-pre overflow-x-auto`
- Typing indicator: agent bubble with 3 dots `animate-bounce` staggered

Input area (`px-4 py-3 border-t flex items-end gap-3`): glass container `rounded-[14px]`: Paperclip + AtSign ghost sm (left) + auto-resize textarea (`min-h-[24px] max-h-[160px]`, Enter sends, Shift+Enter newline) + "GPT-4o" cyan badge + Send primary sm (ArrowUp icon, disabled when empty)

Send handler: append user message → clear input → `setIsTyping(true)` → setTimeout 1200ms → append mock response → `setIsTyping(false)`

---

## PART 9 — Analytics Page

### `src/app/(dashboard)/client/analytics/page.tsx`
PageHeader "Analytics" + DateRangePicker (glass pill, CalendarDays + "Last 30 days" + ChevronDown).

**Row 1 — KPI strip** (`grid grid-cols-5 gap-4`):
- Total Executions · "12,847" · Zap · primary · trend +18
- Avg Response · "1.2s" · Timer · success · trend -8 (negative = improvement)
- Success Rate · "98.7%" · CheckCircle · success · trend +0.3
- Tokens Used · "4.2M" · Cpu · warning · trend +23
- Est. Cost · "$124" · DollarSign · danger · trend +19

**Row 2** (`grid grid-cols-12 gap-5 mt-5`):

"Daily Executions" area chart (`col-span-8`, glass `p-5`): "Export" ghost xs Download icon. Recharts AreaChart height=280, two series (Executions violet, Errors red smaller). 30 data points trending up. Dark glass tooltip.

"Usage by Agent" donut (`col-span-4`, glass `p-5`): PieChart height=200 `innerRadius=65 outerRadius=90`. Data: Nexus-7 34% `#7c3aed`, DataSift 22% `#06b6d4`, QueryMaster 18% `#22c55e`, CodeReview 14% `#f59e0b`, Others 12% `#52525b`. Center: "47" 24px 700 + "agents" 12px. Legend list below (dot + name + % right-aligned).

**Row 3** (`grid grid-cols-12 gap-5 mt-5`):

"Response Time by Agent" bar chart (`col-span-6`, glass `p-5`): Recharts BarChart `layout="vertical"` height=220. YAxis: agent names width=100 fontSize=12. XAxis: milliseconds. Bar: violet gradient fill `radius=[0,4,4,0]`.

"Activity by Time" heatmap (`col-span-6`, glass `p-5`): 7×24 grid. Row labels Mon–Sun (10px text-3). Cells 20×20px `rounded-[3px]`. Color intensity: 0=`rgba(255,255,255,0.03)`, low=`#7c3aed26`, med=`#7c3aed66`, high=`#7c3aedCC`. Hover Tooltip: "Monday 2pm: 47 executions". X-axis hour labels every 4 cols.

---

## PART 10 — Admin Pages

### Admin Dashboard (`src/app/(dashboard)/admin/dashboard/page.tsx`)

**Row 1** (`grid grid-cols-3 gap-4`): Total Organizations · 24 · Building2 · info | Total Users · 187 · Users · primary | Total Agents · 847 · Bot · success

**Row 2** (`grid grid-cols-12 gap-5 mt-5`):

Recent Orgs table (`col-span-8`, glass): "Recent Organizations" + "View all →". DataTable: Name (Building2 icon) | Plan (Pro=violet, Starter=neutral, Enterprise=cyan) | Users count | Agents count | Status | Created. 8 mock orgs.

System Health (`col-span-4`, glass `p-5`): "System Status" + Badge success "All Operational". Services list: each = StatusIndicator + name + uptime Badge. API Gateway 99.98% · DB Cluster 99.99% · Task Queue 100% · Auth 99.97% · Storage warning 98.2%. Separator. "Avg Response: 124ms" + green progress bar.

**Row 3** (`grid grid-cols-12 gap-5 mt-5`):

Activity Feed (`col-span-6`, glass): "Activity Log" + "Clear" ghost. Feed `max-h-[280px] overflow-y-auto`: each entry = colored icon in 28px rounded bg + message 13px + time 11px. 7 mock events.

Quick Actions (`col-span-6`, glass `p-5`): `grid grid-cols-2 gap-3`. Each card (glass glass-hover, text-center, icon 28px + label 14px + desc 12px text-3): UserPlus green "Invite User" | Building2 violet "Create Org" | Settings cyan "System Settings" | BarChart amber "Analytics (Coming Soon)".

### Organizations (`/admin/organizations/page.tsx`)
`useOrganizations()`. PageHeader + "Create Organization" primary. Toolbar: search + status filter. DataTable: Name | Description | Plan | Created | Actions. Pagination + Delete modal + EmptyState (Building2).

### Create Organization — glass card `max-w-xl`: Name, Description, Plan Select (Starter/Pro/Enterprise). Cancel + Create.

### Users (`/admin/users/page.tsx`)
DataTable: Avatar+Name | Email | Role Badge | Org ID (font-mono) | Created. Read-only list (no delete). "Create User" primary.

### Create User — glass card `max-w-xl`: Name, Email, Password (hint: min 6 chars), Role Select (Member/Admin). Zod validation. Cancel + "Create User" (UserPlus icon).

### All Agents (`/admin/agents/page.tsx`)
Read-only platform view. DataTable: Name (Bot cyan icon) | Org ID (mono badge) | Prompt (truncated, mono 12px) | Guardrails (badge) | Created.

### System Settings (`/admin/settings/page.tsx`)
`grid grid-cols-2 gap-5`:

Glass card "General": Toggle "Maintenance Mode" (amber InfoBox "All users see maintenance page" when ON) + Separator + Select "Default LLM Model" (GPT-4o, Claude 3.5 Sonnet, Gemini 1.5 Pro, GPT-4o-mini).

Glass card "Security": Toggle "Require 2FA" (off) + Toggle "Session Timeout" (on) + Select "Session Duration" (15m/30m/1h/4h/8h, visible only when timeout on) + Toggle "Audit Logging" (on).

Save row (`col-span-2 flex justify-end`): "Save Changes" primary (Save icon) → success toast.

---

## PART 11 — Settings & Help Pages

### `src/app/(dashboard)/client/settings/page.tsx` (`'use client'`)

PageHeader "Settings". Uses `useAuth()` for current user.

Glass card "Profile" (`max-w-2xl`): Header with avatar 48px (dicebear seed=user.name). AmberInfoBox: "Profile details can only be updated by your administrator". Four disabled inputs (Full Name, Email, Organization ID font-mono, Role Select). Footer: "Request Changes" ghost sm (ExternalLink icon, mailto).

Glass card "Preferences" (`max-w-2xl mt-5`): Toggle rows: Dark Mode (bound to ThemeContext) + Separator + Email Notifications (on) + Desktop Notifications (off) + Weekly Digest (on). "Save Preferences" primary sm footer.

### `src/app/(dashboard)/client/help/page.tsx` (Server Component)

PageHeader "Help & Documentation".

`grid grid-cols-2 gap-5`:
- "API Reference" card (glass glass-hover): BookOpen 48px violet in `bg-violet-900/30 p-3 rounded-[14px]`, title, desc, "Open Docs" link (ExternalLink) → `http://localhost:8000/docs`
- "Contact Support" card: LifeBuoy 48px cyan in `bg-cyan-900/30`, "Contact Admin" secondary (Mail icon)

"Getting Started" card (`col-span-2`): 3-step guide (numbered circles 32px `bg-violet-600` + heading + desc):
1. Register your tools — "Go to Tools and connect your first integration"
2. Create an agent — "Use the Agent Wizard to configure and deploy"
3. Test in Playground — "Chat with your agent and iterate on the prompt"

"Create your first agent →" primary sm mt-6 → `/client/agents/create`

`grid grid-cols-2 gap-5 mt-5`:
- "Keyboard Shortcuts" glass card: each row = `flex justify-between` — label 13px + `kbd` glass pill font-mono. Shortcuts: ⌘F=Open command palette, ⌘K=New agent, ⌘/=Toggle sidebar, Esc=Close modal, ⇧⏎=New line, ⏎=Send message
- "System Info" glass card: key-value rows (border-b last:border-0), each 12px mono. Platform: ONE-AI v1.0.0, API: http://localhost:8000, Region: eu-west-1, Org: {user.organization_id}, Account: {user.email}. "Check API Status" ghost xs (Activity icon) mt-4.

---

## PART 12 — Contexts & Final Wiring

### `src/contexts/auth-context.tsx` (`'use client'`)
```ts
interface AuthContextValue {
  user: UserPublic | null; isAuthenticated: boolean; isLoading: boolean
  login: (email: string, password: string) => Promise<void>; logout: () => void
}
```
`login()`: call `authApi.login()` → store token in `localStorage` + cookie (`access_token=...; path=/`) → `setUser()` → redirect (admin → `/admin/dashboard`, member → `/client/dashboard`).

`logout()`: clear localStorage + cookie → `setUser(null)` → `/login`.

Mount rehydration: read token from localStorage → `authApi.me()` → `setUser()`.

### `src/contexts/theme-context.tsx` (`'use client'`)
```ts
interface ThemeContextValue { theme: 'dark'|'light'; toggleTheme: () => void }
```
Default: `'dark'`. Persist: `localStorage` key `'ui-theme'`. Apply: `document.documentElement.setAttribute('data-theme', theme)`. Initialize before first paint to avoid flash.

### `src/contexts/sidebar-context.tsx` (`'use client'`)
```ts
interface SidebarContextValue {
  isCollapsed: boolean; variant: 'client'|'admin'
  toggleSidebar: () => void; setCollapsed: (v: boolean) => void
}
```
Auto-collapse at `< 1024px` (useEffect + ResizeObserver or `window.matchMedia`). Persist: `localStorage` key `'sidebar-collapsed'`. `SidebarVariantProvider` sets `variant` in admin/client sub-layouts.

### `src/hooks/use-toast.ts`
Interface: `{ id, type: 'success'|'error'|'warning'|'info', title?, message, duration? }`. `addToast()` auto-removes after duration (default 4000ms). Container: `fixed top-4 right-4 z-[100] flex flex-col gap-2`. Each toast: glass `w-[340px] px-4 py-3 border-l-4` (colored by type) + slideInRight 250ms + icon + title 13px 600 + message 12px text-3 + X close button. Max 3 toasts (FIFO).

### Final File Checklist

**`src/app/`** (18 files): layout, page, globals.css, not-found, error + (auth): layout, login, register, forgot-password + (dashboard): layout + admin: layout, dashboard, organizations, users, agents, settings + client: layout, dashboard, agents, tools, db-connections, playground, analytics, settings, help

**`src/components/`** (21 files): layout: sidebar, topnav, page-header, command-palette + ui: stats-card, data-table, pagination, empty-state, status-indicator, stepper, code-editor, tag-input, key-value-editor, skeleton + dashboard: metric-cards, agent-analytics-chart, agent-execution-status, agent-list-card, task-completion-chart, system-alerts-card, compute-tracker

**`src/hooks/`** (6): use-agents, use-tools, use-db-connections, use-organizations, use-toast, use-sidebar

**`src/lib/`** (9): utils + api: client, auth, agents, tools, db-connections, organizations, index + validations: auth, agent, tool, organization

**`src/contexts/`** (3): auth-context, theme-context, sidebar-context

**`src/types/index.ts`** · **`src/styles/tokens.css`** · **`src/middleware.ts`**

---

## PART 13 — Extended Types & Backend API Integration

> **Backend:** FastAPI at `http://localhost:8000`. MongoDB (Motor). Auth: JWT Bearer tokens. All list endpoints return `Page<T>`. Soft deletes on all resources.

### Updated `src/types/index.ts`

Add these types alongside existing ones:

```ts
// Tool Registry (global catalog of available tool implementations)
export interface ToolRegistryPublic {
  id: string
  name: string
  description?: string
  type: 'db' | 'http' | 'rag' | 'custom'
  is_active: boolean
  tool_schema?: Record<string, unknown>
  created_at: string
}

// Tracing (Langfuse-backed execution traces)
export interface TracePublic {
  id: string
  agent_id?: string
  session_id?: string
  name?: string
  input?: unknown
  output?: unknown
  timestamp: string
  latency?: number        // ms
  total_cost?: number     // USD
  total_tokens?: number
  status?: 'success' | 'error' | 'partial'
}

export interface TraceObservation {
  id: string
  trace_id: string
  type: 'generation' | 'span' | 'event'
  name?: string
  input?: unknown
  output?: unknown
  start_time: string
  end_time?: string
  latency?: number
  model?: string
  prompt_tokens?: number
  completion_tokens?: number
  cost?: number
}

export interface TraceDetail extends TracePublic {
  observations: TraceObservation[]
}

export interface TraceStats {
  total_traces: number
  total_cost: number
  total_tokens: number
  avg_latency: number
  success_rate: number
}

export interface SessionPublic {
  id: string
  user_id: string
  agent_id: string
  created_at: string
  message_count?: number
  last_message_at?: string
}

// Chat
export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
  trace_id?: string
}

export interface ChatRequest {
  agent_id: string
  message: string
  session_id?: string
}

export interface ChatResponse {
  reply: string
  session_id: string
  trace_id?: string
}

// Extended Agent (includes new backend fields)
export interface AgentPublic {
  id: string
  organization_id: string
  name: string
  description?: string
  user_description?: string
  prompt?: string
  instructions?: string
  guardrails?: string
  tool_ids?: string[]
  rag_ids?: string[]
  created_by: string
  created_at: string
}

// Extended Tool (includes all backend fields)
export interface ToolPublic {
  id: string
  organization_id: string
  name?: string
  description?: string
  user_description: string
  db_conn_id?: string
  tool_id: string       // FK to ToolRegistry.id
  created_at: string
}

// DB Connection with optional schema
export interface DbConnectionPublic {
  id: string
  organization_id: string
  tool_id: string
  connection_string: string   // masked in API responses
  created_at: string
}

export interface DbSchema {
  type: 'sql' | 'mongodb'
  tables?: Array<{ name: string; columns: Array<{ name: string; type: string; nullable: boolean }> }>
  collections?: string[]
  databases?: string[]
}
```

### New `src/lib/api/chat.ts`

```ts
import { api } from './client'
import type { ChatResponse } from '@/types'

export const chatApi = {
  send: (agentId: string, message: string, sessionId?: string) =>
    api.post<ChatResponse>('/chat', { agent_id: agentId, message, session_id: sessionId }),
}
```

**Note:** Pass `X-Session-Id` header for continuity. Modify `apiRequest` in `client.ts` to accept extra headers, or pass `sessionId` in request body (backend accepts both).

### New `src/lib/api/tool-registry.ts`

```ts
import { api } from './client'
import type { ToolRegistryPublic, Page } from '@/types'

export const toolRegistryApi = {
  list:   (page = 1, page_size = 20) => api.get<Page<ToolRegistryPublic>>(`/tool-registry?page=${page}&page_size=${page_size}`),
  get:    (id: string) => api.get<ToolRegistryPublic>(`/tool-registry/${id}`),
  create: (body: { name: string; type: string; description?: string; tool_schema?: Record<string, unknown> }) =>
    api.post<ToolRegistryPublic>('/tool-registry', body),
  update: (id: string, body: Partial<ToolRegistryPublic>) => api.put<ToolRegistryPublic>(`/tool-registry/${id}`, body),
  delete: (id: string) => api.delete<void>(`/tool-registry/${id}`),
}
```

### New `src/lib/api/tracing.ts`

```ts
import { api } from './client'
import type { TracePublic, TraceDetail, TraceStats, SessionPublic, Page } from '@/types'

export const tracingApi = {
  listTraces:  (params?: { agent_id?: string; session_id?: string; page?: number; page_size?: number }) => {
    const q = new URLSearchParams({ page: '1', page_size: '20', ...Object.fromEntries(Object.entries(params ?? {}).filter(([,v]) => v != null).map(([k,v]) => [k, String(v)])) })
    return api.get<Page<TracePublic>>(`/traces?${q}`)
  },
  getTrace:    (id: string) => api.get<TraceDetail>(`/traces/${id}`),
  getStats:    (agent_id?: string) => api.get<TraceStats>(`/traces/stats${agent_id ? `?agent_id=${agent_id}` : ''}`),
  listSessions: (page = 1, page_size = 20) => api.get<Page<SessionPublic>>(`/sessions?page=${page}&page_size=${page_size}`),
  agentTraces: (agent_id: string, page = 1) => api.get<Page<TracePublic>>(`/agents/${agent_id}/traces?page=${page}`),
  agentStats:  (agent_id: string) => api.get<TraceStats>(`/agents/${agent_id}/stats`),
}
```

### New `src/lib/api/users.ts`

```ts
import { api } from './client'
import type { UserPublic } from '@/types'

export const usersApi = {
  list:   (page = 1, page_size = 20) => api.get<Page<UserPublic>>(`/users?page=${page}&page_size=${page_size}`),
  create: (body: { name: string; email: string; password: string; role: 'admin' | 'member' }) =>
    api.post<UserPublic>('/auth/users', body),
}
```

### Updated `src/lib/api/db-connections.ts`

Add schema endpoint:
```ts
export const dbConnectionsApi = {
  // ... existing list, get, create, update, delete
  getSchema: (id: string) => api.get<DbSchema>(`/db-connections/${id}/schema`),
}
```

### Updated `src/lib/api/index.ts`

Export all new modules:
```ts
export { agentsApi }      from './agents'
export { toolsApi }       from './tools'
export { dbConnectionsApi } from './db-connections'
export { organizationsApi } from './organizations'
export { authApi }        from './auth'
export { chatApi }        from './chat'
export { toolRegistryApi } from './tool-registry'
export { tracingApi }     from './tracing'
export { usersApi }       from './users'
```

### New hooks

**`src/hooks/use-tracing.ts`**: Same pattern as `use-agents.ts` — wraps `tracingApi.listTraces()` with `loading/error/page/refetch`. Add `agentId` param for filtering.

**`src/hooks/use-sessions.ts`**: Wraps `tracingApi.listSessions()`.

**`src/hooks/use-tool-registry.ts`**: Wraps `toolRegistryApi.list()`.

**`src/hooks/use-chat.ts`**:
```ts
'use client'
import { useState, useCallback, useRef } from 'react'
import { chatApi } from '@/lib/api'
import type { ChatMessage } from '@/types'

export function useChat(agentId: string | null) {
  const [messages, setMessages]     = useState<ChatMessage[]>([])
  const [isTyping, setIsTyping]     = useState(false)
  const [error, setError]           = useState<string | null>(null)
  const sessionIdRef                = useRef<string | undefined>(undefined)

  const send = useCallback(async (text: string) => {
    if (!agentId) return
    setMessages(prev => [...prev, { role: 'user', content: text }])
    setIsTyping(true); setError(null)
    try {
      const res = await chatApi.send(agentId, text, sessionIdRef.current)
      sessionIdRef.current = res.session_id
      setMessages(prev => [...prev, { role: 'assistant', content: res.reply, trace_id: res.trace_id }])
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to send')
    } finally {
      setIsTyping(false)
    }
  }, [agentId])

  const reset = useCallback(() => {
    setMessages([]); sessionIdRef.current = undefined; setError(null)
  }, [])

  return { messages, isTyping, error, send, reset, sessionId: sessionIdRef.current }
}
```

---

## PART 14 — Edit Pages (Agents, Tools, DB Connections)

### Agent Edit — `src/app/(dashboard)/client/agents/[id]/edit/page.tsx` (`'use client'`)

PageHeader: "Edit Agent" + back `← /client/agents`. Stepper same as create ["Identity", "Prompt & Guardrails", "Tools", "Review"] but pre-populated.

On mount: `agentsApi.get(id)` → populate `formData`. Step 3 button says "Save Changes" (not "Deploy"). On submit: `agentsApi.update(id, formData)` → success toast → `router.push('/client/agents')`.

URL pattern: `/client/agents/[id]/edit` — add `id` param to `AgentsPageContent` Edit2 button href.

### Agent Detail — `src/app/(dashboard)/client/agents/[id]/page.tsx` (`'use client'`)

On mount: `agentsApi.get(id)` + `tracingApi.agentStats(id)` + `tracingApi.agentTraces(id)`. PageHeader: agent name + back + "Edit" button → `edit` + "Chat" button → `/client/playground?agent={id}`.

Three panels row:
- Left (`col-span-4`): glass card with agent metadata (created, description, prompt excerpt, guardrails badge, tools count)
- Center (`col-span-4`): StatsCard grid — Total Traces, Total Cost ($), Avg Latency (ms), Success Rate (%)  — from `agentStats`
- Right (`col-span-4`): recent tool pills (using `tool_ids` resolved to names)

Below: `DataTable` of recent traces (from `agentTraces`) — Timestamp | Input (truncated 60) | Latency | Tokens | Cost | Status → click row opens trace detail sheet.

### Tool Edit — `src/app/(dashboard)/client/tools/[id]/edit/page.tsx` (`'use client'`)

Same glass card as create-tool, pre-populated from `toolsApi.get(id)`. On submit: `toolsApi.update(id, data)` → toast → back.

### DB Connection Edit — `src/app/(dashboard)/client/db-connections/[id]/edit/page.tsx` (`'use client'`)

Same glass card as create-db-connection. Password input shows placeholder `••••••••••` (don't pre-fill for security). On submit: `dbConnectionsApi.update(id, data)` — warn user "Updating the connection string will re-encrypt and re-fetch the schema." InfoBox `border-l-4 border-amber-500`.

---

## PART 15 — Tool Registry Browser

### Admin Tool Registry List — `src/app/(dashboard)/admin/tool-registry/page.tsx`

Uses `useToolRegistry()`. PageHeader "Tool Registry" + "Add Tool Type" primary → `/admin/tool-registry/create`.

DataTable columns:
- Name (Wrench cyan icon + name)
- Type (Badge: db=amber, http=cyan, rag=violet, custom=neutral)
- Schema (Badge "Has schema" success | "No schema" neutral)
- Status (StatusIndicator active/inactive + Badge)
- Created
- Actions (Edit2 + Trash2 soft-delete confirm modal)

EmptyState (Wrench, "No tool types in registry yet").

### Admin Create Tool Type — `src/app/(dashboard)/admin/tool-registry/create/page.tsx`

Glass card `max-w-2xl mx-auto p-6`:
- Input: Name (required)
- Select: Type — Database (`db`) | HTTP Endpoint (`http`) | RAG Source (`rag`) | Custom (`custom`)
- Textarea: Description
- Toggle: "Active" (default on)
- KeyValueEditor labeled "Tool Schema" — key = field name, value = JSON type string (string/number/boolean/object). Hint: "Defines expected inputs for this tool."

Cancel + "Register Tool Type" primary.

### Updated Create Tool Flow (Client) — browse registry

In Step 2 of agent creation and in Create Tool page, replace hardcoded mock tool list with real data from `useToolRegistry()`.

**`src/app/(dashboard)/client/tools/create/page.tsx`** update:
- Replace the static "Tool Registry ID" text input with a `<ToolRegistrySelector />` component
- `ToolRegistrySelector`: search Input (glass) + scrollable list of registry items (from `useToolRegistry()`) — each row = checkbox + name Badge type + description 12px. Selecting sets `tool_id`. Loading skeleton 5 rows. EmptyState (Wrench, "No tools in registry").

---

## PART 16 — Real Playground Chat Integration

### Updated `src/app/(dashboard)/client/playground/page.tsx`

Replace mock setTimeout logic with real `useChat` hook. Add session management.

**State changes:**
- Remove `messages` / `isTyping` local state → get from `useChat(selectedAgentId)`
- Add `sessions: SessionPublic[]` from `useSessionsForAgent(selectedAgentId)` — new endpoint `/sessions`
- `sessionId` is managed inside `useChat` via `sessionIdRef`

**Left panel additions (below agent list):**
- Separator + "Sessions" header 12px text-3 (visible only when agent selected)
- Session list (last 5): session item = Chat icon 14px + relative date + message count badge. Click → `chat.reset()` then load session history (future: `GET /sessions/{id}/messages`). "New Chat" ghost xs + Plus icon (calls `chat.reset()`)

**Chat flow change:**
```
send button → chat.send(inputValue) → useChat appends user msg → calls POST /chat → appends assistant reply
```

**Error display:** If `chat.error`, show red toast with message. Show retry button if last message was from user.

**Session header:** Show "Session: {sessionId.slice(-8)}" 10px text-3 mono next to agent name when session active.

**Trace link per message:** If `msg.trace_id`, show small "Trace →" link 10px text-3 bottom-right of assistant bubble → opens `/client/tracing/{trace_id}` in new tab.

**Preselect from URL:** If query param `?agent={id}` present on mount, auto-select that agent.

---

## PART 17 — Tracing & Observability Page

### Add to sidebar (CLIENT variant) under "MENU":
- `/client/tracing` — Activity — Traces

### `src/app/(dashboard)/client/tracing/page.tsx` → renders `<TracingPageContent />`
### `src/app/(dashboard)/client/tracing/loading.tsx`

`TracingPageContent` (`'use client'`):
State: `activeTab ('traces'|'sessions')`, `filterAgentId`, `filterSessionId`, `selectedTrace`, `page`.

PageHeader "Traces & Observability".

**Stats strip** (`grid grid-cols-4 gap-4`): uses `tracingApi.getStats()` on mount.
- Total Traces · `stats.total_traces` · Activity · primary
- Total Cost · `$${stats.total_cost.toFixed(4)}` · DollarSign · warning
- Avg Latency · `${stats.avg_latency}ms` · Timer · info
- Success Rate · `${stats.success_rate}%` · CheckCircle · success

**Tabs** (`flex gap-1 mt-5`): "Traces" + "Sessions" — shadcn Tabs.

**Traces tab:**
Toolbar: agent Select (All agents + list from `useAgents()`) + search Input.

DataTable (uses `useTracing(page, filterAgentId)`):
- Timestamp (formatted relative + absolute on hover Tooltip)
- Agent (name or ID badge mono)
- Input (truncated 60 chars, mono 12px)
- Latency (ms Badge: <500=success, 500-2000=warning, >2000=danger)
- Tokens (number)
- Cost ($0.0000 format)
- Status (StatusIndicator: success=active, error=error)
- Actions: Eye → open Trace Detail Sheet

**Trace Detail Sheet** (shadcn Sheet `side="right" className="w-[560px]"`):
Trigger: clicking Eye or row.

Sheet content:
- Header: trace ID mono 12px + timestamp + close button
- Meta row: agent name + session ID chip + status Badge
- Stats row: latency Badge + tokens + cost
- "Input" section: `bg-surface-3 font-mono text-[13px] p-4 rounded-[10px] max-h-[120px] overflow-y-auto`
- "Output" section: same styling
- "Observations" waterfall (from `traceDetail.observations`):
  Each observation: `flex items-start gap-3 py-3 border-b last:border-0`
  - Type Badge (generation=violet, span=cyan, event=neutral)
  - Name 13px 500 + model 11px text-3
  - Duration pill `${obs.latency}ms` right-aligned
  - Expandable: tokens/cost for generations (Click to expand)
  - Indent child spans with `ml-6 border-l border-[var(--border)]`

**Sessions tab:**
DataTable (uses `useSessions(page)`):
- Session ID (mono 10px badge, truncated)
- Agent (name)
- Messages (count Badge)
- Started (relative date)
- Last Active (relative date)
- Actions: MessageSquare → open playground with that session

Pagination below both tabs.

---

## PART 18 — DB Connection Schema Viewer

### `src/components/ui/db-schema-tree.tsx` (`'use client'`)

```ts
interface DbSchemaTreeProps { schema: DbSchema }
```

SQL schema: collapsible tree — each table = `Table2` icon + table name (click to expand) → indented column rows: `div ml-6 flex items-center gap-2 py-1 text-[12px]` — column name font-mono text-1 + type Badge neutral 10px + "NULL" chip amber if nullable.

MongoDB schema: each database = Database icon + name → collections listed as `Collection` rows with `Hash` icon.

Empty / loading skeleton variant.

### DB Connection Detail — add to list page Actions

Add `Eye` icon button in DB Connections DataTable (alongside existing Eye/EyeOff for connection string).

Opens a sheet `side="right" className="w-[480px]"` on click:
- Header: "Database Schema" + connection ID chip + close
- On mount: `dbConnectionsApi.getSchema(id)` → render `<DbSchemaTree />`
- Loading: 3 skeleton rows
- Error: "Schema not available" EmptyState with refresh button
- Bottom: "Last fetched: {created_at}" 11px text-3 + "Re-fetch" ghost sm → calls update endpoint

---

## PART 19 — Notification Center

### `src/components/layout/notification-center.tsx` (`'use client'`)

Sliding panel triggered from TopNav bell icon (replace `onClick` noop with toggle state).

Sheet `side="right" className="w-[360px]"` or custom panel `fixed right-0 top-[56px] h-[calc(100vh-56px)] w-[360px] bg-[var(--surface)] border-l border-[var(--border)] z-50 flex flex-col`.

Header (`flex items-center justify-between p-4 border-b`): "Notifications" 15px 600 + "Mark all read" ghost xs + X close.

Tabs `flex px-3 pt-2 gap-1` (active tab: `bg-violet-900/30 text-violet-300`):
- All (count Badge)
- Unread

Notification list (`flex-1 overflow-y-auto`):
Each item (`flex items-start gap-3 p-4 border-b hover:bg-white/[0.02] cursor-pointer`, unread has violet `w-2 h-2 rounded-full bg-violet-500 mt-1.5 flex-shrink-0`):
- Icon in 32px rounded bg (agent=Bot violet, tool=Wrench cyan, system=Settings neutral, alert=AlertTriangle amber)
- Content: title 13px 600 + message 12px text-3 mt-0.5 + time 11px text-3 mt-1
- "Dismiss" ghost xs on hover

Mock notifications (6 items, mix of types):
1. Bot violet — "Agent deployed" — "Nexus-7 is now active" — 2m ago
2. Wrench cyan — "Tool registered" — "SQL Query tool connected to prod DB" — 1h ago
3. AlertTriangle amber — "Rate limit warning" — "API usage at 80% of quota" — 3h ago
4. CheckCircle green — "Sync complete" — "All agents synced successfully" — Yesterday
5. Bot violet — "Agent error" — "DataSift failed on last execution" — Yesterday
6. Settings neutral — "Settings updated" — "Maintenance mode disabled" — 2d ago

Empty state: Bell 32px text-3 + "All caught up!" 14px 600 + "No notifications" 12px text-3.

Footer (`p-4 border-t`): "View all activity →" ghost sm full width.

### TopNav update

Replace noop bell onClick with `setNotificationOpen(prev => !prev)`. Render `<NotificationCenter open={notificationOpen} onClose={() => setNotificationOpen(false)} />` below TopNav (outside fixed header, inside portal or just rendered in Dashboard layout).

---

## PART 20 — Missing Loading Skeletons & Sidebar Updates

### Missing `loading.tsx` files

Add these (each mirrors the page's layout with Skeleton placeholders):

- `src/app/(dashboard)/client/tracing/loading.tsx`: 4 stat skeletons (`h-[100px]`) + tabs skeleton + table skeleton 6 rows
- `src/app/(dashboard)/client/agents/[id]/page.tsx loading`: 3 col skeletons + table
- `src/app/(dashboard)/admin/tool-registry/loading.tsx`: table skeleton

### Sidebar CLIENT variant — updated nav items

Under "MENU" section, add after Analytics:
```
/client/tracing  —  Activity  —  Traces
```

### Sidebar ADMIN variant — updated nav items

After Agents:
```
/admin/tool-registry  —  Package  —  Tool Registry
```

### Updated Folder Structure additions

```
src/
├── app/
│   └── (dashboard)/
│       ├── admin/
│       │   └── tool-registry/
│       │       ├── page.tsx + loading.tsx
│       │       └── create/page.tsx
│       └── client/
│           ├── tracing/
│           │   └── page.tsx + loading.tsx
│           ├── agents/
│           │   └── [id]/
│           │       ├── page.tsx         ← agent detail
│           │       └── edit/page.tsx    ← agent edit wizard (pre-filled)
│           ├── tools/
│           │   └── [id]/
│           │       └── edit/page.tsx
│           └── db-connections/
│               └── [id]/
│                   └── edit/page.tsx
└── components/
    ├── layout/
    │   └── notification-center.tsx
    └── ui/
        ├── db-schema-tree.tsx
        └── tool-registry-selector.tsx
```

### Updated Final File Checklist

**New pages** (11): admin/tool-registry, admin/tool-registry/create + client/tracing, client/agents/[id], client/agents/[id]/edit, client/tools/[id]/edit, client/db-connections/[id]/edit + 4 loading.tsx

**New components** (4): notification-center, db-schema-tree, tool-registry-selector, agent-detail-panel

**New API modules** (4): chat, tool-registry, tracing, users

**New hooks** (4): use-chat, use-tracing, use-sessions, use-tool-registry

**New types** (8): ToolRegistryPublic, TracePublic, TraceDetail, TraceObservation, TraceStats, SessionPublic, ChatRequest, ChatResponse, DbSchema

---

## PART 21 — Backend Reference (One-AI FastAPI)

> **Running the backend:** `cd D:\Development-Work\One-AI && uv run uvicorn backend.main:app --reload --port 8000`
> **API docs:** `http://localhost:8000/docs`
> **Admin UI:** `http://localhost:8000/admin`

### Endpoint Summary

| Module | Base Path | Key Endpoints |
|---|---|---|
| Auth | `/auth` | POST /login · POST /signup · GET /me · POST /forgot-password · POST /verify-otp · POST /reset-password · POST /users (admin) |
| Organizations | `/organizations` | CRUD + pagination |
| Agents | `/agents` | CRUD + pagination · GET /agents/{id}/traces · GET /agents/{id}/stats |
| Tools | `/tools` | CRUD + pagination |
| Tool Registry | `/tool-registry` | CRUD + pagination |
| DB Connections | `/db-connections` | CRUD + pagination · GET /{id}/schema |
| Chat | `/chat` | POST /chat (body: agent_id, message; optional: session_id) |
| Tracing | `/traces` `/sessions` | GET /traces · GET /traces/stats · GET /traces/{id} · GET /sessions |
| Health | `/` `/mongo-check` | GET (no auth) |

### Auth Headers

```
Authorization: Bearer <jwt_token>
Content-Type: application/json
X-Session-Id: <session_uuid>   # optional, for chat session continuity
```

### Pagination Query Params

All list endpoints: `?page=1&page_size=20`

Response envelope:
```json
{ "items": [...], "total": 150, "page": 1, "page_size": 20 }
```

### Environment Variables (Frontend `.env.local`)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### CORS

Backend allows `http://localhost:3000` (set via `FRONTEND_URL` in `.env`). No changes needed.

### Key Backend Behaviors

- **Soft deletes**: All resources have `is_deleted` — delete endpoints mark rather than remove. Frontend can ignore deleted items (API excludes them from list endpoints automatically).
- **Connection string masking**: `GET /db-connections` returns `connection_string` with only first 20 chars visible + `***`. Full string never returned via API.
- **Schema auto-fetch**: On `POST /db-connections`, backend automatically connects to the DB and fetches schema. Retrieve with `GET /db-connections/{id}/schema`.
- **OTP expiry**: Password reset OTPs expire in 10 minutes.
- **Rate limiting**: Per-IP, configurable via admin panel at `/admin`.
- **JWT expiry**: 24 hours. On 401, clear token and redirect to `/login`.
- **Roles**: `admin` (org admin) and `member`. Super admin role exists but only for platform-level access via the admin dashboard.
