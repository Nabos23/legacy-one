'use client'

import { useEffect, useRef, useState } from 'react'
import { ExternalLink, Camera, Loader2, Mail, Building2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
import { InfoBox } from '@/components/ui/info-box'
import { Badge } from '@/components/ui/badge'
import { IconTile } from '@/components/ui/icon-tile'
import { SettingsCard } from './settings-card'
import { useAuth } from '@/contexts/auth-context'
import { useToast } from '@/hooks/use-toast'
import { usersApi } from '@/lib/api'

const MAX_AVATAR_BYTES = 5 * 1024 * 1024
const ACCEPTED_AVATAR_TYPES = ['image/png', 'image/jpeg', 'image/gif', 'image/webp']

const ROLE_LABELS: Record<string, string> = {
  user: 'User',
  org_manager: 'Org Manager',
  org_admin: 'Org Admin',
  super_admin: 'Super Admin',
}

/** Self-service profile card — name + avatar are editable by the user; email/org/role require an admin. */
export function ProfileSection({ requestEmail = 'admin@oneai.dev' }: { requestEmail?: string }) {
  const { user, setUser } = useAuth()
  const { toast } = useToast()

  const [name, setName] = useState(user?.name ?? '')
  const [savingName, setSavingName] = useState(false)
  const [uploadingAvatar, setUploadingAvatar] = useState(false)
  const avatarInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    setName(user?.name ?? '')
  }, [user?.name])

  const nameChanged = name.trim() !== '' && name.trim() !== user?.name

  const saveName = async () => {
    const trimmed = name.trim()
    if (!trimmed) {
      toast.error('Name cannot be empty')
      return
    }
    setSavingName(true)
    try {
      const updated = await usersApi.updateMe(trimmed)
      setUser(updated)
      toast.success('Name updated')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not update name')
    } finally {
      setSavingName(false)
    }
  }

  const handleAvatarSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    if (!ACCEPTED_AVATAR_TYPES.includes(file.type)) {
      toast.error('Upload a PNG, JPEG, GIF, or WEBP image')
      return
    }
    if (file.size > MAX_AVATAR_BYTES) {
      toast.error('Image must be under 5MB')
      return
    }
    setUploadingAvatar(true)
    try {
      const updated = await usersApi.uploadAvatar(file)
      setUser(updated)
      toast.success('Profile picture updated')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not upload image')
    } finally {
      setUploadingAvatar(false)
    }
  }

  const avatarSeed = encodeURIComponent(user?.name ?? 'user')

  return (
    <SettingsCard>
      <div className="flex items-center gap-5 mb-6">
        <div className="relative group shrink-0">
          <img
            src={user?.avatar_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${avatarSeed}`}
            alt=""
            className="w-20 h-20 rounded-full ring-4 ring-violet-500/15 border-2 border-[var(--surface)] object-cover shadow-md"
          />
          <button
            type="button"
            onClick={() => avatarInputRef.current?.click()}
            disabled={uploadingAvatar}
            aria-label="Change profile picture"
            className="absolute -bottom-1 -right-1 flex items-center justify-center w-8 h-8 rounded-full bg-violet-600 text-white shadow-lg ring-2 ring-[var(--surface)] hover:bg-violet-700 transition-colors disabled:opacity-70"
          >
            {uploadingAvatar ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Camera className="w-3.5 h-3.5" />
            )}
          </button>
          <input
            ref={avatarInputRef}
            type="file"
            accept={ACCEPTED_AVATAR_TYPES.join(',')}
            onChange={handleAvatarSelect}
            className="hidden"
          />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-[19px] font-bold text-[var(--text-1)] truncate">
              {user?.name ?? 'Your account'}
            </h2>
            <Badge variant="primary">{ROLE_LABELS[user?.role ?? ''] ?? user?.role}</Badge>
          </div>
          <p className="text-[13.5px] text-[var(--text-3)] mt-0.5 truncate">{user?.email}</p>
          <p className="text-[11px] text-[var(--text-3)]/70 mt-1">
            PNG, JPEG, GIF or WEBP — up to 5MB
          </p>
        </div>
      </div>

      <Separator className="mb-6" />

      <div className="space-y-5">
        <div>
          <label className="text-[13px] font-medium block mb-2 text-[var(--text-1)]">
            Full Name
          </label>
          <div className="flex gap-2">
            <Input value={name} onChange={e => setName(e.target.value)} placeholder="Your name" />
            <Button
              variant={nameChanged ? 'primary' : 'secondary'}
              size="sm"
              onClick={saveName}
              disabled={!nameChanged || savingName}
              className="shrink-0 h-9"
            >
              {savingName ? 'Saving…' : 'Save'}
            </Button>
          </div>
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          <div className="flex items-center gap-3 p-3 rounded-xl bg-[var(--surface-2)] border border-[var(--border)]">
            <IconTile icon={Mail} size="sm" color="neutral" />
            <div className="min-w-0">
              <p className="text-[11px] text-[var(--text-3)] uppercase tracking-wide">Email</p>
              <p className="text-[13.5px] font-medium text-[var(--text-1)] truncate">{user?.email}</p>
            </div>
          </div>
          <div className="flex items-center gap-3 p-3 rounded-xl bg-[var(--surface-2)] border border-[var(--border)]">
            <IconTile icon={Building2} size="sm" color="neutral" />
            <div className="min-w-0">
              <p className="text-[11px] text-[var(--text-3)] uppercase tracking-wide">Organization ID</p>
              <p className="text-[13px] font-mono text-[var(--text-1)] truncate">{user?.organization_id}</p>
            </div>
          </div>
        </div>
      </div>

      <InfoBox variant="warning" className="mt-6">
        Email, organization, and role can only be changed by your administrator.
      </InfoBox>

      <div className="mt-4 pt-4 border-t border-[var(--border)]">
        <a href={`mailto:${requestEmail}?subject=Profile%20change%20request&body=User:%20${user?.email}`}>
          <Button variant="ghost" size="sm">
            <ExternalLink className="w-4 h-4 mr-2" />
            Request Changes
          </Button>
        </a>
      </div>
    </SettingsCard>
  )
}
