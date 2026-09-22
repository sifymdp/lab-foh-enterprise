import { useEffect, useState } from 'react'
import { api } from '../api/client'

/* ─── Permission catalogue grouped by category ───────────────────────── */
interface PermInfo {
  code: string
  label: string
  description: string
  isCustom?: boolean
}

interface PermCategory {
  id: string
  label: string
  icon: string
  description: string
  perms: PermInfo[]
  isCustom?: boolean
}

const DEFAULT_CATEGORIES: PermCategory[] = [
  {
    id: 'staff',
    label: 'Staff & Team',
    icon: '👥',
    description: 'Staff member accounts, profiles, and organization access levels',
    perms: [
      { code: 'users.view', label: 'View Staff Accounts', description: 'See all staff accounts, active status, and shift roles' },
      { code: 'users.create', label: 'Add New Staff', description: 'Create user credentials and assign default roles' },
      { code: 'users.update', label: 'Edit Staff Profile', description: 'Update details, roles, and branch assignments' },
      { code: 'users.deactivate', label: 'Suspend / Deactivate', description: 'Suspend or deactivate accounts and freeze access' },
      { code: 'roles.view', label: 'View Roles List', description: 'Inspect defined organization roles and permissions' },
      { code: 'roles.create', label: 'Create Custom Roles', description: 'Add new custom role profiles' },
      { code: 'roles.update', label: 'Edit Role Permissions', description: 'Modify allocated permissions for custom roles' },
      { code: 'permissions.manage', label: 'Manage Access Rules', description: 'Direct overrides, temporary access, and security policies' },
    ],
  },
  {
    id: 'floor',
    label: 'Floor & Tables',
    icon: '◫',
    description: 'Dining room layout, section boundaries, and table assignments',
    perms: [
      { code: 'tables.view', label: 'View Floor Plan', description: 'See live visual floor canvas and table statuses' },
      { code: 'tables.manage', label: 'Manage Tables', description: 'Update table states, mark dirty, or release tables' },
      { code: 'tables.assign', label: 'Assign Waitstaff', description: 'Assign servers to sections and individual tables' },
      { code: 'floor.edit', label: 'Edit Floor Layout', description: 'Add, move, resize tables and sections on canvas' },
    ],
  },
  {
    id: 'cctv',
    label: 'CCTV & AI Vision',
    icon: '🎥',
    description: 'YOLO11 camera feeds, table seating zones, and occupancy mismatch alerts',
    perms: [
      { code: 'camera.view', label: 'View Camera Feeds', description: 'Access live CCTV feeds and AI bounding box overlays' },
      { code: 'camera.analytics.view', label: 'View Vision Analytics', description: 'See occupancy rates, FPS, and bottleneck metrics' },
      { code: 'camera.configuration', label: 'Configure Cameras & ROI', description: 'Add RTSP streams, webcam feeds, and draw table ROIs' },
      { code: 'camera.calibration', label: 'Calibrate Cameras', description: 'Calibrate camera perspective to floor coordinates' },
      { code: 'camera.override', label: 'Verify CCTV Mismatches', description: 'Confirm or dismiss physical vs digital discrepancy alerts' },
    ],
  },
  {
    id: 'bookings',
    label: 'Bookings & Waitlist',
    icon: '📅',
    description: 'Reservations book, party management, and walk-in waitlist queue',
    perms: [
      { code: 'booking.view', label: 'View Reservations', description: 'See the reservation timeline and guest book' },
      { code: 'booking.create', label: 'Take Reservations', description: 'Book tables in advance for guest parties' },
      { code: 'booking.update', label: 'Modify Reservations', description: 'Change party sizes, times, and special requests' },
      { code: 'booking.cancel', label: 'Cancel Bookings', description: 'Cancel bookings and mark guest no-shows' },
      { code: 'reservations.manage', label: 'Manage Waitlist', description: 'Add walk-ins to the queue and send SMS alerts' },
    ],
  },
  {
    id: 'orders',
    label: 'Orders & POS',
    icon: '🍽',
    description: 'Food ordering, table checks, item modifications, and firing to kitchen',
    perms: [
      { code: 'orders.view', label: 'View Orders', description: 'Inspect active orders across all tables' },
      { code: 'orders.create', label: 'Punch Food Orders', description: 'Take orders at table or counter and create KOT' },
      { code: 'orders.update', label: 'Edit Order Items', description: 'Add dishes, change quantities, and add cooking notes' },
      { code: 'orders.confirm', label: 'Fire to Kitchen', description: 'Dispatch tickets directly to kitchen stations' },
      { code: 'orders.serve', label: 'Mark as Served', description: 'Update delivery status when dishes reach guests' },
    ],
  },
  {
    id: 'kitchen',
    label: 'Kitchen (KDS)',
    icon: '👨‍🍳',
    description: 'Kitchen station queues, prep timers, item 86ing, and cook workflows',
    perms: [
      { code: 'kitchen.view', label: 'View Kitchen Queue', description: 'See the live ticket display and prep times' },
      { code: 'kitchen.update', label: 'Update Cooking State', description: 'Mark tickets as in-progress or ready to plate' },
      { code: 'kitchen.manage', label: 'Manage Station Queue', description: 'Re-prioritize tickets and mark ingredients 86' },
      { code: 'kds.view', label: 'View KDS Screen', description: 'Access the kitchen display system live screen' },
      { code: 'kds.bump', label: 'Bump Completed Orders', description: 'Clear finished tickets from the KDS display' },
      { code: 'kds.recall', label: 'Recall Bumped Orders', description: 'Bring back bumped tickets to the active queue' },
      { code: 'kds.priority', label: 'Change Ticket Priority', description: 'Escalate or de-prioritize kitchen ticket order' },
      { code: 'menu.manage', label: 'Manage Menu Items', description: 'Add dishes, set pricing, categories, and ingredients' },
    ],
  },
  {
    id: 'billing',
    label: 'Billing & Discounts',
    icon: '💵',
    description: 'Check generation, itemized invoices, split checks, and discount limits',
    perms: [
      { code: 'billing.view', label: 'View Invoices & Bills', description: 'Inspect open checks and tax itemizations' },
      { code: 'billing.create', label: 'Generate Bills', description: 'Print checks and request guest checkout' },
      { code: 'billing.update', label: 'Modify Bill Items', description: 'Split checks and adjust line items' },
      { code: 'billing.cancel', label: 'Void / Cancel Bills', description: 'Void entire check (requires manager approval)' },
      { code: 'discount.apply', label: 'Apply Discounts', description: 'Apply percentage or promotional discounts' },
      { code: 'discount.approve', label: 'Approve Discount Override', description: 'Approve discounts exceeding staff threshold' },
    ],
  },
  {
    id: 'payments',
    label: 'Payments & Shifts',
    icon: '💳',
    description: 'Payment settlements, cash drawer floats, refunds, and cashier shifts',
    perms: [
      { code: 'payment.view', label: 'View Payment Records', description: 'See transaction logs, card, cash, and UPI entries' },
      { code: 'payment.create', label: 'Collect Payments', description: 'Settle bills via card, cash, UPI, or online' },
      { code: 'payment.refund', label: 'Request Refunds', description: 'Initiate customer refund transactions' },
      { code: 'payment.approve', label: 'Approve Refunds', description: 'Authorise high-value refund requests' },
      { code: 'cashier.shift.start', label: 'Open Cashier Shift', description: 'Declare opening drawer float and start shift' },
      { code: 'cashier.shift.end', label: 'Close Cashier Shift', description: 'Reconcile drawer cash and finalize shift totals' },
      { code: 'cashier.shift.view', label: 'View Shift Summaries', description: 'Review current and historical cashier shift reports' },
    ],
  },
  {
    id: 'reports',
    label: 'Reports & Revenue',
    icon: '📊',
    description: 'Daily revenue analytics, branch sales summaries, and compliance audit trail',
    perms: [
      { code: 'revenue.view_own', label: 'View Own Shift Revenue', description: 'See personal cashier sales total' },
      { code: 'revenue.view_branch', label: 'View Branch Revenue', description: 'Access branch daily sales and category reports' },
      { code: 'revenue.view_all', label: 'Org-Wide Analytics', description: 'Organization revenue dashboard across all branches' },
      { code: 'reports.view', label: 'View Reports', description: 'Access analytical reports and sales graphs' },
      { code: 'reports.export', label: 'Export CSV / PDF', description: 'Download business financial and order exports' },
      { code: 'audit.view', label: 'View Audit Logs', description: 'Inspect user action history and security audit trail' },
    ],
  },
  {
    id: 'settings',
    label: 'Settings & Rules',
    icon: '⚙️',
    description: 'System configurations, billing rules, festival discounts, and hardware printers',
    perms: [
      { code: 'settings.view', label: 'View Settings', description: 'See active billing, payment, and rule configs' },
      { code: 'settings.edit', label: 'Edit System Settings', description: 'Update discount limits, taxes, and service charges' },
      { code: 'settings.printers', label: 'Manage Hardware & Printers', description: 'Configure thermal receipt and kitchen printer IP routes' },
    ],
  },
]

const STANDARD_ROLES = ['OWNER', 'MANAGER', 'HOST', 'CASHIER', 'WAITER', 'CHEF']

const ROLE_META: Record<string, { color: string; icon: string }> = {
  OWNER: { color: '#8b5cf6', icon: '👑' },
  MANAGER: { color: '#3b82f6', icon: '🏢' },
  HOST: { color: '#10b981', icon: '🤝' },
  CASHIER: { color: '#f59e0b', icon: '💰' },
  WAITER: { color: '#06b6d4', icon: '🍽' },
  CHEF: { color: '#ef4444', icon: '👨‍🍳' },
}

const STORAGE_CUSTOM_CATEGORIES_KEY = 'foh_custom_permission_categories_v9'

export function RolesPage() {
  const [matrixData, setMatrixData] = useState<any>({ permissions: [], roles: [], matrix: [] })
  const [selectedRole, setSelectedRole] = useState<string>('MANAGER')
  const [categories, setCategories] = useState<PermCategory[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_CUSTOM_CATEGORIES_KEY)
      if (saved) {
        const parsed = JSON.parse(saved)
        if (Array.isArray(parsed) && parsed.length > 0) return parsed
      }
    } catch { }
    return DEFAULT_CATEGORIES
  })

  // Navigation View: 'MENU' (shows categories with ON/OFF switch) OR specific category ID (shows detailed permissions)
  const [activeView, setActiveView] = useState<'MENU' | string>('MENU')
  const [loading, setLoading] = useState(false)
  const [flash, setFlash] = useState<{ msg: string; ok: boolean } | null>(null)

  // Modal dialog states: Role
  const [showRoleForm, setShowRoleForm] = useState(false)
  const [newRoleName, setNewRoleName] = useState('')

  // Modal dialog states: Category
  const [showCategoryForm, setShowCategoryForm] = useState(false)
  const [newCatLabel, setNewCatLabel] = useState('')
  const [newCatIcon, setNewCatIcon] = useState('🏷️')
  const [newCatDesc, setNewCatDesc] = useState('')

  // Modal dialog states: Permission
  const [showPermForm, setShowPermForm] = useState(false)
  const [targetCatIdForPerm, setTargetCatIdForPerm] = useState<string>('')
  const [newPermLabel, setNewPermLabel] = useState('')
  const [newPermCode, setNewPermCode] = useState('')
  const [newPermDesc, setNewPermDesc] = useState('')

  // Delete mode: select permissions to delete
  const [deleteMode, setDeleteMode] = useState(false)
  const [selectedPermsToDelete, setSelectedPermsToDelete] = useState<Set<string>>(new Set())

  // Delete mode for categories
  const [catDeleteMode, setCatDeleteMode] = useState(false)
  const [selectedCatsToDelete, setSelectedCatsToDelete] = useState<Set<string>>(new Set())

  useEffect(() => {
    loadMatrix()
  }, [])

  // Persist custom categories
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_CUSTOM_CATEGORIES_KEY, JSON.stringify(categories))
    } catch { }
  }, [categories])

  const showFlash = (msg: string, ok = true) => {
    setFlash({ msg, ok })
    setTimeout(() => setFlash(null), 3000)
  }

  const loadMatrix = async () => {
    setLoading(true)
    try {
      const data = await api.getPermissionsMatrix()
      setMatrixData(data)
    } catch {
      showFlash('Could not load permission matrix', false)
    } finally {
      setLoading(false)
    }
  }

  const isEnabled = (code: string) => {
    if (selectedRole.toUpperCase() === 'OWNER') return true
    if (!matrixData || !matrixData.matrix) return false
    const row = matrixData.matrix.find((r: any) => r.permission === code)
    if (!row || !row.roles) return false
    const matchKey = Object.keys(row.roles).find((k) => k.toUpperCase() === selectedRole.toUpperCase())
    return matchKey ? !!row.roles[matchKey] : false
  }

  const handleToggle = async (code: string) => {
    if (selectedRole.toUpperCase() === 'OWNER') return
    const current = isEnabled(code)
    const nextState = !current

    // Optimistic instant update
    setMatrixData((prev: any) => {
      if (!prev || !prev.matrix) return prev
      let found = false
      const updatedMatrix = prev.matrix.map((row: any) => {
        if (row.permission === code) {
          found = true
          return {
            ...row,
            roles: {
              ...row.roles,
              [selectedRole]: nextState,
              [selectedRole.toUpperCase()]: nextState,
            },
          }
        }
        return row
      })
      if (!found) {
        updatedMatrix.push({
          permission: code,
          roles: {
            [selectedRole]: nextState,
            [selectedRole.toUpperCase()]: nextState,
          },
        })
      }
      return { ...prev, matrix: updatedMatrix }
    })

    try {
      await api.toggleMatrixPermission({ role_name: selectedRole, permission: code, enabled: nextState })
      showFlash(nextState ? `ON: ${code}` : `OFF: ${code}`)
    } catch {
      showFlash('Update failed', false)
      await loadMatrix()
    }
  }

  // Bulk Turn ON / OFF all permissions in a category
  const handleToggleCategory = async (cat: PermCategory, turnOn: boolean) => {
    if (selectedRole.toUpperCase() === 'OWNER') return
    const permsToUpdate = cat.perms.filter(p => isEnabled(p.code) !== turnOn)
    if (permsToUpdate.length === 0) return

    // Optimistic update
    setMatrixData((prev: any) => {
      if (!prev || !prev.matrix) return prev
      const updatedMatrix = [...prev.matrix]
      permsToUpdate.forEach(p => {
        const idx = updatedMatrix.findIndex(r => r.permission === p.code)
        if (idx >= 0) {
          updatedMatrix[idx] = {
            ...updatedMatrix[idx],
            roles: {
              ...updatedMatrix[idx].roles,
              [selectedRole]: turnOn,
              [selectedRole.toUpperCase()]: turnOn,
            }
          }
        } else {
          updatedMatrix.push({
            permission: p.code,
            roles: {
              [selectedRole]: turnOn,
              [selectedRole.toUpperCase()]: turnOn,
            }
          })
        }
      })
      return { ...prev, matrix: updatedMatrix }
    })

    try {
      await Promise.all(
        permsToUpdate.map(p =>
          api.toggleMatrixPermission({ role_name: selectedRole, permission: p.code, enabled: turnOn })
        )
      )
      showFlash(`${turnOn ? 'Turned ON' : 'Turned OFF'} ${cat.label} module`)
    } catch {
      showFlash('Category update failed', false)
      await loadMatrix()
    }
  }

  // Create Role
  const handleCreateRole = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await api.createCustomRole({ name: newRoleName, permissions: [] })
      showFlash(`Role "${newRoleName}" created successfully`)
      setShowRoleForm(false)
      setNewRoleName('')
      await loadMatrix()
      setSelectedRole(newRoleName)
    } catch {
      showFlash('Create role failed', false)
    }
  }

  // Delete Role
  const handleDeleteRole = async (roleName: string) => {
    if (STANDARD_ROLES.includes(roleName.toUpperCase())) {
      alert(`Standard system role "${roleName}" cannot be deleted.`)
      return
    }
    if (!confirm(`Are you sure you want to delete the role "${roleName}"? All its assigned permissions will be removed.`)) {
      return
    }

    try {
      await api.deleteCustomRole(roleName)
      showFlash(`Role "${roleName}" deleted successfully`)
      setSelectedRole('MANAGER')
      await loadMatrix()
    } catch {
      showFlash(`Failed to delete role "${roleName}"`, false)
    }
  }

  // Create Category
  const handleCreateCategory = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmedLabel = newCatLabel.trim()
    if (!trimmedLabel) return
    const id = trimmedLabel.toLowerCase().replace(/[^a-z0-9]/g, '_')

    const newCategory: PermCategory = {
      id,
      label: trimmedLabel,
      icon: newCatIcon || '🏷️',
      description: newCatDesc.trim() || `Custom permission category for ${trimmedLabel}`,
      isCustom: true,
      perms: [
        {
          code: `${id}.view`,
          label: `View ${trimmedLabel}`,
          description: `Access and view ${trimmedLabel} operational screen`,
          isCustom: true,
        },
        {
          code: `${id}.manage`,
          label: `Manage ${trimmedLabel}`,
          description: `Full modify and control access to ${trimmedLabel}`,
          isCustom: true,
        },
      ],
    }

    setCategories((prev) => [...prev, newCategory])
    setActiveView(id)
    setShowCategoryForm(false)
    setNewCatLabel('')
    setNewCatDesc('')
    showFlash(`Category "${trimmedLabel}" created!`)
  }

  // Add Permission to Category
  const handleAddPermission = (e: React.FormEvent) => {
    e.preventDefault()
    const label = newPermLabel.trim()
    if (!label || !targetCatIdForPerm) return

    const catObj = categories.find(c => c.id === targetCatIdForPerm)
    const code = newPermCode.trim()
      ? newPermCode.trim().toLowerCase().replace(/\s+/g, '.')
      : `${targetCatIdForPerm}.${label.toLowerCase().replace(/[^a-z0-9]/g, '_')}`

    const newPerm: PermInfo = {
      code,
      label,
      description: newPermDesc.trim() || `Access and manage ${label}`,
      isCustom: true,
    }

    setCategories((prev) =>
      prev.map((cat) => {
        if (cat.id === targetCatIdForPerm) {
          if (cat.perms.some((p) => p.code === code)) return cat
          return { ...cat, perms: [...cat.perms, newPerm] }
        }
        return cat
      })
    )

    setShowPermForm(false)
    setNewPermLabel('')
    setNewPermCode('')
    setNewPermDesc('')
    showFlash(`Permission "${label}" added to ${catObj?.label || 'category'}!`)
  }

  const roles: string[] = matrixData.roles?.length ? matrixData.roles : Object.keys(ROLE_META)
  const isOwner = selectedRole.toUpperCase() === 'OWNER'
  const isCurrentRoleCustom = !STANDARD_ROLES.includes(selectedRole.toUpperCase())

  const isCategoryOn = (cat: PermCategory) => {
    if (isOwner) return true
    return cat.perms.some(p => isEnabled(p.code))
  }

  const categoryEnabledCount = (cat: PermCategory) => cat.perms.filter((p) => isEnabled(p.code)).length
  const selectedCategoryObj = categories.find(c => c.id === activeView)

  // Categories currently turned ON for the active role
  const activeOnCategories = categories.filter(c => isCategoryOn(c))

  return (
    <div style={{ padding: '1.75rem', maxWidth: '1280px', margin: '0 auto' }}>

      {/* ── Page Title ── */}
      <h2 style={{ margin: '0 0 1.25rem', fontSize: '1.35rem', fontWeight: 700 }}>Role Permissions</h2>

      {/* ── Flash Notification ── */}
      {flash && (
        <div style={{
          padding: '0.75rem 1rem', borderRadius: '8px', marginBottom: '1.25rem',
          background: flash.ok ? 'rgba(22, 163, 74, 0.1)' : 'rgba(220, 38, 38, 0.1)',
          border: `1px solid ${flash.ok ? '#86efac' : '#fca5a5'}`,
          color: flash.ok ? '#16a34a' : '#dc2626',
          fontSize: '0.875rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem',
        }}>
          <span>{flash.ok ? '✓' : '✕'}</span>
          <span>{flash.msg}</span>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════
          2-COLUMN LAYOUT: VERTICAL ROLES SIDEBAR (LEFT) + PERMISSION CATEGORIES (RIGHT)
      ══════════════════════════════════════════════════════════ */}
      <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'flex-start' }}>

        {/* ── Left Sidebar: Vertical Roles List ── */}
        <div style={{
          width: '260px',
          minWidth: '240px',
          background: 'var(--bg-elevated)',
          borderRadius: '12px',
          border: '1px solid var(--border)',
          boxShadow: 'var(--shadow-sm)',
          padding: '1rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.5rem',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem', paddingBottom: '0.6rem', borderBottom: '1px solid var(--border)' }}>
            <span style={{
              fontSize: '0.8rem', fontWeight: 700,
              textTransform: 'uppercase', letterSpacing: '0.06em',
              color: 'var(--text-muted)',
            }}>
              ROLE ({roles.length})
            </span>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => setShowRoleForm(true)}
              style={{ fontSize: '0.8rem', color: '#2563eb', padding: '0.2rem 0.45rem', fontWeight: 600 }}
            >
              + Add
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            {roles.map((r) => {
              const isSelected = selectedRole.toUpperCase() === r.toUpperCase()
              const isCustom = !STANDARD_ROLES.includes(r.toUpperCase())
              const rMeta = ROLE_META[r.toUpperCase()] ?? { color: '#6b7280', icon: isCustom ? '⭐' : '👤' }

              return (
                <button
                  key={r}
                  onClick={() => setSelectedRole(r)}
                  style={{
                    width: '100%',
                    padding: '0.75rem 1rem',
                    borderRadius: '8px',
                    border: isSelected ? '2px solid #3b82f6' : '1px solid transparent',
                    background: isSelected ? '#eff6ff' : 'var(--surface-2)',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    textAlign: 'left',
                    boxShadow: isSelected ? '0 0 0 1px #3b82f6' : 'none',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                    <span style={{ fontSize: '1.15rem' }}>{rMeta.icon}</span>
                    <span style={{
                      fontWeight: isSelected ? 700 : 600,
                      fontSize: '0.875rem',
                      color: isSelected ? '#1d4ed8' : 'var(--text)',
                    }}>
                      {r}
                    </span>
                  </div>

                  {isCustom && (
                    <span style={{
                      fontSize: '0.7rem',
                      padding: '0.1rem 0.35rem',
                      borderRadius: '4px',
                      background: 'rgba(245, 158, 11, 0.15)',
                      color: '#b45309',
                      fontWeight: 700,
                    }}>
                      CUSTOM
                    </span>
                  )}
                </button>
              )
            })}
          </div>

          {/* Delete Role Button at bottom of sidebar if custom role is selected */}
          {isCurrentRoleCustom && (
            <div style={{ marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border)' }}>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => handleDeleteRole(selectedRole)}
                style={{
                  width: '100%',
                  color: 'var(--danger)',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.35rem',
                }}
              >
                <span>🗑️</span>
                <span>Delete Role ({selectedRole})</span>
              </button>
            </div>
          )}
        </div>

        {/* ── Right Main Panel: Category Menu & Permissions ── */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '1rem' }}>

          {/* Top Bar: Category Menu & Active Category Chips */}
          <div style={{
            padding: '0.85rem 1.15rem',
            background: 'var(--bg-elevated)',
            borderRadius: '12px',
            border: '1px solid var(--border)',
            boxShadow: 'var(--shadow-sm)',
            display: 'flex',
            alignItems: 'center',
            gap: '0.85rem',
            flexWrap: 'wrap',
          }}>
            {/* Main "Category Menu" button */}
            <button
              type="button"
              onClick={() => setActiveView('MENU')}
              style={{
                padding: '0.55rem 1.15rem',
                borderRadius: '8px',
                border: activeView === 'MENU' ? '2px solid #3b82f6' : '1px solid var(--border)',
                background: activeView === 'MENU' ? '#3b82f6' : 'var(--surface-2)',
                color: activeView === 'MENU' ? '#ffffff' : 'var(--text)',
                fontWeight: 700,
                fontSize: '0.875rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                boxShadow: activeView === 'MENU' ? '0 2px 8px rgba(59, 130, 246, 0.3)' : 'none',
                transition: 'all 0.15s ease',
              }}
            >
              <span>📂</span>
              <span>Category Menu</span>
            </button>

            {/* Separator */}
            <span style={{ color: 'var(--border)', fontSize: '1.2rem' }}>|</span>

            {/* Display all ON Permission Categories dynamically next to Category Menu */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', flex: 1 }}>
              {activeOnCategories.map((cat) => {
                const isCurrentActive = activeView === cat.id
                const enCount = categoryEnabledCount(cat)
                const totCount = cat.perms.length

                return (
                  <button
                    key={cat.id}
                    type="button"
                    onClick={() => setActiveView(cat.id)}
                    style={{
                      padding: '0.45rem 0.85rem',
                      borderRadius: '20px',
                      border: isCurrentActive ? '2px solid #3b82f6' : '1px solid rgba(59, 130, 246, 0.3)',
                      background: isCurrentActive ? '#eff6ff' : 'rgba(59, 130, 246, 0.06)',
                      color: isCurrentActive ? '#1d4ed8' : 'var(--text)',
                      fontWeight: isCurrentActive ? 700 : 500,
                      fontSize: '0.875rem',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.4rem',
                      boxShadow: isCurrentActive ? '0 0 0 1px #3b82f6' : 'none',
                      transition: 'all 0.15s ease',
                    }}
                    title={`Click to configure individual permissions for ${cat.label}`}
                  >
                    <span>{cat.icon}</span>
                    <span>{cat.label}</span>
                    <span style={{
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      padding: '0.08rem 0.35rem',
                      borderRadius: '99px',
                      background: '#dcfce7',
                      color: '#16a34a',
                    }}>
                      {isOwner ? 'ALL' : `${enCount}/${totCount}`}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>

          {/* MAIN DOWN VIEW 1: CATEGORY MENU (ONLY ON/OFF TOGGLES + DELETE) */}
          {activeView === 'MENU' && (
            <div style={{
              background: 'var(--bg-elevated)',
              borderRadius: '12px',
              border: '1px solid var(--border)',
              boxShadow: 'var(--shadow-sm)',
              overflow: 'hidden',
            }}>
              {/* Header */}
              <div style={{
                padding: '1.25rem 1.5rem',
                background: 'var(--surface-2)',
                borderBottom: '1px solid var(--border)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: '1rem',
              }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700 }}>
                    📂 Permission Categories <span style={{ color: '#2563eb' }}>for {selectedRole}</span>
                  </h3>
                  <p className="muted" style={{ margin: '0.2rem 0 0', fontSize: '0.8rem' }}>
                    Select a category to view or toggle its permissions.
                  </p>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                  {!catDeleteMode && (
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => setShowCategoryForm(true)}
                      style={{ fontSize: '0.8rem', fontWeight: 600 }}
                    >
                      + Category
                    </button>
                  )}
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => {
                      setCatDeleteMode(!catDeleteMode)
                      setSelectedCatsToDelete(new Set())
                    }}
                    style={{
                      color: catDeleteMode ? 'var(--danger)' : 'var(--text-muted)',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      background: catDeleteMode ? 'rgba(220, 38, 38, 0.08)' : 'transparent',
                      border: catDeleteMode ? '1px solid rgba(220, 38, 38, 0.2)' : 'none',
                      borderRadius: '6px',
                    }}
                    title={catDeleteMode ? 'Exit delete mode' : 'Select categories to delete'}
                  >
                    {catDeleteMode ? '✕ Cancel' : '🗑️ Delete'}
                  </button>
                  {!catDeleteMode && (
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600 }}>
                      {categories.length} Categories
                    </span>
                  )}
                </div>
              </div>

              {/* Category Rows */}
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                {categories.map((cat, idx) => {
                  const onState = isCategoryOn(cat)
                  const enCount = categoryEnabledCount(cat)
                  const totCount = cat.perms.length
                  const isLast = idx === categories.length - 1
                  const isCatSelected = selectedCatsToDelete.has(cat.id)

                  return (
                    <div
                      key={cat.id}
                      onClick={catDeleteMode ? () => {
                        setSelectedCatsToDelete(prev => {
                          const next = new Set(prev)
                          if (next.has(cat.id)) next.delete(cat.id)
                          else next.add(cat.id)
                          return next
                        })
                      } : undefined}
                      style={{
                        padding: '1.25rem 1.5rem',
                        borderBottom: isLast ? 'none' : '1px solid var(--border)',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: '1.5rem',
                        transition: 'background 0.15s ease',
                        cursor: catDeleteMode ? 'pointer' : 'default',
                        background: isCatSelected ? 'rgba(220, 38, 38, 0.05)' : 'transparent',
                      }}
                    >
                      {/* Left: Checkbox (delete mode) + Category Icon, Title, and Description */}
                      <div
                        onClick={!catDeleteMode ? () => {
                          if (onState) setActiveView(cat.id)
                        } : undefined}
                        style={{
                          flex: 1,
                          display: 'flex',
                          alignItems: 'center',
                          gap: '1rem',
                          cursor: catDeleteMode ? 'pointer' : (onState ? 'pointer' : 'default'),
                        }}
                      >
                        {catDeleteMode && (
                          <div style={{
                            width: '20px', height: '20px', borderRadius: '4px', flexShrink: 0,
                            border: isCatSelected ? '2px solid var(--danger)' : '2px solid var(--border-strong)',
                            background: isCatSelected ? 'var(--danger)' : 'transparent',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            transition: 'all 0.15s ease',
                          }}>
                            {isCatSelected && (
                              <span style={{ color: '#fff', fontSize: '0.7rem', fontWeight: 700 }}>✓</span>
                            )}
                          </div>
                        )}
                        <span style={{
                          fontSize: '1.5rem',
                          padding: '0.5rem',
                          background: onState ? 'rgba(59, 130, 246, 0.1)' : 'var(--surface-2)',
                          borderRadius: '10px',
                        }}>
                          {cat.icon}
                        </span>
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.25rem' }}>
                            <strong style={{ fontSize: '0.95rem', color: onState ? '#1d4ed8' : 'var(--text)' }}>
                              {cat.label}
                            </strong>
                            {onState && (
                              <span style={{
                                fontSize: '0.75rem',
                                fontWeight: 700,
                                padding: '0.1rem 0.45rem',
                                borderRadius: '99px',
                                background: '#dcfce7',
                                color: '#16a34a',
                              }}>
                                {isOwner ? 'ALL' : `${enCount}/${totCount} active`}
                              </span>
                            )}
                          </div>
                          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                            {cat.description}
                          </div>
                        </div>
                      </div>

                      {/* Right: ON / OFF Switch (hidden in delete mode) */}
                      {!catDeleteMode && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.9rem' }}>
                          <button
                            type="button"
                            disabled={isOwner}
                            onClick={() => handleToggleCategory(cat, !onState)}
                            style={{
                              width: '52px',
                              height: '28px',
                              borderRadius: '99px',
                              background: onState ? '#3b82f6' : '#cbd5e1',
                              border: 'none',
                              cursor: isOwner ? 'default' : 'pointer',
                              position: 'relative',
                              transition: 'background-color 0.2s ease',
                              padding: '2px',
                              outline: 'none',
                            }}
                            title={isOwner ? 'Owner has all permissions' : onState ? 'Click to turn OFF category' : 'Click to turn ON category'}
                          >
                            <span
                              style={{
                                display: 'block',
                                width: '24px',
                                height: '24px',
                                borderRadius: '50%',
                                background: '#ffffff',
                                boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
                                transform: onState ? 'translateX(24px)' : 'translateX(0px)',
                                transition: 'transform 0.2s ease',
                              }}
                            />
                          </button>

                          <span style={{
                            minWidth: '45px',
                            fontWeight: 700,
                            fontSize: '0.875rem',
                            color: onState ? '#16a34a' : 'var(--text-muted)',
                          }}>
                            {onState ? 'ON' : 'OFF'}
                          </span>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>

              {/* Delete Mode: Action Bar */}
              {catDeleteMode && selectedCatsToDelete.size > 0 && (
                <div style={{
                  padding: '0.75rem 1.5rem',
                  background: 'rgba(220, 38, 38, 0.06)',
                  borderTop: '1px solid rgba(220, 38, 38, 0.15)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--danger)' }}>
                    {selectedCatsToDelete.size} categor{selectedCatsToDelete.size > 1 ? 'ies' : 'y'} selected
                  </span>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => setSelectedCatsToDelete(new Set(categories.map(c => c.id)))}
                      style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)' }}
                    >
                      Select All
                    </button>
                    <button
                      type="button"
                      className="btn btn-sm"
                      onClick={() => {
                        const count = selectedCatsToDelete.size
                        if (!confirm(`Delete ${count} categor${count > 1 ? 'ies' : 'y'} and all their permissions? This cannot be undone.`)) return
                        setCategories(prev => prev.filter(c => !selectedCatsToDelete.has(c.id)))
                        showFlash(`${count} categor${count > 1 ? 'ies' : 'y'} deleted`)
                        setSelectedCatsToDelete(new Set())
                        setCatDeleteMode(false)
                      }}
                      style={{
                        background: 'var(--danger)',
                        color: '#fff',
                        fontSize: '0.8rem',
                        fontWeight: 600,
                        borderRadius: '6px',
                        border: 'none',
                      }}
                    >
                      Delete Selected
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* MAIN DOWN VIEW 2: CONFIGURE DETAILED PERMISSIONS FOR CATEGORY */}
          {selectedCategoryObj && activeView !== 'MENU' && (
            <div style={{
              background: 'var(--bg-elevated)',
              borderRadius: '12px',
              border: '1px solid var(--border)',
              boxShadow: 'var(--shadow-sm)',
              overflow: 'hidden',
            }}>
              {/* Division Header */}
              <div style={{
                padding: '1.25rem 1.5rem',
                background: 'var(--surface-2)',
                borderBottom: '1px solid var(--border)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: '1rem',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <span style={{ fontSize: '1.5rem' }}>{selectedCategoryObj.icon}</span>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700 }}>
                      {selectedCategoryObj.label} Permissions Configuration <span style={{ color: '#2563eb' }}>for {selectedRole}</span>
                    </h3>
                    <p className="muted" style={{ margin: '0.2rem 0 0', fontSize: '0.8rem' }}>
                      {selectedCategoryObj.description}
                    </p>
                  </div>
                </div>

                {/* Actions: + Permission, Turn All ON / OFF, Delete Mode & Back */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                  {/* + Permission Button */}
                  {!deleteMode && (
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={() => {
                        setTargetCatIdForPerm(selectedCategoryObj.id)
                        setShowPermForm(true)
                      }}
                      style={{ fontSize: '0.8rem', fontWeight: 600 }}
                    >
                      + Permission
                    </button>
                  )}

                  {!isOwner && !deleteMode && (
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleToggleCategory(selectedCategoryObj, categoryEnabledCount(selectedCategoryObj) !== selectedCategoryObj.perms.length)}
                      style={{ fontSize: '0.8rem', fontWeight: 600 }}
                    >
                      {categoryEnabledCount(selectedCategoryObj) === selectedCategoryObj.perms.length
                        ? '✕ Turn All OFF'
                        : '✓ Turn All ON'}
                    </button>
                  )}

                  {/* Delete Mode Toggle */}
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => {
                      setDeleteMode(!deleteMode)
                      setSelectedPermsToDelete(new Set())
                    }}
                    style={{
                      color: deleteMode ? 'var(--danger)' : 'var(--text-muted)',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      background: deleteMode ? 'rgba(220, 38, 38, 0.08)' : 'transparent',
                      border: deleteMode ? '1px solid rgba(220, 38, 38, 0.2)' : 'none',
                      borderRadius: '6px',
                    }}
                    title={deleteMode ? 'Exit delete mode' : 'Select permissions to delete'}
                  >
                    {deleteMode ? '✕ Cancel' : '🗑️ Delete'}
                  </button>

                  {!deleteMode && (
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => setActiveView('MENU')}
                      style={{ fontSize: '0.8rem', color: '#2563eb', fontWeight: 600 }}
                    >
                      ← Back to Menu
                    </button>
                  )}
                </div>
              </div>

              {/* Detailed Permissions Rows */}
              {loading ? (
                <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                  <div className="spinner" style={{ margin: '0 auto 0.75rem' }} />
                  <p>Loading permissions...</p>
                </div>
              ) : selectedCategoryObj.perms.length === 0 ? (
                <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                  <p style={{ margin: '0 0 1rem', fontSize: '1rem' }}>No permissions in this category yet.</p>
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => {
                      setTargetCatIdForPerm(selectedCategoryObj.id)
                      setShowPermForm(true)
                    }}
                  >
                    + Add First Permission
                  </button>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  {selectedCategoryObj.perms.map((p, idx) => {
                    const enabled = isEnabled(p.code)
                    const isLast = idx === selectedCategoryObj.perms.length - 1

                    const isSelectedForDelete = selectedPermsToDelete.has(p.code)

                    return (
                      <div
                        key={p.code}
                        onClick={deleteMode ? () => {
                          setSelectedPermsToDelete(prev => {
                            const next = new Set(prev)
                            if (next.has(p.code)) next.delete(p.code)
                            else next.add(p.code)
                            return next
                          })
                        } : undefined}
                        style={{
                          padding: '1.25rem 1.5rem',
                          borderBottom: isLast ? 'none' : '1px solid var(--border)',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          gap: '1.5rem',
                          transition: 'background 0.15s ease',
                          cursor: deleteMode ? 'pointer' : 'default',
                          background: isSelectedForDelete ? 'rgba(220, 38, 38, 0.05)' : 'transparent',
                        }}
                      >
                        {/* Left: Checkbox (delete mode) + Permission Title & Code */}
                        <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                          {deleteMode && (
                            <div style={{
                              width: '20px', height: '20px', borderRadius: '4px', flexShrink: 0,
                              border: isSelectedForDelete ? '2px solid var(--danger)' : '2px solid var(--border-strong)',
                              background: isSelectedForDelete ? 'var(--danger)' : 'transparent',
                              display: 'flex', alignItems: 'center', justifyContent: 'center',
                              transition: 'all 0.15s ease',
                            }}>
                              {isSelectedForDelete && (
                                <span style={{ color: '#fff', fontSize: '0.7rem', fontWeight: 700 }}>✓</span>
                              )}
                            </div>
                          )}
                          <div>
                            <div style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--text)', marginBottom: '0.25rem' }}>
                              {p.label}
                            </div>
                            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: '1.4' }}>
                              {p.description}{' '}
                              <span style={{ fontSize: '0.75rem', color: 'var(--primary)', fontFamily: 'monospace', marginLeft: '0.35rem' }}>
                                · {p.code}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Right: ON / OFF Switch (hidden in delete mode) */}
                        {!deleteMode && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                            <button
                              type="button"
                              disabled={isOwner}
                              onClick={() => handleToggle(p.code)}
                              style={{
                                width: '52px',
                                height: '28px',
                                borderRadius: '99px',
                                background: enabled ? '#3b82f6' : '#cbd5e1',
                                border: 'none',
                                cursor: isOwner ? 'default' : 'pointer',
                                position: 'relative',
                                transition: 'background-color 0.2s ease',
                                padding: '2px',
                                outline: 'none',
                              }}
                              title={isOwner ? 'Owner has all permissions' : enabled ? 'Click to turn OFF' : 'Click to turn ON'}
                            >
                              <span
                                style={{
                                  display: 'block',
                                  width: '24px',
                                  height: '24px',
                                  borderRadius: '50%',
                                  background: '#ffffff',
                                  boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
                                  transform: enabled ? 'translateX(24px)' : 'translateX(0px)',
                                  transition: 'transform 0.2s ease',
                                }}
                              />
                            </button>

                            <span style={{
                              minWidth: '45px',
                              fontWeight: 700,
                              fontSize: '0.875rem',
                              color: enabled ? '#16a34a' : 'var(--text-muted)',
                            }}>
                              {enabled ? 'ON' : 'OFF'}
                            </span>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}

              {/* Delete Mode: Sticky Action Bar */}
              {deleteMode && selectedPermsToDelete.size > 0 && (
                <div style={{
                  padding: '0.75rem 1.5rem',
                  background: 'rgba(220, 38, 38, 0.06)',
                  borderTop: '1px solid rgba(220, 38, 38, 0.15)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--danger)' }}>
                    {selectedPermsToDelete.size} permission{selectedPermsToDelete.size > 1 ? 's' : ''} selected
                  </span>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => {
                        // Select all
                        if (selectedCategoryObj) {
                          setSelectedPermsToDelete(new Set(selectedCategoryObj.perms.map(p => p.code)))
                        }
                      }}
                      style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)' }}
                    >
                      Select All
                    </button>
                    <button
                      type="button"
                      className="btn btn-sm"
                      onClick={() => {
                        if (!selectedCategoryObj) return
                        const count = selectedPermsToDelete.size
                        if (!confirm(`Delete ${count} permission${count > 1 ? 's' : ''}? This cannot be undone.`)) return
                        setCategories(prev =>
                          prev.map(cat => {
                            if (cat.id === selectedCategoryObj.id) {
                              return { ...cat, perms: cat.perms.filter(p => !selectedPermsToDelete.has(p.code)) }
                            }
                            return cat
                          })
                        )
                        showFlash(`${count} permission${count > 1 ? 's' : ''} deleted`)
                        setSelectedPermsToDelete(new Set())
                        setDeleteMode(false)
                      }}
                      style={{
                        background: 'var(--danger)',
                        color: '#fff',
                        fontSize: '0.8rem',
                        fontWeight: 600,
                        borderRadius: '6px',
                        border: 'none',
                      }}
                    >
                      Delete Selected
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

        </div>
      </div>

      {/* ── Add Role Modal ── */}
      {showRoleForm && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal" style={{ maxWidth: '420px' }}>
            <h3 style={{ margin: '0 0 1rem' }}>Add Role</h3>
            <form onSubmit={handleCreateRole}>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                Role Name
              </label>
              <input
                className="input"
                style={{ width: '100%', marginBottom: '1.25rem' }}
                placeholder="e.g. Barista, Floor Supervisor"
                value={newRoleName}
                onChange={(e) => setNewRoleName(e.target.value)}
                required
                autoFocus
              />
              <div className="modal-actions" style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowRoleForm(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary btn-sm" disabled={!newRoleName.trim()}>
                  Add Role
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Add Category Modal ── */}
      {showCategoryForm && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal" style={{ maxWidth: '440px' }}>
            <h3 style={{ margin: '0 0 0.5rem' }}>Add Category</h3>
            <p className="muted" style={{ margin: '0 0 1.25rem', fontSize: '0.8rem' }}>
              Create a new permission category module (e.g. Bar & Beverage, Valet).
            </p>
            <form onSubmit={handleCreateCategory}>
              <div style={{ display: 'flex', gap: '0.6rem', marginBottom: '0.9rem' }}>
                <div style={{ width: '75px' }}>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.3rem' }}>
                    Icon
                  </label>
                  <select
                    className="input"
                    value={newCatIcon}
                    onChange={(e) => setNewCatIcon(e.target.value)}
                    style={{ width: '100%', padding: '0.45rem' }}
                  >
                    <option value="🏷️">🏷️</option>
                    <option value="🍸">🍸</option>
                    <option value="📦">📦</option>
                    <option value="🚗">🚗</option>
                    <option value="🧾">🧾</option>
                    <option value="⭐">⭐</option>
                    <option value="🛡️">🛡️</option>
                  </select>
                </div>
                <div style={{ flex: 1 }}>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.3rem' }}>
                    Category Label *
                  </label>
                  <input
                    className="input"
                    style={{ width: '100%' }}
                    placeholder="e.g. Bar & Beverage"
                    value={newCatLabel}
                    onChange={(e) => setNewCatLabel(e.target.value)}
                    required
                    autoFocus
                  />
                </div>
              </div>

              <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, marginBottom: '0.3rem' }}>
                Description
              </label>
              <input
                className="input"
                style={{ width: '100%', marginBottom: '1.25rem' }}
                placeholder="Explain what this category module covers"
                value={newCatDesc}
                onChange={(e) => setNewCatDesc(e.target.value)}
              />

              <div className="modal-actions" style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowCategoryForm(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary btn-sm" disabled={!newCatLabel.trim()}>
                  Add Category
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Add Permission Modal ── */}
      {showPermForm && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal" style={{ maxWidth: '440px' }}>
            <h3 style={{ margin: '0 0 0.5rem' }}>Add Permission</h3>
            <p className="muted" style={{ margin: '0 0 1.25rem', fontSize: '0.8rem' }}>
              Add a new actionable permission into <strong>{categories.find(c => c.id === targetCatIdForPerm)?.label}</strong>.
            </p>
            <form onSubmit={handleAddPermission}>
              <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, marginBottom: '0.3rem' }}>
                Permission Title *
              </label>
              <input
                className="input"
                style={{ width: '100%', marginBottom: '0.9rem' }}
                placeholder="e.g. Approve Complimentary Dessert"
                value={newPermLabel}
                onChange={(e) => setNewPermLabel(e.target.value)}
                required
                autoFocus
              />

              <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, marginBottom: '0.3rem' }}>
                Permission Key Code (Optional)
              </label>
              <input
                className="input"
                style={{ width: '100%', marginBottom: '0.9rem' }}
                placeholder={`e.g. ${targetCatIdForPerm}.approve_dessert`}
                value={newPermCode}
                onChange={(e) => setNewPermCode(e.target.value)}
              />

              <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, marginBottom: '0.3rem' }}>
                Description
              </label>
              <input
                className="input"
                style={{ width: '100%', marginBottom: '1.25rem' }}
                placeholder="Explain what access this permission gives to staff"
                value={newPermDesc}
                onChange={(e) => setNewPermDesc(e.target.value)}
              />

              <div className="modal-actions" style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowPermForm(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary btn-sm" disabled={!newPermLabel.trim()}>
                  Add Permission
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
