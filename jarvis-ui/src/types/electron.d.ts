export interface ElectronAPI {
  // Window controls
  minimize: () => void
  maximize: () => void
  close: () => void

  // Window state
  onMaximized: (callback: (isMaximized: boolean) => void) => void

  // Voice commands
  onStartListening: (callback: () => void) => void
  onStopListening: (callback: () => void) => void

  // Conversation
  onClearConversation: (callback: () => void) => void

  // Preferences
  onOpenPreferences: (callback: () => void) => void

  // System info
  getPlatform: () => Promise<string>
  getVersion: () => Promise<string>

  // Check if running in Electron
  isElectron: boolean
}

declare global {
  interface Window {
    electron?: ElectronAPI
  }
}

export {}
