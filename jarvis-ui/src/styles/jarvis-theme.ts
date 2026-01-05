// JARVIS Iron Man Theme
export const jarvisTheme = {
  colors: {
    // Primary blues
    primary: '#00d4ff',
    primaryDim: '#0088aa',
    primaryGlow: 'rgba(0, 212, 255, 0.6)',

    // Background layers
    bgDeep: '#050a12',
    bgPanel: '#0a1428',
    bgOverlay: 'rgba(10, 20, 40, 0.85)',

    // Accent colors
    accent: '#ff6b35',      // Arc reactor orange
    success: '#00ff88',
    warning: '#ffaa00',
    error: '#ff3366',

    // Text
    textPrimary: '#e0f4ff',
    textSecondary: '#8ab4d4',
    textMuted: '#4a6a8a',

    // Borders
    border: 'rgba(0, 212, 255, 0.3)',
    borderActive: 'rgba(0, 212, 255, 0.8)',
  },

  gradients: {
    arcReactor: 'radial-gradient(circle, #00d4ff 0%, #0088aa 50%, transparent 70%)',
    glowRadial: 'radial-gradient(circle, rgba(0, 212, 255, 0.3) 0%, transparent 70%)',
    panelBg: 'linear-gradient(135deg, rgba(10, 20, 40, 0.9) 0%, rgba(5, 10, 18, 0.95) 100%)',
  },

  shadows: {
    glow: '0 0 20px rgba(0, 212, 255, 0.4)',
    glowStrong: '0 0 40px rgba(0, 212, 255, 0.6)',
    innerGlow: 'inset 0 0 20px rgba(0, 212, 255, 0.2)',
    text: '0 0 10px rgba(0, 212, 255, 0.8), 0 0 20px rgba(0, 212, 255, 0.4)',
  },

  fonts: {
    display: '"Orbitron", "Rajdhani", sans-serif',
    body: '"Rajdhani", "Roboto", sans-serif',
    mono: '"JetBrains Mono", "Fira Code", monospace',
  },
} as const

export type JarvisTheme = typeof jarvisTheme
