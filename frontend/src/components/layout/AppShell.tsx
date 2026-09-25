import { useCallback, useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { ToastStack } from '../ui/ToastStack'
import { useAuth } from '../../context/AuthContext'
import { useSocket } from '../../context/SocketContext'
import { ConnectionStatus } from '../common/ConnectionStatus'
import { GlobalSearch } from '../common/GlobalSearch'
import { AIChatWidget } from '../ui/AIChatWidget'
import { WalkoutEmergencyModal } from '../floor/WalkoutEmergencyModal'
import { VoiceReceptionistModal } from '../voice/VoiceReceptionistModal'
import { playWalkoutAlarm } from '../../lib/soundAlerts'
import type { AIEvent } from '../../api/extensions'

interface NavItem {
  to: string
  label: string
  icon: string
  hasBadge?: boolean
}

interface ToastItem { id: string; message: string; variant?: 'default' | 'error' }

function SidebarToggleIcon({ collapsed }: { collapsed?: boolean }) {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 18 18"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      style={{ display: 'block', flexShrink: 0 }}
      aria-hidden="true"
    >
      {/* Outer Rounded Rectangle Frame */}
      <rect
        x="1.75"
        y="2.25"
        width="14.5"
        height="13.5"
        rx="2.5"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      {/* Left Sidebar Filled Area (matches user screenshot) */}
      <path
        d="M 1.75 4.75 C 1.75 3.37 2.87 2.25 4.25 2.25 L 6.5 2.25 L 6.5 15.75 L 4.25 15.75 C 2.87 15.75 1.75 14.63 1.75 13.25 Z"
        fill="currentColor"
        opacity={collapsed ? 0.35 : 1}
      />
      {/* Divider line between sidebar and main panel */}
      <line
        x1="6.5"
        y1="2.25"
        x2="6.5"
        y2="15.75"
        stroke="currentColor"
        strokeWidth="1.5"
      />
    </svg>
  )
}

export function AppShell() {
  const { user, logout } = useAuth()
  const { connected, on } = useSocket()
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem('foh_sidebar_collapsed') === 'true'
    } catch {
      return false
    }
  })

  const toggleSidebar = () => {
    setIsSidebarCollapsed((prev) => {
      const next = !prev
      try {
        localStorage.setItem('foh_sidebar_collapsed', String(next))
      } catch {}
      return next
    })
  }

  const pushToast = useCallback((message: string, ms = 5000, variant: 'default' | 'error' = 'default') => {
    const id = crypto.randomUUID()
    setToasts((prev) => [...prev, { id, message, variant }])
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), ms)
  }, [])

  const [activeWalkoutAlert, setActiveWalkoutAlert] = useState<AIEvent | null>(null)
  const [voiceModalOpen, setVoiceModalOpen] = useState(false)

  useEffect(() => {
    const onOpenWalkout = (e: Event) => {
      const alertDetail = (e as CustomEvent<AIEvent>).detail
      if (alertDetail) {
        playWalkoutAlarm()
        setActiveWalkoutAlert(alertDetail)
      }
    }
    const onOpenVoice = () => setVoiceModalOpen(true)
    window.addEventListener('foh:open-walkout-modal', onOpenWalkout)
    window.addEventListener('foh:open-voice-receptionist', onOpenVoice)
    return () => {
      window.removeEventListener('foh:open-walkout-modal', onOpenWalkout)
      window.removeEventListener('foh:open-voice-receptionist', onOpenVoice)
    }
  }, [])

  useEffect(() => {
    if (!user) return
    const unsubOrder = on('order_placed', (payload) => {
      const data = payload as { tableNumber?: string; itemCount?: number }
      if (user.role !== 'WAITER' && user.role !== 'HOST' && user.role !== 'CHEF') return
      const num = data.tableNumber ?? '?'
      const count = data.itemCount ?? 0
      pushToast(`New order at Table ${num} — ${count} items`, 6000)
    })

    const unsubWalkout = on('walkout_detected', (payload) => {
      const event = payload as AIEvent
      playWalkoutAlarm()
      setActiveWalkoutAlert(event)
      pushToast(
        `🚨 CRITICAL: Walkout detected at Table ${event.metadata?.table_number ?? '?'}. Total: $${event.metadata?.unpaid_total ?? 0}`,
        10000,
        'error',
      )
    })

    return () => {
      unsubOrder()
      unsubWalkout()
    }
  }, [on, user, pushToast])

  // Generate Navigation items dynamically based on user permissions
  const getNavItems = (): NavItem[] => {
    if (!user) return []
    const role = (user.role || '').toUpperCase()
    const perms = new Set((user as any).permissions ?? [])

    const hasP = (p: string) => role === 'OWNER' || perms.has(p)

    const dashboard = { to: '/dashboard', label: 'Dashboard', icon: '⚡' }
    const floor = { to: '/floor', label: 'Floor Plan', icon: '◫' }
    const sessions = { to: '/sessions', label: 'Sessions Stand', icon: '☰' }
    const billing = { to: '/billing', label: 'Billing', icon: '$' }
    const payments = { to: '/payments', label: 'Payments terminal', icon: '💳' }
    const shifts = { to: '/shifts', label: 'Cashier Shifts', icon: '📅' }
    const refunds = { to: '/refunds', label: 'Refunds / Approvals', icon: '🛡' }
    const revenue = { to: '/revenue', label: 'Revenue Report', icon: '📊' }
    const reservations = { to: '/reservations', label: 'Reservations Stand', icon: '📅' }
    const menu = { to: '/menu', label: 'Menu', icon: '🍽' }
    const camera = { to: '/camera-setup', label: 'Camera Setup', icon: '📷' }

    // Decoupled admin views
    const team = { to: '/users', label: 'Staff Accounts', icon: '👥' }
    const roles = { to: '/roles', label: 'Role Permissions', icon: '🔐' }
    const overrides = { to: '/overrides', label: 'Overrides & History', icon: '🛡' }
    const staffSessions = { to: '/staff-sessions', label: 'Active Sessions', icon: '💻' }
    const settings = { to: '/settings', label: 'Settings & Rules', icon: '⚙' }
    const audit    = { to: '/audit-logs', label: 'Audit Trail',         icon: '◎' }
    const insights = { to: '/insights',   label: 'Operational Insights', icon: '🧠' }

    const items: NavItem[] = []

    // Dashboard and Floor Plan are visible to all users in RBAC
    items.push(dashboard)
    items.push(floor)

    // Team Stand is visible if users.view is allowed
    if (hasP('users.view')) items.push(team)

    // Roles and Permissions Matrix (Owner only)
    if (role === 'OWNER') items.push(roles)

    // Temporary/Direct Overrides & History (Owner only)
    if (role === 'OWNER') items.push(overrides)

    // Active User Sessions (Owner only)
    if (role === 'OWNER') items.push(staffSessions)

    // Business settings (Owner only)
    if (role === 'OWNER') items.push(settings)

    // Sessions is visible if booking.view is allowed
    if (hasP('booking.view')) items.push(sessions)

    // Billing is visible if billing.view is allowed
    if (hasP('billing.view')) items.push(billing)

    // Payments is visible if payment.view is allowed
    if (hasP('payment.view')) items.push(payments)

    // Shifts is visible if cashier.shift.view is allowed
    if (hasP('cashier.shift.view')) items.push(shifts)

    // Refunds is visible if payment.refund or payment.approve is allowed
    if (hasP('payment.refund') || hasP('payment.approve') || hasP('payment.refund.request') || hasP('payment.refund.approve') || hasP('discount.approve')) items.push(refunds)

    // Revenue is visible if revenue.view_own or revenue.view_branch or revenue.view_all is allowed
    if (hasP('revenue.view_own') || hasP('revenue.view_branch') || hasP('revenue.view_all')) items.push(revenue)

    // Reservations is visible if booking.view or reservations.manage is allowed
    if (hasP('booking.view') || hasP('reservations.manage')) items.push(reservations)

    // Menu is visible if menu.manage is allowed
    if (hasP('menu.manage')) items.push(menu)

    // Kitchen Display System - Live Station Queue
    const kitchen = { to: '/kitchen', label: 'Kitchen Display', icon: '👨‍🍳' }
    if (hasP('kitchen.view') || hasP('kds.view')) items.push(kitchen)

    // High-Density KDS Board
    const kds = { to: '/kds', label: 'KDS Board', icon: '⚡' }
    if (hasP('kitchen.view') || hasP('kds.view')) items.push(kds)

    // AI Customer Booking & Waitlist Stand (Member 4)
    const booking = { to: '/booking', label: 'AI Booking Stand', icon: '🤖' }
    if (hasP('booking.view') || role === 'OWNER' || role === 'MANAGER') items.push(booking)

    // Camera setup is visible to tables.manage
    if (hasP('tables.manage')) items.push(camera)

    // Audit logs is visible if audit.view is allowed
    if (hasP('audit.view')) items.push(audit)

    // Operational Insights — Owner and Manager
    if (role === 'OWNER' || role === 'MANAGER') items.push(insights)

    return items
  }

  const navItems = getNavItems()

  return (
    <div className={`app-shell ${isSidebarCollapsed ? 'app-shell--collapsed' : ''}`}>
      <ToastStack toasts={toasts} />
      <aside className={`app-sidebar ${isSidebarCollapsed ? 'app-sidebar--collapsed' : ''}`}>
        <div className="sidebar-brand">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', minWidth: 0, flex: 1 }}>
            <span className="brand-mark" title="Front of House">FOH</span>
            {!isSidebarCollapsed && (
              <div className="brand-text">
                <strong>FOH Admin</strong>
                <span className="brand-sub">Table management</span>
              </div>
            )}
          </div>
          <button
            type="button"
            className="sidebar-collapse-btn"
            onClick={toggleSidebar}
            title={isSidebarCollapsed ? 'Expand Sidebar' : 'Minimize Sidebar'}
            aria-label={isSidebarCollapsed ? 'Expand Sidebar' : 'Minimize Sidebar'}
          >
            <SidebarToggleIcon collapsed={isSidebarCollapsed} />
          </button>
        </div>

        <nav className="app-nav" aria-label="Main">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''} ${isSidebarCollapsed ? 'nav-item--collapsed' : ''}`}
              title={isSidebarCollapsed ? item.label : undefined}
            >
              <span className="nav-item__icon" aria-hidden>
                {item.icon}
              </span>
              {!isSidebarCollapsed && <span className="nav-item__label">{item.label}</span>}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <span
            className={`socket-indicator ${connected ? 'socket-indicator--live' : ''}`}
            title={connected ? 'Live Sync Active' : 'Offline'}
          >
            <span className="socket-indicator__dot" />
            {!isSidebarCollapsed && (connected ? 'Live sync' : 'Offline')}
          </span>
        </div>
      </aside>

      <div className="app-content">
        <nav className="mobile-nav" aria-label="Mobile">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => (isActive ? 'active' : '')}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <header className="app-topbar">
          <div className="topbar-title" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <button
              type="button"
              className="topbar-sidebar-toggle"
              onClick={toggleSidebar}
              title={isSidebarCollapsed ? 'Expand Sidebar' : 'Minimize Sidebar'}
            >
              <SidebarToggleIcon collapsed={isSidebarCollapsed} />
            </button>
            <div>
              <h1>Front-of-House stand</h1>
              <p className="muted">Welcome to tonight's dinner service</p>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <GlobalSearch />
            <button
              type="button"
              onClick={() => setVoiceModalOpen(true)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                background: '#042f2e',
                color: '#2dd4bf',
                border: '1px solid #0f766e',
                borderRadius: 8,
                padding: '5px 11px',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
                boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
              }}
              title="Open AI Voice Receptionist Simulator"
            >
              <span style={{ fontSize: 13 }}>📞</span>
              <span>Voice Receptionist</span>
            </button>
            <div className="topbar-user" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <ConnectionStatus />
              <span className={`role-badge role-${user?.role.toLowerCase()}`}>{user?.role}</span>
              <span className="user-name">{user?.name}</span>
              <button type="button" className="btn btn-ghost btn-sm" onClick={logout}>Sign out</button>
            </div>
          </div>
        </header>
        <main className="app-main">
          <Outlet />
        </main>
      </div>

      {activeWalkoutAlert && (
        <WalkoutEmergencyModal
          alert={activeWalkoutAlert}
          onClose={() => setActiveWalkoutAlert(null)}
          onResolved={() => {
            setActiveWalkoutAlert(null)
            pushToast('Loss prevention incident resolved.', 4000)
          }}
        />
      )}
      <VoiceReceptionistModal
        isOpen={voiceModalOpen}
        onClose={() => setVoiceModalOpen(false)}
      />
      <AIChatWidget />
    </div>
  )
}
