import { ReactNode } from 'react'
import { motion } from 'framer-motion'
import { useSystemStore } from '../../stores/systemStore'

interface MainLayoutProps {
  children: ReactNode
}

export function MainLayout({ children }: MainLayoutProps) {
  const { isConnected } = useSystemStore()

  return (
    <div className="h-screen w-screen bg-jarvis-bg-deep overflow-hidden relative">
      {/* Background grid pattern */}
      <div className="absolute inset-0 opacity-10">
        <div
          className="w-full h-full"
          style={{
            backgroundImage: `
              linear-gradient(rgba(0, 212, 255, 0.1) 1px, transparent 1px),
              linear-gradient(90deg, rgba(0, 212, 255, 0.1) 1px, transparent 1px)
            `,
            backgroundSize: '50px 50px',
          }}
        />
      </div>

      {/* Radial glow in center */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: 'radial-gradient(circle at 50% 50%, rgba(0, 212, 255, 0.08) 0%, transparent 50%)',
        }}
      />

      {/* Top status bar */}
      <motion.header
        className="absolute top-0 left-0 right-0 h-12 flex items-center justify-between px-6 z-50"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <div className="flex items-center gap-4">
          <h1 className="font-display text-xl font-bold holographic-text tracking-wider">
            J.A.R.V.I.S
          </h1>
          <span className="text-jarvis-text-muted text-sm font-mono">v0.1.0</span>
        </div>

        <div className="flex items-center gap-4">
          {/* Connection status */}
          <div className="flex items-center gap-2">
            <div
              className={`w-2 h-2 rounded-full ${
                isConnected ? 'bg-jarvis-success' : 'bg-jarvis-error'
              }`}
              style={{
                boxShadow: isConnected
                  ? '0 0 8px rgba(0, 255, 136, 0.8)'
                  : '0 0 8px rgba(255, 51, 102, 0.8)',
              }}
            />
            <span className="text-jarvis-text-secondary text-sm font-mono">
              {isConnected ? 'CONNECTED' : 'OFFLINE'}
            </span>
          </div>
        </div>
      </motion.header>

      {/* Main content */}
      <main className="h-full pt-12 pb-4 px-4">
        {children}
      </main>

      {/* Scan lines overlay */}
      <div className="scan-lines" />
    </div>
  )
}
