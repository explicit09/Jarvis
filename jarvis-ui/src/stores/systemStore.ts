import { create } from 'zustand'

interface Metrics {
  asrLatency: number
  llmLatency: number
  ttsLatency: number
  e2eLatency: number
}

interface SystemStore {
  isConnected: boolean
  activeTool: string | null
  metrics: Metrics
  hubInfo: {
    hubIp: string
    hubPort: number
    clientsConnected: number
  } | null

  setIsConnected: (isConnected: boolean) => void
  setActiveTool: (tool: string | null) => void
  setMetrics: (metrics: Partial<Metrics>) => void
  setHubInfo: (info: SystemStore['hubInfo']) => void
}

export const useSystemStore = create<SystemStore>((set) => ({
  isConnected: false,
  activeTool: null,
  metrics: {
    asrLatency: 0,
    llmLatency: 0,
    ttsLatency: 0,
    e2eLatency: 0,
  },
  hubInfo: null,

  setIsConnected: (isConnected) => set({ isConnected }),
  setActiveTool: (activeTool) => set({ activeTool }),
  setMetrics: (metrics) =>
    set((state) => ({ metrics: { ...state.metrics, ...metrics } })),
  setHubInfo: (hubInfo) => set({ hubInfo }),
}))
