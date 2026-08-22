import { create } from 'zustand'

export interface UserProfile {
  id: string
  email: string
  fullName?: string
  role?: string
}

interface AuthState {
  user: UserProfile | null
  token: string | null
  isAuthenticated: boolean
  setUser: (user: UserProfile | null, token?: string | null) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  setUser: (user, token = null) =>
    set({
      user,
      token,
      isAuthenticated: Boolean(user),
    }),
  logout: () =>
    set({
      user: null,
      token: null,
      isAuthenticated: false,
    }),
}))
