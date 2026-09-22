interface EmptyStateProps {
  icon?: string
  title: string
  message?: string
}

export function EmptyState({ icon = '○', title, message }: EmptyStateProps) {
  return (
    <div style={{ textAlign: 'center', padding: '60px 24px', color: '#64748b' }}>
      <div style={{ fontSize: 48, marginBottom: 12 }} aria-hidden>{icon}</div>
      <p style={{ fontSize: 16, margin: '0 0 6px', color: '#334155' }}>{title}</p>
      {message && <p style={{ fontSize: 13, margin: 0 }}>{message}</p>}
    </div>
  )
}
