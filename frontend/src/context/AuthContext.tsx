import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api } from '../api/client'
import type { AuthUser } from '../types'

interface AuthContextValue {
  user: AuthUser | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

function isTokenExpired(): boolean {
  const expires = localStorage.getItem('foh_token_expires')
  if (!expires) return true
  return new Date(expires) <= new Date()
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  const logout = useCallback(() => {
    localStorage.removeItem('foh_access_token')
    localStorage.removeItem('foh_token_expires')
    setUser(null)
  }, [])

  const logoutExpired = useCallback(() => {
    sessionStorage.setItem('foh_session_expired', '1')
    logout()
  }, [logout])

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.login(email, password)
    localStorage.setItem('foh_access_token', res.accessToken)
    localStorage.setItem('foh_token_expires', res.expiresAt)
    setUser(res.user)
  }, [])

  useEffect(() => {
    async function restore() {
      const token = localStorage.getItem('foh_access_token')
      if (!token || isTokenExpired()) {
        logout()
        setLoading(false)
        return
      }
      try {
        const me = await api.getMe()
        setUser(me)
      } catch {
        logout()
      } finally {
        setLoading(false)
      }
    }
    restore()
  }, [logout])

  useEffect(() => {
    const interval = setInterval(() => {
      if (user && isTokenExpired()) logoutExpired()
    }, 60_000)
    return () => clearInterval(interval)
  }, [user, logoutExpired])

  const value = useMemo(
    () => ({ user, loading, login, logout }),
    [user, loading, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
