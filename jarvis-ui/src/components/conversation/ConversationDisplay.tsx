import { useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useConversationStore } from '../../stores/conversationStore'
import { MessageBubble } from './MessageBubble'
import { TypingIndicator } from './TypingIndicator'

export function ConversationDisplay() {
  const { messages, isLoading } = useConversationStore()
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  return (
    <div
      ref={scrollRef}
      className="h-full overflow-y-auto px-4 py-2 space-y-4"
    >
      <AnimatePresence>
        {messages.map((message) => (
          <motion.div
            key={message.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3 }}
          >
            <MessageBubble message={message} />
          </motion.div>
        ))}

        {isLoading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <TypingIndicator />
          </motion.div>
        )}
      </AnimatePresence>

      {messages.length === 0 && !isLoading && (
        <div className="h-full flex items-center justify-center">
          <p className="text-jarvis-text-muted text-center font-body">
            Ready to assist. <br />
            <span className="text-jarvis-primary">Speak or type a command.</span>
          </p>
        </div>
      )}
    </div>
  )
}
