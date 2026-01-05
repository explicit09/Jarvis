import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'

interface SystemStats {
  cpu: number
  memory: number
  disk: number
  network: { up: number; down: number }
  uptime: string
}

// Circular progress ring
function CircularProgress({
  value,
  label,
  size = 80,
  color = '#00d4ff'
}: {
  value: number
  label: string
  size?: number
  color?: string
}) {
  const strokeWidth = 6
  const radius = (size - strokeWidth) / 2
  const circumference = radius * 2 * Math.PI
  const offset = circumference - (value / 100) * circumference

  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: size, height: size }}>
        <svg className="transform -rotate-90" width={size} height={size}>
          {/* Background circle */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="rgba(0, 212, 255, 0.1)"
            strokeWidth={strokeWidth}
          />
          {/* Progress circle */}
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: offset }}
            transition={{ duration: 1, ease: 'easeOut' }}
            style={{
              filter: `drop-shadow(0 0 6px ${color})`,
            }}
          />
        </svg>
        {/* Value in center */}
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-lg font-display text-jarvis-text-primary">
            {value}%
          </span>
        </div>
      </div>
      <span className="text-xs font-mono text-jarvis-text-muted mt-1">{label}</span>
    </div>
  )
}

export function SystemMetrics() {
  const [stats, setStats] = useState<SystemStats>({
    cpu: 23,
    memory: 67,
    disk: 45,
    network: { up: 1.2, down: 15.8 },
    uptime: '4d 12h 30m',
  })

  // Simulate fluctuating stats
  useEffect(() => {
    const interval = setInterval(() => {
      setStats(prev => ({
        ...prev,
        cpu: Math.min(100, Math.max(5, prev.cpu + (Math.random() - 0.5) * 10)),
        memory: Math.min(100, Math.max(30, prev.memory + (Math.random() - 0.5) * 5)),
        network: {
          up: Math.max(0, prev.network.up + (Math.random() - 0.5) * 2),
          down: Math.max(0, prev.network.down + (Math.random() - 0.5) * 5),
        },
      }))
    }, 2000)

    return () => clearInterval(interval)
  }, [])

  return (
    <motion.div
      className="glass-panel p-4 rounded-lg"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3 }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs font-mono text-jarvis-text-muted">SYSTEM</span>
        <span className="text-xs font-mono text-jarvis-success">● ONLINE</span>
      </div>

      {/* Circular gauges */}
      <div className="flex justify-around mb-4">
        <CircularProgress
          value={Math.round(stats.cpu)}
          label="CPU"
          color={stats.cpu > 80 ? '#ff3366' : '#00d4ff'}
        />
        <CircularProgress
          value={Math.round(stats.memory)}
          label="RAM"
          color={stats.memory > 80 ? '#ffaa00' : '#00d4ff'}
        />
        <CircularProgress
          value={Math.round(stats.disk)}
          label="DISK"
        />
      </div>

      {/* Network stats */}
      <div className="border-t border-jarvis-border pt-3">
        <div className="text-xs font-mono text-jarvis-text-muted mb-2">NETWORK</div>
        <div className="flex justify-between">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-jarvis-success" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
            </svg>
            <span className="text-sm font-mono text-jarvis-text-primary">
              {stats.network.up.toFixed(1)} MB/s
            </span>
          </div>
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-jarvis-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
            </svg>
            <span className="text-sm font-mono text-jarvis-text-primary">
              {stats.network.down.toFixed(1)} MB/s
            </span>
          </div>
        </div>
      </div>

      {/* Uptime */}
      <div className="mt-3 pt-3 border-t border-jarvis-border flex justify-between items-center">
        <span className="text-xs font-mono text-jarvis-text-muted">UPTIME</span>
        <span className="text-sm font-mono text-jarvis-text-secondary">{stats.uptime}</span>
      </div>
    </motion.div>
  )
}
