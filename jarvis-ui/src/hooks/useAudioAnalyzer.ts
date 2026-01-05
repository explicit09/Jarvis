import { useEffect, useRef } from 'react'
import { useVoiceStore } from '../stores/voiceStore'

export function useAudioAnalyzer() {
  const { isRecording, setFrequencyData, setAudioLevel } = useVoiceStore()
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyzerRef = useRef<AnalyserNode | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const animationRef = useRef<number>()

  useEffect(() => {
    if (!isRecording) {
      // Cleanup when not recording
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current)
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop())
      }
      setFrequencyData(null)
      setAudioLevel(0)
      return
    }

    const setupAudio = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        streamRef.current = stream

        audioContextRef.current = new AudioContext()
        analyzerRef.current = audioContextRef.current.createAnalyser()
        analyzerRef.current.fftSize = 256
        analyzerRef.current.smoothingTimeConstant = 0.8

        const source = audioContextRef.current.createMediaStreamSource(stream)
        source.connect(analyzerRef.current)

        const bufferLength = analyzerRef.current.frequencyBinCount
        const dataArray = new Uint8Array(bufferLength)

        const analyze = () => {
          if (!analyzerRef.current || !isRecording) return

          analyzerRef.current.getByteFrequencyData(dataArray)
          setFrequencyData(new Uint8Array(dataArray))

          // Calculate average level
          const sum = dataArray.reduce((a, b) => a + b, 0)
          const avg = sum / bufferLength / 255
          setAudioLevel(avg)

          animationRef.current = requestAnimationFrame(analyze)
        }

        analyze()
      } catch (error) {
        console.error('Failed to setup audio analyzer:', error)
      }
    }

    setupAudio()

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current)
      }
      if (audioContextRef.current) {
        audioContextRef.current.close()
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop())
      }
    }
  }, [isRecording, setFrequencyData, setAudioLevel])
}
