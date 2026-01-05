import { motion } from 'framer-motion'
import { useSystemStore } from '../../stores/systemStore'
import { MetricsDisplay } from './MetricsDisplay'
import { ConnectionStatus } from './ConnectionStatus'

export function StatusOverlay() {
  const { activeTool } = useSystemStore()

  return (
    <>
      {/* Top right - Connection and Hub info */}
      <motion.div
        className="absolute top-16 right-4 z-40"
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 0.3 }}
      >
        <ConnectionStatus />
      </motion.div>

      {/* Bottom left - Metrics */}
      <motion.div
        className="absolute bottom-20 left-4 z-40"
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 0.4 }}
      >
        <MetricsDisplay />
      </motion.div>

      {/* Active tool indicator */}
      {activeTool && (
        <motion.div
          className="absolute bottom-20 right-4 z-40"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.9 }}
        >
          <div className="glass-panel px-4 py-2 rounded-lg">
            <div className="text-xs font-mono text-jarvis-text-muted mb-1">ACTIVE TOOL</div>
            <div className="text-sm font-display text-jarvis-warning">
              {activeTool}
            </div>
          </div>
        </motion.div>
      )}
    </>
  )
}
