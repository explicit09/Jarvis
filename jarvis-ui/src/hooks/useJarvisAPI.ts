import { useCallback } from 'react'
import { useConversationStore } from '../stores/conversationStore'
import { useSystemStore } from '../stores/systemStore'
import { useVoiceStore } from '../stores/voiceStore'

const API_BASE = 'http://localhost:18000'

export function useJarvisAPI() {
  const { addMessage, sessionId, setIsLoading } = useConversationStore()
  const { setMetrics, setIsConnected, setActiveTool } = useSystemStore()
  const { setState } = useVoiceStore()

  const checkConnection = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/healthz`)
      const data = await res.json()
      setIsConnected(data.ok === true)
      return data.ok === true
    } catch {
      setIsConnected(false)
      return false
    }
  }, [setIsConnected])

  const sendChat = useCallback(async (text: string): Promise<{ text: string } | null> => {
    setIsLoading(true)
    setState('processing')

    addMessage({ role: 'user', content: text })

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, session_id: sessionId }),
      })

      const data = await res.json()

      if (data.ok) {
        addMessage({ role: 'assistant', content: data.response })
        if (data.metrics) {
          setMetrics({ llmLatency: data.metrics.llm_ms })
        }
        return { text: data.response }
      }

      return null
    } catch (error) {
      console.error('Chat error:', error)
      addMessage({ role: 'assistant', content: 'Connection error. Please try again.' })
      return null
    } finally {
      setIsLoading(false)
      setState('idle')
    }
  }, [sessionId, addMessage, setIsLoading, setMetrics, setState])

  const sendVoice = useCallback(async (audioBlob: Blob): Promise<{ text: string } | null> => {
    setIsLoading(true)
    setState('processing')

    try {
      const formData = new FormData()
      formData.append('audio', audioBlob, 'recording.webm')

      const res = await fetch(`${API_BASE}/voice/ptt?session_id=${sessionId}`, {
        method: 'POST',
        body: formData,
      })

      const data = await res.json()

      if (data.ok) {
        addMessage({ role: 'user', content: data.transcript })
        addMessage({ role: 'assistant', content: data.response })
        setMetrics({
          asrLatency: data.metrics?.asr_ms || 0,
          llmLatency: data.metrics?.llm_ms || 0,
          e2eLatency: data.metrics?.e2e_ms || 0,
        })
        return { text: data.response }
      }

      return null
    } catch (error) {
      console.error('Voice error:', error)
      return null
    } finally {
      setIsLoading(false)
      setState('idle')
    }
  }, [sessionId, addMessage, setIsLoading, setMetrics, setState])

  const speak = useCallback(async (text: string): Promise<ArrayBuffer | null> => {
    setState('speaking')
    setActiveTool('tts')

    try {
      const res = await fetch(`${API_BASE}/speak`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      })

      if (res.ok) {
        const ttsMs = res.headers.get('X-TTS-MS')
        if (ttsMs) {
          setMetrics({ ttsLatency: parseInt(ttsMs) })
        }
        return await res.arrayBuffer()
      }
      return null
    } catch (error) {
      console.error('TTS error:', error)
      return null
    } finally {
      setState('idle')
      setActiveTool(null)
    }
  }, [setState, setMetrics, setActiveTool])

  const getHubInfo = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/hub/info`)
      const data = await res.json()
      useSystemStore.getState().setHubInfo({
        hubIp: data.hub_ip,
        hubPort: data.hub_port,
        clientsConnected: data.clients_connected,
      })
      return data
    } catch {
      return null
    }
  }, [])

  return {
    checkConnection,
    sendChat,
    sendVoice,
    speak,
    getHubInfo,
  }
}
