import { useSocket } from '../../context/SocketContext'

export function ConnectionStatus() {
  const { status } = useSocket()

  const config = {
    connected: {
      color: '#10b981',
      bg: 'rgba(16, 185, 129, 0.12)',
      label: 'Live Sync',
      icon: '🟢',
    },
    reconnecting: {
      color: '#f59e0b',
      bg: 'rgba(245, 158, 11, 0.12)',
      label: 'Reconnecting...',
      icon: '🟡',
    },
    disconnected: {
      color: '#ef4444',
      bg: 'rgba(239, 68, 68, 0.12)',
      label: 'Offline',
      icon: '🔴',
    },
  }[status] || {
    color: '#6b7280',
    bg: 'rgba(107, 114, 128, 0.12)',
    label: 'Connecting',
    icon: '⚪',
  }

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.35rem',
        padding: '0.2rem 0.6rem',
        borderRadius: '9999px',
        fontSize: '0.75rem',
        fontWeight: 600,
        color: config.color,
        background: config.bg,
        border: `1px solid ${config.color}33`,
        letterSpacing: '0.02em',
        transition: 'all 0.2s ease',
      }}
      title={`WebSocket Status: ${status}`}
    >
      <span style={{ fontSize: '0.6rem' }}>{config.icon}</span>
      <span>{config.label}</span>
    </div>
  )
}
