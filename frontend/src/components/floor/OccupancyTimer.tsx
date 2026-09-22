import { useEffect, useState } from 'react'

function formatElapsed(ms: number): string {
  const totalSec = Math.floor(ms / 1000)
  const h = Math.floor(totalSec / 3600)
  const m = Math.floor((totalSec % 3600) / 60)
  const s = totalSec % 60
  if (h > 0) return `${h}h ${m}m`
  return `${m}m ${s}s`
}

export function OccupancyTimer({ seatedAt }: { seatedAt: string }) {
  const [elapsed, setElapsed] = useState(() => Date.now() - new Date(seatedAt).getTime())

  useEffect(() => {
    const id = setInterval(() => {
      setElapsed(Date.now() - new Date(seatedAt).getTime())
    }, 1000)
    return () => clearInterval(id)
  }, [seatedAt])

  return <span className="occupancy-timer">{formatElapsed(elapsed)}</span>
}
