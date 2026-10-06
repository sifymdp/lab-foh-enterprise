import { type ReactNode, useEffect, useState } from 'react'

interface PhoneFrameContainerProps {
  title: string
  roleSubtitle: string
  roleBadge: string
  badgeColor?: string
  children: ReactNode
  onRefresh?: () => void
  activeTabCount?: number
}

export function PhoneFrameContainer({
  title,
  roleSubtitle,
  roleBadge,
  badgeColor = '#c2410c',
  children,
  onRefresh,
  activeTabCount,
}: PhoneFrameContainerProps) {
  const [isMobileScreen, setIsMobileScreen] = useState(
    typeof window !== 'undefined' ? window.innerWidth <= 768 : false
  )

  const [phoneFrameActive, setPhoneFrameActive] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem('foh_phone_frame_mode')
      return saved === null ? true : saved === 'true'
    } catch {
      return true
    }
  })

  useEffect(() => {
    const handleResize = () => {
      setIsMobileScreen(window.innerWidth <= 768)
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const toggleMode = () => {
    setPhoneFrameActive((prev) => {
      const next = !prev
      try {
        localStorage.setItem('foh_phone_frame_mode', String(next))
      } catch {}
      return next
    })
  }

  // Current simulated phone time
  const [currentTime, setCurrentTime] = useState('')
  useEffect(() => {
    const updateTime = () => {
      const d = new Date()
      setCurrentTime(d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }))
    }
    updateTime()
    const timer = setInterval(updateTime, 30000)
    return () => clearInterval(timer)
  }, [])

  // If on actual mobile phone screen, render full-bleed responsive phone view
  if (isMobileScreen) {
    return (
      <div className="phone-native-view" style={{ width: '100%', minHeight: '100%', paddingBottom: '70px' }}>
        {/* Mobile Header Bar */}
        <div
          style={{
            position: 'sticky',
            top: 0,
            zIndex: 40,
            background: 'rgba(255, 255, 255, 0.95)',
            backdropFilter: 'blur(10px)',
            borderBottom: '1px solid var(--border)',
            padding: '10px 14px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span
              style={{
                fontSize: '0.72rem',
                fontWeight: 800,
                background: badgeColor,
                color: '#ffffff',
                padding: '3px 8px',
                borderRadius: '6px',
                letterSpacing: '0.04em',
              }}
            >
              {roleBadge}
            </span>
            <strong style={{ fontSize: '0.95rem', color: 'var(--text)' }}>{title}</strong>
          </div>
          {onRefresh && (
            <button
              type="button"
              onClick={onRefresh}
              className="btn btn-secondary"
              style={{ padding: '4px 10px', fontSize: '0.8rem', minHeight: '32px' }}
            >
              ↻ Sync
            </button>
          )}
        </div>

        {/* Content */}
        <div style={{ padding: '12px' }}>{children}</div>
      </div>
    )
  }

  // Desktop view with Phone Simulator Frame
  return (
    <div style={{ padding: '1rem', maxWidth: '1280px', margin: '0 auto' }}>
      {/* Control bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '1.25rem',
          background: 'var(--bg-elevated)',
          padding: '10px 16px',
          borderRadius: 'var(--radius)',
          border: '1px solid var(--border)',
          flexWrap: 'wrap',
          gap: '0.75rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span
            style={{
              fontSize: '0.75rem',
              fontWeight: 800,
              background: badgeColor,
              color: '#ffffff',
              padding: '4px 9px',
              borderRadius: '6px',
            }}
          >
            {roleBadge}
          </span>
          <div>
            <h2 style={{ fontSize: '1.2rem', margin: 0, fontWeight: 700 }}>{title}</h2>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{roleSubtitle}</span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {onRefresh && (
            <button
              type="button"
              onClick={onRefresh}
              className="btn btn-secondary"
              style={{ fontSize: '0.82rem', padding: '6px 12px', minHeight: '34px' }}
            >
              ↻ Refresh Live
            </button>
          )}
          <button
            type="button"
            onClick={toggleMode}
            className={`btn ${phoneFrameActive ? 'btn-primary' : 'btn-secondary'}`}
            style={{
              fontSize: '0.82rem',
              padding: '6px 14px',
              minHeight: '34px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
            title={phoneFrameActive ? 'Switch to wide responsive layout' : 'Switch to phone frame chassis'}
          >
            <span>{phoneFrameActive ? '📱 Phone Frame: ON' : '🖥️ Wide View: ON'}</span>
            <span style={{ fontSize: '0.72rem', opacity: 0.8 }}>(Click to switch)</span>
          </button>
        </div>
      </div>

      {phoneFrameActive ? (
        /* ─── PHONE CHASSIS SIMULATOR ─── */
        <div style={{ display: 'flex', justifyContent: 'center', padding: '10px 0 30px' }}>
          <div
            className="phone-simulator-frame"
            style={{
              width: '412px',
              minHeight: '840px',
              maxHeight: '90vh',
              background: '#0f172a',
              borderRadius: '48px',
              padding: '12px',
              boxShadow: '0 25px 60px -15px rgba(0, 0, 0, 0.35), 0 0 0 1px rgba(255, 255, 255, 0.1)',
              display: 'flex',
              flexDirection: 'column',
              position: 'relative',
            }}
          >
            {/* Outer volume & power buttons indicators */}
            <div
              style={{
                position: 'absolute',
                left: '-3px',
                top: '115px',
                width: '3px',
                height: '45px',
                background: '#334155',
                borderRadius: '2px 0 0 2px',
              }}
            />
            <div
              style={{
                position: 'absolute',
                left: '-3px',
                top: '175px',
                width: '3px',
                height: '45px',
                background: '#334155',
                borderRadius: '2px 0 0 2px',
              }}
            />
            <div
              style={{
                position: 'absolute',
                right: '-3px',
                top: '140px',
                width: '3px',
                height: '65px',
                background: '#334155',
                borderRadius: '0 2px 2px 0',
              }}
            />

            {/* Inner Phone Screen */}
            <div
              style={{
                flex: 1,
                background: '#f8fafc',
                borderRadius: '38px',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
                position: 'relative',
              }}
            >
              {/* Phone Status Bar + Dynamic Island */}
              <div
                style={{
                  height: '42px',
                  background: '#ffffff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0 22px',
                  fontSize: '0.78rem',
                  fontWeight: 700,
                  color: '#0f172a',
                  borderBottom: '1px solid rgba(0,0,0,0.05)',
                  flexShrink: 0,
                }}
              >
                <span>{currentTime || '9:41'}</span>
                {/* Dynamic Island Pill */}
                <div
                  style={{
                    width: activeTabCount ? '112px' : '94px',
                    height: '24px',
                    background: '#000000',
                    borderRadius: '16px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                  }}
                >
                  <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: activeTabCount ? '#f59e0b' : '#10b981' }} />
                  <span style={{ color: '#ffffff', fontSize: '0.65rem', fontWeight: 600 }}>
                    {activeTabCount ? `${activeTabCount} Pending` : 'FOH Live'}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem' }}>
                  <span>5G</span>
                  <span>📶</span>
                  <span>🔋</span>
                </div>
              </div>

              {/* Scrollable Phone Screen App Content */}
              <div
                style={{
                  flex: 1,
                  overflowY: 'auto',
                  padding: '12px',
                  WebkitOverflowScrolling: 'touch',
                }}
              >
                {children}
              </div>

              {/* iOS Home Indicator Bar */}
              <div
                style={{
                  height: '20px',
                  background: '#ffffff',
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  flexShrink: 0,
                  borderTop: '1px solid rgba(0,0,0,0.04)',
                }}
              >
                <div
                  style={{
                    width: '120px',
                    height: '4px',
                    background: '#cbd5e1',
                    borderRadius: '999px',
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* Wide Responsive View */
        <div style={{ background: 'var(--surface)', borderRadius: 'var(--radius-lg)', padding: '1.25rem', border: '1px solid var(--border)' }}>
          {children}
        </div>
      )}
    </div>
  )
}
