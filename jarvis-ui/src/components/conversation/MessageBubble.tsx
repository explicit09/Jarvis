import { Message } from '../../stores/conversationStore'

interface MessageBubbleProps {
  message: Message
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`
          max-w-[80%] px-4 py-3 rounded-lg
          ${isUser
            ? 'bg-jarvis-primary/20 border border-jarvis-primary/40'
            : 'bg-jarvis-bg-panel border border-jarvis-border'
          }
        `}
      >
        {/* Role label */}
        <div className={`text-xs font-mono mb-1 ${isUser ? 'text-jarvis-primary' : 'text-jarvis-text-muted'}`}>
          {isUser ? 'YOU' : 'JARVIS'}
        </div>

        {/* Message content */}
        <p
          className={`
            font-body text-sm leading-relaxed
            ${isUser ? 'text-jarvis-text-primary' : 'holographic-text'}
          `}
        >
          {message.content}
        </p>

        {/* Timestamp */}
        <div className="text-xs text-jarvis-text-muted mt-2 font-mono">
          {new Date(message.timestamp).toLocaleTimeString()}
        </div>
      </div>
    </div>
  )
}
