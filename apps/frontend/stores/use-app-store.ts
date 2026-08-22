import { create } from 'zustand'

export type HealthFilter = 'ALL' | 'Healthy' | 'Degraded' | 'Critical'

interface AppState {
  selectedConnectionId: string | null
  healthFilter: HealthFilter
  pollingIntervalMs: number
  isLiveMode: boolean
  setSelectedConnectionId: (id: string | null) => void
  setHealthFilter: (filter: HealthFilter) => void
  setPollingIntervalMs: (ms: number) => void
  setIsLiveMode: (isLive: boolean) => void
}

export const useAppStore = create<AppState>((set) => ({
  selectedConnectionId: null,
  healthFilter: 'ALL',
  pollingIntervalMs: 5000,
  isLiveMode: true,
  setSelectedConnectionId: (id) => set({ selectedConnectionId: id }),
  setHealthFilter: (healthFilter) => set({ healthFilter }),
  setPollingIntervalMs: (pollingIntervalMs) => set({ pollingIntervalMs }),
  setIsLiveMode: (isLiveMode) => set({ isLiveMode }),
}))
