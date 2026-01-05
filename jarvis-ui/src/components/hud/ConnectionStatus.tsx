import { useSystemStore } from '../../stores/systemStore'

export function ConnectionStatus() {
  const { hubInfo, isConnected } = useSystemStore()

  return (
    <div className="glass-panel px-4 py-3 rounded-lg min-w-[180px]">
      <div className="text-xs font-mono text-jarvis-text-muted mb-2">HUB STATUS</div>

      <div className="space-y-2">
        {/* Connection status */}
        <div className="flex items-center justify-between">
          <span className="text-xs font-mono text-jarvis-text-muted">STATUS</span>
          <div className="flex items-center gap-2">
            <div
              className={`w-2 h-2 rounded-full ${
                isConnected ? 'bg-jarvis-success' : 'bg-jarvis-error'
              }`}
              style={{
                boxShadow: isConnected
                  ? '0 0 6px rgba(0, 255, 136, 0.8)'
                  : '0 0 6px rgba(255, 51, 102, 0.8)',
              }}
            />
            <span className={`text-sm font-mono ${isConnected ? 'text-jarvis-success' : 'text-jarvis-error'}`}>
              {isConnected ? 'ONLINE' : 'OFFLINE'}
            </span>
          </div>
        </div>

        {/* Hub IP */}
        {hubInfo && (
          <>
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-jarvis-text-muted">IP</span>
              <span className="text-sm font-mono text-jarvis-text-secondary">
                {hubInfo.hubIp}:{hubInfo.hubPort}
              </span>
            </div>

            {/* Clients connected */}
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-jarvis-text-muted">CLIENTS</span>
              <span className="text-sm font-mono text-jarvis-primary">
                {hubInfo.clientsConnected}
              </span>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
