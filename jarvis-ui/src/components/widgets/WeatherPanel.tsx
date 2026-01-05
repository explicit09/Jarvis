import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'

interface WeatherData {
  temp: number
  condition: string
  humidity: number
  wind: number
  feelsLike: number
  location: string
  forecast: { day: string; high: number; low: number; icon: string }[]
}

// Weather condition icons (SVG paths)
const WeatherIcons: Record<string, JSX.Element> = {
  sunny: (
    <svg viewBox="0 0 24 24" className="w-full h-full" fill="currentColor">
      <circle cx="12" cy="12" r="5" />
      <path d="M12 2v2M12 20v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M2 12h2M20 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"
        stroke="currentColor" strokeWidth="2" fill="none" />
    </svg>
  ),
  cloudy: (
    <svg viewBox="0 0 24 24" className="w-full h-full" fill="currentColor">
      <path d="M19 18H6a4 4 0 01-1.5-7.7 5.5 5.5 0 0110.7-1.8A3.5 3.5 0 0119 12v0a3 3 0 010 6z" />
    </svg>
  ),
  rainy: (
    <svg viewBox="0 0 24 24" className="w-full h-full" fill="currentColor">
      <path d="M16 18H6a4 4 0 01-1.5-7.7 5.5 5.5 0 0110.7-1.8A3.5 3.5 0 0118 12" />
      <path d="M8 19v2M12 19v2M16 19v2" stroke="currentColor" strokeWidth="2" fill="none" />
    </svg>
  ),
}

export function WeatherPanel() {
  const [weather] = useState<WeatherData>({
    temp: 72,
    condition: 'Fair',
    humidity: 45,
    wind: 8,
    feelsLike: 70,
    location: 'Los Angeles, CA',
    forecast: [
      { day: 'Today', high: 75, low: 62, icon: 'sunny' },
      { day: 'Tomorrow', high: 73, low: 60, icon: 'cloudy' },
      { day: 'Wed', high: 68, low: 55, icon: 'rainy' },
      { day: 'Thu', high: 70, low: 58, icon: 'sunny' },
      { day: 'Fri', high: 72, low: 60, icon: 'sunny' },
    ],
  })

  // In a real app, fetch weather from API
  useEffect(() => {
    // Could call your jarvis weather tool here
  }, [])

  return (
    <motion.div
      className="glass-panel p-4 rounded-lg"
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: 0.2 }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-mono text-jarvis-text-muted">WEATHER</span>
        <span className="text-xs font-mono text-jarvis-text-secondary">{weather.location}</span>
      </div>

      {/* Current weather */}
      <div className="flex items-center gap-4 mb-4">
        <div className="w-16 h-16 text-jarvis-primary">
          {WeatherIcons.sunny}
        </div>
        <div>
          <div className="text-4xl font-display text-jarvis-primary">
            {weather.temp}°
            <span className="text-lg text-jarvis-text-muted">F</span>
          </div>
          <div className="text-sm text-jarvis-text-secondary">{weather.condition}</div>
        </div>
      </div>

      {/* Details */}
      <div className="grid grid-cols-3 gap-2 mb-4 text-center">
        <div className="glass-panel p-2 rounded">
          <div className="text-xs text-jarvis-text-muted">FEELS</div>
          <div className="text-sm font-display text-jarvis-text-primary">{weather.feelsLike}°</div>
        </div>
        <div className="glass-panel p-2 rounded">
          <div className="text-xs text-jarvis-text-muted">HUMID</div>
          <div className="text-sm font-display text-jarvis-text-primary">{weather.humidity}%</div>
        </div>
        <div className="glass-panel p-2 rounded">
          <div className="text-xs text-jarvis-text-muted">WIND</div>
          <div className="text-sm font-display text-jarvis-text-primary">{weather.wind}mph</div>
        </div>
      </div>

      {/* Forecast */}
      <div className="border-t border-jarvis-border pt-3">
        <div className="text-xs font-mono text-jarvis-text-muted mb-2">5-DAY FORECAST</div>
        <div className="flex justify-between">
          {weather.forecast.map((day) => (
            <div key={day.day} className="text-center">
              <div className="text-xs text-jarvis-text-muted">{day.day}</div>
              <div className="w-6 h-6 mx-auto my-1 text-jarvis-primary opacity-60">
                {WeatherIcons[day.icon] || WeatherIcons.sunny}
              </div>
              <div className="text-xs">
                <span className="text-jarvis-text-primary">{day.high}°</span>
                <span className="text-jarvis-text-muted">/{day.low}°</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  )
}
