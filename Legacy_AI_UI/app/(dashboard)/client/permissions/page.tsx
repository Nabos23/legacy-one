'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { RotateCcw, Save, Shield, Users2 } from 'lucide-react'
import { PageHeader } from '@/components/ui/page-header'
import { Tabs } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { useToast } from '@/hooks/use-toast'
import { useAuth } from '@/contexts/auth-context'
import { useTeams } from '@/hooks/use-teams'
import { authApi, rolePermissionsApi, teamsApi, type EditableRole } from '@/lib/api'
import type { PermissionDefinition, TeamPublic } from '@/types'

const EDITABLE_ROLES: EditableRole[] = ['org_manager', 'user']
type Mode = 'roles' | 'teams'

const humanizeResource = (resource: string) =>
  resource
    .split('_')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')

export default function PermissionsPage() {
  const { user, permissions, refreshPermissions } = useAuth()
  const { toast } = useToast()
  const orgId = user?.organization_id

  const [mode, setMode] = useState<Mode>('roles')
  const [role, setRole] = useState<EditableRole>('org_manager')
  const [roleLabels, setRoleLabels] = useState<Record<string, string>>({})
  const [selectedTeamId, setSelectedTeamId] = useState<string>('')
  
  const [catalog, setCatalog] = useState<PermissionDefinition[]>([])
  const [checked, setChecked] = useState<Set<string>>(new Set())
  const [isOverride, setIsOverride] = useState(false)
  const [updatedAt, setUpdatedAt] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { data: teamsData, loading: teamsLoading } = useTeams(1, orgId ?? undefined, undefined, 100, mode === 'teams')
  const teams = teamsData?.items ?? []

  const requestIdRef = useRef(0)
  const roleRef = useRef<EditableRole>(role)
  roleRef.current = role

  // Set default selected team when switching to teams mode
  useEffect(() => {
    if (mode === 'teams' && teams.length > 0 && !selectedTeamId) {
      setSelectedTeamId(teams[0].id ?? '')
    }
  }, [mode, teams, selectedTeamId])

  useEffect(() => {
    authApi.allRoles()
      .then(roles => {
        const map: Record<string, string> = {}
        for (const r of roles) map[r.name] = r.label
        setRoleLabels(map)
      })
      .catch(() => setRoleLabels({}))
  }, [])

  useEffect(() => {
    authApi.permissionCatalog().then(setCatalog).catch(() => setCatalog([]))
  }, [])

  // Load Role or Team permissions
  useEffect(() => {
    if (!orgId) {
      setLoading(false)
      return
    }

    const requestId = ++requestIdRef.current
    setLoading(true)
    setError(null)

    if (mode === 'roles') {
      rolePermissionsApi.get(orgId, role)
        .then(res => {
          if (requestId !== requestIdRef.current) return
          setChecked(new Set(res.permission_names))
          setIsOverride(res.is_override)
          setUpdatedAt(res.updated_at ?? null)
        })
        .catch(e => {
          if (requestId !== requestIdRef.current) return
          setError(e instanceof Error ? e.message : 'Failed to load role permissions')
        })
        .finally(() => {
          if (requestId === requestIdRef.current) setLoading(false)
        })
    } else {
      if (!selectedTeamId) {
        setLoading(false)
        setChecked(new Set())
        return
      }
      teamsApi.getPermissions(selectedTeamId)
        .then(perms => {
          if (requestId !== requestIdRef.current) return
          setChecked(new Set(perms))
          setIsOverride(perms.length > 0)
          setUpdatedAt(null)
        })
        .catch(e => {
          if (requestId !== requestIdRef.current) return
          setError(e instanceof Error ? e.message : 'Failed to load team permissions')
        })
        .finally(() => {
          if (requestId === requestIdRef.current) setLoading(false)
        })
    }
  }, [orgId, role, mode, selectedTeamId])

  const grouped = useMemo(() => {
    const byResource = new Map<string, PermissionDefinition[]>()
    for (const p of catalog) {
      const list = byResource.get(p.resource) ?? []
      list.push(p)
      byResource.set(p.resource, list)
    }
    return [...byResource.entries()].sort(([a], [b]) => a.localeCompare(b))
  }, [catalog])

  const toggle = (name: string) => {
    setChecked(prev => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  const handleSave = async () => {
    if (!orgId) return
    const requestId = ++requestIdRef.current
    setSaving(true)
    try {
      if (mode === 'roles') {
        const savedRole = role
        const res = await rolePermissionsApi.update(orgId, savedRole, [...checked])
        if (requestId !== requestIdRef.current || roleRef.current !== savedRole) return
        setChecked(new Set(res.permission_names))
        setIsOverride(res.is_override)
        setUpdatedAt(res.updated_at ?? null)
        toast.success('Role permissions updated')
        refreshPermissions()
      } else {
        if (!selectedTeamId) return
        const updatedTeam = await teamsApi.updatePermissions(selectedTeamId, [...checked])
        if (requestId !== requestIdRef.current) return
        setChecked(new Set(updatedTeam.permissions ?? []))
        setIsOverride((updatedTeam.permissions ?? []).length > 0)
        toast.success('Team permissions updated')
        refreshPermissions()
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to save permissions')
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async () => {
    if (!orgId || mode !== 'roles') return
    const resetRole = role
    const requestId = ++requestIdRef.current
    setSaving(true)
    try {
      const res = await rolePermissionsApi.reset(orgId, resetRole)
      if (requestId !== requestIdRef.current || roleRef.current !== resetRole) return
      setChecked(new Set(res.permission_names))
      setIsOverride(res.is_override)
      setUpdatedAt(res.updated_at ?? null)
      toast.success('Reverted to default role permissions')
      refreshPermissions()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to reset permissions')
    } finally {
      setSaving(false)
    }
  }

  const canEdit = permissions.edit_role_permissions || permissions.edit_team

  return (
    <>
      <PageHeader
        title="Permissions"
        description="Customize permissions by Role or configure specific permissions for Teams"
      />

      <div className="flex flex-wrap items-center gap-3 mb-5">
        <Tabs
          value={mode}
          onChange={v => setMode(v as Mode)}
          tabs={[
            { value: 'roles', label: 'Role Permissions' },
            { value: 'teams', label: 'Team Permissions' },
          ]}
        />

        {mode === 'roles' ? (
          <Tabs
            value={role}
            onChange={v => setRole(v as EditableRole)}
            tabs={EDITABLE_ROLES.map(r => ({ value: r, label: roleLabels[r] ?? r }))}
          />
        ) : (
          <div className="w-64">
            <Select
              value={selectedTeamId}
              onValueChange={(v: string) => setSelectedTeamId(v)}
              options={teams.map(t => ({ value: t.id ?? '', label: t.name }))}
              placeholder={teamsLoading ? 'Loading teams…' : 'Select team…'}
            />
          </div>
        )}

        <Badge variant={isOverride ? 'primary' : 'neutral'}>
          {mode === 'roles' ? (isOverride ? 'Customized' : 'Default') : (checked.size > 0 ? `${checked.size} Granted` : 'No Team Perms')}
        </Badge>

        <div className="ml-auto flex items-center gap-2">
          {canEdit && (
            <>
              {mode === 'roles' && (
                <Button variant="secondary" size="sm" onClick={handleReset} disabled={saving || !isOverride}>
                  <RotateCcw className="w-3.5 h-3.5 mr-1.5" />
                  Reset to Default
                </Button>
              )}
              <Button variant="primary" size="sm" onClick={handleSave} disabled={saving || loading || (mode === 'teams' && !selectedTeamId)}>
                <Save className="w-3.5 h-3.5 mr-1.5" />
                Save Changes
              </Button>
            </>
          )}
        </div>
      </div>

      {error ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <p className="text-[16px] font-semibold text-[var(--text-1)]">Failed to load permissions</p>
          <p className="text-[14px] text-[var(--text-3)] mt-2 max-w-md">{error}</p>
        </div>
      ) : loading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full rounded-[var(--radius-lg)]" />
          ))}
        </div>
      ) : mode === 'teams' && !selectedTeamId ? (
        <div className="flex flex-col items-center justify-center py-16 text-center glass rounded-[var(--radius-lg)]">
          <Users2 className="w-10 h-10 text-[var(--text-3)] mb-3" />
          <p className="text-[15px] font-semibold text-[var(--text-1)]">No Team Selected</p>
          <p className="text-[13px] text-[var(--text-3)] mt-1 max-w-md">
            Select a team above to view and configure its custom team permissions.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {grouped.map(([resource, defs]) => (
            <div key={resource} className="glass rounded-[var(--radius-lg)] p-5">
              <h3 className="text-[14px] font-semibold mb-3">{humanizeResource(resource)}</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {defs.map(p => (
                  <label
                    key={p.name}
                    className="flex items-start gap-2.5 p-2 rounded-[var(--radius-sm)] cursor-pointer hover:bg-[var(--surface-2)]"
                  >
                    <Checkbox
                      checked={checked.has(p.name)}
                      onChange={() => toggle(p.name)}
                      disabled={!canEdit}
                    />
                    <span>
                      <span className="block text-[13.5px] font-medium">{p.label}</span>
                      <span className="block text-[12px] text-[var(--text-3)]">{p.description}</span>
                    </span>
                  </label>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {updatedAt && mode === 'roles' && (
        <p className="text-[12px] text-[var(--text-3)] mt-4">
          Last updated {new Date(updatedAt).toLocaleString()}
        </p>
      )}
    </>
  )
}
