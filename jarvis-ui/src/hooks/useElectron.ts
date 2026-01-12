import { useEffect, useCallback } from 'react'
import { useConversationStore } from '../stores/conversationStore'
import { useVoiceStore } from '../stores/voiceStore'

/**
 * Hook to handle Electron-specific functionality
 * Returns whether the app is running in Electron and provides utilities
 */
export function useElectron() {
  const isElectron = typeof window !== 'undefined' && !!window.electron

  const { clearMessages } = useConversationStore()
  const { setState, setIsRecording } = useVoiceStore()

  // Handle voice commands from menu/shortcuts
  useEffect(() => {
    if (!window.electron) return

    window.electron.onStartListening(() => {
      setState('listening')
      setIsRecording(true)
    })

    window.electron.onStopListening(() => {
      setState('idle')
      setIsRecording(false)
    })

    window.electron.onClearConversation(() => {
      clearMessages()
    })

    window.electron.onOpenPreferences(() => {
      // TODO: Open preferences modal
      console.log('Open preferences')
    })
  }, [setState, setIsRecording, clearMessages])

  const minimize = useCallback(() => {
    window.electron?.minimize()
  }, [])

  const maximize = useCallback(() => {
    window.electron?.maximize()
  }, [])

  const close = useCallback(() => {
    window.electron?.close()
  }, [])

  const getPlatform = useCallback(async () => {
    if (!window.electron) return 'web'
    return window.electron.getPlatform()
  }, [])

  const getVersion = useCallback(async () => {
    if (!window.electron) return '0.0.0'
    return window.electron.getVersion()
  }, [])

  return {
    isElectron,
    minimize,
    maximize,
    close,
    getPlatform,
    getVersion,
  }
}
