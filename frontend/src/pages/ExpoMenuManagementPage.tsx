import { useCallback, useEffect, useMemo, useState } from 'react'
import { API_URL, getToken } from '../api/client'
import { useAuth } from '../context/AuthContext'

const STATIONS = [
  'TANDOOR',
  'INDIAN_GRAVY',
  'SOUTH_INDIAN',
  'CHINESE_WOK',
  'CONTINENTAL_GRILL',
  'COLD_KITCHEN_SALAD',
  'BAKERY_CONFECTIONERY',
  'SWEETS_MITHAI',
  'BEVERAGE_BAR',
] as const

type Station = (typeof STATIONS)[number]

interface MenuItem {
  id: string
  name: string
  description?: string | null
  price: number
  station?: Station | string | null
  available: boolean
  is_available: boolean
}

interface FormState {
  name: string
  description: string
  price: string
  station: Station
  is_available: boolean
}

const EMPTY_FORM: FormState = {
  name: '',
  description: '',
  price: '',
  station: 'TANDOOR',
  is_available: true,
}

async function fetchJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken()
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const detail = typeof body.detail === 'string' ? body.detail : 'Request failed'
    throw new Error(detail)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}

export function ExpoMenuManagementPage() {
  const { user } = useAuth()
  const [items, setItems] = useState<MenuItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)

  const loadItems = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchJson<MenuItem[]>('/menu/all')
      setItems(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load menu items')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void loadItems() }, [loadItems])

  const groupedItems = useMemo(() => {
    return STATIONS.reduce<Record<string, MenuItem[]>>((acc, station) => {
      acc[station] = items.filter((item) => (item.station ?? '').toUpperCase() === station)
      return acc
    }, {} as Record<string, MenuItem[]>)
  }, [items])

  const resetForm = () => {
    setEditingId(null)
    setForm(EMPTY_FORM)
  }

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.name.trim() || !form.price) {
      setError('Name and price are required')
      return
    }

    const payload = {
      name: form.name.trim(),
      description: form.description.trim() || null,
      price: Number(form.price),
      station: form.station,
      category: form.station,
      available: form.is_available,
      is_available: form.is_available,
      display_order: 0,
    }

    setSaving(true)
    setError('')

    try {
      if (editingId) {
        await fetchJson(`/menu/menu-items/${editingId}`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        })
      } else {
        await fetchJson('/menu/menu-items', {
          method: 'POST',
          body: JSON.stringify(payload),
        })
      }
      resetForm()
      await loadItems()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save menu item')
    } finally {
      setSaving(false)
    }
  }

  const onDelete = async (id: string) => {
    try {
      setError('')
      await fetchJson(`/menu/menu-items/${id}`, { method: 'DELETE' })
      setItems((prev) => prev.filter((item) => item.id !== id))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete menu item')
    }
  }

  const onToggleAvailability = async (item: MenuItem) => {
    const next = !item.is_available
    try {
      const updated = await fetchJson<MenuItem>(`/menu/menu-items/${item.id}/availability?available=${next}`, {
        method: 'PATCH',
      })
      setItems((prev) => prev.map((row) => (row.id === item.id ? updated : row)))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update availability')
    }
  }

  const beginEdit = (item: MenuItem) => {
    setEditingId(item.id)
    setForm({
      name: item.name,
      description: item.description ?? '',
      price: String(item.price),
      station: (item.station as Station) || 'TANDOOR',
      is_available: item.is_available,
    })
  }

  if (!user || !['CHEF', 'MANAGER', 'OWNER', 'EXPO'].includes(user.role as string)) {
    return null
  }

  if (loading) {
    return (
      <div className="page-loading" style={{ minHeight: '60vh', background: '#0f172a' }}>
        <div className="spinner" />
        <p style={{ color: '#e2e8f0' }}>Loading menu…</p>
      </div>
    )
  }

  return (
    <div style={{ padding: '24px', color: '#f8fafc', background: '#0f172a', minHeight: '100vh' }}>
      <div style={{ maxWidth: 1200, margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <div>
            <p style={{ margin: 0, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.12em', fontSize: 12 }}>Executive Chef</p>
            <h1 style={{ margin: '8px 0 0', fontSize: 32, color: '#f8fafc' }}>Menu Management</h1>
          </div>
          <button type="button" className="btn btn-primary" onClick={resetForm}>
            {editingId ? 'Cancel edit' : 'New item'}
          </button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '420px minmax(0, 1fr)', gap: 24 }}>
          <form onSubmit={onSubmit} style={{ background: '#111827', border: '1px solid #334155', borderRadius: 16, padding: 20 }}>
            <h2 style={{ margin: '0 0 16px', fontSize: 22, color: '#f8fafc' }}>
              {editingId ? 'Edit item' : 'Create a menu item'}
            </h2>

            <label className="field" style={{ display: 'block', marginBottom: 16 }}>
              <span style={{ display: 'block', color: '#cbd5e1', marginBottom: 8 }}>Name</span>
              <input
                className="input"
                value={form.name}
                onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
                placeholder="Paneer Tikka"
                required
              />
            </label>

            <label className="field" style={{ display: 'block', marginBottom: 16 }}>
              <span style={{ display: 'block', color: '#cbd5e1', marginBottom: 8 }}>Description</span>
              <textarea
                className="input"
                value={form.description}
                onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
                placeholder="A smoky starter with mint chutney"
                rows={4}
                style={{ resize: 'vertical', minHeight: 90 }}
              />
            </label>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
              <label className="field" style={{ display: 'block', margin: 0 }}>
                <span style={{ display: 'block', color: '#cbd5e1', marginBottom: 8 }}>Price</span>
                <input
                  className="input"
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.price}
                  onChange={(e) => setForm((prev) => ({ ...prev, price: e.target.value }))}
                  placeholder="299"
                  required
                />
              </label>

              <label className="field" style={{ display: 'block', margin: 0 }}>
                <span style={{ display: 'block', color: '#cbd5e1', marginBottom: 8 }}>Station</span>
                <select
                  className="input"
                  value={form.station}
                  onChange={(e) => setForm((prev) => ({ ...prev, station: e.target.value as Station }))}
                >
                  {STATIONS.map((station) => (
                    <option key={station} value={station}>{station}</option>
                  ))}
                </select>
              </label>
            </div>

            <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 20, color: '#cbd5e1' }}>
              <span>Available to guests</span>
              <button
                type="button"
                onClick={() => setForm((prev) => ({ ...prev, is_available: !prev.is_available }))}
                aria-label="Toggle availability"
                style={{
                  position: 'relative',
                  width: 52,
                  height: 30,
                  borderRadius: 999,
                  border: 'none',
                  background: form.is_available ? '#16a34a' : '#475569',
                  cursor: 'pointer',
                  transition: 'background 0.2s ease',
                }}
              >
                <span
                  style={{
                    position: 'absolute',
                    top: 4,
                    left: form.is_available ? 28 : 4,
                    width: 20,
                    height: 20,
                    borderRadius: '50%',
                    background: '#fff',
                    transition: 'left 0.2s ease',
                  }}
                />
              </button>
            </label>

            {error && (
              <div style={{ background: '#7f1d1d', color: '#fee2e2', padding: '10px 12px', borderRadius: 8, marginBottom: 16 }}>
                {error}
              </div>
            )}

            <button type="submit" className="btn btn-primary" disabled={saving} style={{ width: '100%' }}>
              {saving ? 'Saving…' : editingId ? 'Save changes' : 'Create item'}
            </button>
          </form>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {STATIONS.map((station) => {
              const stationItems = groupedItems[station] ?? []
              return (
                <div key={station} style={{ background: '#111827', border: '1px solid #334155', borderRadius: 16, overflow: 'hidden' }}>
                  <div style={{ background: '#1e293b', padding: '12px 16px', borderBottom: '1px solid #334155' }}>
                    <h3 style={{ margin: 0, fontSize: 16, color: '#f8fafc' }}>{station}</h3>
                  </div>

                  <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {stationItems.length === 0 ? (
                      <div style={{ padding: '16px 8px', color: '#94a3b8', fontSize: 14 }}>No items for this station yet.</div>
                    ) : (
                      stationItems.map((item) => (
                        <div
                          key={item.id}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 12,
                            padding: '12px 14px',
                            borderRadius: 12,
                            background: item.is_available ? '#0f172a' : '#1f2937',
                            border: '1px solid #334155',
                            opacity: item.is_available ? 1 : 0.6,
                          }}
                        >
                          <div style={{ flex: 1 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <strong style={{ color: '#f8fafc', fontSize: 15 }}>{item.name}</strong>
                              {!item.is_available && (
                                <span style={{ background: '#7f1d1d', color: '#fecaca', fontSize: 10, padding: '3px 6px', borderRadius: 999 }}>86'd</span>
                              )}
                            </div>
                            {item.description && (
                              <div style={{ fontSize: 12, color: '#cbd5e1', marginTop: 4 }}>{item.description}</div>
                            )}
                            <div style={{ marginTop: 8, color: '#f8fafc', fontWeight: 700 }}>₹{Number(item.price).toFixed(2)}</div>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <button type="button" className="btn btn-secondary btn-sm" onClick={() => beginEdit(item)}>
                              Edit
                            </button>
                            <button type="button" className="btn btn-ghost btn-sm" onClick={() => onDelete(item.id)}>
                              Delete
                            </button>
                            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, color: '#cbd5e1' }}>
                              <span>{item.is_available ? 'Live' : '86'}</span>
                              <input
                                type="checkbox"
                                checked={item.is_available}
                                onChange={() => onToggleAvailability(item)}
                                style={{ width: 18, height: 18, accentColor: '#22c55e' }}
                              />
                            </label>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
