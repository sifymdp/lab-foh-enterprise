interface ToastItem {
  id: string
  message: string
  variant?: 'default' | 'error'
}

interface ToastStackProps {
  toasts: ToastItem[]
}

export function ToastStack({ toasts }: ToastStackProps) {
  if (!toasts.length) return null
  return (
    <div style={{ position: 'fixed', top: 16, right: 16, zIndex: 1500, display: 'flex', flexDirection: 'column', gap: 8 }}>
      {toasts.map((t) => (
        <div
          key={t.id}
          style={{
            maxWidth: 360,
            padding: '12px 16px',
            background: t.variant === 'error' ? '#b91c1c' : '#1e293b',
            color: '#fff',
            borderRadius: 8,
            boxShadow: '0 4px 12px rgba(0,0,0,0.25)',
            fontSize: 14,
          }}
        >
          {t.message}
        </div>
      ))}
    </div>
  )
}
