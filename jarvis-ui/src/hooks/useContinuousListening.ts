import { useCallback, useRef, useState, useEffect } from 'react'
import { useVoiceStore } from '../stores/voiceStore'

interface UseContinuousListeningOptions {
  onSpeechEnd: (audioBlob: Blob) => void
  silenceThreshold?: number      // Audio level below this = silence (0-1)
  silenceDuration?: number       // ms of silence before stopping
  minSpeechDuration?: number     // Minimum ms of speech to process
  enabled?: boolean
}

export function useContinuousListening({
  onSpeechEnd,
  silenceThreshold = 0.02,
  silenceDuration = 1500,
  minSpeechDuration = 500,
  enabled = true,
}: UseContinuousListeningOptions) {
  const [isListening, setIsListening] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)

  const { state, setIsRecording, setState, setFrequencyData, setAudioLevel } = useVoiceStore()

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyzerRef = useRef<AnalyserNode | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const enabledRef = useRef(enabled)

  const silenceStartRef = useRef<number | null>(null)
  const speechStartRef = useRef<number | null>(null)
  const animationFrameRef = useRef<number>()

  useEffect(() => {
    enabledRef.current = enabled

    // If we get disabled mid-session, make sure recording is stopped
    if (!enabled) {
      silenceStartRef.current = null

      if (mediaRecorderRef.current?.state === 'recording') {
        mediaRecorderRef.current.stop()
      }

      if (isSpeaking) {
        setIsSpeaking(false)
        setIsRecording(false)
      }
    }
  }, [enabled, isSpeaking, setIsRecording, setIsSpeaking])

  const startListening = useCallback(async () => {
    if (isListening || state === 'speaking' || state === 'processing') return

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        }
      })
      streamRef.current = stream

      // Setup audio analysis
      audioContextRef.current = new AudioContext()
      analyzerRef.current = audioContextRef.current.createAnalyser()
      analyzerRef.current.fftSize = 256
      analyzerRef.current.smoothingTimeConstant = 0.8

      const source = audioContextRef.current.createMediaStreamSource(stream)
      source.connect(analyzerRef.current)

      // Setup media recorder
      mediaRecorderRef.current = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus',
      })

      chunksRef.current = []

      mediaRecorderRef.current.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data)
        }
      }

      mediaRecorderRef.current.onstop = () => {
        const speechDuration = speechStartRef.current
          ? Date.now() - speechStartRef.current
          : 0

        if (speechDuration >= minSpeechDuration && chunksRef.current.length > 0) {
          const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
          onSpeechEnd(blob)
        }

        chunksRef.current = []
        speechStartRef.current = null
        silenceStartRef.current = null
      }

      setIsListening(true)
      setState('idle')

      // Start monitoring audio levels
      const bufferLength = analyzerRef.current.frequencyBinCount
      const dataArray = new Uint8Array(bufferLength)

      const monitor = () => {
        if (!analyzerRef.current) return

        analyzerRef.current.getByteFrequencyData(dataArray)
        setFrequencyData(new Uint8Array(dataArray))

        // Calculate audio level (0-1)
        const sum = dataArray.reduce((a, b) => a + b, 0)
        const level = sum / bufferLength / 255
        setAudioLevel(level)

        // Pause detection but keep the loop alive when disabled
        if (!enabledRef.current) {
          animationFrameRef.current = requestAnimationFrame(monitor)
          return
        }

        const now = Date.now()
        const isSpeakingNow = level > silenceThreshold

        if (isSpeakingNow) {
          silenceStartRef.current = null

          if (!isSpeaking) {
            // Started speaking - begin recording
            setIsSpeaking(true)
            setIsRecording(true)
            setState('listening')
            speechStartRef.current = now
            chunksRef.current = []

            if (mediaRecorderRef.current?.state === 'inactive') {
              mediaRecorderRef.current.start(100)
            }
          }
        } else if (isSpeaking) {
          // Currently in speech, check for silence
          if (!silenceStartRef.current) {
            silenceStartRef.current = now
          } else if (now - silenceStartRef.current >= silenceDuration) {
            // Silence detected - stop recording
            setIsSpeaking(false)
            setIsRecording(false)

            if (mediaRecorderRef.current?.state === 'recording') {
              mediaRecorderRef.current.stop()
            }
          }
        }

        animationFrameRef.current = requestAnimationFrame(monitor)
      }

      monitor()

    } catch (error) {
      console.error('Failed to start listening:', error)
    }
  }, [
    isListening, state, silenceThreshold, silenceDuration,
    minSpeechDuration, onSpeechEnd, setState, setIsRecording,
    setFrequencyData, setAudioLevel, isSpeaking
  ])

  const stopListening = useCallback(() => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current)
    }

    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop()
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop())
    }

    if (audioContextRef.current) {
      audioContextRef.current.close()
    }

    setIsListening(false)
    setIsSpeaking(false)
    setIsRecording(false)
    setState('idle')
    setFrequencyData(null)
    setAudioLevel(0)
  }, [setState, setIsRecording, setFrequencyData, setAudioLevel])

  // Auto-restart listening after processing/speaking is done
  useEffect(() => {
    if (enabled && !isListening && state === 'idle') {
      const timeout = setTimeout(() => {
        startListening()
      }, 500) // Small delay before restarting

      return () => clearTimeout(timeout)
    }
  }, [enabled, isListening, state, startListening])

  // Cleanup on unmount
  useEffect(() => {
    return () => stopListening()
  }, [stopListening])

  return {
    isListening,
    isSpeaking,
    startListening,
    stopListening,
  }
}
