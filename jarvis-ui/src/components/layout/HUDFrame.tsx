import { motion } from 'framer-motion'
import { ReactNode } from 'react'

interface HUDFrameProps {
  children: ReactNode
  className?: string
}

export function HUDFrame({ children, className = '' }: HUDFrameProps) {
  return (
    <div className={`relative ${className}`}>
      {/* Corner brackets */}
      <motion.div
        className="hud-corner hud-corner-tl"
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 0.6, scale: 1 }}
        transition={{ delay: 0.1 }}
      />
      <motion.div
        className="hud-corner hud-corner-tr"
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 0.6, scale: 1 }}
        transition={{ delay: 0.2 }}
      />
      <motion.div
        className="hud-corner hud-corner-bl"
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 0.6, scale: 1 }}
        transition={{ delay: 0.3 }}
      />
      <motion.div
        className="hud-corner hud-corner-br"
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 0.6, scale: 1 }}
        transition={{ delay: 0.4 }}
      />

      {/* Content */}
      <div className="p-6">{children}</div>
    </div>
  )
}
