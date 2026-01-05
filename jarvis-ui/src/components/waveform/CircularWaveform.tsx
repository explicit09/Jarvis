import { useRef, useEffect } from 'react'
import { useVoiceStore } from '../../stores/voiceStore'

interface CircularWaveformProps {
  size?: number
  className?: string
}

export function CircularWaveform({ size = 300, className = '' }: CircularWaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const { frequencyData, state } = useVoiceStore()
  const animationRef = useRef<number>()

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const centerX = size / 2
    const centerY = size / 2
    const radius = size * 0.35
    const barCount = 64

    const draw = () => {
      ctx.clearRect(0, 0, size, size)

      // Draw base circle
      ctx.beginPath()
      ctx.arc(centerX, centerY, radius, 0, Math.PI * 2)
      ctx.strokeStyle = 'rgba(0, 212, 255, 0.2)'
      ctx.lineWidth = 1
      ctx.stroke()

      // Draw waveform bars
      for (let i = 0; i < barCount; i++) {
        const angle = (i / barCount) * Math.PI * 2 - Math.PI / 2
        const dataIndex = frequencyData
          ? Math.floor((i / barCount) * frequencyData.length)
          : 0
        const value = frequencyData ? frequencyData[dataIndex] / 255 : 0

        // Add some movement even when idle
        const idleValue = state === 'idle' ? Math.sin(Date.now() * 0.002 + i * 0.2) * 0.1 + 0.1 : 0
        const barHeight = (value || idleValue) * size * 0.15

        const x1 = centerX + Math.cos(angle) * radius
        const y1 = centerY + Math.sin(angle) * radius
        const x2 = centerX + Math.cos(angle) * (radius + barHeight)
        const y2 = centerY + Math.sin(angle) * (radius + barHeight)

        const gradient = ctx.createLinearGradient(x1, y1, x2, y2)
        gradient.addColorStop(0, 'rgba(0, 212, 255, 0.4)')
        gradient.addColorStop(1, 'rgba(0, 212, 255, 0.8)')

        ctx.beginPath()
        ctx.moveTo(x1, y1)
        ctx.lineTo(x2, y2)
        ctx.strokeStyle = gradient
        ctx.lineWidth = 3
        ctx.lineCap = 'round'
        ctx.stroke()

        // Add glow
        ctx.shadowColor = '#00d4ff'
        ctx.shadowBlur = 10
      }

      animationRef.current = requestAnimationFrame(draw)
    }

    draw()

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current)
      }
    }
  }, [size, frequencyData, state])

  return (
    <canvas
      ref={canvasRef}
      width={size}
      height={size}
      className={`pointer-events-none ${className}`}
      style={{ filter: 'drop-shadow(0 0 10px rgba(0, 212, 255, 0.5))' }}
    />
  )
}
