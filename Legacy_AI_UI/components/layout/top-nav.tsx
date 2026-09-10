'use client'

import { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  Menu,
  Search,
  Bell,
  Settings,
  LogOut,
  ChevronDown,
  Moon,
  Sun,
  ShieldCheck,
  Shield,
  Users,
  User as UserIcon,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { IconTile } from '@/components/ui/icon-tile'
import { Separator } from '@/components/ui/separator'
import { CommandPalette, useCommandPalette } from '@/components/layout/command-palette'
import { NotificationCenter } from '@/components/layout/notification-center'
import { Breadcrumb, crumbsFromPath } from '@/components/ui/breadcrumb'
import { useSidebar } from '@/hooks/use-sidebar'
import { useNotifications } from '@/hooks/use-notifications'
import { useAuth } from '@/contexts/auth-context'
import { useTheme } from '@/contexts/theme-context'
import { useBreadcrumbLabels } from '@/contexts/breadcrumb-context'
import { cn } from '@/lib/utils'

interface TopNavProps {
  variant?: 'client' | 'admin'
}

/** Friendly label/icon/tone per role — falls back to a title-cased raw value for
 * any role string the backend adds later that isn't listed here. */
const ROLE_CONFIG: Record<string, { label: string; icon: typeof Shield; variant: 'primary' | 'info' | 'neutral' }> = {
  super_admin: { label: 'Super Admin', icon: ShieldCheck, variant: 'primary' },
  org_admin: { label: 'Org Admin', icon: Shield, variant: 'primary' },
  org_manager: { label: 'Org Manager', icon: Users, variant: 'info' },
  user: { label: 'Member', icon: UserIcon, variant: 'neutral' },
}

function roleConfig(role?: string) {
  if (role && ROLE_CONFIG[role]) return ROLE_CONFIG[role]
  const label = (role ?? 'Member').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
  return { label, icon: UserIcon, variant: 'neutral' as const }
}

export function TopNav({ variant = 'client' }: TopNavProps) {
  const { toggleMobile } = useSidebar()
  const { user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const pathname = usePathname()
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [showNotifications, setShowNotifications] = useState(false)
  const { open, setOpen } = useCommandPalette()
  const {
    items: notifications,
    loading: notificationsLoading,
    error: notificationsError,
    unreadCount,
    refetch: refetchNotifications,
    markAllRead,
    dismiss: dismissNotification,
  } = useNotifications()

  const breadcrumbLabels = useBreadcrumbLabels()
  const crumbs = crumbsFromPath(pathname ?? '', breadcrumbLabels)
  const displayName = user?.name ?? 'Guest'
  const displayEmail = user?.email ?? ''
  const avatarSeed = encodeURIComponent(displayName)
  const navVariant = pathname?.startsWith('/admin') ? 'admin' : variant

  return (
    <>
      {/*
        Same glass as sidebar header: bg-white/[0.88] dark:bg-[#0b0b18]/90 + backdrop-blur-2xl
        Same border-b: border-black/[0.06] dark:border-white/[0.06]
        This makes the two headers visually merge into one continuous chrome bar.
      */}
      <header
        className="sticky top-0 z-30 h-[56px] flex items-center px-4 gap-3
          bg-white/[0.88] dark:bg-[#0b0b18]/90
          backdrop-blur-2xl
          border-b border-black/[0.06] dark:border-white/[0.06]"
      >
        {/* Left — mobile hamburger + breadcrumb */}
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleMobile}
            className="lg:hidden text-[var(--text-2)] hover:bg-black/[0.05] dark:hover:bg-white/[0.06]"
          >
            <Menu className="w-5 h-5" />
          </Button>

          <Breadcrumb items={crumbs} className="hidden sm:flex" />
        </div>

        {/* Center — search bar trigger */}
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Search"
          className="hidden md:flex items-center gap-2.5 w-[220px] lg:w-[280px] h-9 px-3.5
            rounded-full overflow-hidden
            bg-black/[0.04] dark:bg-white/[0.05]
            border border-black/[0.08] dark:border-white/[0.08]
            text-[13px] text-[var(--text-3)]
            hover:border-violet-400/50 dark:hover:border-violet-500/40
            hover:bg-black/[0.06] dark:hover:bg-white/[0.08]
            hover:text-[var(--text-1)]
            focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/40
            transition-all duration-200 group"
        >
          <Search className="w-3.5 h-3.5 shrink-0 text-[var(--text-3)] group-hover:text-violet-500 transition-colors duration-200" />
          <span className="flex-1 text-left truncate text-[13px]">
            Search...
          </span>
          <kbd className="text-[10px] px-1.5 py-0.5 rounded-md font-mono shrink-0
            bg-black/[0.06] dark:bg-white/[0.08]
            border border-black/[0.07] dark:border-white/[0.08]
            text-[var(--text-3)]">
            ⌘K
          </kbd>
        </button>

        {/* Right — icon actions + user */}
        <div className="flex items-center gap-0.5">
          {/* Theme toggle */}
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleTheme}
            aria-label="Toggle theme"
            className="text-[var(--text-2)] hover:text-[var(--text-1)]
              hover:bg-black/[0.05] dark:hover:bg-white/[0.06]"
          >
            {theme === 'dark'
              ? <Sun className="w-[17px] h-[17px]" />
              : <Moon className="w-[17px] h-[17px]" />
            }
          </Button>

          {/* Notification bell */}
          <Button
            variant="ghost"
            size="icon"
            className="relative text-[var(--text-2)] hover:text-[var(--text-1)]
              hover:bg-black/[0.05] dark:hover:bg-white/[0.06]"
            onClick={() => {
              setShowNotifications(v => {
                if (!v) refetchNotifications()
                return !v
              })
            }}
          >
            <Bell className="w-[17px] h-[17px]" />
            {unreadCount > 0 && (
              <span className="absolute top-[9px] right-[9px] w-2 h-2 rounded-full
                bg-violet-500 border-2
                border-white dark:border-[#0b0b18]" />
            )}
          </Button>

          {/* User avatar + menu */}
          <div className="relative ml-1">
            <button
              type="button"
              onClick={() => setShowUserMenu(!showUserMenu)}
              aria-expanded={showUserMenu}
              className={cn(
                'flex items-center gap-2 pl-1 pr-2.5 py-1 rounded-xl',
                'transition-[background-color,transform] duration-150 active:scale-[0.97]',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/50',
                showUserMenu ? 'bg-black/[0.05] dark:bg-white/[0.06]' : 'hover:bg-black/[0.05] dark:hover:bg-white/[0.06]',
              )}
            >
              <div className="relative">
                <img
                  src={user?.avatar_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${avatarSeed}`}
                  alt={displayName}
                  className={cn(
                    'w-7 h-7 rounded-full object-cover ring-2 transition-[box-shadow]',
                    showUserMenu ? 'ring-violet-500/60' : 'ring-violet-400/40',
                  )}
                />
                <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5
                  bg-emerald-500 dark:bg-emerald-400 rounded-full
                  border-2 border-white dark:border-[#0b0b18]" />
              </div>
              <span className="hidden sm:block text-[13px] font-medium text-[var(--text-1)] max-w-[100px] truncate">
                {displayName.split(' ')[0]}
              </span>
              <ChevronDown className={cn(
                'w-3.5 h-3.5 text-[var(--text-3)] hidden sm:block transition-transform duration-200',
                showUserMenu && 'rotate-180',
              )} />
            </button>

            {showUserMenu && (() => {
              const { label: roleLabel, icon: RoleIcon, variant: roleVariant } = roleConfig(user?.role)
              return (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setShowUserMenu(false)} />
                  <div className="absolute right-0 mt-2 w-[240px] z-50 animate-scaleIn origin-top-right
                    rounded-2xl overflow-hidden
                    bg-white/90 dark:bg-[#111122]/95
                    backdrop-blur-2xl
                    border border-black/[0.08] dark:border-white/[0.1]
                    shadow-[0_8px_40px_rgba(0,0,0,0.12)] dark:shadow-[0_8px_40px_rgba(0,0,0,0.6)]">

                    {/* User info header */}
                    <div className="px-4 py-4">
                      <div className="flex items-center gap-3">
                        <img
                          src={user?.avatar_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${avatarSeed}`}
                          alt={displayName}
                          className="w-10 h-10 rounded-2xl ring-2 ring-violet-400/40 object-cover shadow-sm"
                        />
                        <div className="min-w-0">
                          <p className="text-[13.5px] font-semibold text-[var(--text-1)] truncate">{displayName}</p>
                          <p className="text-[11px] text-[var(--text-3)] truncate mt-0.5">{displayEmail}</p>
                        </div>
                      </div>
                      <Badge variant={roleVariant} className="mt-3 text-[10px] gap-1">
                        <RoleIcon className="w-3 h-3" />
                        {roleLabel}
                      </Badge>
                    </div>

                    <Separator className="opacity-50" />

                    <div className="p-1.5">
                      <Link
                        href={pathname?.startsWith('/admin') ? '/admin/settings' : '/client/settings'}
                        className="flex items-center gap-2.5 px-2.5 py-2 rounded-xl text-[13px] text-[var(--text-2)]
                          hover:bg-black/[0.04] dark:hover:bg-white/[0.05]
                          hover:text-[var(--text-1)] active:scale-[0.98] transition-[background-color,color,transform]
                          focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/50"
                        onClick={() => setShowUserMenu(false)}
                      >
                        <IconTile icon={Settings} size="sm" color="neutral" />
                        Settings
                      </Link>

                      <button
                        type="button"
                        onClick={() => logout()}
                        className="w-full text-left mt-0.5 px-2.5 py-2 rounded-xl text-[13px]
                          flex items-center gap-2.5
                          text-[var(--text-3)]
                          hover:bg-red-50 dark:hover:bg-red-500/10
                          hover:text-red-600 dark:hover:text-red-400
                          active:scale-[0.98] transition-[background-color,color,transform]
                          focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500/40"
                      >
                        <IconTile icon={LogOut} size="sm" color="danger" />
                        Log out
                      </button>
                    </div>
                  </div>
                </>
              )
            })()}
          </div>
        </div>
      </header>

      <CommandPalette open={open} onOpenChange={setOpen} variant={navVariant} />
      <NotificationCenter
        open={showNotifications}
        onClose={() => setShowNotifications(false)}
        notifications={notifications}
        loading={notificationsLoading}
        error={notificationsError}
        onMarkAllRead={markAllRead}
        onDismiss={dismissNotification}
      />
    </>
  )
}
