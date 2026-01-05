import { motion } from 'framer-motion'

export function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="bg-jarvis-bg-panel border border-jarvis-border rounded-lg px-4 py-3">
        <div className="text-xs font-mono mb-1 text-jarvis-text-muted">JARVIS</div>
        <div className="flex items-center gap-1">
          {[0, 1, 2].map((i) => (
            <motion.div
              key={i}
              className="w-2 h-2 rounded-full bg-jarvis-primary"
              animate={{
                opacity: [0.3, 1, 0.3],
                scale: [0.8, 1, 0.8],
              }}
              transition={{
                duration: 1,
                repeat: Infinity,
                delay: i * 0.2,
              }}
            />
          ))}
          <span className="ml-2 text-jarvis-text-muted text-sm font-body">Processing...</span>
        </div>
      </div>
    </div>
  )
}
