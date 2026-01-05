import { motion } from 'framer-motion'

export function ScanLines() {
  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden">
      {/* Static scan lines */}
      <div className="scan-lines" />

      {/* Moving scan line */}
      <motion.div
        className="absolute left-0 right-0 h-[2px]"
        style={{
          background: 'linear-gradient(90deg, transparent, rgba(0, 212, 255, 0.3), transparent)',
        }}
        animate={{
          top: ['-10%', '110%'],
        }}
        transition={{
          duration: 3,
          repeat: Infinity,
          ease: 'linear',
        }}
      />
    </div>
  )
}
