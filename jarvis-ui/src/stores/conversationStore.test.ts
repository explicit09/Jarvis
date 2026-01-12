import { describe, it, expect, beforeEach } from 'vitest'
import { useConversationStore } from './conversationStore'

describe('conversationStore', () => {
  beforeEach(() => {
    // Reset store state before each test
    useConversationStore.setState({
      messages: [],
      isLoading: false,
      sessionId: 'default',
    })
  })

  describe('addMessage', () => {
    it('should add a user message', () => {
      const { addMessage } = useConversationStore.getState()

      addMessage({ role: 'user', content: 'Hello' })

      const { messages } = useConversationStore.getState()
      expect(messages).toHaveLength(1)
      expect(messages[0].role).toBe('user')
      expect(messages[0].content).toBe('Hello')
      expect(messages[0].id).toBeDefined()
      expect(messages[0].timestamp).toBeDefined()
    })

    it('should add an assistant message', () => {
      const { addMessage } = useConversationStore.getState()

      addMessage({ role: 'assistant', content: 'Hi there!' })

      const { messages } = useConversationStore.getState()
      expect(messages).toHaveLength(1)
      expect(messages[0].role).toBe('assistant')
      expect(messages[0].content).toBe('Hi there!')
    })

    it('should add multiple messages in order', () => {
      const { addMessage } = useConversationStore.getState()

      addMessage({ role: 'user', content: 'Hello' })
      addMessage({ role: 'assistant', content: 'Hi!' })
      addMessage({ role: 'user', content: 'How are you?' })

      const { messages } = useConversationStore.getState()
      expect(messages).toHaveLength(3)
      expect(messages[0].content).toBe('Hello')
      expect(messages[1].content).toBe('Hi!')
      expect(messages[2].content).toBe('How are you?')
    })

    it('should generate unique IDs for each message', () => {
      const { addMessage } = useConversationStore.getState()

      addMessage({ role: 'user', content: 'First' })
      addMessage({ role: 'user', content: 'Second' })

      const { messages } = useConversationStore.getState()
      expect(messages[0].id).not.toBe(messages[1].id)
    })
  })

  describe('updateMessage', () => {
    it('should update message content', () => {
      const { addMessage, updateMessage } = useConversationStore.getState()

      addMessage({ role: 'assistant', content: 'Initial', isTyping: true })

      const { messages } = useConversationStore.getState()
      const messageId = messages[0].id

      updateMessage(messageId, 'Updated content')

      const updatedMessages = useConversationStore.getState().messages
      expect(updatedMessages[0].content).toBe('Updated content')
      expect(updatedMessages[0].isTyping).toBe(false)
    })

    it('should not update non-existent message', () => {
      const { addMessage, updateMessage } = useConversationStore.getState()

      addMessage({ role: 'user', content: 'Original' })
      updateMessage('non-existent-id', 'New content')

      const { messages } = useConversationStore.getState()
      expect(messages[0].content).toBe('Original')
    })
  })

  describe('setIsLoading', () => {
    it('should set loading state to true', () => {
      const { setIsLoading } = useConversationStore.getState()

      setIsLoading(true)

      const { isLoading } = useConversationStore.getState()
      expect(isLoading).toBe(true)
    })

    it('should set loading state to false', () => {
      useConversationStore.setState({ isLoading: true })
      const { setIsLoading } = useConversationStore.getState()

      setIsLoading(false)

      const { isLoading } = useConversationStore.getState()
      expect(isLoading).toBe(false)
    })
  })

  describe('clearMessages', () => {
    it('should clear all messages', () => {
      const { addMessage, clearMessages } = useConversationStore.getState()

      addMessage({ role: 'user', content: 'Message 1' })
      addMessage({ role: 'assistant', content: 'Message 2' })

      clearMessages()

      const { messages } = useConversationStore.getState()
      expect(messages).toHaveLength(0)
    })
  })

  describe('setSessionId', () => {
    it('should set session ID', () => {
      const { setSessionId } = useConversationStore.getState()

      setSessionId('new-session-123')

      const { sessionId } = useConversationStore.getState()
      expect(sessionId).toBe('new-session-123')
    })
  })
})
