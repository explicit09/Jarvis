import { useCallback, useRef, useState, useEffect } from 'react'
import { useVoiceStore } from '../stores/voiceStore'
import { useConversationStore } from '../stores/conversationStore'

type VoiceState = 'idle' | 'listening_wake_word' | 'listening_speech' | 'processing' | 'speaking'

interface VoiceEvent {
  type: string
  state: VoiceState
  text?: string
  wake_word?: string
}

interface UseVoiceWebSocketOptions {
  url?: string
  onReady?: () => void
  onWakeWordDetected?: () => void
  onTranscription?: (text: string) => void
  onResponse?: (text: string) => void
  onError?: (error: string) => void
}

export function useVoiceWebSocket({
  url = 'ws://localhost:18000/ws/voice',
  onReady,
  onWakeWordDetected,
  onTranscription,
  onResponse,
  onError,
}: UseVoiceWebSocketOptions = {}) {
  const [isConnected, setIsConnected] = useState(false)
  const [voiceState, setVoiceState] = useState<VoiceState>('idle')
  const [wakeWord, setWakeWord] = useState<string>('')

  const wsRef = useRef<WebSocket | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const audioQueueRef = useRef<ArrayBuffer[]>([])
  const isPlayingRef = useRef(false)

  const { setState: setStoreState, setAudioLevel } = useVoiceStore()
  const { addMessage } = useConversationStore()

  // Map voice state to store state
  const mapState = useCallback((state: VoiceState) => {
    switch (state) {
      case 'listening_wake_word':
      case 'listening_speech':
        return 'listening'
      case 'processing':
        return 'processing'
      case 'speaking':
        return 'speaking'
      default:
        return 'idle'
    }
  }, [])

  // Play audio from queue
  const playNextAudio = useCallback(async () => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) return

    isPlayingRef.current = true
    const audioData = audioQueueRef.current.shift()!

    try {
      const audioContext = new AudioContext()
      const audioBuffer = await audioContext.decodeAudioData(audioData)
      const source = audioContext.createBufferSource()
      source.buffer = audioBuffer
      source.connect(audioContext.destination)

      source.onended = () => {
        isPlayingRef.current = false
        playNextAudio() // Play next in queue
      }

      source.start(0)
    } catch (error) {
      console.error('Failed to play audio:', error)
      isPlayingRef.current = false
      playNextAudio()
    }
  }, [])

  // Handle WebSocket messages
  const handleMessage = useCallback((event: MessageEvent) => {
    if (event.data instanceof Blob) {
      // Binary audio data - convert to ArrayBuffer and queue for playback
      event.data.arrayBuffer().then(buffer => {
        audioQueueRef.current.push(buffer)
        playNextAudio()
      })
      return
    }

    try {
      const data: VoiceEvent = JSON.parse(event.data)
      setVoiceState(data.state)
      setStoreState(mapState(data.state))

      switch (data.type) {
        case 'ready':
          if (data.wake_word) setWakeWord(data.wake_word)
          onReady?.()
          break

        case 'wake_word_detected':
          onWakeWordDetected?.()
          break

        case 'transcription':
          if (data.text) {
            addMessage({ role: 'user', content: data.text })
            onTranscription?.(data.text)
          }
          break

        case 'response':
          if (data.text) {
            addMessage({ role: 'assistant', content: data.text })
            onResponse?.(data.text)
          }
          break

        case 'error':
          if (data.text) onError?.(data.text)
          break
      }
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error)
    }
  }, [mapState, setStoreState, addMessage, onReady, onWakeWordDetected, onTranscription, onResponse, onError, playNextAudio])

  // Start microphone and stream audio
  const startStreaming = useCallback(async () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.error('WebSocket not connected')
      return
    }

    try {
      // Get microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        }
      })
      streamRef.current = stream

      // Create audio context
      audioContextRef.current = new AudioContext({ sampleRate: 16000 })
      const source = audioContextRef.current.createMediaStreamSource(stream)

      // Create script processor for raw audio access
      // Note: ScriptProcessorNode is deprecated but still widely supported
      // AudioWorklet would be the modern alternative
      processorRef.current = audioContextRef.current.createScriptProcessor(4096, 1, 1)

      processorRef.current.onaudioprocess = (e) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          const inputData = e.inputBuffer.getChannelData(0)

          // Calculate audio level for visualization
          let sum = 0
          for (let i = 0; i < inputData.length; i++) {
            sum += inputData[i] * inputData[i]
          }
          const rms = Math.sqrt(sum / inputData.length)
          setAudioLevel(rms)

          // Send as Float32Array (binary)
          wsRef.current.send(inputData.buffer)
        }
      }

      source.connect(processorRef.current)
      processorRef.current.connect(audioContextRef.current.destination)

      console.log('Audio streaming started')
    } catch (error) {
      console.error('Failed to start audio streaming:', error)
      onError?.('Microphone access denied')
    }
  }, [setAudioLevel, onError])

  // Stop streaming
  const stopStreaming = useCallback(() => {
    if (processorRef.current) {
      processorRef.current.disconnect()
      processorRef.current = null
    }

    if (audioContextRef.current) {
      audioContextRef.current.close()
      audioContextRef.current = null
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop())
      streamRef.current = null
    }

    setAudioLevel(0)
    console.log('Audio streaming stopped')
  }, [setAudioLevel])

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    console.log('Connecting to voice WebSocket...')
    const ws = new WebSocket(url)

    ws.onopen = () => {
      console.log('Voice WebSocket connected')
      setIsConnected(true)
      startStreaming()
    }

    ws.onmessage = handleMessage

    ws.onerror = (error) => {
      console.error('Voice WebSocket error:', error)
      onError?.('WebSocket connection error')
    }

    ws.onclose = () => {
      console.log('Voice WebSocket closed')
      setIsConnected(false)
      setVoiceState('idle')
      setStoreState('idle')
      stopStreaming()
    }

    wsRef.current = ws
  }, [url, handleMessage, startStreaming, stopStreaming, setStoreState, onError])

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    stopStreaming()

    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    setIsConnected(false)
    setVoiceState('idle')
    setStoreState('idle')
  }, [stopStreaming, setStoreState])

  // Send command to skip wake word
  const skipWakeWord = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'skip_wake_word' }))
    }
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect()
    }
  }, [disconnect])

  return {
    isConnected,
    voiceState,
    wakeWord,
    connect,
    disconnect,
    skipWakeWord,
  }
}
