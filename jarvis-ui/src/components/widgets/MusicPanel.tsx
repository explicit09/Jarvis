import { useState } from 'react'
import { motion } from 'framer-motion'

interface Track {
  title: string
  artist: string
  album: string
  duration: number
  position: number
  isPlaying: boolean
  artwork?: string
}

export function MusicPanel() {
  const [track] = useState<Track>({
    title: 'No Track Playing',
    artist: 'Unknown Artist',
    album: '',
    duration: 0,
    position: 0,
    isPlaying: false,
  })

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const handleControl = async (action: 'play' | 'pause' | 'next' | 'previous') => {
    try {
      // This would call your music control API
      await fetch('http://localhost:18000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: action === 'play' ? 'play music' :
                action === 'pause' ? 'pause music' :
                action === 'next' ? 'next song' : 'previous song'
        }),
      })
    } catch (error) {
      console.error('Music control error:', error)
    }
  }

  return (
    <motion.div
      className="glass-panel p-4 rounded-lg"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.4 }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-mono text-jarvis-text-muted">NOW PLAYING</span>
        <div className={`w-2 h-2 rounded-full ${track.isPlaying ? 'bg-jarvis-success animate-pulse' : 'bg-jarvis-text-muted'}`} />
      </div>

      {/* Album art / Visualizer */}
      <div className="relative w-full aspect-square mb-4 rounded-lg overflow-hidden bg-jarvis-bg-deep">
        {track.artwork ? (
          <img src={track.artwork} alt={track.album} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            {/* Music icon / visualizer placeholder */}
            <svg className="w-16 h-16 text-jarvis-primary opacity-30" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/>
            </svg>
          </div>
        )}

        {/* Overlay gradient */}
        <div className="absolute inset-0 bg-gradient-to-t from-jarvis-bg-deep/80 to-transparent" />

        {/* Track info overlay */}
        <div className="absolute bottom-0 left-0 right-0 p-3">
          <div className="text-sm font-display text-jarvis-text-primary truncate">
            {track.title}
          </div>
          <div className="text-xs text-jarvis-text-secondary truncate">
            {track.artist}
          </div>
        </div>
      </div>

      {/* Progress bar */}
      <div className="mb-3">
        <div className="h-1 bg-jarvis-border rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-jarvis-primary"
            style={{
              width: `${track.duration > 0 ? (track.position / track.duration) * 100 : 0}%`,
              boxShadow: '0 0 10px rgba(0, 212, 255, 0.5)',
            }}
          />
        </div>
        <div className="flex justify-between mt-1">
          <span className="text-xs font-mono text-jarvis-text-muted">
            {formatTime(track.position)}
          </span>
          <span className="text-xs font-mono text-jarvis-text-muted">
            {formatTime(track.duration)}
          </span>
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center justify-center gap-4">
        <button
          onClick={() => handleControl('previous')}
          className="p-2 text-jarvis-text-secondary hover:text-jarvis-primary transition-colors"
        >
          <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
            <path d="M6 6h2v12H6zm3.5 6l8.5 6V6z"/>
          </svg>
        </button>

        <button
          onClick={() => handleControl(track.isPlaying ? 'pause' : 'play')}
          className="p-3 rounded-full bg-jarvis-primary/20 border border-jarvis-primary text-jarvis-primary hover:bg-jarvis-primary/30 transition-all"
          style={{ boxShadow: '0 0 20px rgba(0, 212, 255, 0.3)' }}
        >
          {track.isPlaying ? (
            <svg className="w-8 h-8" fill="currentColor" viewBox="0 0 24 24">
              <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
            </svg>
          ) : (
            <svg className="w-8 h-8" fill="currentColor" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z"/>
            </svg>
          )}
        </button>

        <button
          onClick={() => handleControl('next')}
          className="p-2 text-jarvis-text-secondary hover:text-jarvis-primary transition-colors"
        >
          <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
            <path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z"/>
          </svg>
        </button>
      </div>
    </motion.div>
  )
}
