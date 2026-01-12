import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'

export function TitleBar() {
  const [isMaximized, setIsMaximized] = useState(false)
  const [platform, setPlatform] = useState<string>('darwin')

  useEffect(() => {
    // Get platform
    if (window.electron) {
      window.electron.getPlatform().then(setPlatform)
      window.electron.onMaximized(setIsMaximized)
    }
  }, [])

  // Don't show on macOS (uses native traffic lights)
  if (platform === 'darwin' || !window.electron) {
    return null
  }

  const handleMinimize = () => window.electron?.minimize()
  const handleMaximize = () => window.electron?.maximize()
  const handleClose = () => window.electron?.close()

  return (
    <div
      className="fixed top-0 left-0 right-0 h-8 flex items-center justify-between px-3 z-50"
      style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
    >
      {/* App title */}
      <div className="flex items-center gap-2">
        <div className="w-3 h-3 rounded-full bg-jarvis-primary animate-pulse" />
        <span className="text-jarvis-text-secondary text-xs font-display tracking-wider">
          J.A.R.V.I.S
        </span>
      </div>

      {/* Window controls (Windows/Linux style) */}
      <div
        className="flex items-center gap-1"
        style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
      >
        <motion.button
          onClick={handleMinimize}
          whileHover={{ backgroundColor: 'rgba(255,255,255,0.1)' }}
          className="w-10 h-8 flex items-center justify-center text-jarvis-text-secondary hover:text-jarvis-text-primary transition-colors"
        >
          <svg width="10" height="1" viewBox="0 0 10 1" fill="currentColor">
            <rect width="10" height="1" />
          </svg>
        </motion.button>

        <motion.button
          onClick={handleMaximize}
          whileHover={{ backgroundColor: 'rgba(255,255,255,0.1)' }}
          className="w-10 h-8 flex items-center justify-center text-jarvis-text-secondary hover:text-jarvis-text-primary transition-colors"
        >
          {isMaximized ? (
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor">
              <rect x="2" y="0" width="8" height="8" strokeWidth="1" />
              <rect x="0" y="2" width="8" height="8" strokeWidth="1" fill="var(--jarvis-bg)" />
            </svg>
          ) : (
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor">
              <rect x="0" y="0" width="10" height="10" strokeWidth="1" />
            </svg>
          )}
        </motion.button>

        <motion.button
          onClick={handleClose}
          whileHover={{ backgroundColor: 'rgba(255,0,0,0.8)' }}
          className="w-10 h-8 flex items-center justify-center text-jarvis-text-secondary hover:text-white transition-colors"
        >
          <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor">
            <path d="M1 1L9 9M9 1L1 9" stroke="currentColor" strokeWidth="1.5" />
          </svg>
        </motion.button>
      </div>
    </div>
  )
}
