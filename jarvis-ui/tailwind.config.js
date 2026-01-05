/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        jarvis: {
          primary: '#00d4ff',
          'primary-dim': '#0088aa',
          'primary-glow': 'rgba(0, 212, 255, 0.6)',
          'bg-deep': '#050a12',
          'bg-panel': '#0a1428',
          'bg-overlay': 'rgba(10, 20, 40, 0.85)',
          accent: '#ff6b35',
          success: '#00ff88',
          warning: '#ffaa00',
          error: '#ff3366',
          'text-primary': '#e0f4ff',
          'text-secondary': '#8ab4d4',
          'text-muted': '#4a6a8a',
          border: 'rgba(0, 212, 255, 0.3)',
          'border-active': 'rgba(0, 212, 255, 0.8)',
        }
      },
      fontFamily: {
        display: ['Orbitron', 'Rajdhani', 'sans-serif'],
        body: ['Rajdhani', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      boxShadow: {
        'glow': '0 0 20px rgba(0, 212, 255, 0.4)',
        'glow-strong': '0 0 40px rgba(0, 212, 255, 0.6)',
        'inner-glow': 'inset 0 0 20px rgba(0, 212, 255, 0.2)',
      },
      animation: {
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
        'spin-slow': 'spin 8s linear infinite',
        'scan': 'scan 2s linear infinite',
      },
      keyframes: {
        'pulse-glow': {
          '0%, 100%': { opacity: '0.6', transform: 'scale(1)' },
          '50%': { opacity: '1', transform: 'scale(1.05)' },
        },
        'scan': {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100%)' },
        },
      },
    },
  },
  plugins: [],
}
