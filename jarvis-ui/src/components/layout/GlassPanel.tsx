import { motion } from 'framer-motion'
import { ReactNode } from 'react'

interface GlassPanelProps {
  children: ReactNode
  className?: string
  animate?: boolean
}

export function GlassPanel({ children, className = '', animate = true }: GlassPanelProps) {
  const content = (
    <div
      className={`
        glass-panel rounded-lg
        ${className}
      `}
    >
      {children}
    </div>
  )

  if (!animate) return content

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      {content}
    </motion.div>
  )
}
