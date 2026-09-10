# Enterprise Auth & User Onboarding

> **Status:** Planned — not yet implemented  
> **Created:** 2026-06-08  
> **Context:** Design doc from product/architecture discussion on how ONE-AI should handle client login, sign-up, and enterprise-grade access control.

---

## Summary

For an enterprise-grade B2B platform like ONE-AI, **open public sign-up is not the primary onboarding path**. Access should be **provisioned, controlled, and audited**.

**Recommended approach:** Platform admin creates organizations and invites users. Clients log in at `/login`. Public `/register` should be disabled in production (or limited to trial/dev only).

---

## Current State (as of this doc)

### What exists today

| Feature | Location | Notes |
|---|---|---|
| Login | `/login` | Email + password via `POST /auth/login` |
| Self sign-up | `/register` | Creates account + auto personal org via `POST /auth/register` |
| Admin creates user | `/admin/users/create` | Name, email, password, role (`admin` \| `member`) |
| Admin creates org | `/admin/organizations/create` | Name, description, plan |
| Role redirect | `lib/auth-cookies.ts` | `admin` → `/admin/dashboard`, `member` → `/client/dashboard` |
| Route protection | `proxy.ts` | Checks JWT cookie exists; does **not** enforce role per route |
| Forgot password | `/forgot-password` | OTP flow |

### Current roles

```ts
role: 'admin' | 'member'
```

- `member` → client workspace (`/client/*`)
- `admin` → admin dashboard (`/admin/*`) — currently overloaded (platform + org)

### Known gaps

- Public `/register` creates an isolated personal org — users cannot join an existing company org
- Admin "Create User" has no `organization_id` selector
- No invite-email flow (admin sets password manually)
- No SSO (SAML/OIDC), SCIM, or domain verification
- 2FA, audit logging, session policies exist as **UI toggles only** in `/admin/settings`
- Any logged-in user can navigate to both `/client/*` and `/admin/*` URLs

---

## Approach Comparison

### Option A: Self sign-up (`/register`)

**How it works:** User fills name, email, password → backend creates account + personal org → auto-login.

**Good for:**
- Dev/demo environments
- Free trial / solo developers
- Low-friction "try the product" funnels

**Bad for enterprise because:**
- Each user gets their own org (no shared company workspace)
- No control over who can create accounts
- No join-existing-org flow
- Hard to align with IT procurement and security reviews

### Option B: Admin-provisioned users (recommended primary)

**How it works:** Platform admin creates org → creates/invites users → client logs in at `/login`.

**Good for:**
- B2B / enterprise customers
- Correct multi-tenancy (`organization_id` scoping)
- IT-controlled access
- Auditability and offboarding

### Recommendation

| Environment | Approach |
|---|---|
| **Production** | Admin-provisioned users + invite flow. Disable `/register`. |
| **Staging / dev** | Keep `/register` optional for testing |
| **Free trial (optional)** | Self-signup with personal org, or invite-only trial orgs |

---

## Enterprise Mental Model

Think in **three layers**, not just "admin vs client":

```
┌─────────────────────────────────────────────────────────┐
│  PLATFORM LAYER (ONE-AI operator — us)                    │
│  Super Admin: orgs, billing, global tool registry, health │
└──────────────────────────┬──────────────────────────────┘
                           │ creates
┌──────────────────────────▼──────────────────────────────┐
│  TENANT LAYER (customer company — e.g. Acme Corp)        │
│  Org Admin: invite users, org settings, security policy  │
└──────────────────────────┬──────────────────────────────┘
                           │ invites
┌──────────────────────────▼──────────────────────────────┐
│  USER LAYER (customer employees)                         │
│  Members: agents, tools, playground, analytics, traces     │
└─────────────────────────────────────────────────────────┘
```

| Layer | Who | Responsibilities |
|---|---|---|
| **Platform** | ONE-AI operator | Onboard customers, create orgs, plans, platform monitoring |
| **Tenant** | Customer IT / team lead | Invite employees, assign roles, org security |
| **User** | Employees | Use agents and tools within their org only |

---

## Enterprise Onboarding Flow

### Standard customer journey

```
1. Acme Corp signs contract
2. Platform admin creates org "Acme Corp" (Enterprise plan)
3. Platform admin invites jane@acme.com as Org Admin
4. Jane receives invite email → sets password (or uses SSO)
5. Jane invites team from Client Settings → Team
6. Engineers log in → land on /client/dashboard
7. When someone leaves, IT disables them in IdP → access revoked
```

### Authentication methods (by maturity)

| Method | Typical use |
|---|---|
| **Email invite + set password** | SMB / early enterprise |
| **SSO (SAML/OIDC)** | Microsoft Entra ID, Okta, Google Workspace — most enterprise deals |
| **SCIM provisioning** | Auto sync users from corporate directory (joiners/leavers) |

Password-only `/login` is acceptable for **dev/demo**, not for production enterprise.

---

## Target Role Model

Current `admin` / `member` is too coarse. Target model:

| Role | Scope | Permissions (summary) |
|---|---|---|
| **Platform Super Admin** | Whole ONE-AI platform | Orgs, billing, global tool registry, system settings |
| **Org Admin** | One customer org | Invite users, org settings, view billing |
| **Agent Builder** | One org | Create/edit agents, tools, DB connections |
| **Agent User** | One org | Playground, analytics — no admin actions |
| **Auditor / Viewer** | One org | Read-only traces, logs, compliance exports |

### Route access (target)

| Role | `/admin/*` | `/client/*` |
|---|---|---|
| Platform Super Admin | ✅ | ✅ (optional) |
| Org Admin | ❌ | ✅ + team/settings |
| Agent Builder | ❌ | ✅ + create/edit |
| Agent User | ❌ | ✅ use only |
| Auditor | ❌ | ✅ read-only |

---

## Enterprise Security Requirements

Features hinted in `/admin/settings` that must be **enforced** in production:

1. **SSO required** — Sign in with Microsoft/Okta; optional disable local passwords
2. **MFA** — Enforced via IdP or native app MFA
3. **Domain verification** — Only `@acme.com` emails can join Acme's org
4. **Session policies** — Idle timeout (e.g. 30m), configurable duration
5. **RBAC** — Least privilege per role
6. **Audit logs** — Immutable log: who created/edited/deleted agents, tools, DB connections, users
7. **Data isolation** — Every API call scoped by `organization_id`
8. **Offboarding** — Disable in IdP → immediate access revocation (SCIM)

---

## Gap Analysis: Today vs Enterprise

| Capability | Today | Enterprise target |
|---|---|---|
| Public `/register` | ✅ Enabled | ❌ Disabled in prod |
| Admin creates users | ✅ Basic | ✅ + org assignment + invite email |
| Invite links | UI copy only | ✅ Tokenized invite flow |
| Org assignment on user create | ❌ Missing | ✅ Required |
| SSO (Entra/Okta) | ❌ | ✅ Phase 3 |
| SCIM | ❌ | ✅ Phase 3 |
| Org Admin role (tenant layer) | ❌ | ✅ Phase 2 |
| Domain-restricted join | ❌ | ✅ Phase 2 |
| Role-based route guards | ❌ Token only | ✅ Role + org enforced |
| MFA / 2FA | UI toggle | ✅ Enforced |
| Audit logging | UI toggle | ✅ Real audit trail |
| API org scoping | Partial | ✅ Strict on all endpoints |

---

## Implementation Phases

### Phase 1 — B2B MVP (highest priority)

- [ ] Disable public `/register` in production (`NEXT_PUBLIC_ALLOW_REGISTER=false` or middleware redirect)
- [ ] Add `organization_id` to admin Create User form (`/admin/users/create`)
- [ ] Replace manual password handoff with **invite email** flow
  - Admin creates user → backend sends invite link → user sets password on first visit
- [ ] Enforce role-based route guards in `proxy.ts` / middleware
  - `member` → block `/admin/*`
  - platform admin only → allow `/admin/*`
- [ ] Ensure all API calls enforce `organization_id` from JWT (backend)

**Files likely touched:**
- `proxy.ts`
- `app/(dashboard)/admin/users/create/page.tsx`
- `lib/api/users.ts`
- `lib/validations/organization.ts`
- `app/(auth)/register/page.tsx` (gate or remove)
- Backend: invite token endpoints, org on user create

### Phase 2 — Mid-market enterprise

- [ ] Introduce **Org Admin** role inside client workspace
- [ ] Client Settings → Team management (invite, remove, change role)
- [ ] Domain allowlist per org (e.g. only `@acme.com`)
- [ ] Real audit log page (client + admin views)
- [ ] Enforce session timeout and MFA settings (backend + middleware)
- [ ] Split `admin` into `platform_admin` vs `org_admin`

**Files likely touched:**
- `types/index.ts` (role enum)
- `app/(dashboard)/client/settings/page.tsx` (team tab)
- New: `app/(dashboard)/client/settings/team/page.tsx`
- New: `app/(dashboard)/admin/audit-log/page.tsx`

### Phase 3 — Full enterprise

- [ ] SSO via SAML/OIDC (Microsoft Entra ID, Okta)
- [ ] SCIM user provisioning (auto provision/deprovision)
- [ ] Per-org security policies (SSO required, MFA required, IP allowlist)
- [ ] Compliance exports (SOC2-style audit reports)
- [ ] Optional: separate admin API for platform operators

**Integrations to evaluate:**
- Microsoft Entra ID (OIDC/SAML + SCIM)
- Okta
- WorkOS / Auth0 B2B (accelerator options)

---

## Day-to-Day Flows (reference)

### Platform operator onboards new customer

```
Admin → Organizations → Create Organization
Admin → Users → Create User (org = Acme, role = org_admin)
System → sends invite email to jane@acme.com
Jane → clicks invite → sets password → /client/dashboard
```

### Org admin invites engineer

```
Jane → Client Settings → Team → Invite User
Bob enters email → receives invite → /client/dashboard
Bob uses Agents, Playground, Tracing (member role)
```

### Employee offboarding

```
IT disables bob@acme.com in Entra ID
SCIM/webhook revokes ONE-AI access immediately
Bob's sessions invalidated; audit log records deprovision event
```

---

## API Endpoints (existing backend reference)

From `ONE_AI_V0_PROMPT.md` Part 21:

| Module | Endpoints |
|---|---|
| Auth | `POST /auth/login`, `POST /auth/register`, `GET /auth/me`, `POST /auth/forgot-password`, `POST /users` (admin) |
| Organizations | CRUD + pagination |
| Users | List + create (admin) |

### Endpoints to add (planned)

| Endpoint | Purpose |
|---|---|
| `POST /auth/invite` | Send invite email with token |
| `POST /auth/accept-invite` | Set password + activate account |
| `GET /auth/invite/{token}` | Validate invite token |
| `POST /auth/sso/{provider}` | SSO initiation (Phase 3) |
| `GET /audit-logs` | Query audit events (Phase 2) |
| `POST /scim/v2/Users` | SCIM provisioning (Phase 3) |

---

## Environment Variables (planned)

```env
# Existing
NEXT_PUBLIC_API_URL=http://localhost:8000

# Phase 1
NEXT_PUBLIC_ALLOW_REGISTER=false

# Phase 3
NEXT_PUBLIC_SSO_ENABLED=true
NEXT_PUBLIC_SSO_PROVIDER=entra
ENTRA_TENANT_ID=
ENTRA_CLIENT_ID=
```

---

## Open Questions (decide before Phase 1)

1. **Trial users:** Disable `/register` entirely, or keep for `NEXT_PUBLIC_ALLOW_REGISTER=true` in staging only?
2. **First org admin:** Always created by platform admin, or self-serve after sales creates org?
3. **Password policy:** Min length, complexity, rotation — align with backend validation?
4. **Invite expiry:** 24h / 7d / configurable per org?
5. **Platform admin bootstrap:** How is the first super admin created? (seed script / env / manual DB)

---

## Related Files

| File | Relevance |
|---|---|
| `app/(auth)/login/page.tsx` | Login UI |
| `app/(auth)/register/page.tsx` | Self-signup (to gate/disable) |
| `app/(dashboard)/admin/users/create/page.tsx` | Admin user provisioning |
| `app/(dashboard)/admin/organizations/create/page.tsx` | Org creation |
| `app/(dashboard)/admin/settings/page.tsx` | Security toggles (to wire up) |
| `lib/auth-cookies.ts` | Post-login redirect by role |
| `proxy.ts` | Route protection (to extend with RBAC) |
| `contexts/auth-context.tsx` | Auth state |
| `types/index.ts` | `UserPublic`, roles |

---

## Decision Log

| Date | Decision |
|---|---|
| 2026-06-08 | Primary onboarding = admin-provisioned users, not open sign-up |
| 2026-06-08 | Split platform admin vs org admin in future phases |
| 2026-06-08 | Implement in 3 phases: B2B MVP → mid-market → full enterprise |
