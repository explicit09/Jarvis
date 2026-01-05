import { create } from 'zustand'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  isTyping?: boolean
  spoken?: boolean
}

interface ConversationStore {
  messages: Message[]
  isLoading: boolean
  sessionId: string

  addMessage: (message: Omit<Message, 'id' | 'timestamp'>) => void
  updateMessage: (id: string, content: string) => void
  setIsLoading: (isLoading: boolean) => void
  clearMessages: () => void
  setSessionId: (sessionId: string) => void
}

export const useConversationStore = create<ConversationStore>((set) => ({
  messages: [],
  isLoading: false,
  sessionId: 'default',

  addMessage: (message) =>
    set((state) => ({
      messages: [
        ...state.messages,
        {
          ...message,
          id: crypto.randomUUID(),
          timestamp: Date.now(),
        },
      ],
    })),

  updateMessage: (id, content) =>
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === id ? { ...msg, content, isTyping: false } : msg
      ),
    })),

  setIsLoading: (isLoading) => set({ isLoading }),

  clearMessages: () => set({ messages: [] }),

  setSessionId: (sessionId) => set({ sessionId }),
}))
