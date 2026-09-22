import { useState } from 'react'
import { lossPreventionApi, type AIEvent } from '../../api/extensions'

interface WalkoutEmergencyModalProps {
  alert: AIEvent
  onClose: () => void
  onResolved: (eventId: string, resolution: string) => void
}

export function WalkoutEmergencyModal({
  alert,
  onClose,
  onResolved,
}: WalkoutEmergencyModalProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notes, setNotes] = useState('')

  const metadata = alert.metadata
  const tableNum = metadata?.table_number ?? '?'
  const unpaid = metadata?.unpaid_total ?? 0
  const guestName = metadata?.guest_name ?? 'Walk-in Guest'
  const items = metadata?.items ?? []

  const handleAction = async (
    resolution: 'PAID_COUNTER' | 'FALSE_ALARM' | 'LOGGED_UNRECOVERED',
  ) => {
    setLoading(true)
    setError(null)
    try {
      await lossPreventionApi.resolve(alert.id, resolution, notes || undefined)
      onResolved(alert.id, resolution)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resolve incident')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(15, 23, 42, 0.75)',
        backdropFilter: 'blur(6px)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '16px',
        animation: 'fadeIn 0.2s ease-out',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '540px',
          backgroundColor: '#1e293b',
          borderRadius: '16px',
          boxShadow: '0 25px 50px -12px rgba(220, 38, 38, 0.35), 0 0 0 2px #ef4444',
          color: '#f8fafc',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Emergency Header */}
        <div
          style={{
            backgroundColor: '#dc2626',
            color: '#ffffff',
            padding: '16px 20px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '24px' }}>🚨</span>
            <div>
              <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 700, letterSpacing: '0.02em' }}>
                LOSS PREVENTION: WALKOUT DETECTED
              </h2>
              <p style={{ margin: 0, fontSize: '13px', opacity: 0.9 }}>
                Ceiling camera detected guests vacated without paying
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: '#ffffff',
              fontSize: '20px',
              cursor: 'pointer',
              padding: '4px',
              opacity: 0.8,
            }}
          >
            ✕
          </button>
        </div>

        {/* Modal Content */}
        <div style={{ padding: '24px' }}>
          {error && (
            <div
              style={{
                backgroundColor: 'rgba(239, 68, 68, 0.2)',
                border: '1px solid #ef4444',
                color: '#fca5a5',
                padding: '10px 14px',
                borderRadius: '8px',
                marginBottom: '16px',
                fontSize: '13px',
              }}
            >
              {error}
            </div>
          )}

          {/* Table & Total Exposure Card */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '12px',
              marginBottom: '20px',
            }}
          >
            <div
              style={{
                backgroundColor: '#0f172a',
                padding: '14px 16px',
                borderRadius: '10px',
                border: '1px solid #334155',
              }}
            >
              <div style={{ fontSize: '12px', color: '#94a3b8', textTransform: 'uppercase' }}>
                Table Number
              </div>
              <div style={{ fontSize: '26px', fontWeight: 800, color: '#38bdf8' }}>
                Table {tableNum}
              </div>
              <div style={{ fontSize: '13px', color: '#cbd5e1', marginTop: '2px' }}>
                {guestName} ({metadata?.party_size ?? 2} guests)
              </div>
            </div>

            <div
              style={{
                backgroundColor: '#450a0a',
                padding: '14px 16px',
                borderRadius: '10px',
                border: '1px solid #dc2626',
              }}
            >
              <div style={{ fontSize: '12px', color: '#fca5a5', textTransform: 'uppercase' }}>
                Unpaid Exposure
              </div>
              <div style={{ fontSize: '26px', fontWeight: 800, color: '#f87171' }}>
                ${unpaid.toFixed(2)}
              </div>
              <div style={{ fontSize: '13px', color: '#fca5a5', marginTop: '2px' }}>
                {metadata?.item_count ?? items.length} unpaid items
              </div>
            </div>
          </div>

          {/* Itemized Order Breakdown */}
          {items.length > 0 && (
            <div style={{ marginBottom: '20px' }}>
              <div
                style={{
                  fontSize: '13px',
                  fontWeight: 600,
                  color: '#cbd5e1',
                  marginBottom: '8px',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                }}
              >
                Unpaid Items Ordered
              </div>
              <div
                style={{
                  backgroundColor: '#0f172a',
                  border: '1px solid #334155',
                  borderRadius: '10px',
                  maxHeight: '140px',
                  overflowY: 'auto',
                  padding: '8px 12px',
                }}
              >
                {items.map((item, index) => (
                  <div
                    key={index}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '6px 0',
                      borderBottom:
                        index < items.length - 1 ? '1px solid #1e293b' : 'none',
                      fontSize: '13px',
                    }}
                  >
                    <span>
                      <strong style={{ color: '#38bdf8' }}>{item.quantity}x</strong>{' '}
                      {item.item_name}
                    </span>
                    <span style={{ color: '#e2e8f0', fontWeight: 500 }}>
                      ${item.line_total.toFixed(2)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Optional Resolution Notes */}
          <div style={{ marginBottom: '24px' }}>
            <label
              style={{
                display: 'block',
                fontSize: '12px',
                color: '#94a3b8',
                marginBottom: '6px',
              }}
            >
              Resolution Notes (Optional)
            </label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Paid in cash at register, or customer stepped out to smoke"
              style={{
                width: '100%',
                padding: '10px 14px',
                backgroundColor: '#0f172a',
                border: '1px solid #334155',
                borderRadius: '8px',
                color: '#ffffff',
                fontSize: '13px',
                boxSizing: 'border-box',
              }}
            />
          </div>

          {/* 1-Click Action Buttons */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <button
              disabled={loading}
              onClick={() => handleAction('PAID_COUNTER')}
              style={{
                padding: '12px 16px',
                backgroundColor: '#16a34a',
                color: '#ffffff',
                border: 'none',
                borderRadius: '10px',
                fontSize: '14px',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                transition: 'background 0.15s ease',
              }}
            >
              <span>💳</span> Guest Paid at Counter / Cashier (Mark Paid & Clean)
            </button>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <button
                disabled={loading}
                onClick={() => handleAction('FALSE_ALARM')}
                style={{
                  padding: '10px 14px',
                  backgroundColor: '#334155',
                  color: '#e2e8f0',
                  border: '1px solid #475569',
                  borderRadius: '10px',
                  fontSize: '13px',
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                💨 False Alarm (Stepped Out)
              </button>

              <button
                disabled={loading}
                onClick={() => handleAction('LOGGED_UNRECOVERED')}
                style={{
                  padding: '10px 14px',
                  backgroundColor: '#7f1d1d',
                  color: '#fecaca',
                  border: '1px solid #991b1b',
                  borderRadius: '10px',
                  fontSize: '13px',
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                ⚠️ Log Unrecovered Walkout
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
