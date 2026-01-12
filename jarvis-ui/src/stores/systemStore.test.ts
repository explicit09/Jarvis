import { describe, it, expect, beforeEach } from 'vitest'
import { useSystemStore } from './systemStore'

describe('systemStore', () => {
  beforeEach(() => {
    // Reset store state before each test
    useSystemStore.setState({
      isConnected: false,
      activeTool: null,
      metrics: {
        asrLatency: 0,
        llmLatency: 0,
        ttsLatency: 0,
        e2eLatency: 0,
      },
      hubInfo: null,
    })
  })

  describe('setIsConnected', () => {
    it('should set connected to true', () => {
      const { setIsConnected } = useSystemStore.getState()
      setIsConnected(true)
      expect(useSystemStore.getState().isConnected).toBe(true)
    })

    it('should set connected to false', () => {
      useSystemStore.setState({ isConnected: true })
      const { setIsConnected } = useSystemStore.getState()
      setIsConnected(false)
      expect(useSystemStore.getState().isConnected).toBe(false)
    })
  })

  describe('setActiveTool', () => {
    it('should set active tool', () => {
      const { setActiveTool } = useSystemStore.getState()
      setActiveTool('web_search')
      expect(useSystemStore.getState().activeTool).toBe('web_search')
    })

    it('should clear active tool', () => {
      useSystemStore.setState({ activeTool: 'some_tool' })
      const { setActiveTool } = useSystemStore.getState()
      setActiveTool(null)
      expect(useSystemStore.getState().activeTool).toBe(null)
    })
  })

  describe('setMetrics', () => {
    it('should set ASR latency', () => {
      const { setMetrics } = useSystemStore.getState()
      setMetrics({ asrLatency: 150 })
      expect(useSystemStore.getState().metrics.asrLatency).toBe(150)
    })

    it('should set LLM latency', () => {
      const { setMetrics } = useSystemStore.getState()
      setMetrics({ llmLatency: 500 })
      expect(useSystemStore.getState().metrics.llmLatency).toBe(500)
    })

    it('should set TTS latency', () => {
      const { setMetrics } = useSystemStore.getState()
      setMetrics({ ttsLatency: 200 })
      expect(useSystemStore.getState().metrics.ttsLatency).toBe(200)
    })

    it('should set E2E latency', () => {
      const { setMetrics } = useSystemStore.getState()
      setMetrics({ e2eLatency: 850 })
      expect(useSystemStore.getState().metrics.e2eLatency).toBe(850)
    })

    it('should merge multiple metrics', () => {
      const { setMetrics } = useSystemStore.getState()
      setMetrics({ asrLatency: 100, llmLatency: 300 })

      const { metrics } = useSystemStore.getState()
      expect(metrics.asrLatency).toBe(100)
      expect(metrics.llmLatency).toBe(300)
      expect(metrics.ttsLatency).toBe(0) // Unchanged
    })

    it('should preserve existing metrics when partially updating', () => {
      useSystemStore.setState({
        metrics: {
          asrLatency: 100,
          llmLatency: 200,
          ttsLatency: 300,
          e2eLatency: 600,
        },
      })

      const { setMetrics } = useSystemStore.getState()
      setMetrics({ llmLatency: 250 })

      const { metrics } = useSystemStore.getState()
      expect(metrics.asrLatency).toBe(100)
      expect(metrics.llmLatency).toBe(250)
      expect(metrics.ttsLatency).toBe(300)
      expect(metrics.e2eLatency).toBe(600)
    })
  })

  describe('setHubInfo', () => {
    it('should set hub info', () => {
      const { setHubInfo } = useSystemStore.getState()
      const hubInfo = {
        hubIp: '192.168.1.100',
        hubPort: 18000,
        clientsConnected: 3,
      }
      setHubInfo(hubInfo)
      expect(useSystemStore.getState().hubInfo).toEqual(hubInfo)
    })

    it('should clear hub info', () => {
      useSystemStore.setState({
        hubInfo: { hubIp: '10.0.0.1', hubPort: 8000, clientsConnected: 1 },
      })
      const { setHubInfo } = useSystemStore.getState()
      setHubInfo(null)
      expect(useSystemStore.getState().hubInfo).toBe(null)
    })
  })
})
