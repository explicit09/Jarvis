import { useState, KeyboardEvent } from 'react'
import { motion } from 'framer-motion'

interface TextInputProps {
  onSend: (text: string) => void
  disabled?: boolean
}

export function TextInput({ onSend, disabled = false }: TextInputProps) {
  const [text, setText] = useState('')

  const handleSend = () => {
    if (text.trim() && !disabled) {
      onSend(text.trim())
      setText('')
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex gap-3">
      <div className="flex-1 relative">
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder="Type a command..."
          className="
            w-full px-4 py-3 rounded-lg
            bg-jarvis-bg-panel border border-jarvis-border
            text-jarvis-text-primary placeholder-jarvis-text-muted
            font-body text-sm
            focus:outline-none focus:border-jarvis-primary
            transition-colors duration-200
            disabled:opacity-50
          "
        />
        <div className="absolute inset-0 rounded-lg pointer-events-none opacity-0 hover:opacity-100 transition-opacity"
          style={{ boxShadow: 'inset 0 0 20px rgba(0, 212, 255, 0.1)' }}
        />
      </div>

      <motion.button
        onClick={handleSend}
        disabled={disabled || !text.trim()}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        className="
          px-6 py-3 rounded-lg
          bg-jarvis-primary/20 border border-jarvis-primary/60
          text-jarvis-primary font-display font-semibold text-sm
          hover:bg-jarvis-primary/30 hover:border-jarvis-primary
          transition-all duration-200
          disabled:opacity-50 disabled:cursor-not-allowed
        "
        style={{
          boxShadow: text.trim() ? '0 0 20px rgba(0, 212, 255, 0.3)' : 'none',
        }}
      >
        SEND
      </motion.button>
    </div>
  )
}
