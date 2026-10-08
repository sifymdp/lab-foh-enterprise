import { useEffect, useState } from 'react'

function formatRemaining(ms: number): string {
  if (ms <= 0) return 'Releasing soon'
  const totalSec = Math.floor(ms / 1000)
  const h = Math.floor(totalSec / 3600)
  const m = Math.floor((totalSec % 3600) / 60)
  const s = totalSec % 60
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

export function ReleaseCountdown({ until }: { until: string }) {
  const [remaining, setRemaining] = useState(() => new Date(until).getTime() - Date.now())

  useEffect(() => {
    const tick = () => setRemaining(new Date(until).getTime() - Date.now())
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [until])

  const expired = remaining <= 0
  return (
    <span style={{ color: expired ? '#b91c1c' : '#64748b', fontWeight: expired ? 600 : 400 }}>
      Auto-release in {formatRemaining(remaining)}
    </span>
  )
}
