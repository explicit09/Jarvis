const { contextBridge, ipcRenderer } = require('electron')

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electron', {
  // Window controls
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),

  // Window state
  onMaximized: (callback) => {
    ipcRenderer.on('window-maximized', (_, isMaximized) => callback(isMaximized))
  },

  // Voice commands
  onStartListening: (callback) => {
    ipcRenderer.on('start-listening', () => callback())
  },
  onStopListening: (callback) => {
    ipcRenderer.on('stop-listening', () => callback())
  },

  // Conversation
  onClearConversation: (callback) => {
    ipcRenderer.on('clear-conversation', () => callback())
  },

  // Preferences
  onOpenPreferences: (callback) => {
    ipcRenderer.on('open-preferences', () => callback())
  },

  // System info
  getPlatform: () => ipcRenderer.invoke('get-platform'),
  getVersion: () => ipcRenderer.invoke('get-version'),

  // Check if running in Electron
  isElectron: true,
})

// Add types for TypeScript
// This file is loaded as CommonJS, but the types help with IDE support
