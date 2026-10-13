import React, { useEffect, useState } from 'react'
import { api } from '../../api/client'

interface DigitalTwinReplayModalProps {
  floorId: string
  isOpen: boolean
  onClose: () => void
}

interface TimelineEvent {
  id: string
  timestamp: string
  table_id: string
  table_number: string
  event_type: string
  source: string
  details: any
}

export const DigitalTwinReplayModal: React.FC<DigitalTwinReplayModalProps> = ({
  floorId,
  isOpen,
  onClose,
}) => {
  const [loading, setLoading] = useState(false)
  const [events, setEvents] = useState<TimelineEvent[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [speed, setSpeed] = useState<1 | 2 | 5>(1)

  useEffect(() => {
    if (!isOpen || !floorId) return
    setLoading(true)
    api
      .getDigitalTwinReplay(floorId)
      .then((data) => {
        setEvents(data.timeline || [])
        setCurrentIndex(0)
      })
      .catch((err) => console.error('Failed to load replay events', err))
      .finally(() => setLoading(false))
  }, [isOpen, floorId])

  useEffect(() => {
    if (!isPlaying || events.length === 0) return
    const intervalMs = Math.round(1500 / speed)
    const timer = setInterval(() => {
      setCurrentIndex((prev) => {
        if (prev >= events.length - 1) {
          setIsPlaying(false)
          return prev
        }
        return prev + 1
      })
    }, intervalMs)

    return () => clearInterval(timer)
  }, [isPlaying, events.length, speed])

  if (!isOpen) return null

  const currentEvent = events[currentIndex]

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.75)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        padding: '1rem',
      }}
    >
      <div
        style={{
          background: '#0f172a',
          color: '#f8fafc',
          border: '1px solid rgba(56, 189, 248, 0.3)',
          borderRadius: 12,
          maxWidth: 720,
          width: '100%',
          padding: '1.5rem',
          boxShadow: '0 20px 50px rgba(0, 0, 0, 0.5)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <span style={{ fontSize: '1.4rem' }}>⏪</span>
            <div>
              <h3 style={{ margin: 0, color: '#38bdf8', fontSize: '1.15rem' }}>Digital Twin Historical Replay</h3>
              <p style={{ margin: 0, fontSize: '0.8rem', color: '#94a3b8' }}>
                Timeline event-log state reconstruction
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', color: '#94a3b8', fontSize: '1.25rem', cursor: 'pointer' }}
          >
            ✕
          </button>
        </div>

        {loading ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#94a3b8' }}>Loading historical events...</div>
        ) : events.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#94a3b8' }}>
            No status changes or historical dining events recorded in the last 4 hours for this floor.
          </div>
        ) : (
          <>
            <div
              style={{
                background: '#1e293b',
                borderRadius: 8,
                padding: '1rem',
                border: '1px solid rgba(148, 163, 184, 0.2)',
                marginBottom: '1rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', fontSize: '0.82rem' }}>
                <span style={{ color: '#38bdf8', fontWeight: 600 }}>
                  Event {currentIndex + 1} of {events.length}
                </span>
                <span style={{ color: '#94a3b8' }}>
                  {currentEvent ? new Date(currentEvent.timestamp).toLocaleTimeString() : ''}
                </span>
              </div>

              {currentEvent && (
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.4rem' }}>
                    <span
                      style={{
                        background: '#0284c7',
                        color: '#fff',
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        padding: '2px 8px',
                        borderRadius: 4,
                      }}
                    >
                      Table {currentEvent.table_number}
                    </span>
                    <strong style={{ fontSize: '0.95rem' }}>{currentEvent.event_type.replace(/_/g, ' ')}</strong>
                  </div>
                  <pre
                    style={{
                      background: '#020617',
                      color: '#a5f3fc',
                      padding: '0.6rem',
                      borderRadius: 6,
                      fontSize: '0.78rem',
                      margin: 0,
                      overflowX: 'auto',
                    }}
                  >
                    {JSON.stringify(currentEvent.details, null, 2)}
                  </pre>
                </div>
              )}
            </div>

            {/* Scrubber controls */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '1rem' }}>
              <input
                type="range"
                min={0}
                max={events.length - 1}
                value={currentIndex}
                onChange={(e) => setCurrentIndex(Number(e.target.value))}
                style={{ flex: 1, accentColor: '#38bdf8' }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button
                  type="button"
                  className="btn btn-sm"
                  style={{ background: '#38bdf8', color: '#0f172a', fontWeight: 700 }}
                  onClick={() => setIsPlaying(!isPlaying)}
                >
                  {isPlaying ? '⏸ Pause' : '▶ Play'}
                </button>
                <button
                  type="button"
                  className="btn btn-sm btn-ghost"
                  style={{ color: '#f8fafc', border: '1px solid #334155' }}
                  onClick={() => setCurrentIndex(0)}
                >
                  ⏮ Reset
                </button>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Speed:</span>
                {([1, 2, 5] as const).map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setSpeed(s)}
                    style={{
                      padding: '0.2rem 0.5rem',
                      borderRadius: 4,
                      fontSize: '0.75rem',
                      background: speed === s ? '#38bdf8' : '#1e293b',
                      color: speed === s ? '#0f172a' : '#f8fafc',
                      border: 'none',
                      cursor: 'pointer',
                      fontWeight: 600,
                    }}
                  >
                    {s}x
                  </button>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
