import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'

export function DateTimePanel() {
  const [time, setTime] = useState(new Date())

  useEffect(() => {
    const interval = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(interval)
  }, [])

  const hours = time.getHours().toString().padStart(2, '0')
  const minutes = time.getMinutes().toString().padStart(2, '0')
  const seconds = time.getSeconds().toString().padStart(2, '0')

  const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
  const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December']

  const dayName = dayNames[time.getDay()]
  const monthName = monthNames[time.getMonth()]
  const date = time.getDate()
  const year = time.getFullYear()

  // Generate calendar days
  const firstDayOfMonth = new Date(time.getFullYear(), time.getMonth(), 1).getDay()
  const daysInMonth = new Date(time.getFullYear(), time.getMonth() + 1, 0).getDate()
  const calendarDays = []

  for (let i = 0; i < firstDayOfMonth; i++) {
    calendarDays.push(null)
  }
  for (let i = 1; i <= daysInMonth; i++) {
    calendarDays.push(i)
  }

  return (
    <motion.div
      className="glass-panel p-4 rounded-lg"
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: 0.1 }}
    >
      {/* Digital clock */}
      <div className="text-center mb-4">
        <div className="flex items-center justify-center gap-1">
          <span className="text-5xl font-display holographic-text tracking-wider">
            {hours}
          </span>
          <motion.span
            className="text-5xl font-display text-jarvis-primary"
            animate={{ opacity: [1, 0.3, 1] }}
            transition={{ duration: 1, repeat: Infinity }}
          >
            :
          </motion.span>
          <span className="text-5xl font-display holographic-text tracking-wider">
            {minutes}
          </span>
          <span className="text-2xl font-mono text-jarvis-text-muted ml-2 self-end mb-2">
            {seconds}
          </span>
        </div>

        <div className="text-sm text-jarvis-text-secondary mt-1">
          {time.getHours() >= 12 ? 'PM' : 'AM'} • Local Time
        </div>
      </div>

      {/* Date display */}
      <div className="text-center border-t border-jarvis-border pt-3 mb-3">
        <div className="text-lg font-display text-jarvis-text-primary">
          {dayName}
        </div>
        <div className="text-sm text-jarvis-text-secondary">
          {monthName} {date}, {year}
        </div>
      </div>

      {/* Mini calendar */}
      <div className="border-t border-jarvis-border pt-3">
        <div className="grid grid-cols-7 gap-1 text-center text-xs">
          {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((d, i) => (
            <div key={i} className="text-jarvis-text-muted font-mono py-1">
              {d}
            </div>
          ))}
          {calendarDays.map((day, i) => (
            <div
              key={i}
              className={`py-1 rounded ${
                day === date
                  ? 'bg-jarvis-primary text-jarvis-bg-deep font-bold'
                  : day
                  ? 'text-jarvis-text-secondary hover:bg-jarvis-primary/20'
                  : ''
              }`}
            >
              {day || ''}
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  )
}
