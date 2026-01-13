import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useJarvisAPI } from './useJarvisAPI'
import { useConversationStore } from '../stores/conversationStore'
import { useSystemStore } from '../stores/systemStore'
import { useVoiceStore } from '../stores/voiceStore'

describe('useJarvisAPI', () => {
  const mockFetch = vi.fn()

  beforeEach(() => {
    // Reset all stores
    useConversationStore.setState({
      messages: [],
      isLoading: false,
      sessionId: 'test-session',
    })
    useSystemStore.setState({
      isConnected: false,
      activeTool: null,
      metrics: { asrLatency: 0, llmLatency: 0, ttsLatency: 0, e2eLatency: 0 },
      hubInfo: null,
    })
    useVoiceStore.setState({
      state: 'idle',
      isRecording: false,
      audioLevel: 0,
      frequencyData: null,
    })

    // Setup fetch mock
    globalThis.fetch = mockFetch
    mockFetch.mockClear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('checkConnection', () => {
    it('should set connected to true when healthz returns ok', async () => {
      mockFetch.mockResolvedValueOnce({
        json: () => Promise.resolve({ ok: true }),
      })

      const { result } = renderHook(() => useJarvisAPI())

      let connected: boolean = false
      await act(async () => {
        connected = await result.current.checkConnection()
      })

      expect(connected).toBe(true)
      expect(useSystemStore.getState().isConnected).toBe(true)
    })

    it('should set connected to false when healthz fails', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'))

      const { result } = renderHook(() => useJarvisAPI())

      let connected: boolean = true
      await act(async () => {
        connected = await result.current.checkConnection()
      })

      expect(connected).toBe(false)
      expect(useSystemStore.getState().isConnected).toBe(false)
    })

    it('should set connected to false when healthz returns not ok', async () => {
      mockFetch.mockResolvedValueOnce({
        json: () => Promise.resolve({ ok: false }),
      })

      const { result } = renderHook(() => useJarvisAPI())

      let connected: boolean = true
      await act(async () => {
        connected = await result.current.checkConnection()
      })

      expect(connected).toBe(false)
      expect(useSystemStore.getState().isConnected).toBe(false)
    })
  })

  describe('sendChat', () => {
    it('should send chat message and receive response', async () => {
      mockFetch.mockResolvedValueOnce({
        json: () =>
          Promise.resolve({
            ok: true,
            response: 'Hello! How can I help?',
            metrics: { llm_ms: 150 },
          }),
      })

      const { result } = renderHook(() => useJarvisAPI())

      let response: { text: string } | null = null
      await act(async () => {
        response = await result.current.sendChat('Hello')
      })

      expect(response).toEqual({ text: 'Hello! How can I help?' })

      // Check messages were added
      const { messages } = useConversationStore.getState()
      expect(messages).toHaveLength(2)
      expect(messages[0].role).toBe('user')
      expect(messages[0].content).toBe('Hello')
      expect(messages[1].role).toBe('assistant')
      expect(messages[1].content).toBe('Hello! How can I help?')
    })

    it('should set loading state during request', async () => {
      let resolvePromise: (value: unknown) => void
      mockFetch.mockReturnValueOnce(
        new Promise((resolve) => {
          resolvePromise = resolve
        })
      )

      const { result } = renderHook(() => useJarvisAPI())

      act(() => {
        result.current.sendChat('Test')
      })

      // Should be loading
      expect(useConversationStore.getState().isLoading).toBe(true)

      // Resolve the request
      await act(async () => {
        resolvePromise!({
          json: () => Promise.resolve({ ok: true, response: 'Response' }),
        })
      })

      // Should no longer be loading
      expect(useConversationStore.getState().isLoading).toBe(false)
    })

    it('should handle chat error', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'))

      const { result } = renderHook(() => useJarvisAPI())

      let response: { text: string } | null = { text: 'not null' }
      await act(async () => {
        response = await result.current.sendChat('Hello')
      })

      expect(response).toBe(null)

      // Should add error message
      const { messages } = useConversationStore.getState()
      const lastMessage = messages[messages.length - 1]
      expect(lastMessage.role).toBe('assistant')
      expect(lastMessage.content).toContain('error')
    })

    it('should update metrics on successful response', async () => {
      mockFetch.mockResolvedValueOnce({
        json: () =>
          Promise.resolve({
            ok: true,
            response: 'Test',
            metrics: { llm_ms: 250 },
          }),
      })

      const { result } = renderHook(() => useJarvisAPI())

      await act(async () => {
        await result.current.sendChat('Hello')
      })

      expect(useSystemStore.getState().metrics.llmLatency).toBe(250)
    })
  })

  describe('speak', () => {
    it('should call speak endpoint and return audio', async () => {
      const audioBuffer = new ArrayBuffer(100)
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'X-TTS-MS': '150' }),
        arrayBuffer: () => Promise.resolve(audioBuffer),
      })

      const { result } = renderHook(() => useJarvisAPI())

      let audio: ArrayBuffer | null = null
      await act(async () => {
        audio = await result.current.speak('Hello world')
      })

      expect(audio).toBe(audioBuffer)
      expect(useSystemStore.getState().metrics.ttsLatency).toBe(150)
    })

    it('should set voice state to speaking during TTS', async () => {
      let resolvePromise: (value: unknown) => void
      mockFetch.mockReturnValueOnce(
        new Promise((resolve) => {
          resolvePromise = resolve
        })
      )

      const { result } = renderHook(() => useJarvisAPI())

      act(() => {
        result.current.speak('Test')
      })

      // Should be speaking
      expect(useVoiceStore.getState().state).toBe('speaking')

      // Resolve
      await act(async () => {
        resolvePromise!({
          ok: true,
          headers: new Headers(),
          arrayBuffer: () => Promise.resolve(new ArrayBuffer(10)),
        })
      })

      // Should be idle
      expect(useVoiceStore.getState().state).toBe('idle')
    })

    it('should return null on speak error', async () => {
      mockFetch.mockRejectedValueOnce(new Error('TTS error'))

      const { result } = renderHook(() => useJarvisAPI())

      let audio: ArrayBuffer | null = new ArrayBuffer(1)
      await act(async () => {
        audio = await result.current.speak('Hello')
      })

      expect(audio).toBe(null)
    })
  })
})
