import { useSystemStore } from '../../stores/systemStore'

export function MetricsDisplay() {
  const { metrics } = useSystemStore()

  const items = [
    { label: 'ASR', value: metrics.asrLatency, unit: 'ms' },
    { label: 'LLM', value: metrics.llmLatency, unit: 'ms' },
    { label: 'TTS', value: metrics.ttsLatency, unit: 'ms' },
  ]

  return (
    <div className="glass-panel px-4 py-3 rounded-lg">
      <div className="text-xs font-mono text-jarvis-text-muted mb-2">LATENCY</div>
      <div className="flex gap-4">
        {items.map(({ label, value, unit }) => (
          <div key={label} className="text-center">
            <div className="text-xs font-mono text-jarvis-text-muted">{label}</div>
            <div className="text-lg font-display text-jarvis-primary">
              {value > 0 ? value : '--'}
              <span className="text-xs text-jarvis-text-muted ml-1">{unit}</span>
            </div>
          </div>
        ))}
      </div>

      {/* E2E latency bar */}
      {metrics.e2eLatency > 0 && (
        <div className="mt-2 pt-2 border-t border-jarvis-border">
          <div className="flex justify-between items-center">
            <span className="text-xs font-mono text-jarvis-text-muted">E2E</span>
            <span className="text-sm font-display text-jarvis-success">
              {metrics.e2eLatency}ms
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
