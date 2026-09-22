import { useEffect, useState } from 'react'

interface TimerProps {
  startedAt: string
  endedAt?: string | null
  status: 'RECEIVED' | 'PREPARING' | 'READY' | 'SERVED'
  estimatedMinutes?: number
  warningMinutes: number
  warningMessage: string
}

export function KDSTimer({
  startedAt,
  endedAt,
  status,
  estimatedMinutes,
  warningMinutes,
  warningMessage,
}: TimerProps) {
  const [elapsedSeconds, setElapsedSeconds] = useState(0)

  useEffect(() => {
    const updateElapsed = () => {
      const started = new Date(startedAt).getTime()
      const end = endedAt ? new Date(endedAt).getTime() : Date.now()
      const seconds = Math.floor((end - started) / 1000)
      setElapsedSeconds(Math.max(0, seconds))
    }

    updateElapsed()
    const interval = setInterval(updateElapsed, 1000)
    return () => clearInterval(interval)
  }, [startedAt, endedAt])

  const minutes = Math.floor(elapsedSeconds / 60)
  const seconds = elapsedSeconds % 60
  const formatted = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`

  const label = status === 'RECEIVED'
    ? 'Waiting:'
    : status === 'PREPARING'
      ? 'Prep time:'
      : status === 'READY'
        ? 'Ready for:'
        : 'Served:'

  const expectedText = status === 'PREPARING' && typeof estimatedMinutes === 'number'
    ? `Expected: ${String(Math.floor((estimatedMinutes * 60) / 60)).padStart(2, '0')}:${String(Math.floor((estimatedMinutes * 60) % 60)).padStart(2, '0')}`
    : undefined

  const warningSeconds = warningMinutes * 60
  const estimateSeconds = (estimatedMinutes ?? 10) * 60
  const lateAfterSeconds = estimateSeconds + 2 * 60
  let colorClass = 'timer-ok'
  if (status !== 'SERVED' && elapsedSeconds >= warningSeconds) {
    colorClass = 'timer-late'
  }
  if (status === 'PREPARING' && elapsedSeconds >= lateAfterSeconds + 5 * 60) {
    colorClass = 'timer-critical'
  }

  return (
    <div className="order-card__timer-stack">
      <div style={{ fontSize: 12, color: '#cbd5e1', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 700 }}>
        {label}
      </div>
      <div className={`kds-timer ${colorClass}`}>
        ⏱️ {formatted}
      </div>
      {expectedText && (
        <div style={{ fontSize: 12, color: '#bfdbfe', fontWeight: 600 }}>
          {expectedText}
        </div>
      )}
      {status !== 'SERVED' && elapsedSeconds >= warningSeconds && (
        <div className="order-card__workflow-alert">
          ⚠️ {warningMessage}
        </div>
      )}
    </div>
  )
}