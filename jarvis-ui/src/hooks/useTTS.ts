import { useCallback, useRef } from 'react'
import { useVoiceStore } from '../stores/voiceStore'

const API_BASE = 'http://localhost:18000'

export function useTTS() {
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const { setState } = useVoiceStore()

  const speak = useCallback(async (text: string): Promise<void> => {
    if (!text.trim()) return

    setState('speaking')

    try {
      // Call the TTS endpoint
      const response = await fetch(`${API_BASE}/speak`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      })

      if (!response.ok) {
        // Fallback to browser TTS
        speakWithBrowserTTS(text)
        return
      }

      const audioBlob = await response.blob()
      const audioUrl = URL.createObjectURL(audioBlob)

      // Play the audio
      if (audioRef.current) {
        audioRef.current.pause()
      }

      audioRef.current = new Audio(audioUrl)
      audioRef.current.onended = () => {
        setState('idle')
        URL.revokeObjectURL(audioUrl)
      }
      audioRef.current.onerror = () => {
        // Fallback to browser TTS on error
        speakWithBrowserTTS(text)
      }

      await audioRef.current.play()
    } catch (error) {
      console.error('TTS error:', error)
      // Fallback to browser TTS
      speakWithBrowserTTS(text)
    }
  }, [setState])

  const speakWithBrowserTTS = useCallback((text: string) => {
    if ('speechSynthesis' in window) {
      const utterance = new SpeechSynthesisUtterance(text)
      utterance.rate = 1.0
      utterance.pitch = 1.0

      // Try to find a good voice
      const voices = speechSynthesis.getVoices()
      const preferredVoice = voices.find(v =>
        v.name.includes('Daniel') ||
        v.name.includes('Samantha') ||
        v.lang.startsWith('en')
      )
      if (preferredVoice) {
        utterance.voice = preferredVoice
      }

      utterance.onend = () => setState('idle')
      speechSynthesis.speak(utterance)
    } else {
      setState('idle')
    }
  }, [setState])

  const stop = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }
    if ('speechSynthesis' in window) {
      speechSynthesis.cancel()
    }
    setState('idle')
  }, [setState])

  return { speak, stop }
}
