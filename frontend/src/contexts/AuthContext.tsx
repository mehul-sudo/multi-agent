import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { authApi, tokenStore, type UserProfile } from '../lib/api'

interface AuthState {
  user: UserProfile | null
  isLoading: boolean
  isAuthenticated: boolean
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>
  register: (username: string, email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isLoading: true,
    isAuthenticated: false,
  })

  // On mount: try to restore session
  useEffect(() => {
    const token = tokenStore.getAccess()
    if (!token) {
      setState({ user: null, isLoading: false, isAuthenticated: false })
      return
    }
    authApi.me()
      .then((user) => setState({ user, isLoading: false, isAuthenticated: true }))
      .catch(() => {
        tokenStore.clear()
        setState({ user: null, isLoading: false, isAuthenticated: false })
      })
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const response = await authApi.login(email, password)
    tokenStore.setTokens(response.access_token, response.refresh_token)
    setState({ user: response.user, isLoading: false, isAuthenticated: true })
  }, [])

  const register = useCallback(async (username: string, email: string, password: string) => {
    await authApi.register(username, email, password)
  }, [])

  const logout = useCallback(async () => {
    await authApi.logout()
    setState({ user: null, isLoading: false, isAuthenticated: false })
  }, [])

  return (
    <AuthContext.Provider value={{ ...state, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
