import { useEffect, useCallback, useState } from 'react'
import { MainLayout } from './components/layout/MainLayout'
import { GlassPanel } from './components/layout/GlassPanel'
import { HUDFrame } from './components/layout/HUDFrame'
import { EnhancedArcReactor } from './components/orb/EnhancedArcReactor'
import { CircularWaveform } from './components/waveform/CircularWaveform'
import { ConversationDisplay } from './components/conversation/ConversationDisplay'
import { TextInput } from './components/controls/TextInput'
import { StatusOverlay } from './components/hud/StatusOverlay'
import { HexGrid } from './components/effects/HexGrid'
import { DateTimePanel } from './components/widgets/DateTimePanel'
import { WeatherPanel } from './components/widgets/WeatherPanel'
import { SystemMetrics } from './components/widgets/SystemMetrics'
import { MusicPanel } from './components/widgets/MusicPanel'
import { TitleBar } from './components/electron/TitleBar'
import { useJarvisAPI } from './hooks/useJarvisAPI'
import { useTTS } from './hooks/useTTS'
import { useVoiceWebSocket } from './hooks/useVoiceWebSocket'
import { useElectron } from './hooks/useElectron'
import { useConversationStore } from './stores/conversationStore'
import { useVoiceStore } from './stores/voiceStore'

export default function App() {
  const { checkConnection, sendChat, getHubInfo } = useJarvisAPI()
  const { isLoading } = useConversationStore()
  const { state: voiceState } = useVoiceStore()
  const { speak } = useTTS()
  const { isElectron } = useElectron()
  const [voiceEnabled, setVoiceEnabled] = useState(false)

  // WebSocket voice streaming (handles wake word + STT + TTS on server)
  const {
    isConnected,
    voiceState: wsVoiceState,
    wakeWord,
    connect,
    disconnect,
    skipWakeWord,
  } = useVoiceWebSocket({
    onReady: () => console.log('Voice WebSocket ready'),
    onWakeWordDetected: () => console.log('Wake word detected!'),
    onTranscription: (text) => console.log('Transcription:', text),
    onResponse: (text) => console.log('Response:', text),
    onError: (error) => console.error('Voice error:', error),
  })

  // Check connection on mount and periodically
  useEffect(() => {
    checkConnection()
    getHubInfo()

    const interval = setInterval(() => {
      checkConnection()
    }, 10000)

    return () => clearInterval(interval)
  }, [checkConnection, getHubInfo])

  // Handle text input (fallback when voice not connected)
  const handleSendText = useCallback(async (text: string) => {
    const response = await sendChat(text)
    if (response?.text) {
      await speak(response.text)
    }
  }, [sendChat, speak])

  // Toggle voice connection
  const toggleVoice = () => {
    if (voiceEnabled) {
      disconnect()
      setVoiceEnabled(false)
    } else {
      connect()
      setVoiceEnabled(true)
    }
  }

  // Get display state
  const displayState = isConnected ? wsVoiceState : voiceState
  const getStateText = () => {
    if (!isConnected) return 'DISCONNECTED'
    switch (wsVoiceState) {
      case 'listening_wake_word': return `SAY "${wakeWord.toUpperCase()}"`
      case 'listening_speech': return 'LISTENING...'
      case 'processing': return 'PROCESSING...'
      case 'speaking': return 'SPEAKING...'
      default: return 'READY'
    }
  }

  return (
    <MainLayout>
      {/* Electron title bar (Windows/Linux only) */}
      {isElectron && <TitleBar />}

      {/* Background effects */}
      <HexGrid />

      {/* Status overlays */}
      <StatusOverlay />

      {/* Full Dashboard Layout */}
      <div className="h-full grid grid-cols-12 gap-4 p-4">
        {/* Left Column - Date/Time & Weather */}
        <div className="col-span-12 lg:col-span-3 flex flex-col gap-4">
          <DateTimePanel />
          <WeatherPanel />
        </div>

        {/* Center Column - Arc Reactor & Conversation */}
        <div className="col-span-12 lg:col-span-6 flex flex-col gap-4">
          {/* Arc Reactor with Waveform */}
          <div className="flex-shrink-0 flex flex-col items-center justify-center relative py-4">
            {/* Circular waveform behind orb */}
            <div className="absolute pointer-events-none">
              <CircularWaveform size={380} />
            </div>

            {/* Enhanced Arc Reactor Orb */}
            <div className="w-[320px] h-[320px] z-10 pointer-events-none">
              <EnhancedArcReactor className="w-full h-full" />
            </div>

            {/* Listening Status Indicator */}
            <div className="mt-4 flex flex-col items-center gap-3 z-20 relative">
              <div className="flex items-center gap-2">
                {/* Main voice toggle */}
                <button
                  onClick={toggleVoice}
                  className={`px-4 py-2 rounded-full font-mono text-xs transition-all ${
                    isConnected
                      ? 'bg-jarvis-primary/20 border border-jarvis-primary text-jarvis-primary'
                      : 'bg-jarvis-bg-panel border border-jarvis-border text-jarvis-text-muted'
                  }`}
                  style={isConnected ? { boxShadow: '0 0 15px rgba(0, 212, 255, 0.3)' } : {}}
                >
                  {isConnected ? 'VOICE ON' : 'VOICE OFF'}
                </button>

                {/* Skip wake word button (when connected and waiting for wake word) */}
                {isConnected && wsVoiceState === 'listening_wake_word' && (
                  <button
                    onClick={skipWakeWord}
                    className="px-4 py-2 rounded-full font-mono text-xs transition-all bg-jarvis-accent/20 border border-jarvis-accent text-jarvis-accent hover:bg-jarvis-accent/30"
                  >
                    SKIP WAKE WORD
                  </button>
                )}
              </div>

              {/* Status indicator */}
              <div className="flex items-center gap-2 h-5">
                {voiceEnabled && (
                  <>
                    <div className={`w-2 h-2 rounded-full animate-pulse ${
                      isConnected ? 'bg-jarvis-success' : 'bg-jarvis-error'
                    }`} />
                    <span className="text-xs font-mono text-jarvis-text-secondary">
                      {getStateText()}
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Conversation Panel */}
          <HUDFrame className="flex-1 flex flex-col min-h-0">
            <GlassPanel className="flex-1 flex flex-col min-h-0" animate={false}>
              {/* Conversation header */}
              <div className="px-4 py-3 border-b border-jarvis-border flex items-center justify-between">
                <h2 className="font-display text-sm text-jarvis-text-secondary tracking-wider">
                  CONVERSATION LOG
                </h2>
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${
                    displayState === 'speaking' ? 'bg-jarvis-accent animate-pulse' :
                    displayState === 'listening' || displayState === 'listening_speech' ? 'bg-jarvis-success animate-pulse' :
                    displayState === 'processing' ? 'bg-jarvis-warning animate-pulse' :
                    'bg-jarvis-text-muted'
                  }`} />
                  <span className="text-xs font-mono text-jarvis-text-muted uppercase">
                    {displayState}
                  </span>
                </div>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-hidden">
                <ConversationDisplay />
              </div>

              {/* Text input */}
              <div className="p-4 border-t border-jarvis-border">
                <TextInput onSend={handleSendText} disabled={isLoading} />
              </div>
            </GlassPanel>
          </HUDFrame>
        </div>

        {/* Right Column - System Metrics & Music */}
        <div className="col-span-12 lg:col-span-3 flex flex-col gap-4">
          <SystemMetrics />
          <MusicPanel />
        </div>
      </div>

      {/* Bottom HUD status bar */}
      <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-jarvis-bg-deep to-transparent">
        <div className="h-full flex items-center justify-center gap-8 text-xs font-mono text-jarvis-text-muted">
          <span>JARVIS v2.0</span>
          <span className="text-jarvis-primary">|</span>
          <span>{isElectron ? 'DESKTOP' : 'WEB'}</span>
          <span className="text-jarvis-primary">|</span>
          <span>{isConnected ? 'VOICE CONNECTED' : 'AI ASSISTANT ONLINE'}</span>
        </div>
      </div>
    </MainLayout>
  )
}
