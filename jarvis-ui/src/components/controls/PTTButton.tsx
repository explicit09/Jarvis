import { useState, useCallback, useRef } from 'react'
import { motion } from 'framer-motion'
import { useVoiceStore } from '../../stores/voiceStore'

interface PTTButtonProps {
  onRecordingComplete: (blob: Blob) => void
  disabled?: boolean
}

export function PTTButton({ onRecordingComplete, disabled = false }: PTTButtonProps) {
  const [isPressed, setIsPressed] = useState(false)
  const { state, setIsRecording, setState } = useVoiceStore()
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus',
      })

      chunksRef.current = []

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data)
        }
      }

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop())
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })

        // Convert webm to wav for the API
        const wavBlob = await convertToWav(blob)
        onRecordingComplete(wavBlob)
      }

      mediaRecorderRef.current = mediaRecorder
      mediaRecorder.start(100) // Collect data every 100ms
      setIsRecording(true)
      setState('listening')
    } catch (error) {
      console.error('Failed to start recording:', error)
    }
  }, [onRecordingComplete, setIsRecording, setState])

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
      setIsRecording(false)
      setState('processing')
    }
  }, [setIsRecording, setState])

  const handleMouseDown = () => {
    if (!disabled) {
      setIsPressed(true)
      startRecording()
    }
  }

  const handleMouseUp = () => {
    if (isPressed) {
      setIsPressed(false)
      stopRecording()
    }
  }

  const isListening = state === 'listening'

  return (
    <motion.button
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onTouchStart={handleMouseDown}
      onTouchEnd={handleMouseUp}
      disabled={disabled}
      className={`
        relative w-20 h-20 rounded-full
        border-2 transition-all duration-200
        flex items-center justify-center
        ${isListening
          ? 'border-jarvis-primary bg-jarvis-primary/30'
          : 'border-jarvis-border bg-jarvis-bg-panel hover:border-jarvis-primary/60'
        }
        disabled:opacity-50 disabled:cursor-not-allowed
      `}
      style={{
        boxShadow: isListening
          ? '0 0 40px rgba(0, 212, 255, 0.6), inset 0 0 20px rgba(0, 212, 255, 0.3)'
          : 'none',
      }}
      whileTap={{ scale: 0.95 }}
    >
      {/* Pulsing ring when listening */}
      {isListening && (
        <motion.div
          className="absolute inset-0 rounded-full border-2 border-jarvis-primary"
          animate={{
            scale: [1, 1.5],
            opacity: [0.6, 0],
          }}
          transition={{
            duration: 1,
            repeat: Infinity,
          }}
        />
      )}

      {/* Mic icon */}
      <svg
        className={`w-8 h-8 ${isListening ? 'text-jarvis-primary' : 'text-jarvis-text-secondary'}`}
        fill="currentColor"
        viewBox="0 0 24 24"
      >
        <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm-1 1.93c-3.94-.49-7-3.85-7-7.93h2c0 3.31 2.69 6 6 6s6-2.69 6-6h2c0 4.08-3.06 7.44-7 7.93V20h4v2H8v-2h4v-4.07z" />
      </svg>

      {/* Label */}
      <span className="absolute -bottom-8 left-1/2 -translate-x-1/2 text-xs font-mono text-jarvis-text-muted whitespace-nowrap">
        {isListening ? 'LISTENING...' : 'HOLD TO SPEAK'}
      </span>
    </motion.button>
  )
}

// Convert WebM audio to WAV format
async function convertToWav(webmBlob: Blob): Promise<Blob> {
  // For simplicity, we'll just return the blob and let the server handle conversion
  // In production, you'd use the Web Audio API to properly convert
  return webmBlob
}
