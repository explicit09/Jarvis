import { useCallback, useRef, useState, useEffect } from 'react'

// Web Speech API types
interface SpeechRecognitionEvent {
  results: SpeechRecognitionResultList
  resultIndex: number
}

interface SpeechRecognitionResultList {
  length: number
  [index: number]: SpeechRecognitionResult
}

interface SpeechRecognitionResult {
  length: number
  [index: number]: SpeechRecognitionAlternative
}

interface SpeechRecognitionAlternative {
  transcript: string
  confidence: number
}

interface SpeechRecognitionErrorEvent {
  error: string
}

interface SpeechRecognitionInstance {
  continuous: boolean
  interimResults: boolean
  lang: string
  maxAlternatives: number
  onstart: (() => void) | null
  onresult: ((event: SpeechRecognitionEvent) => void) | null
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
  abort: () => void
}

interface SpeechRecognitionConstructor {
  new (): SpeechRecognitionInstance
}

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor
    webkitSpeechRecognition?: SpeechRecognitionConstructor
  }
}

interface UseWakeWordOptions {
  wakeWords?: string[]
  onWakeWordDetected: () => void
  enabled?: boolean
}

export function useWakeWord({
  wakeWords = ['jarvis', 'hey jarvis', 'ok jarvis'],
  onWakeWordDetected,
  enabled = true,
}: UseWakeWordOptions) {
  const [isListening, setIsListening] = useState(false)
  const [isSupported, setIsSupported] = useState(false)
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null)
  const isRestartingRef = useRef(false)
  const enabledRef = useRef(enabled)

  // Keep ref in sync
  useEffect(() => {
    enabledRef.current = enabled
  }, [enabled])

  // Check for Web Speech API support
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    setIsSupported(!!SpeechRecognition)
  }, [])

  const stopListening = useCallback(() => {
    isRestartingRef.current = false
    if (recognitionRef.current) {
      try {
        recognitionRef.current.onend = null
        recognitionRef.current.onerror = null
        recognitionRef.current.onresult = null
        recognitionRef.current.abort()
      } catch {
        // Ignore errors during cleanup
      }
      recognitionRef.current = null
    }
    setIsListening(false)
  }, [])

  const startListening = useCallback(() => {
    if (!isSupported || isRestartingRef.current) return

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) return

    // Clean up existing
    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort()
      } catch {
        // Ignore
      }
    }

    const recognition = new SpeechRecognition()
    recognition.continuous = false  // Single result mode - more stable
    recognition.interimResults = false
    recognition.lang = 'en-US'
    recognition.maxAlternatives = 3

    recognition.onstart = () => {
      setIsListening(true)
    }

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      for (let i = 0; i < event.results.length; i++) {
        for (let j = 0; j < event.results[i].length; j++) {
          const transcript = event.results[i][j].transcript.toLowerCase().trim()

          const detected = wakeWords.some(word =>
            transcript.includes(word.toLowerCase())
          )

          if (detected) {
            console.log('Wake word detected:', transcript)
            onWakeWordDetected()
            return
          }
        }
      }
    }

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      if (event.error === 'aborted' || event.error === 'no-speech') {
        // Normal - just restart
      } else {
        console.error('Wake word error:', event.error)
      }
    }

    recognition.onend = () => {
      setIsListening(false)
      // Auto-restart if still enabled
      if (enabledRef.current && !isRestartingRef.current) {
        isRestartingRef.current = true
        setTimeout(() => {
          isRestartingRef.current = false
          if (enabledRef.current) {
            startListening()
          }
        }, 300)
      }
    }

    recognitionRef.current = recognition

    try {
      recognition.start()
    } catch (error) {
      console.error('Failed to start wake word:', error)
      setIsListening(false)
    }
  }, [isSupported, wakeWords, onWakeWordDetected])

  // Start/stop based on enabled
  useEffect(() => {
    if (enabled && isSupported) {
      startListening()
    } else {
      stopListening()
    }

    return () => stopListening()
  }, [enabled, isSupported, startListening, stopListening])

  return {
    isListening,
    isSupported,
    startListening,
    stopListening,
  }
}
