'use client'

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react'
import type { UserPublic } from '@/types'
import { authApi } from '@/lib/api'
import { API_FORBIDDEN_EVENT } from '@/lib/api/client'
import { setAuthCookie, clearAuthCookie } from '@/lib/auth-cookies'

interface AuthContextType {
  user: UserPublic | null
  permissions: Record<string, boolean>
  loading: boolean
  login: (email: string, password: string, rememberMe?: boolean) => Promise<UserPublic>
  completeOAuthLogin: (token: string) => Promise<UserPublic>
  logout: () => void
  isAuthenticated: boolean
  /** Updates the in-memory user (e.g. after a profile/avatar change) without a full re-auth. */
  setUser: (user: UserPublic) => void
  /** Re-fetches resolved permissions from backend and syncs React state & cookies immediately. */
  refreshPermissions: () => Promise<Record<string, boolean>>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserPublic | null>(null)
  const [permissions, setPermissions] = useState<Record<string, boolean>>({})
  const [loading, setLoading] = useState(true)

  const refreshPermissions = useCallback(async () => {
    const token = localStorage.getItem('access_token')
    if (!token) return {}
    try {
      const perms = await authApi.mePermissions()
      const remembered = localStorage.getItem('remember_me') === 'true'
      const isOrgAdmin = perms.is_org_admin || user?.role === 'org_admin' || user?.role === 'org admin' || user?.role === 'admin'
      const permsObj: Record<string, boolean> = {
        ...(perms.resolved_permissions || {}),
        is_super_admin: perms.is_super_admin || false,
        is_org_admin: Boolean(isOrgAdmin),
      }
      setAuthCookie(token, remembered, user?.role, permsObj)
      setPermissions(permsObj)
      return permsObj
    } catch {
      return {}
    }
  }, [user?.role])

  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem('access_token')
      if (token) {
        const remembered = localStorage.getItem('remember_me') === 'true'
        setAuthCookie(token, remembered)
        try {
          const [userData, permissionsData] = await Promise.all([
            authApi.me(),
            authApi.mePermissions().catch(() => ({ user_id: '', role_stored: '', is_super_admin: false, is_org_admin: false, resolved_permissions: {} as Record<string, boolean> }))
          ])
          setUser(userData)
          const isOrgAdmin = permissionsData.is_org_admin || userData.role === 'org_admin' || userData.role === 'org admin' || userData.role === 'admin'
          const permsObj: Record<string, boolean> = {
            ...(permissionsData.resolved_permissions || {}),
            is_super_admin: permissionsData.is_super_admin || false,
            is_org_admin: isOrgAdmin,
          }
          setAuthCookie(token, remembered, userData.role, permsObj)
          setPermissions(permsObj)
        } catch {
          localStorage.removeItem('access_token')
          clearAuthCookie()
        }
      }
      setLoading(false)
    }
    checkAuth()
  }, [])

  useEffect(() => {
    if (!user) return
    const onFocus = () => {
      refreshPermissions()
    }
    const onForbidden = () => {
      refreshPermissions()
    }
    window.addEventListener('focus', onFocus)
    window.addEventListener(API_FORBIDDEN_EVENT, onForbidden)
    return () => {
      window.removeEventListener('focus', onFocus)
      window.removeEventListener(API_FORBIDDEN_EVENT, onForbidden)
    }
  }, [user, refreshPermissions])

  const login = async (email: string, password: string, rememberMe = false) => {
    const response = await authApi.login(email, password)
    localStorage.setItem('access_token', response.access_token)
    localStorage.setItem('remember_me', String(rememberMe))
    setUser(response.user)
    try {
      const perms = await authApi.mePermissions()
      const isOrgAdmin = perms.is_org_admin || response.user.role === 'org_admin' || response.user.role === 'org admin' || response.user.role === 'admin'
      const permsObj: Record<string, boolean> = {
        ...(perms.resolved_permissions || {}),
        is_super_admin: perms.is_super_admin || false,
        is_org_admin: isOrgAdmin,
      }
      setAuthCookie(response.access_token, rememberMe, response.user.role, permsObj)
      setPermissions(permsObj)
    } catch {
      setAuthCookie(response.access_token, rememberMe, response.user.role)
      setPermissions({})
    }
    return response.user
  }

  const completeOAuthLogin = useCallback(async (token: string) => {
    localStorage.setItem('access_token', token)
    localStorage.setItem('remember_me', 'true')
    try {
      const [userData, perms] = await Promise.all([
        authApi.me(),
        authApi.mePermissions().catch(() => null),
      ])
      setUser(userData)
      const isOrgAdmin = perms?.is_org_admin || userData.role === 'org_admin' || userData.role === 'org admin' || userData.role === 'admin'
      const permsObj: Record<string, boolean> = perms ? {
        ...(perms.resolved_permissions || {}),
        is_super_admin: perms.is_super_admin || false,
        is_org_admin: isOrgAdmin,
      } : {}
      setAuthCookie(token, true, userData.role, permsObj)
      setPermissions(permsObj)
      return userData
    } catch (error) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('remember_me')
      clearAuthCookie()
      throw error
    }
  }, [])

  const logout = () => {
    authApi.logout().catch(() => {})
    localStorage.removeItem('access_token')
    localStorage.removeItem('remember_me')
    clearAuthCookie()
    setUser(null)
    setPermissions({})
    window.location.href = '/login'
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        permissions,
        loading,
        login,
        completeOAuthLogin,
        logout,
        isAuthenticated: !!user,
        setUser,
        refreshPermissions,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
