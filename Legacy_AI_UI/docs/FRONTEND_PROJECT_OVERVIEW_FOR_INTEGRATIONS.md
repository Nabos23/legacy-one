# ONE-AI Frontend — Technical Overview for Integrations

> **Generated:** 2026-06-29
> **Purpose:** Complete frontend technical overview to plan UI work for integrations with Slack, Microsoft Teams, Jira, ClickUp, Gmail, Outlook, SharePoint, Google Drive, and OneDrive.
> **Rule:** This document is read-only analysis. No code was changed or refactored.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Frontend Repository Structure](#2-frontend-repository-structure)
3. [Framework and App Architecture](#3-framework-and-app-architecture)
4. [Authentication Flow](#4-authentication-flow)
5. [API Client Layer](#5-api-client-layer)
6. [State Management](#6-state-management)
7. [Main Product Screens](#7-main-product-screens)
8. [Agent UI](#8-agent-ui)
9. [Tool and MCP UI](#9-tool-and-mcp-ui)
10. [Chat UI](#10-chat-ui)
11. [Existing Integration/Settings UI](#11-existing-integrationsettings-ui)
12. [Frontend Readiness for Integrations](#12-frontend-readiness-for-integrations)
13. [Recommended Integration UI Architecture](#13-recommended-integration-ui-architecture)
14. [Proposed Frontend Pages/Components](#14-proposed-frontend-pagescomponents)
15. [Frontend Implementation Tasks](#15-frontend-implementation-tasks)
16. [Frontend Risks and Unknowns](#16-frontend-risks-and-unknowns)
17. [Final Summary](#17-final-summary)

---

## 1. Executive Summary

### What This Frontend Does

ONE-AI is an **enterprise AI agent management platform** frontend. It provides a web dashboard for creating, configuring, deploying, and chatting with AI agents. Agents can be given tools (DB connections, HTTP tools, custom tools) and connected to external MCP (Model Context Protocol) servers for extended capabilities. The platform supports multi-tenant organizations, role-based access control (RBAC), real-time chat with agents, and observability (tracing/cost analytics).

### Framework and Architecture

- **Framework:** Next.js 16.2.6 (App Router) with React 19 and TypeScript 5.7.3
- **Styling:** Tailwind CSS v4 with custom CSS variables for theming (light/dark)
- **UI Library:** shadcn/ui pattern (custom components in `components/ui/`), lucide-react icons
- **State:** React Context (auth, theme, sidebar, toast) + custom hooks with `useState`/`useEffect` data fetching
- **API:** Manual fetch wrapper (`lib/api/client.ts`) with JWT Bearer token auth
- **No TanStack Query, no Redux, no Zustand** — all data fetching is via custom hooks

### Main User Flows

1. **Auth:** Login → role-based redirect → admin dashboard (super_admin) or client dashboard (org users)
2. **Agent Management:** Create agent (5-step stepper: Identity → Prompt & Guardrails → Tools → MCP Servers → Review) → Deploy → Chat
3. **Tool Management:** Register tools in global registry (admin) → Assign tools to agents (client)
4. **MCP Server Management:** Browse catalog or enter custom URL → Test connection → Attach to agent → Discover tools
5. **Chat/Playground:** Select agent or supervisor mode → Send messages → View responses with markdown rendering → Trace links
6. **Observability:** View traces, costs, token usage, agent breakdowns via charts and tables

### Current Maturity Level

**Mid-stage product** — all core CRUD screens, chat, tracing, and agent configuration exist. The UI is polished with glass morphism, animations, and dark mode. However:
- No test suite exists (Playwright is installed but no test files found)
- `proxy.ts` handles server-side route protection (token presence only, not role/validity)
- No React Query / caching layer — every page refetches on mount
- No integration settings UI exists whatsoever
- `typescript: { ignoreBuildErrors: true }` in next.config suggests unresolved type issues
- `postcss.config.mjs` is compromised — contains obfuscated malicious JS (see Security Alert above)

### How Frontend Connects to Backend

The frontend connects to a separate backend API via `NEXT_PUBLIC_API_URL` (default: `http://localhost:8001`). All communication is REST JSON over fetch. Authentication uses JWT Bearer tokens stored in `localStorage` and mirrored to a client-set cookie for potential middleware use.

---

> **SECURITY ALERT:** `postcss.config.mjs` contains obfuscated malicious JavaScript appended after the legitimate PostCSS config on line 12. It manipulates `global`, `require`, and `module` — characteristic of a supply-chain compromise. **Investigate immediately before running `npm dev` or `npm build`.**  Additionally, `proxy.ts` exists as a Next.js 16 route protection proxy (replaces traditional `middleware.ts`) but was not noted in the initial analysis — it provides server-side token-based route gating for `/admin/*` and `/client/*` paths.

---

## 2. Frontend Repository Structure

```
One-AI-UI/
├── app/                          # Next.js App Router pages and layouts
│   ├── layout.tsx                # Root layout — providers: Theme, Auth, Sidebar, Toast
│   ├── page.tsx                  # Landing page (marketing/public)
│   ├── globals.css               # Global styles, CSS variables, Tailwind imports
│   ├── (auth)/                   # Auth route group
│   │   ├── layout.tsx            # Minimal auth layout (bg + centered content)
│   │   ├── login/page.tsx        # Login screen with email/password + social buttons
│   │   ├── register/page.tsx     # Registration screen
│   │   └── forgot-password/page.tsx  # Forgot password flow (OTP-based)
│   └── (dashboard)/              # Dashboard route group
│       ├── layout.tsx            # Force-dynamic wrapper
│       ├── admin/                # Super admin area
│       │   ├── layout.tsx        # Admin sidebar layout (SidebarVariantProvider)
│       │   ├── dashboard/page.tsx
│       │   ├── organizations/    # CRUD: list, create, [id], [id]/edit
│       │   ├── users/            # CRUD: list, create
│       │   ├── agents/           # CRUD: list, create, [id], [id]/edit
│       │   ├── tool-registry/    # CRUD: list, create, [id]/edit
│       │   ├── mcp-servers/page.tsx  # MCP server management
│       │   ├── playground/page.tsx   # Admin chat playground
│       │   ├── tracing/page.tsx      # Observability/analytics
│       │   ├── settings/page.tsx     # Admin settings
│       │   └── help/page.tsx         # Help page
│       └── client/               # Org-scoped user area
│           ├── layout.tsx        # Client sidebar layout
│           ├── dashboard/page.tsx
│           ├── users/            # list, create
│           ├── agents/           # CRUD: list, create, [id], [id]/edit
│           ├── tools/            # CRUD: list, create, [id], [id]/edit
│           ├── db-connections/   # CRUD: list, create, [id]/edit, [id]/schema
│           ├── playground/page.tsx   # Client chat playground
│           ├── tracing/page.tsx
│           ├── settings/page.tsx
│           └── help/page.tsx
├── components/                   # Reusable React components
│   ├── ui/                       # Design system primitives (29 components)
│   │   ├── button.tsx, input.tsx, textarea.tsx, card.tsx
│   │   ├── dialog.tsx, badge.tsx, tabs.tsx, tooltip.tsx
│   │   ├── data-table.tsx, pagination.tsx, separator.tsx
│   │   ├── page-header.tsx, breadcrumb.tsx, stepper.tsx
│   │   ├── form-field.tsx, checkbox.tsx, toggle.tsx
│   │   ├── tag-input.tsx, key-value-editor.tsx
│   │   ├── code-editor.tsx, markdown.tsx
│   │   ├── stats-card.tsx, status-indicator.tsx, icon-tile.tsx
│   │   ├── info-box.tsx, empty-state.tsx, skeleton.tsx
│   │   ├── reveal.tsx, typing-indicator.tsx
│   │   └── db-schema-tree.tsx
│   ├── layout/                   # Layout components (4 files)
│   │   ├── dashboard-layout.tsx  # Main dashboard shell (sidebar + topnav + content)
│   │   ├── sidebar.tsx           # Collapsible sidebar with permission-filtered nav
│   │   ├── top-nav.tsx           # Top navigation bar (breadcrumb, search, notifications, user menu)
│   │   ├── command-palette.tsx   # ⌘K command palette
│   │   └── notification-center.tsx  # Notification dropdown panel
│   ├── dashboard/                # Dashboard-specific widgets (6 files)
│   │   ├── metric-cards.tsx
│   │   ├── agent-list-card.tsx
│   │   ├── agent-analytics-chart.tsx
│   │   ├── agent-execution-status.tsx
│   │   ├── task-completion-chart.tsx
│   │   ├── system-alerts-card.tsx
│   │   └── compute-tracker.tsx
│   ├── mcp/                      # MCP-specific components (3 files)
│   │   ├── connect-mcp-sheet.tsx # Slide-out sheet: catalog browse + custom URL + test + OAuth
│   │   ├── agent-mcp-step.tsx    # Agent creation Step 4: manage MCP servers per agent
│   │   └── mcp-status-badge.tsx  # Status + transport badges
│   ├── tracing/                  # Tracing components (1 file)
│   │   └── tracing-view.tsx      # Full observability view (~815 lines)
│   └── landing/                  # Marketing landing page components (18 files)
│       ├── landing.tsx, hero.tsx, nav.tsx, footer.tsx
│       ├── features.tsx, pricing.tsx, testimonials.tsx
│       ├── bento.tsx, showcase.tsx, cta.tsx, faq.tsx
│       ├── stats.tsx, how-it-works.tsx, orchestration.tsx
│       ├── logo.tsx, logos-band.tsx, statement.tsx
│       ├── scroll-progress.tsx, velocity-marquee.tsx
│       ├── magnetic.tsx, trace-replay.tsx, section-heading.tsx
│       ├── agent-field.tsx, side-field.tsx
│       └── reveal (animation helper)
├── contexts/                     # React Context providers (4 files)
│   ├── auth-context.tsx          # AuthProvider: user, permissions, login, logout
│   ├── theme-context.tsx         # ThemeProvider: light/dark toggle
│   ├── sidebar-context.tsx       # SidebarProvider: collapse/mobile state
│   └── toast-context.tsx         # ToastProvider: toast notifications
├── hooks/                        # Custom React hooks (19 files)
│   ├── use-agents.ts             # Fetch agents (by org or all)
│   ├── use-tools.ts              # Fetch tools
│   ├── use-tool-registry.ts      # Fetch tool registry
│   ├── use-mcp-servers.ts        # Fetch MCP servers (all or by agent)
│   ├── use-db-connections.ts     # Fetch DB connections
│   ├── use-organizations.ts      # Fetch organizations
│   ├── use-users.ts              # Fetch users
│   ├── use-chat.ts               # Chat state: messages, send, history
│   ├── use-sessions.ts           # Chat session list management
│   ├── use-tracing.ts            # Trace stats fetching
│   ├── use-notifications.ts      # Notification fetching + actions
│   ├── use-org-settings.ts       # Org settings CRUD
│   ├── use-sidebar.ts            # Sidebar state consumer
│   ├── use-toast.ts              # Toast consumer
│   ├── use-greeting.ts           # Time-based greeting string
│   ├── use-bulk-delete.ts        # Bulk delete helper
│   ├── use-reveal.ts             # Scroll reveal animation
│   ├── use-lenis.ts              # Smooth scroll (landing page)
│   └── use-gsap-scroll.ts        # GSAP scroll animations (landing page)
├── lib/                          # Utility libraries (24 files)
│   ├── config.ts                 # API_BASE_URL from NEXT_PUBLIC_API_URL
│   ├── utils.ts                  # cn(), truncate(), formatDate(), avatarColor()
│   ├── auth-cookies.ts           # setAuthCookie(), clearAuthCookie(), getDashboardPath()
│   ├── api/                      # API client layer (14 files)
│   │   ├── client.ts             # Core fetch wrapper: apiRequest(), api.get/post/put/patch/delete
│   │   ├── index.ts              # Barrel export for all API modules
│   │   ├── auth.ts               # login, register, me, mePermissions, logout, forgot/reset password
│   │   ├── agents.ts             # CRUD agents
│   │   ├── tools.ts              # CRUD tools
│   │   ├── tool-registry.ts      # CRUD tool registry
│   │   ├── mcp-servers.ts        # MCP: list, catalog, test, create, oauthStart, discover, update, delete
│   │   ├── organizations.ts      # CRUD organizations
│   │   ├── users.ts              # List/create users
│   │   ├── chat.ts               # Sessions: create, send, direct, list, history
│   │   ├── tracing.ts            # Traces: list, detail, stats, sessions, agent traces
│   │   ├── db-connections.ts     # CRUD DB connections + schema + preview
│   │   ├── settings.ts           # Org settings get/update
│   │   ├── health.ts             # Health check (API Gateway + Database)
│   │   ├── notifications.ts      # List, unread count, mark read, dismiss
│   │   └── prompt-generator.ts   # AI prompt generation
│   └── validations/              # Zod validation schemas (4 files)
│       ├── auth.ts               # login, register, password, forgotPassword schemas
│       ├── agent.ts              # Agent creation validation
│       ├── tool.ts               # Tool validation
│       ├── organization.ts       # Organization validation
│       └── db-connection.ts      # DB connection validation
├── types/                        # TypeScript type definitions (1 file)
│   └── index.ts                  # All shared interfaces: Page<T>, UserPublic, AgentPublic, etc.
├── styles/                       # Design tokens
│   └── tokens.css                # Light/dark theme CSS variables (oklch colors, spacing, radius, type scale)
├── docs/                         # Documentation
│   └── enterprise-auth-onboarding.md  # Planned enterprise auth design doc
├── public/                       # Static assets (minimal — showcase/README.md only)
├── proxy.ts                      # Next.js 16 edge route protection (replaces middleware.ts)
├── components.json               # shadcn/ui config (style: base-nova, icon: lucide, aliases)
├── package.json                  # Dependencies and scripts
├── package-lock.json             # npm lockfile
├── pnpm-lock.yaml                # pnpm lockfile (both lockfiles coexist)
├── next.config.mjs               # Next.js config (ignoreBuildErrors: true, unoptimized images)
├── postcss.config.mjs            # PostCSS config ⚠️ COMPROMISED — contains obfuscated malicious JS
├── tsconfig.json                 # TypeScript config (strict: true, target: ES6, @/* alias)
├── API_REFERENCE.md              # Backend API reference doc
├── ONE_AI_V0_PROMPT.md           # Original v0 prompt/design doc
├── AGENTS.md                     # Agent rules for AI assistants
├── CLAUDE.md                     # Claude-specific instructions
└── README.md                     # Project readme
```

### Additional Files Not in Tree

- `app/error.tsx` — Global error boundary (shows error message + "Try again" button)
- `app/not-found.tsx` — Custom 404 page (links back to `/login`)
- `app/icon.svg` — Favicon/app icon
- `app/globals.css` — Global CSS (imports Tailwind + `styles/tokens.css`)
- **11 `loading.tsx` files** — Skeleton loading states for: client/dashboard, client/agents, client/tools, client/users, client/db-connections, client/tracing, admin/dashboard, admin/agents, admin/organizations, admin/users, admin/tracing

### Notable Observations

| Area | Observation |
|------|-------------|
| **Duplicate pages** | Admin and client areas mirror many pages (dashboard, agents, tools, playground, tracing, settings, help). This is intentional — admin sees cross-org, client sees org-scoped. |
| **Landing page** | 18 marketing components in `components/landing/` — entirely separate from the app. Uses GSAP, Lenis, and Motion for animations. |
| **No test files** | `playwright` is a devDependency but zero test files exist. |
| **No `.env` files** | No `.env.example` or `.env.local` file exists. The only env var is `NEXT_PUBLIC_API_URL`. |
| **proxy.ts (not middleware.ts)** | Next.js 16 uses `proxy.ts` instead of `middleware.ts`. Server-side token check exists but only validates cookie presence, not role/permissions. |
| **Compromised postcss.config.mjs** | Contains obfuscated malicious JS after the valid config. Investigate before running builds. |
| **`docs/` folder** | Contains `enterprise-auth-onboarding.md` — a planning doc for enterprise auth. May indicate upcoming SSO/SAML work relevant to integrations. |
| **Dual lockfiles** | Both `package-lock.json` and `pnpm-lock.yaml` exist. The canonical package manager is ambiguous. |
| **Design token system** | `styles/tokens.css` defines a comprehensive token system using oklch colors, spacing scale, and type scale — used via `var(--*)` in Tailwind arbitrary values. |
| **`@vercel/analytics`** | Listed in `package.json` but never imported — unused dependency. |
| **11 `loading.tsx` files** | Next.js Suspense loading states exist for most major pages — good UX foundation. |
| **Global error/404 pages** | `app/error.tsx` and `app/not-found.tsx` exist with branded error pages. |
| **No integration folder** | No `integrations/`, `connected-apps/`, or similar directory exists anywhere. |

---

## 3. Framework and App Architecture

### Framework

| Aspect | Value |
|--------|-------|
| Framework | Next.js 16.2.6 |
| React | 19.x |
| TypeScript | 5.7.3 |
| CSS | Tailwind CSS v4.2 + PostCSS |
| Icons | lucide-react 1.16.0 |
| Charts | recharts 3.8.1 |
| Animations | motion 12.40 (Framer Motion successor), GSAP 3.15, Lenis 1.3 |
| Form validation | Zod 4.4.3 |
| UI base | shadcn 4.8.0 (style: base-nova), class-variance-authority, tailwind-merge, clsx |
| Analytics | @vercel/analytics 1.6.1 (installed but **not imported** anywhere — unused dependency) |
| Smooth scroll | Lenis 1.3 (landing page only) |

### Routing System

Next.js App Router with route groups:
- **`(auth)`** — Unauthenticated pages: `/login`, `/register`, `/forgot-password`
- **`(dashboard)`** — Authenticated area, split into:
  - **`admin/`** — Super admin routes (cross-org view)
  - **`client/`** — Org-scoped user routes

Total pages: **42 pages** across both areas.

### Layouts

| Layout | File | Purpose |
|--------|------|---------|
| Root | `app/layout.tsx` | Wraps entire app in ThemeProvider → AuthProvider → SidebarProvider → ToastProvider. Fonts: Geist Sans + Geist Mono via `next/font/google`. Inline `<script>` for flash-free theme initialization. |
| Auth | `app/(auth)/layout.tsx` | Minimal wrapper with background styling |
| Dashboard | `app/(dashboard)/layout.tsx` | Sets `force-dynamic`, pass-through |
| Admin | `app/(dashboard)/admin/layout.tsx` | Client component — `SidebarVariantProvider(variant="admin")` + `DashboardLayout(variant="admin")` |
| Client | `app/(dashboard)/client/layout.tsx` | Client component — `SidebarVariantProvider(variant="client")` + `DashboardLayout(variant="client")` |

### Server vs. Client Components

Almost every page is a **client component** (`'use client'`). The only server components are the layout wrappers. This is because:
- Auth state is read from `localStorage` (client-only)
- All data fetching happens client-side via fetch hooks
- No server actions or RSC data patterns are used

### Design Token System

**File:** `styles/tokens.css`

All colors, spacing, radius, and typography are defined as CSS custom properties using oklch color space:
- **Light/dark themes** — `:root, [data-theme="light"]` and `[data-theme="dark"]` rulesets
- **Semantic colors** — `--primary` (violet `#7c3aed`), `--secondary`, `--success`, `--warning`, `--danger`
- **Surface hierarchy** — `--bg`, `--surface`, `--surface-2`, `--surface-3`
- **Text hierarchy** — `--text-1`, `--text-2`, `--text-3`
- **Spacing scale** — `--space-1` (4px) through `--space-12` (48px)
- **Radius scale** — `--radius-sm` (6px) through `--radius-xl` (20px)
- **Type scale** — `--text-xs` (11px) through `--text-3xl` (30px)

Components use these tokens via Tailwind arbitrary values (e.g., `bg-[var(--surface)]`, `text-[var(--text-1)]`) and glassmorphism utility classes (`.glass`, `.glass-hover`, `.glass-card`).

### shadcn/ui Configuration

**File:** `components.json`

```json
{
  "style": "base-nova",
  "rsc": true,
  "tsx": true,
  "tailwind": { "css": "app/globals.css", "baseColor": "neutral", "cssVariables": true },
  "aliases": { "components": "@/components", "utils": "@/lib/utils", "ui": "@/components/ui" },
  "iconLibrary": "lucide"
}
```

### Build Setup

```js
// next.config.mjs
const nextConfig = {
  typescript: { ignoreBuildErrors: true },  // ⚠️ Type errors suppressed
  images: { unoptimized: true },            // No image optimization
}
```

### TypeScript Configuration

**File:** `tsconfig.json`

- `strict: true` — strict mode enabled
- `target: ES6` — compiles to ES6
- `@/*` path alias maps to both `./src/*` and `./*` (fallback since no `src/` dir exists — all app code is at the root)
- `jsx: react-jsx` — React 19 JSX transform
- `skipLibCheck: true` — library type checking disabled for speed

**Contradiction:** `tsconfig` has `strict: true` but `next.config.mjs` has `ignoreBuildErrors: true` — so TypeScript errors exist but are silently ignored during builds.

### Environment Variables

| Variable | Location | Purpose |
|----------|----------|---------|
| `NEXT_PUBLIC_API_URL` | `lib/config.ts` | Backend API base URL (default: `http://localhost:8001`) |

No `.env.example` file exists. No other environment variables are referenced.

### Middleware / Route Protection

**File:** `proxy.ts` (Next.js 16 replaces `middleware.ts` with `proxy.ts`)

Server-side edge route protection:
- Protected routes (`/admin/*`, `/client/*`): requires `access_token` cookie, otherwise redirects to `/login?from=<path>`
- Auth routes (`/login`, `/register`, `/forgot-password`): if token cookie exists, redirects to `/client/dashboard`
- Matcher excludes `_next/static`, `_next/image`, `favicon.ico`, `api`

**Note:** This only checks cookie presence, not token validity or user role. Role/permission enforcement is still client-side in `DashboardLayout`.

---

## 4. Authentication Flow

### Login Screen

**File:** `app/(auth)/login/page.tsx`

- Email/password form with Zod validation (`loginSchema`)
- "Remember me" checkbox (extends cookie max-age from 24h to 30d)
- Social login buttons (Google, GitHub) — **UI only, not functional** (buttons have no `onClick` handlers)
- Forgot password link → `/forgot-password`
- Register link → `/register`
- On success: `window.location.href = getDashboardPath(user.role)` (hard redirect based on role)

### Signup Screen

**File:** `app/(auth)/register/page.tsx`

- Name, email, password, confirm password form
- Zod validation with strong password rules (`registerSchema`)
- Calls `authApi.register()` — backend auto-creates an org named after the user
- On success: saves token → redirects to `/client/dashboard`

### Forgot Password Screen

**File:** `app/(auth)/forgot-password/page.tsx`

3-step OTP-based flow using the `Stepper` component:
1. **Email** — enter email, validated with `forgotPasswordSchema`, calls `authApi.forgotPassword(email)`
2. **Verify OTP** — 6-digit code input, calls `authApi.verifyOtp(email, otp)`
3. **New Password** — new password + confirm, calls `authApi.resetPassword(email, otp, newPassword)`

### Token Storage

| Storage | What | Purpose |
|---------|------|---------|
| `localStorage.access_token` | JWT token | Primary auth token for API calls |
| `localStorage.remember_me` | Boolean string | Controls cookie expiry |
| `document.cookie.access_token` | Same JWT | Mirror for potential middleware (not used) |

**Security concern:** Token is in `localStorage` (XSS-accessible) and client-set cookie (not HttpOnly). The code acknowledges this in `auth-cookies.ts` comments.

### Auth Provider

**File:** `contexts/auth-context.tsx`

Provides:
- `user: UserPublic | null`
- `permissions: Record<string, boolean>` (from `/auth/me/permissions`)
- `loading: boolean`
- `login(email, password, rememberMe)` → calls API, stores token, fetches user + permissions
- `logout()` → clears storage, redirects to `/login`
- `isAuthenticated: boolean` (derived: `!!user`)

On mount: checks `localStorage` for token → calls `authApi.me()` + `authApi.mePermissions()` → sets user/permissions state.

### Protected Routes

**File:** `components/layout/dashboard-layout.tsx`

Client-side route protection:
1. While `loading` → shows spinner
2. If `!isAuthenticated` → redirects to `/login?from=<currentPath>`
3. If visiting `/admin/*` and not `super_admin` → redirects to `/client/dashboard`
4. Per-route permission check via `ROUTE_PERMISSIONS` map:

```
/admin/organizations → create_org
/admin/users → create_user
/admin/agents → create_agent
/admin/tool-registry → create_tool
/client/agents → create_agent
/client/tools → create_tool
/client/db-connections → create_db_connection
/client/playground → create_chat_session
/admin/playground → create_chat_session
```

5. If permission denied → shows "Access Denied" card with "Go to Dashboard" button

### Current User Fetching

- `authApi.me()` → `GET /auth/me` → returns `UserPublic`
- `authApi.mePermissions()` → `GET /auth/me/permissions` → returns `PermissionsResponse` with `resolved_permissions` map and `is_super_admin` flag

### Logout Flow

1. `authApi.logout()` (fire-and-forget POST to backend)
2. Remove `access_token` and `remember_me` from localStorage
3. Clear auth cookie
4. Set `user` and `permissions` to null
5. Hard redirect to `/login`

### Role/Permission Handling

Roles: `user`, `org_manager`, `org_admin`, `super_admin`

Permissions are resolved server-side and sent as a flat boolean map (e.g., `{ view_agent: true, create_agent: false }`). The frontend uses these for:
- **Sidebar filtering:** Nav items have `permission` property, hidden if user lacks it
- **Route gating:** `ROUTE_PERMISSIONS` map in `DashboardLayout`
- **Role-specific rendering:** Some components check `user.role === 'super_admin'`

### Organization Switching

**Not present.** Users belong to one org (`user.organization_id`). Super admins can view all orgs but don't "switch" into them — they see cross-org data by default.

### Enterprise Auth Roadmap

**File:** `docs/enterprise-auth-onboarding.md` (Status: Planned, not implemented)

A design doc outlines planned enterprise auth features:
- **Admin-provisioned onboarding** — disable public `/register`, admin creates orgs and invites users
- **Expanded RBAC** — `user`, `org_manager`, `org_admin`, `super_admin` (partially implemented in code)
- **SSO/SAML/OIDC** — not yet implemented but planned
- **SCIM user provisioning** — planned for enterprise tier
- **Domain-verified org join** — planned but not implemented
- **2FA, audit logging, session policies** — UI toggles exist in admin settings but are not enforced

**Relevance for integrations:** Enterprise SSO/OIDC support would share OAuth infrastructure with integration OAuth flows. Planning both together could reduce redundant work.

---

## 5. API Client Layer

### Core Client

**File:** `lib/api/client.ts`

A manual fetch wrapper built on the native `fetch` API.

```typescript
const api = {
  get: <T>(path) => apiRequest<T>(path),
  post: <T>(path, body) => apiRequest<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  put: <T>(path, body) => apiRequest<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
  patch: <T>(path, body) => apiRequest<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: <T>(path) => apiRequest<T>(path, { method: 'DELETE' }),
}
```

### Base URL

**File:** `lib/config.ts`

```typescript
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, '') ?? 'http://localhost:8001'
```

### Auth Headers

Every request adds `Authorization: Bearer <token>` if a token exists in `localStorage`.

```typescript
const getToken = () =>
  typeof window === 'undefined' ? null : localStorage.getItem('access_token')
```

### Error Handling

**Custom error class:** `ApiError(status, detail)`

- **401 Unauthorized:** Clears token + cookie → redirects to `/login` → throws `ApiError(401, 'Unauthorized')`
- **Other errors:** Parses JSON body for `detail` field → throws `ApiError(status, detail)`
- **204 No Content:** Returns `undefined`
- **Empty body:** Returns `undefined`

### Request/Response Typing

All API functions are generic: `apiRequest<T>()`. Each domain API module (e.g., `agentsApi`) specifies the return type:

```typescript
agentsApi.list = (page, page_size, search) =>
  api.get<Page<AgentPublic>>(`/agents?page=${page}&page_size=${page_size}...`)
```

Types are defined in `types/index.ts` (330 lines, 30+ interfaces) — all manually written (not auto-generated).

### Type Inventory

| Domain | Interfaces | Key Fields |
|--------|-----------|------------|
| **Pagination** | `Page<T>` | `items`, `total`, `page`, `page_size`, `total_pages` |
| **Auth** | `UserPublic`, `TokenResponse`, `PermissionsResponse` | Role enum: `user`/`org_manager`/`org_admin`/`super_admin` |
| **Org** | `OrganizationPublic` | name, description, timestamps |
| **Agent** | `AgentPublic` | `tool_ids[]`, `rag_ids[]`, `mcp_server_ids[]`, prompt, guardrails |
| **Tool** | `ToolPublic` | org_id, agent_id, tool_id (registry ref) |
| **DB Connection** | `DbConnectionPublic`, `DbSchema`, `DbConnectionPreviewResponse` | SQL/Mongo schema introspection types |
| **Tool Registry** | `ToolRegistryPublic` | type: `db`/`http`/`rag`/`custom`, `tool_schema` JSON |
| **Chat** | `ChatMessage`, `ChatResponse`, `DirectChatResponse`, `SessionPublic`, `SessionListItem`, `ConversationTurn`, `ConversationSummary`, `AgentHistory`, `SessionHistoryResponse` | Full chat/session model |
| **Tracing** | `TraceListItem`, `TraceDetail`, `TraceStats`, `ObservationItem` | Langfuse-aligned trace model |
| **Notifications** | `NotificationPublic`, `NotificationType` | type: `agent`/`tool`/`alert`/`success`/`system` |
| **Settings** | `OrgSettings`, `OrgSettingsUpdate` | maintenance_mode, 2fa, session_timeout, audit_logging, default_model |
| **MCP** | `McpServerPublic`, `McpCatalogEntry`, `McpTestConnectionResult`, `McpToolSpec` | Full MCP server model with tools, transport, auth type |

**Note:** `ConversationTurn` has `tool_called?: boolean` and `tool_name?: string` fields — these exist in the type but are **not rendered** in the chat UI.

### Retry Behavior

**None.** There is no retry logic, exponential backoff, or request queue. Failed requests throw immediately.

### API Modules

| File | Export | Endpoints |
|------|--------|-----------|
| `lib/api/auth.ts` | `authApi` | login, register, forgotPassword, verifyOtp, resetPassword, me, mePermissions, logout |
| `lib/api/agents.ts` | `agentsApi` | list, listByOrg, get, create, update, delete |
| `lib/api/tools.ts` | `toolsApi` | list, listByOrg, get, create, update, delete |
| `lib/api/tool-registry.ts` | `toolRegistryApi` | list, get, create, update, delete |
| `lib/api/mcp-servers.ts` | `mcpApi` | list, listByAgent, get, catalog, testConnection, create, oauthStart, discover, update, delete |
| `lib/api/organizations.ts` | `organizationsApi` | list, get, create, update, delete |
| `lib/api/users.ts` | `usersApi` | list, listByOrg, create |
| `lib/api/chat.ts` | `chatApi` | createSession, sendMessage, sendDirectMessage, listSessions, renameSession, getSessionMessages |
| `lib/api/tracing.ts` | `tracingApi` | listTraces, getTrace, getStats, listSessions, agentTraces, agentStats |
| `lib/api/db-connections.ts` | `dbConnectionsApi` | list, listByOrg, get, preview, create, update, updateDescriptions, delete, getSchema |
| `lib/api/settings.ts` | `settingsApi` | get, update (org settings) |
| `lib/api/health.ts` | `healthApi` | check (probes API Gateway + Database) |
| `lib/api/notifications.ts` | `notificationsApi` | list, unreadCount, markRead, markAllRead, dismiss |
| `lib/api/prompt-generator.ts` | `promptGeneratorApi` | generate (AI prompt generation) |

### Generated vs. Manual

**All manual.** No OpenAPI/Swagger code generation. No auto-generated types. All API functions and types are hand-written.

### Backend API Documentation

**File:** `API_REFERENCE.md`

A reference doc exists documenting the backend REST API (FastAPI + MongoDB). It covers:
- Auth, organizations, agents, tools, DB connections, chat (LangGraph), tool registry, prompt generator, tracing (Langfuse)
- Pagination envelope (`Page<T>` with `items`, `total`, `page`, `page_size`, `total_pages`)
- Soft deletes, rate limiting (429 + `Retry-After`), org-scoped access
- **No integration endpoints exist in the backend API yet** — all integration CRUD/OAuth/webhook endpoints must be designed and built

---

## 6. State Management

### Global State

| Context | File | State |
|---------|------|-------|
| `AuthContext` | `contexts/auth-context.tsx` | `user`, `permissions`, `loading`, `isAuthenticated` |
| `ThemeContext` | `contexts/theme-context.tsx` | `theme` ('light' \| 'dark'), `toggleTheme` |
| `SidebarContext` | `contexts/sidebar-context.tsx` | `isCollapsed`, `isMobileOpen`, `variant`, toggle functions |
| `ToastContext` | `contexts/toast-context.tsx` | Toast queue, `toast.success()`, `toast.error()`, `toast.info()` |

### Local State Patterns

Every data-fetching page uses the same pattern:
1. Call a custom hook (e.g., `useAgents(page)`)
2. Hook internally uses `useState` + `useEffect` + `useCallback`
3. Returns `{ data, loading, error, refetch }`
4. Page renders loading/error/data states

There is **no caching**. Each page mount triggers a fresh API call. Navigating away and back refetches everything.

### Query/Cache Libraries

**None.** No TanStack Query, SWR, or any caching layer. This means:
- No automatic refetching on focus/reconnect
- No cache invalidation
- No optimistic updates (except `useSessions.renameSession`)
- No request deduplication

### Form Handling

- **Zod** for schema validation (`lib/validations/`)
- **Manual `useState`** for form fields (no react-hook-form or formik)
- Validation runs on submit or step change
- Error messages stored in `errors` state object

### Validation Schemas Detail

| File | Schemas | Key Rules |
|------|---------|-----------|
| `lib/validations/auth.ts` | `loginSchema`, `registerSchema`, `passwordSchema`, `forgotPasswordSchema` | Password: min 8 chars, uppercase, lowercase, digit, special char |
| `lib/validations/agent.ts` | `createAgentSchema` | Name min 2 chars, prompt min 10 chars, guardrails min 10 chars |
| `lib/validations/tool.ts` | `createToolSchema` | Requires org_id, agent_id, tool_id, description min 10 chars |
| `lib/validations/organization.ts` | `createOrganizationSchema`, `createUserSchema` | Org name min 2 chars; user role enum: user/org_manager/org_admin/super_admin |
| `lib/validations/db-connection.ts` | `createDbConnectionSchema`, `previewDbConnectionSchema` | Requires org_id, connection_string min 10 chars |

All schemas export `z.infer<>` types for compile-time type safety (e.g., `CreateAgentInput`, `CreateToolInput`).

### Loading/Error States

- Most hooks return `loading: boolean` and `error: string | null`
- Pages show `<Loader2>` spinner while loading
- Errors shown via `toast.error()` or inline error text
- Some pages have `<EmptyState>` components for zero-data states
- `<Skeleton>` components exist but are sparingly used
- **11 `loading.tsx` files** provide Next.js Suspense boundaries with skeleton states for major pages (dashboard, agents, tools, users, db-connections, tracing, organizations)
- **`app/error.tsx`** — global error boundary shows error message + "Try again" button
- **`app/not-found.tsx`** — custom 404 page with link back to `/login`

---

## 7. Main Product Screens

### Dashboard (Admin)

| Attribute | Value |
|-----------|-------|
| **File** | `app/(dashboard)/admin/dashboard/page.tsx` |
| **Purpose** | Super admin overview: system health, org/user/agent counts, charts |
| **Components** | MetricCards, AgentListCard, AgentAnalyticsChart, AgentExecutionStatus, TaskCompletionChart, SystemAlertsCard, ComputeTracker |
| **API calls** | `healthApi.check()`, `organizationsApi.list()`, `usersApi.list()`, `agentsApi.list()`, `tracingApi.getStats()` |
| **Permission** | Super admin only (enforced by layout) |
| **Missing UX** | No real-time refresh, no auto-refresh interval, service health cards are hardcoded static for some services |

### Dashboard (Client)

| Attribute | Value |
|-----------|-------|
| **File** | `app/(dashboard)/client/dashboard/page.tsx` |
| **Purpose** | Org-scoped overview: greeting, agent count, tool count, recent activity |
| **Components** | MetricCards, AgentListCard, quick-action cards |
| **API calls** | `useAgents()`, `useTools()`, `tracingApi.getStats()` |
| **Permission** | Any authenticated org user |
| **Missing UX** | No personalized recommendations, no recent chat sessions widget |

### Organizations (Admin)

| Attribute | Value |
|-----------|-------|
| **Files** | `admin/organizations/page.tsx`, `create/page.tsx`, `[id]/page.tsx`, `[id]/edit/page.tsx` |
| **Purpose** | CRUD organizations |
| **Components** | DataTable, PageHeader, form inputs |
| **API calls** | `organizationsApi.*` |
| **Permission** | `create_org` |
| **Missing UX** | No org member count display, no org-level settings from list view |

### Users (Admin & Client)

| Attribute | Value |
|-----------|-------|
| **Files** | `admin/users/page.tsx`, `admin/users/create/page.tsx`, `client/users/page.tsx`, `client/users/create/page.tsx` |
| **Purpose** | List/create users. Admin sees all users, client sees org-scoped. |
| **API calls** | `usersApi.list()`, `usersApi.listByOrg()`, `usersApi.create()` |
| **Permission** | `create_user` / `view_user` |
| **Missing UX** | No user edit/delete, no role change UI, no user detail page |

### Agents (Admin & Client)

| Attribute | Value |
|-----------|-------|
| **Files** | `admin/agents/page.tsx`, `admin/agents/create/page.tsx`, `admin/agents/[id]/page.tsx`, `admin/agents/[id]/edit/page.tsx` + client equivalents |
| **Purpose** | CRUD agents with 5-step stepper creation flow |
| **Components** | Stepper, CodeEditor, AgentMcpStep, ConnectMcpSheet |
| **API calls** | `agentsApi.*`, `toolsApi.*`, `mcpApi.*`, `promptGeneratorApi.*` |
| **Permission** | `create_agent` / `view_agent` |
| **Missing UX** | No agent versioning, no agent duplication, no guardrail templates |

### Tools (Client)

| Attribute | Value |
|-----------|-------|
| **Files** | `client/tools/page.tsx`, `client/tools/create/page.tsx`, `client/tools/[id]/page.tsx`, `client/tools/[id]/edit/page.tsx` |
| **Purpose** | CRUD org-level tools (assigned to agents) |
| **API calls** | `toolsApi.*` |
| **Permission** | `create_tool` / `view_tool` |
| **Missing UX** | No tool testing UI, no tool execution history |

### Tool Registry (Admin)

| Attribute | Value |
|-----------|-------|
| **Files** | `admin/tool-registry/page.tsx`, `create/page.tsx`, `[id]/edit/page.tsx` |
| **Purpose** | Global tool type registry: db, http, rag, custom |
| **API calls** | `toolRegistryApi.*` |
| **Permission** | `create_tool` |
| **Missing UX** | No tool schema preview, no tool usage stats |

### MCP Servers (Admin)

| Attribute | Value |
|-----------|-------|
| **File** | `admin/mcp-servers/page.tsx` |
| **Purpose** | Global view of all MCP servers across all agents |
| **Components** | DataTable, McpStatusBadge, McpTransportBadge, ConnectMcpSheet |
| **API calls** | `mcpApi.list()`, `mcpApi.discover()`, `mcpApi.update()`, `mcpApi.delete()` |
| **Permission** | `create_tool` |
| **Missing UX** | No MCP server detail page, no connection string editing |

### DB Connections (Client)

| Attribute | Value |
|-----------|-------|
| **Files** | `client/db-connections/page.tsx`, `create/page.tsx`, `[id]/edit/page.tsx`, `[id]/schema/page.tsx` |
| **Purpose** | Manage database connections for tools |
| **Components** | DbSchemaTree, form inputs |
| **API calls** | `dbConnectionsApi.*` |
| **Permission** | `create_db_connection` / `view_db_connection` |
| **Missing UX** | No connection testing UI, no query preview |

### Playground / Chat

| Attribute | Value |
|-----------|-------|
| **Files** | `client/playground/page.tsx`, `admin/playground/page.tsx` |
| **Purpose** | Full chat interface with session management + agent selection |
| **Admin variant** | Admin playground adds an org picker dropdown (`useOrganizations`) to scope chat to a specific org's agents |
| **See Section 10** for details |

### Tracing / Observability

| Attribute | Value |
|-----------|-------|
| **Files** | `client/tracing/page.tsx`, `admin/tracing/page.tsx` |
| **Purpose** | View traces, costs, token usage, agent breakdowns |
| **Components** | TracingView (815+ lines), StatsCard, DataTable, recharts |
| **API calls** | `tracingApi.*` |
| **Permission** | `view_trace` |
| **Missing UX** | No trace search/filtering, no cost alerts, no export |

### Settings (Client)

| Attribute | Value |
|-----------|-------|
| **File** | `client/settings/page.tsx` |
| **Purpose** | User settings: profile display (read-only), password change (OTP-based), preferences |
| **Sections** | 1. Profile card (name, email, org_id, role — all disabled/read-only, "Request Changes" mailto link) 2. Password change (OTP flow: send code → enter code + new password) 3. Preferences (dark mode toggle, email/desktop notifications, weekly digest — saved to localStorage) |
| **API calls** | `authApi.forgotPassword()`, `authApi.resetPassword()` |
| **Avatar** | DiceBear Avataaars SVG API (`api.dicebear.com`) |
| **Note** | Notification preferences are stored in `localStorage` only (`oneai:client-prefs`), not sent to backend |
| **Missing UX** | No profile editing, no API key management, no integration settings, no "Connected Apps" tab |

### Settings (Admin)

| Attribute | Value |
|-----------|-------|
| **File** | `admin/settings/page.tsx` |
| **Purpose** | Organization-level settings: maintenance mode, 2FA, session timeout, audit logging, default model |
| **API calls** | `useOrgSettings().save()` |
| **Missing UX** | No integration configuration, no webhook management |

### Command Palette (⌘K)

**File:** `components/layout/command-palette.tsx`

Global keyboard shortcut (⌘K / Ctrl+K) opens a searchable command palette:
- **Static pages** — hardcoded navigation items for both client and admin areas
- **Dynamic entities** — fetches agents (`useAgents`), organizations (`useOrganizations`), and tools (`useTools`) for quick-jump
- **Quick actions** — "New Agent", "New Tool", "New DB Connection" links
- **Fuzzy search** — filters all items by label
- **Keyboard navigation** — arrow keys, Enter to select

**Relevance for integrations:** This palette should be extended with integration-related commands (e.g., "Connect Slack", "View Connected Apps") and dynamic integration entities.

### Notification Center

**File:** `components/layout/notification-center.tsx`

Dropdown panel triggered from TopNav bell icon:
- Fetches notifications via `useNotifications()` hook → `notificationsApi.list()`
- Shows icon-coded notifications: agent (violet), tool (cyan), alert (amber), success (green), system (gray)
- Actions: "Mark all read", dismiss individual notifications
- Optimistic UI for mark-all-read and dismiss (reverts on API failure)
- Relative timestamps (e.g., "2m ago", "Yesterday")

**Relevance for integrations:** Notification types should be extended for integration events (e.g., "Slack disconnected", "Jira token expiring", "Gmail sync complete").

### Help Pages

| Attribute | Value |
|-----------|-------|
| **Files** | `client/help/page.tsx`, `admin/help/page.tsx` |
| **Purpose** | Static help/FAQ content |
| **Missing UX** | No dynamic docs, no search |

---

## 8. Agent UI

### Agent Creation/Editing

**File:** `app/(dashboard)/client/agents/create/page.tsx` (654 lines)

5-step stepper flow:

| Step | Name | Content |
|------|------|---------|
| 0 | Identity | Name, description, avatar color, org selector (super admin) |
| 1 | Prompt & Guardrails | System prompt editor (CodeEditor), AI prompt generation button, prompt templates, guardrails textarea |
| 2 | Tools | Checkbox list of org tools, search filter, selected tools sidebar |
| 3 | MCP Servers | `AgentMcpStep` component — list connected servers, add/remove/discover |
| 4 | Review | Summary cards for identity, prompt, tools + Deploy button |

### Prompt Editor

- `CodeEditor` component (`components/ui/code-editor.tsx`) — styled textarea with line numbers and char limit
- 4 prompt templates: Customer Support, Data Analysis, Code Review, General Assistant
- AI prompt generation via `promptGeneratorApi.generate()` — only available to `super_admin` and `org_admin`

### Tool Assignment

- Loads all org tools via `useTools(1)`
- Checkbox list with search filter
- Selected tools shown as tags in sidebar
- "Create new tool" link opens in new tab
- Tool IDs stored in `formData.toolIds[]`

### RAG Source Assignment

**Not present in UI.** The `AgentPublic` type has `rag_ids: string[]` but there is no UI for assigning RAG sources. The agent creation flow does not include a RAG step.

### MCP Server Assignment

**File:** `components/mcp/agent-mcp-step.tsx`

- Lists MCP servers attached to the agent via `useMcpServersByAgent(agentId)`
- Shows server name, status badge, transport badge, tools list
- Actions: Refresh tools (discover), Delete
- "Add Server" button opens `ConnectMcpSheet`
- Changes are saved live (not batched with agent save)

### Guardrail Settings

- Simple textarea in Step 1 of agent creation
- Validation: minimum 10 characters
- No structured guardrail builder or template system

### Chat Entry Points

- Agent detail page has a "Chat" button linking to `/client/playground?agent=<id>`
- Playground page supports selecting any agent from a dropdown

### UX Gaps for Integration-Based Tools

- **No integration-specific tool category** — tools are generic (db, http, rag, custom)
- **No OAuth connection per tool** — MCP servers have OAuth, but regular tools don't
- **No tool capability preview** — what actions can this Slack/Jira tool perform?
- **No per-integration configuration** — no channel selector for Slack, no project selector for Jira
- **No tool permission scoping** — no way to restrict which Slack channels an agent can access

---

## 9. Tool and MCP UI

### Tool Registry UI (Admin)

**Files:** `admin/tool-registry/page.tsx`, `create/page.tsx`, `[id]/edit/page.tsx`

- DataTable listing all tool types in the global registry
- Create form: name, type (db/http/rag/custom), description, is_active toggle, JSON schema editor
- Types are `toolRegistryApi` calls
- No tool testing or preview functionality

### Org Tool UI (Client)

**Files:** `client/tools/page.tsx`, `create/page.tsx`, `[id]/page.tsx`, `[id]/edit/page.tsx`

- DataTable listing org-scoped tools
- Create form: select agent, select tool type from registry, add description
- Tool detail page shows basic info
- Edit page allows updating name, description, tool_id

### Tool Assignment UI

- Embedded in agent creation Step 2 (see Section 8)
- Checkbox-based multi-select with search
- No drag-and-drop, no categorization, no integration grouping

### MCP Server Registration UI

**File:** `components/mcp/connect-mcp-sheet.tsx` (494 lines)

Two-tab slide-out sheet:

**Tab 1 — Browse Catalog:**
- Search the backend MCP catalog (`mcpApi.catalog()`)
- Shows server name, description, category badge, transport badge
- Placeholder fields for required credentials (API keys, tokens)
- Homepage link for each entry

**Tab 2 — Custom URL / Command:**
- Text input for connection string (HTTP URL or stdio command)
- Optional bearer token input

**Shared:**
- Agent selector dropdown (attach to which agent)
- Description input
- "Test Connection" button → shows success/failure + discovered tools list
- "Authorize with OAuth" button (for HTTP URLs) → opens backend OAuth URL in new tab
- "Connect Server" save button

### MCP OAuth/Connect UI

- `mcpApi.oauthStart()` returns `{ authorization_url, state }`
- Frontend opens `authorization_url` in a new tab (`window.open`)
- Shows confirmation message: "Authorization opened in a new tab. Complete the flow there."
- **No OAuth callback page exists in the frontend** — the backend likely handles the callback directly
- After OAuth, user manually refreshes the server list

### MCP Discovery UI

- "Refresh tools" button on each MCP server card
- Calls `mcpApi.discover(id)` → backend re-probes the server and updates tool list
- No auto-discovery on connection

### Tool Status/Error UI

**File:** `components/mcp/mcp-status-badge.tsx`

- `McpStatusBadge` — shows colored dot + label for `pending`, `connected`, `error`
- `McpTransportBadge` — shows transport type (stdio, http, sse, websocket) + auth type
- Error messages shown inline below server cards when `status === 'error'`

### Missing UI for External Integrations

| Missing UI | Description |
|------------|-------------|
| **Integration catalog page** | No browsable list of supported integrations (Slack, Jira, etc.) |
| **Provider connect/disconnect cards** | No card-based UI for connecting/disconnecting integration providers |
| **Connected accounts list** | No view of which integrations are connected for an org or user |
| **OAuth callback page** | No `/integrations/callback` or similar page for OAuth redirects |
| **Integration status dashboard** | No view of connected integration health, token expiry, sync status |
| **Per-integration configuration** | No Slack channel picker, Jira project picker, etc. |
| **Integration permission management** | No UI for admins to control which integrations are available to which roles |
| **Webhook management** | No UI for viewing or managing incoming webhooks from integrations |
| **Token refresh/expiry indicators** | No banners or warnings for expired OAuth tokens |
| **Integration audit log** | No log of integration connection/disconnection events |

---

## 10. Chat UI

### Chat Session UI (Playground)

**File:** `app/(dashboard)/client/playground/page.tsx` (444 lines)

Two-panel layout:
- **Left panel (300px):** Session history list with rename/delete actions, "New Chat" button
- **Right panel:** Chat area with agent selector header, message stream, input bar

### Agent Selection

- Dropdown in chat header showing "Supervisor Session" (routes to all agents) or specific agent
- Changing agent resets the session
- Agent avatars with color coding
- "Online" status indicator (hardcoded, not real-time)

### Message Rendering

- User messages: violet gradient bubble, right-aligned
- Assistant messages: surface-colored bubble, left-aligned, with agent avatar
- Markdown rendering via `components/ui/markdown.tsx`
- Timestamps on hover
- Trace ID links on assistant messages (link to `/client/tracing`)

### Tool Call Display

**Not present.** The `ConversationTurn` type has `tool_called?: boolean` and `tool_name?: string` but these fields are not rendered in the chat UI. Tool calls are invisible to the user.

### Streaming

**Not present.** Chat uses request/response pattern:
1. User sends message
2. Frontend shows `TypingIndicator`
3. Backend processes and returns complete response
4. Frontend renders complete response

No SSE, WebSocket, or streaming support.

### Conversation History

- `useChat` hook fetches history via `chatApi.getSessionMessages(sessionId)`
- History is flattened from agent-grouped conversations into chronological messages
- Deduplication of user messages by content+timestamp
- Sessions listed via `useSessions()` → `chatApi.listSessions()`
- Session rename via `chatApi.renameSession()`

### Error/Loading States

- `TypingIndicator` component (animated dots) shown while waiting for response
- Error messages set via `toast.error()` when send fails
- Error state displayed as text (not retry button)
- Session list shows skeleton loading state

### How Integration Tool Outputs Should Be Displayed

Currently there is no special rendering for tool outputs. For integrations, the chat UI will need:
- **Structured tool output cards** — e.g., Jira ticket card, Slack message preview, email draft
- **Tool execution indicators** — "Searching Jira...", "Sending email..."
- **Action confirmation dialogs** — "Agent wants to send this email. Approve?"
- **Rich previews** — file attachments from Google Drive, Outlook calendar events
- **Error states** — "Slack connection expired. Reconnect?"

---

## 11. Existing Integration/Settings UI

### What Already Exists

| Feature | Status | Details |
|---------|--------|---------|
| Integration settings page | **Missing** | No `/settings/integrations` or `/integrations` page exists |
| OAuth connect buttons | **Partial** | MCP OAuth flow exists via `ConnectMcpSheet` (for MCP servers only) |
| Connected account cards | **Missing** | No card-based connected accounts view |
| Disconnect/reconnect flow | **Missing** | MCP servers can be deleted but no reconnect/reauthorize flow |
| Provider status | **Partial** | `McpStatusBadge` shows MCP server status but not integration-level status |
| Webhook status | **Missing** | No webhook management UI |
| User-level connected apps | **Missing** | No per-user integration connections |
| Org-level connected apps | **Missing** | No per-org integration settings |
| Admin integration controls | **Missing** | No admin UI to enable/disable integrations for the platform |

### What Exists That Could Be Reused

1. **MCP OAuth flow** (`mcpApi.oauthStart()`) — the pattern of starting an OAuth flow and opening in a new tab is established
2. **MCP catalog browsing** — the catalog search + card selection pattern could be adapted for an integration catalog
3. **MCP status badges** — the status badge component pattern could be extended for integration status
4. **Settings page structure** — the admin/client settings pages provide a layout pattern for integration settings sections
5. **DataTable + Pagination** — the table pattern is mature and reusable for connected accounts listing
6. **ConnectMcpSheet** slide-out panel — the side sheet pattern is excellent for connect/configure flows

### What Needs to Be Added

1. **Integration settings page** (`/client/settings/integrations` or `/integrations`)
2. **Integration provider catalog** with status, connect/disconnect per provider
3. **OAuth callback route** (`/integrations/callback`) for OAuth redirect handling
4. **Connected accounts management** per user and per org
5. **Integration permission controls** in admin settings
6. **Token expiry monitoring** and refresh prompts
7. **Webhook management panel**
8. **Integration-specific configuration forms** (e.g., select Slack workspace/channel)

---

## 12. Frontend Readiness for Integrations

### Slack

| Aspect | Requirement | Readiness |
|--------|-------------|-----------|
| **Required UI screens** | OAuth connect page, workspace/channel selector, notification preferences, message preview in chat | Not started |
| **Required API calls** | `integrationsApi.connectSlack()`, `integrationsApi.listSlackChannels()`, `integrationsApi.disconnectSlack()`, `integrationsApi.getSlackStatus()` | Not started |
| **Required states** | Connection status, selected channels, workspace info, token validity | Not started |
| **Required permission checks** | Admin can enable/disable for org, user can connect personal Slack | Not started |
| **OAuth redirect needs** | Redirect to Slack OAuth → callback page → save token → redirect back to settings | MCP OAuth pattern exists but needs dedicated callback page |
| **UX complexity** | **Medium** — straightforward OAuth + channel selection |

### Microsoft Teams

| Aspect | Requirement | Readiness |
|--------|-------------|-----------|
| **Required UI screens** | Azure AD OAuth connect, Teams/channel selector, notification settings, adaptive card preview in chat | Not started |
| **Required API calls** | `integrationsApi.connectTeams()`, `integrationsApi.listTeamsChannels()`, `integrationsApi.disconnectTeams()` | Not started |
| **Required states** | Azure AD tenant info, team/channel selections, connection status | Not started |
| **Required permission checks** | Admin consent flow for org-wide Teams access, user consent for personal | Not started |
| **OAuth redirect needs** | Azure AD OAuth with admin consent → callback → token storage | Needs callback page + admin consent UI |
| **UX complexity** | **High** — Azure AD admin consent is complex, Teams API has nested team/channel hierarchy |

### Jira

| Aspect | Requirement | Readiness |
|--------|-------------|-----------|
| **Required UI screens** | Atlassian OAuth connect, site/project selector, issue type mapping, Jira ticket cards in chat | Not started |
| **Required API calls** | `integrationsApi.connectJira()`, `integrationsApi.listJiraProjects()`, `integrationsApi.getJiraStatus()` | Not started |
| **Required states** | Atlassian site info, selected projects, field mappings | Not started |
| **Required permission checks** | Org admin enables Jira, users connect personal Atlassian accounts | Not started |
| **OAuth redirect needs** | Atlassian OAuth 2.0 (3LO) → callback → site selection → token storage | Needs callback page |
| **UX complexity** | **Medium** — standard OAuth + project/issue type configuration |

### ClickUp

| Aspect | Requirement | Readiness |
|--------|-------------|-----------|
| **Required UI screens** | OAuth connect, workspace/space/list selector, task cards in chat | Not started |
| **Required API calls** | `integrationsApi.connectClickUp()`, `integrationsApi.listClickUpSpaces()` | Not started |
| **Required states** | Workspace info, hierarchy selections, connection status | Not started |
| **Required permission checks** | Org admin enables ClickUp, users connect personal accounts | Not started |
| **OAuth redirect needs** | ClickUp OAuth → callback → workspace selection | Needs callback page |
| **UX complexity** | **Medium** — similar to Jira with hierarchical workspace structure |

### Gmail

| Aspect | Requirement | Readiness |
|--------|-------------|-----------|
| **Required UI screens** | Google OAuth connect, email compose preview in chat, permission scope selector | Not started |
| **Required API calls** | `integrationsApi.connectGmail()`, `integrationsApi.getGmailStatus()`, `integrationsApi.disconnectGmail()` | Not started |
| **Required states** | Google account info, connected email address, scope permissions | Not started |
| **Required permission checks** | User-level only (personal email), org admin can enable/disable | Not started |
| **OAuth redirect needs** | Google OAuth with mail scopes → callback → token storage | Needs callback page |
| **UX complexity** | **Low-Medium** — standard Google OAuth, but email compose/preview in chat adds complexity |

### Outlook

| Aspect | Requirement | Readiness |
|--------|-------------|-----------|
| **Required UI screens** | Microsoft OAuth connect, email compose preview, calendar event preview | Not started |
| **Required API calls** | `integrationsApi.connectOutlook()`, `integrationsApi.getOutlookStatus()` | Not started |
| **Required states** | Microsoft account info, connected email, calendar access status | Not started |
| **Required permission checks** | User-level or org-level via Azure AD, admin controls scope | Not started |
| **OAuth redirect needs** | Microsoft OAuth with Mail/Calendar scopes → callback | Shares Azure AD callback with Teams |
| **UX complexity** | **Medium** — shares Azure AD OAuth with Teams, adds mail + calendar scopes |

### SharePoint

| Aspect | Requirement | Readiness |
|--------|-------------|-----------|
| **Required UI screens** | Microsoft OAuth connect, site/library browser, document picker, file preview | Not started |
| **Required API calls** | `integrationsApi.connectSharePoint()`, `integrationsApi.listSharePointSites()`, `integrationsApi.listSharePointLibraries()` | Not started |
| **Required states** | SharePoint site info, library selections, sync status | Not started |
| **Required permission checks** | Org admin enables SharePoint access, scoped by site permissions | Not started |
| **OAuth redirect needs** | Shares Azure AD OAuth → adds Sites.Read.All or similar scope | Shares callback with Teams/Outlook |
| **UX complexity** | **High** — complex site/library/folder hierarchy, document permissions |

### Google Drive

| Aspect | Requirement | Readiness |
|--------|-------------|-----------|
| **Required UI screens** | Google OAuth connect, folder browser, file picker, document preview | Not started |
| **Required API calls** | `integrationsApi.connectGoogleDrive()`, `integrationsApi.listDriveFolders()`, `integrationsApi.getDriveStatus()` | Not started |
| **Required states** | Google account info, selected folders, sync status | Not started |
| **Required permission checks** | User-level connection, org admin can enable/disable | Not started |
| **OAuth redirect needs** | Google OAuth with Drive scopes → callback → folder selection | Shares Google callback with Gmail |
| **UX complexity** | **Medium** — standard Google OAuth + folder tree component |

### OneDrive

| Aspect | Requirement | Readiness |
|--------|-------------|-----------|
| **Required UI screens** | Microsoft OAuth connect, folder browser, file picker | Not started |
| **Required API calls** | `integrationsApi.connectOneDrive()`, `integrationsApi.listOneDriveFolders()` | Not started |
| **Required states** | Microsoft account info, selected folders, sync status | Not started |
| **Required permission checks** | User-level or org-level, admin controls | Not started |
| **OAuth redirect needs** | Shares Azure AD OAuth → adds Files.Read scope | Shares callback with Teams/Outlook/SharePoint |
| **UX complexity** | **Medium** — shares Azure AD OAuth, simpler than SharePoint |

### Summary

| Integration | UX Complexity | OAuth Provider | Shares Callback |
|-------------|--------------|----------------|-----------------|
| Slack | Medium | Slack | Standalone |
| Microsoft Teams | High | Azure AD | With Outlook, SharePoint, OneDrive |
| Jira | Medium | Atlassian | With other Atlassian products |
| ClickUp | Medium | ClickUp | Standalone |
| Gmail | Low-Medium | Google | With Google Drive |
| Outlook | Medium | Azure AD | With Teams, SharePoint, OneDrive |
| SharePoint | High | Azure AD | With Teams, Outlook, OneDrive |
| Google Drive | Medium | Google | With Gmail |
| OneDrive | Medium | Azure AD | With Teams, Outlook, SharePoint |

**Effective OAuth providers:** 4 (Slack, Azure AD, Atlassian, Google, ClickUp)
**Callback pages needed:** 4-5 (one per OAuth provider, possibly consolidated into one generic callback)

---

## 13. Recommended Integration UI Architecture

### Where Integration Settings Should Live

```
/client/integrations                    ← Main integrations catalog page
/client/integrations/callback           ← Generic OAuth callback handler
/admin/settings → "Integrations" tab    ← Admin controls for enabling/disabling integrations
/client/settings → "Connected Apps" tab ← User-level connected apps
```

### How Provider Cards Should Work

Each integration provider should be a card showing:
- Provider logo + name
- Brief description
- Connection status badge (Connected / Not Connected / Error / Expired)
- Connected account info (email/workspace name)
- Connect / Disconnect / Reconnect button
- Settings gear icon for per-integration configuration

Cards should be grouped by category:
- **Communication:** Slack, Microsoft Teams
- **Project Management:** Jira, ClickUp
- **Email:** Gmail, Outlook
- **File Storage:** SharePoint, Google Drive, OneDrive

### How Connect/Disconnect Should Work

**Connect Flow:**
1. User clicks "Connect" on provider card
2. Frontend calls `integrationsApi.startOAuth(provider)` → gets `authorization_url`
3. Frontend opens OAuth URL (same tab or popup)
4. User authorizes in provider's UI
5. Provider redirects to `/client/integrations/callback?code=...&state=...`
6. Callback page sends code to backend → backend exchanges for token
7. Callback page redirects back to integrations page with success toast

**Disconnect Flow:**
1. User clicks "Disconnect" on connected provider card
2. Confirmation dialog: "Disconnect Slack? Agents using Slack tools will lose access."
3. Frontend calls `integrationsApi.disconnect(provider, connectionId)`
4. Card updates to "Not Connected" state

### How OAuth Callback Page Should Work

**File:** `/app/(dashboard)/client/integrations/callback/page.tsx`

1. Read `code`, `state`, `error` from URL search params
2. If `error` → show error message + "Return to Integrations" button
3. If `code` + `state` → call `integrationsApi.completeOAuth(provider, code, state)`
4. Show loading spinner during exchange
5. On success → redirect to `/client/integrations` with `?connected=<provider>` query param
6. Integrations page shows success toast for the connected provider

### How Connected Accounts Should Be Shown

Two levels:
- **Org-level connections** (admin-managed): Visible to all org members, used by all agents. Shown in admin settings.
- **User-level connections** (self-service): Only visible to the connecting user. Shown in user settings.

Each connected account card shows:
- Provider logo
- Connected email/account name
- Connection timestamp
- Last used timestamp
- Status (Active / Token Expired / Error)
- Scopes granted
- Actions: Reconnect, Disconnect, View Permissions

### How Agents Should Select Allowed Integrations/Tools

Extend the agent creation Step 2 (Tools) and Step 3 (MCP) to include:
- **Integration Tools section** — grouped by provider (e.g., "Slack: Send Message, Read Channel, Search Messages")
- **Integration selector** — checkboxes per integration tool, filtered by what's connected
- **Configuration per tool** — e.g., select allowed Slack channels for this agent

### How Errors and Expired Tokens Should Be Shown

1. **Global banner** (in TopNav or below it): "Your Slack connection has expired. [Reconnect]"
2. **Badge on sidebar** nav item: red dot on "Integrations" when any connection has issues
3. **Agent detail page warning**: "This agent uses Slack tools but the Slack connection has expired."
4. **Chat inline error**: When agent tries to use an expired integration, show error card in chat with reconnect link

### How Admins Should Manage Integration Permissions

**Admin Settings → Integrations tab:**
- List of all integration providers
- Toggle to enable/disable each for the entire org
- For enabled integrations:
  - Who can connect: "All users" / "Admins only" / "Specific roles"
  - Allowed scopes (if applicable)
  - Max connections per user
- Audit log of connection/disconnection events

---

## 14. Proposed Frontend Pages/Components

### New Pages

| Page | Recommended Path | Purpose |
|------|-----------------|---------|
| `IntegrationsIndexPage` | `app/(dashboard)/client/integrations/page.tsx` | Browse and manage integrations |
| `OAuthCallbackPage` | `app/(dashboard)/client/integrations/callback/page.tsx` | Handle OAuth redirects |
| `IntegrationDetailPage` | `app/(dashboard)/client/integrations/[provider]/page.tsx` | Provider-specific configuration |
| `AdminIntegrationsSettings` | Extend `app/(dashboard)/admin/settings/page.tsx` with Integrations tab | Org-level integration management |
| `UserConnectedApps` | Extend `app/(dashboard)/client/settings/page.tsx` with Connected Apps tab | User's connected accounts |

### New Components

| Component | Recommended Path | Purpose |
|-----------|-----------------|---------|
| `IntegrationProviderCard` | `components/integrations/integration-provider-card.tsx` | Card showing provider name, status, connect/disconnect actions |
| `ConnectedAccountCard` | `components/integrations/connected-account-card.tsx` | Card for a connected account with status, scopes, actions |
| `IntegrationStatusBadge` | `components/integrations/integration-status-badge.tsx` | Status badge: Connected / Not Connected / Expired / Error |
| `OAuthConnectButton` | `components/integrations/oauth-connect-button.tsx` | Button that initiates OAuth flow for a provider |
| `IntegrationCatalog` | `components/integrations/integration-catalog.tsx` | Grid of available integration cards |
| `IntegrationConfigSheet` | `components/integrations/integration-config-sheet.tsx` | Slide-out configuration panel (like ConnectMcpSheet) |
| `AgentIntegrationSelector` | `components/integrations/agent-integration-selector.tsx` | Multi-select for integration tools in agent creation |
| `ToolPermissionDisplay` | `components/integrations/tool-permission-display.tsx` | Shows what permissions/scopes a tool requires |
| `WebhookHealthPanel` | `components/integrations/webhook-health-panel.tsx` | Panel showing webhook endpoints and their health |
| `TokenExpiredBanner` | `components/integrations/token-expired-banner.tsx` | Global/contextual banner for expired OAuth tokens |
| `IntegrationAuditLog` | `components/integrations/integration-audit-log.tsx` | Table of integration connection/disconnection events |
| `ProviderLogo` | `components/integrations/provider-logo.tsx` | SVG logos for each integration provider |
| `ScopePermissionList` | `components/integrations/scope-permission-list.tsx` | List of OAuth scopes with descriptions |
| `IntegrationToolCard` | `components/integrations/integration-tool-card.tsx` | Tool card showing integration-specific actions (e.g., "Send Slack Message") |
| `ChannelSelector` | `components/integrations/channel-selector.tsx` | Slack/Teams channel picker |
| `FolderBrowser` | `components/integrations/folder-browser.tsx` | Google Drive/OneDrive/SharePoint folder tree browser |

### New Sidebar Navigation Item

Add to `components/layout/sidebar.tsx` client sections:

```typescript
{ label: 'Integrations', href: '/client/integrations', icon: <Plug size={17} />, permission: 'view_integration' }
```

---

## 15. Frontend Implementation Tasks

### New Pages

| # | Task | Estimated Size |
|---|------|---------------|
| 1 | Create `/client/integrations` page with provider catalog | Large |
| 2 | Create `/client/integrations/callback` OAuth callback page | Medium |
| 3 | Create `/client/integrations/[provider]` detail/config page | Medium |
| 4 | Add "Integrations" tab to admin settings page | Medium |
| 5 | Add "Connected Apps" tab to client settings page | Medium |

### New Components

| # | Task | Estimated Size |
|---|------|---------------|
| 6 | Build `IntegrationProviderCard` component | Medium |
| 7 | Build `ConnectedAccountCard` component | Medium |
| 8 | Build `IntegrationStatusBadge` component | Small |
| 9 | Build `OAuthConnectButton` component | Small |
| 10 | Build `IntegrationCatalog` grid layout | Medium |
| 11 | Build `IntegrationConfigSheet` slide-out panel | Large |
| 12 | Build `AgentIntegrationSelector` for agent creation | Medium |
| 13 | Build `TokenExpiredBanner` component | Small |
| 14 | Build `WebhookHealthPanel` component | Medium |
| 15 | Build `IntegrationAuditLog` component | Medium |
| 16 | Build `ProviderLogo` component with all provider SVGs | Small |
| 17 | Build `ChannelSelector` component (Slack/Teams) | Medium |
| 18 | Build `FolderBrowser` component (Drive/SharePoint/OneDrive) | Large |
| 19 | Build `ToolPermissionDisplay` component | Small |
| 20 | Build `IntegrationToolCard` for chat tool output rendering | Medium |

### New API Client Methods

| # | Task | File |
|---|------|------|
| 21 | Create `lib/api/integrations.ts` with all integration API methods | `lib/api/integrations.ts` |
| 22 | Add `listProviders()` — list available integration providers | |
| 23 | Add `getProviderStatus(provider)` — check connection status | |
| 24 | Add `startOAuth(provider, scopes)` — initiate OAuth flow | |
| 25 | Add `completeOAuth(provider, code, state)` — exchange code for token | |
| 26 | Add `disconnect(provider, connectionId)` — revoke connection | |
| 27 | Add `reconnect(provider, connectionId)` — refresh expired token | |
| 28 | Add `listConnections(orgId?)` — list all connections for user/org | |
| 29 | Add `getConnectionHealth(connectionId)` — check token validity | |
| 30 | Add `listIntegrationTools(provider)` — list available tools per provider | |
| 31 | Add `getWebhookStatus(provider)` — check webhook health | |
| 32 | Add `getAuditLog(orgId, provider?)` — integration event log | |
| 33 | Update `lib/api/index.ts` with new exports | `lib/api/index.ts` |

### New Types/Interfaces

| # | Task | File |
|---|------|------|
| 34 | Add `IntegrationProvider` interface | `types/index.ts` |
| 35 | Add `IntegrationConnection` interface | `types/index.ts` |
| 36 | Add `IntegrationStatus` type ('connected' \| 'disconnected' \| 'expired' \| 'error') | `types/index.ts` |
| 37 | Add `OAuthStartResponse` interface | `types/index.ts` |
| 38 | Add `IntegrationTool` interface | `types/index.ts` |
| 39 | Add `WebhookStatus` interface | `types/index.ts` |
| 40 | Add `IntegrationAuditEntry` interface | `types/index.ts` |
| 41 | Add `IntegrationPermissions` interface | `types/index.ts` |

### New Hooks

| # | Task | File |
|---|------|------|
| 42 | Create `useIntegrations()` — list providers + connection status | `hooks/use-integrations.ts` |
| 43 | Create `useIntegrationConnection(provider)` — single provider connection status | `hooks/use-integration-connection.ts` |
| 44 | Create `useIntegrationTools(provider)` — tools for a specific provider | `hooks/use-integration-tools.ts` |
| 45 | Create `useOAuthCallback()` — handle OAuth callback logic | `hooks/use-oauth-callback.ts` |
| 46 | Create `useTokenHealth()` — poll/check token expiry across integrations | `hooks/use-token-health.ts` |

### New State/Query Logic

| # | Task |
|---|------|
| 47 | Consider adding TanStack Query for integration state caching (prevents refetch storms) |
| 48 | Add integration connection status to global state (for banner/badge rendering) |
| 49 | Add WebSocket/SSE listener for real-time integration status changes |

### New Forms

| # | Task |
|---|------|
| 50 | Integration configuration form (per-provider settings) |
| 51 | Slack channel/workspace selection form |
| 52 | Jira project/issue type selection form |
| 53 | Google Drive folder selection form |
| 54 | Admin integration permissions form |

### New Permission Guards

| # | Task |
|---|------|
| 55 | Add `view_integration` permission to sidebar and route checks |
| 56 | Add `manage_integration` permission for connect/disconnect actions |
| 57 | Add `admin_integration` permission for org-level integration controls |
| 58 | Update `ROUTE_PERMISSIONS` map in `DashboardLayout` |

### New Error States

| # | Task |
|---|------|
| 59 | OAuth flow error page (user denied, timeout, server error) |
| 60 | Token expired inline error in chat |
| 61 | Integration unavailable error in agent creation |
| 62 | Rate limit error display for integration API calls |
| 63 | Scope mismatch warning (connected but missing required scopes) |

### New Tests

| # | Task |
|---|------|
| 64 | Set up Playwright test infrastructure (currently empty) |
| 65 | OAuth callback flow tests |
| 66 | Integration connect/disconnect flow tests |
| 67 | Agent creation with integration tools tests |
| 68 | Token expiry banner behavior tests |
| 69 | Permission-gated integration UI tests |

---

## 16. Frontend Risks and Unknowns

### Code Risks

| Risk | Severity | Detail |
|------|----------|--------|
| **Compromised `postcss.config.mjs`** | **Critical** | Contains obfuscated malicious JS appended after the valid config. Manipulates `global`, `require`, and `module`. Must be cleaned before any builds. |
| `ignoreBuildErrors: true` in next.config | **High** | Unknown TypeScript errors may exist. Adding new code could introduce subtle type bugs that are silently ignored. |
| No caching layer | **Medium** | Every navigation refetches data. Adding integration status checks on every page load could create excessive API calls. |
| localStorage for tokens | **Medium** | Tokens are XSS-accessible. Integration OAuth tokens (if stored client-side) inherit this risk. |
| Proxy.ts only checks token presence | **Medium** | `proxy.ts` verifies the `access_token` cookie exists but doesn't validate token validity or user role. Integration callback routes need careful auth handling. |
| No test suite | **High** | Zero test coverage. Integration flows (OAuth, multi-step connection) are high-risk to ship without tests. |
| Manual API client | **Low** | No auto-generated types from backend OpenAPI. Integration API contract mismatches won't be caught at build time. |
| Dual lockfiles | **Low** | Both `package-lock.json` and `pnpm-lock.yaml` exist, creating ambiguity about which package manager is canonical. |

### UX Risks

| Risk | Severity | Detail |
|------|----------|--------|
| OAuth popup blocked | **Medium** | Current MCP OAuth flow uses `window.open()` which can be blocked by browsers. Consider same-tab redirect instead. |
| No loading skeleton for integrations | **Low** | Current loading states use spinners. Integration catalog should use skeleton cards for better perceived performance. |
| Multi-provider confusion | **Medium** | Microsoft has 4 integrations (Teams, Outlook, SharePoint, OneDrive) sharing one OAuth. UX must clearly communicate which services are being connected. |
| No offline/error recovery | **Medium** | If OAuth callback fails, user has no way to retry without starting over. |

### Auth Risks

| Risk | Severity | Detail |
|------|----------|--------|
| Token storage security | **High** | Integration OAuth tokens should NOT be stored in the frontend. Backend must handle all token storage and refresh. |
| CSRF on OAuth callback | **Medium** | OAuth state parameter must be validated server-side to prevent CSRF attacks. |
| Scope escalation | **Medium** | Need UI to clearly show what permissions each integration requests. Users should not be surprised by access level. |
| Token refresh UX | **Medium** | How does the frontend handle mid-session token expiry? Silent refresh or user intervention? |

### API Dependency Risks

| Risk | Severity | Detail |
|------|----------|--------|
| No backend integration API exists yet | **Critical** | All integration API endpoints need to be built. Frontend cannot proceed without API contract. |
| No OpenAPI spec | **Medium** | Without a spec, frontend and backend may diverge on types, endpoints, and error formats. |
| Rate limiting unknown | **Medium** | Third-party APIs (Slack, Microsoft Graph, etc.) have rate limits. Backend must handle this, but frontend needs error states. |
| Webhook delivery | **Low** | Webhook status depends on backend infrastructure. Frontend can only display status, not debug delivery issues. |

### Missing Backend Endpoints (Assumed Needed)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/integrations/providers` | GET | List available integration providers |
| `/integrations/connections` | GET | List user/org connections |
| `/integrations/{provider}/oauth/start` | POST | Start OAuth flow |
| `/integrations/{provider}/oauth/callback` | POST | Complete OAuth exchange |
| `/integrations/{provider}/disconnect` | POST | Revoke connection |
| `/integrations/{provider}/reconnect` | POST | Refresh token |
| `/integrations/{provider}/status` | GET | Check connection health |
| `/integrations/{provider}/tools` | GET | List available tools |
| `/integrations/{provider}/config` | GET/PUT | Provider-specific configuration |
| `/integrations/audit-log` | GET | Connection event log |
| `/integrations/webhooks` | GET | Webhook status |

### Missing Design System Components

| Component | Purpose |
|-----------|---------|
| Dropdown select with search | For channel/project/folder selection |
| Tree browser | For Drive/SharePoint folder hierarchy |
| Multi-step wizard (beyond Stepper) | For complex connection flows |
| Confirmation dialog | For disconnect/destructive actions (currently uses `window.confirm()`) |
| Banner/Alert strip | For token expiry warnings |
| Logo/icon library | Integration provider logos |

### Questions to Ask Before Implementation

1. **Backend API contract:** What are the exact endpoints, request/response shapes, and error codes for integration management?
2. **Token storage:** Will the backend store all OAuth tokens, or will some be stored client-side?
3. **OAuth flow:** Same-tab redirect or popup window? Which providers require which flow?
4. **Org vs. user connections:** Which integrations support org-level connections (admin-managed) vs. user-level (self-service)?
5. **Scope granularity:** Can users select which scopes/permissions to grant, or is it all-or-nothing?
6. **Webhook architecture:** Does the backend handle webhook ingestion, or does the frontend need to display webhook URLs for manual setup?
7. **Integration tool mapping:** How are integration tools (e.g., "Slack: Send Message") represented in the tool registry? New tool type? MCP-based?
8. **Agent-integration linking:** Are integrations linked at the agent level, org level, or both?
9. **Rate limiting:** How should the frontend display rate limit errors from third-party APIs?
10. **Mobile support:** Are integration settings needed on mobile viewport, or desktop-only?
11. **Real-time status:** Should integration connection status be polled or pushed (WebSocket)?
12. **Multi-org support:** Can a super admin manage integrations across multiple orgs?

---

## 17. Final Summary

### Is Frontend Integration-Ready?

**No.** The frontend has zero integration-specific UI. However, the codebase is well-structured and provides reusable patterns (MCP OAuth flow, catalog browsing, status badges, slide-out sheets, data tables) that can be extended for integrations.

### Best Frontend Path Forward

1. **Define the backend API contract first** — frontend work is blocked on knowing the integration API endpoints
2. **Add TanStack Query** — the current useState/useEffect pattern won't scale for integration status polling; integration state needs caching and background refetching
3. **Build the integration infrastructure layer** — API client, types, hooks, before any UI
4. **Start with one provider** (recommend Slack — simplest OAuth, most visual) as a proof-of-concept
5. **Build the generic integration framework** — provider cards, OAuth callback, status badges
6. **Extend to remaining providers** — add provider-specific configuration forms
7. **Update agent creation flow** — add integration tool selection step
8. **Add chat tool output rendering** — structured cards for integration tool results

### Top 10 Frontend Files to Understand First

| # | File | Why |
|---|------|-----|
| 1 | `lib/api/client.ts` | Core API layer — all backend communication goes through here |
| 2 | `contexts/auth-context.tsx` | Auth state — user, permissions, login/logout |
| 3 | `types/index.ts` | All TypeScript interfaces — the frontend's data contract |
| 4 | `components/layout/dashboard-layout.tsx` | Route protection + layout structure |
| 5 | `lib/api/mcp-servers.ts` | Best existing example of OAuth/connection API patterns |
| 6 | `components/mcp/connect-mcp-sheet.tsx` | Best existing example of connection UI (catalog + custom + test + OAuth) |
| 7 | `components/layout/sidebar.tsx` | Navigation structure + permission filtering |
| 8 | `hooks/use-mcp-servers.ts` | Data fetching hook pattern used throughout |
| 9 | `app/(dashboard)/client/agents/create/page.tsx` | Multi-step form pattern with tool/MCP selection |
| 10 | `app/(dashboard)/client/playground/page.tsx` | Chat UI — where integration tool outputs will appear |

### Top 10 Frontend Files Likely to Change for Integrations

| # | File | Change |
|---|------|--------|
| 1 | `types/index.ts` | Add ~10 new interfaces for integrations |
| 2 | `lib/api/index.ts` | Export new `integrationsApi` module |
| 3 | `components/layout/sidebar.tsx` | Add "Integrations" nav item |
| 4 | `components/layout/dashboard-layout.tsx` | Add integration route permissions |
| 5 | `components/layout/top-nav.tsx` | Add token expiry notification/banner |
| 6 | `app/(dashboard)/client/agents/create/page.tsx` | Add integration tool selection step |
| 7 | `app/(dashboard)/client/settings/page.tsx` | Add "Connected Apps" section |
| 8 | `app/(dashboard)/admin/settings/page.tsx` | Add "Integrations" admin controls |
| 9 | `app/(dashboard)/client/playground/page.tsx` | Add structured tool output cards |
| 10 | `contexts/auth-context.tsx` | Potentially add integration connection status to auth context |

---

*End of document. This overview is a read-only analysis — no code was changed.*
