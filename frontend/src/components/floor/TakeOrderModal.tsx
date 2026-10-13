import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { menuApi, ordersApi, type MenuItem } from '../../api/extensions'
import { HOTEL_CUISINES, type CuisineCategory } from '../../pages/MenuPage'
import { useFloor } from '../../context/FloorContext'
import type { Table } from '../../types'

interface TakeOrderModalProps {
  table: Table
  onClose: () => void
}

function matchesCuisine(item: MenuItem, cuisineId: string): boolean {
  if (cuisineId === 'All') return true
  const itemCat = (item.category || '').toLowerCase()
  const target = cuisineId.toLowerCase()
  if (target === 'drinks' || target === 'beverages') {
    return (
      itemCat === 'drinks' ||
      itemCat === 'beverages' ||
      itemCat.includes('drink') ||
      itemCat.includes('beverage') ||
      itemCat.includes('coffee') ||
      itemCat.includes('tea')
    )
  }
  if (target.includes('south')) return itemCat.includes('south')
  if (target.includes('north')) return itemCat.includes('north')
  if (target.includes('asian') || target.includes('chinese')) return itemCat.includes('asian') || itemCat.includes('chinese')
  if (target.includes('italian') || target.includes('continental')) return itemCat.includes('italian') || itemCat.includes('continental')
  if (target.includes('liquor') || target.includes('cocktail')) return itemCat.includes('liquor') || itemCat.includes('cocktail') || itemCat.includes('bar')
  if (target.includes('starter')) return itemCat.includes('starter') || itemCat.includes('appetizer')
  if (target.includes('dessert')) return itemCat.includes('dessert') || itemCat.includes('sweet')
  return itemCat === target
}

function getDietaryType(item: MenuItem): 'veg' | 'non-veg' | 'liquor' {
  if (item.dietaryType === 'veg' || item.dietaryType === 'non-veg' || item.dietaryType === 'liquor') {
    return item.dietaryType
  }
  const cat = (item.category || '').toLowerCase()
  const name = (item.name || '').toLowerCase()
  if (cat.includes('liquor') || cat.includes('cocktail') || cat.includes('beer') || cat.includes('wine') || cat.includes('bar')) {
    return 'liquor'
  }
  if (
    name.includes('chicken') ||
    name.includes('mutton') ||
    name.includes('fish') ||
    name.includes('prawn') ||
    name.includes('lamb') ||
    name.includes('pork') ||
    name.includes('beef') ||
    name.includes('meat') ||
    name.includes('seafood') ||
    name.includes('egg') ||
    (name.includes('kebab') && !name.includes('paneer'))
  ) {
    return 'non-veg'
  }
  return 'veg'
}

export function TakeOrderModal({ table, onClose }: TakeOrderModalProps) {
  const { sessions, refresh } = useFloor()
  const [menuItems, setMenuItems] = useState<MenuItem[]>([])
  const [menuLoading, setMenuLoading] = useState(true)
  const [quantities, setQuantities] = useState<Record<string, number>>({})
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Waiter Search & Categorization States
  const [searchQuery, setSearchQuery] = useState('')
  const [activeCuisine, setActiveCuisine] = useState<string>('All')
  const [dietaryFilter, setDietaryFilter] = useState<'ALL' | 'VEG' | 'NON_VEG' | 'LIQUOR'>('ALL')
  const searchInputRef = useRef<HTMLInputElement>(null)

  // Note Features (Item-level notes & General Order note)
  const [itemNotes, setItemNotes] = useState<Record<string, string>>({})
  const [expandedNoteItemId, setExpandedNoteItemId] = useState<string | null>(null)
  const [orderNote, setOrderNote] = useState<string>('')
  const [showOrderNoteInput, setShowOrderNoteInput] = useState<boolean>(false)

  const session = sessions.find(
    (s) => (s.tableId === table.id || (s as any).table_id === table.id) && !s.closedAt && ['SEATED', 'ACTIVE', 'OCCUPIED'].includes(s.status),
  )

  useEffect(() => {
    document.body.classList.add('foh-modal-open')
    return () => document.body.classList.remove('foh-modal-open')
  }, [])

  // Auto-focus search input for fast waiter punch-in
  useEffect(() => {
    const timer = setTimeout(() => {
      searchInputRef.current?.focus()
    }, 100)
    return () => clearTimeout(timer)
  }, [])

  useEffect(() => {
    let cancelled = false
    setMenuLoading(true)
    menuApi
      .listPublic()
      .then((items) => {
        if (!cancelled) setMenuItems(items.filter((i) => i.available))
      })
      .catch(() => {
        if (!cancelled) setError('Could not load menu')
      })
      .finally(() => {
        if (!cancelled) setMenuLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const selectedItems = useMemo(
    () =>
      Object.entries(quantities)
        .filter(([, qty]) => qty > 0)
        .map(([menuItemId, quantity]) => ({ menuItemId, quantity })),
    [quantities],
  )

  const selectedItemsCount = selectedItems.length
  const totalItemQuantity = useMemo(
    () => selectedItems.reduce((acc, curr) => acc + curr.quantity, 0),
    [selectedItems],
  )

  const total = useMemo(() => {
    return selectedItems.reduce((sum, line) => {
      const item = menuItems.find((m) => m.id === line.menuItemId)
      return sum + (item ? item.price * line.quantity : 0)
    }, 0)
  }, [selectedItems, menuItems])

  function setQty(itemId: string, qty: number) {
    const nextQty = Math.max(0, qty)
    setQuantities((prev) => ({ ...prev, [itemId]: nextQty }))
    if (nextQty === 0) {
      if (expandedNoteItemId === itemId) {
        setExpandedNoteItemId(null)
      }
    }
  }

  function handleClearAll() {
    setQuantities({})
    setItemNotes({})
    setOrderNote('')
    setExpandedNoteItemId(null)
  }

  // Filter items by Search Query, Cuisine Category, and Dietary Type
  const filteredItems = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()

    return menuItems.filter((item) => {
      // If "SELECTED" filter is active, only show items with qty > 0
      if (activeCuisine === 'SELECTED') {
        if ((quantities[item.id] || 0) <= 0) return false
      } else if (activeCuisine !== 'All') {
        if (!matchesCuisine(item, activeCuisine)) return false
      }

      // Dietary filter
      if (dietaryFilter !== 'ALL') {
        const dType = getDietaryType(item)
        if (dietaryFilter === 'VEG' && dType !== 'veg') return false
        if (dietaryFilter === 'NON_VEG' && dType !== 'non-veg') return false
        if (dietaryFilter === 'LIQUOR' && dType !== 'liquor') return false
      }

      // Search match
      if (q) {
        const matchesName = item.name.toLowerCase().includes(q)
        const matchesCat = (item.category || '').toLowerCase().includes(q)
        const matchesDesc = (item.description || '').toLowerCase().includes(q)
        const matchesCode = (item.itemCode || '').toLowerCase().includes(q)
        const matchesStation = (item.station || '').toLowerCase().includes(q)
        if (!matchesName && !matchesCat && !matchesDesc && !matchesCode && !matchesStation) {
          return false
        }
      }

      return true
    })
  }, [menuItems, searchQuery, activeCuisine, dietaryFilter, quantities])

  async function handleSubmit() {
    if (selectedItems.length === 0) return
    setSubmitting(true)
    setError(null)
    try {
      const itemsPayload = selectedItems.map((line) => ({
        menuItemId: line.menuItemId,
        quantity: line.quantity,
        notes: itemNotes[line.menuItemId]?.trim() || undefined,
      }))

      await ordersApi.place(table.id, itemsPayload, session?.id, orderNote.trim() || undefined)
      await refresh()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not place order')
    } finally {
      setSubmitting(false)
    }
  }

  return createPortal(
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="take-order-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="modal take-order-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="take-order-header">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '1.3rem' }}>🍽️</span>
              <h3 id="take-order-title" style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700, color: '#0f172a' }}>
                Take Order — Table {table.number}
              </h3>
            </div>
            <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: 3 }}>
              {session?.guestName ? (
                <span>
                  Guest: <strong style={{ color: '#0f172a' }}>{session.guestName}</strong> ({session.partySize} {session.partySize === 1 ? 'guest' : 'guests'})
                </span>
              ) : (
                <span>Fast Table POS Order Entry & Kitchen Notes</span>
              )}
            </div>
          </div>

          <button
            type="button"
            className="twin-hud-close-btn"
            onClick={onClose}
            title="Close modal (Esc)"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* ── Search Bar ── */}
        <div className="take-order-search-box">
          <span style={{ position: 'absolute', left: '12px', fontSize: '0.95rem', color: '#94a3b8', pointerEvents: 'none' }}>
            🔍
          </span>
          <input
            ref={searchInputRef}
            type="text"
            className="take-order-search-input"
            placeholder="Search dish name, code (e.g. D04), category or keywords..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery('')}
              style={{
                position: 'absolute',
                right: '10px',
                background: 'transparent',
                border: 'none',
                color: '#94a3b8',
                cursor: 'pointer',
                fontSize: '0.9rem',
                padding: '4px',
              }}
              title="Clear search"
            >
              ✕
            </button>
          )}
        </div>

        {/* ── Cuisine Categories (matches Menu page: South India, North India, Beverages, etc.) ── */}
        <div className="take-order-cuisine-bar">
          <button
            type="button"
            className={`cuisine-tab-btn ${activeCuisine === 'All' ? 'active' : ''}`}
            onClick={() => setActiveCuisine('All')}
          >
            <span>🌐</span>
            <span>All Cuisines</span>
            <span className="count-chip">{menuItems.length}</span>
          </button>

          {selectedItemsCount > 0 && (
            <button
              type="button"
              className={`cuisine-tab-btn ${activeCuisine === 'SELECTED' ? 'active' : ''}`}
              onClick={() => setActiveCuisine('SELECTED')}
              style={activeCuisine !== 'SELECTED' ? { borderColor: '#10b981', color: '#059669', background: '#ecfdf5' } : { background: '#059669', borderColor: '#059669' }}
              title="View only items selected in order"
            >
              <span>🛒</span>
              <span>Selected Dishes</span>
              <span className="count-chip" style={activeCuisine === 'SELECTED' ? { background: '#ffffff', color: '#059669' } : {}}>
                {selectedItemsCount}
              </span>
            </button>
          )}

          {HOTEL_CUISINES.map((cuisine: CuisineCategory) => {
            const count = menuItems.filter((i) => matchesCuisine(i, cuisine.id)).length
            const isActive = activeCuisine === cuisine.id

            return (
              <button
                key={cuisine.id}
                type="button"
                className={`cuisine-tab-btn ${isActive ? 'active' : ''}`}
                onClick={() => setActiveCuisine(cuisine.id)}
                title={cuisine.desc}
              >
                <span>{cuisine.icon}</span>
                <span>{cuisine.label}</span>
                <span className="count-chip">{count}</span>
              </button>
            )
          })}
        </div>

        {/* ── Dietary Quick Sub-Filters ── */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', fontSize: '0.78rem' }}>
          <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
            <span style={{ color: '#64748b', fontWeight: 600, fontSize: '0.74rem' }}>Filter:</span>
            <button
              type="button"
              onClick={() => setDietaryFilter('ALL')}
              style={{
                border: 'none',
                background: dietaryFilter === 'ALL' ? '#e2e8f0' : 'transparent',
                fontWeight: dietaryFilter === 'ALL' ? 700 : 500,
                color: dietaryFilter === 'ALL' ? '#0f172a' : '#64748b',
                padding: '2px 8px',
                borderRadius: '6px',
                cursor: 'pointer',
              }}
            >
              All
            </button>
            <button
              type="button"
              onClick={() => setDietaryFilter('VEG')}
              style={{
                border: 'none',
                background: dietaryFilter === 'VEG' ? '#dcfce7' : 'transparent',
                fontWeight: dietaryFilter === 'VEG' ? 700 : 500,
                color: dietaryFilter === 'VEG' ? '#166534' : '#64748b',
                padding: '2px 8px',
                borderRadius: '6px',
                cursor: 'pointer',
              }}
            >
              🟢 Veg
            </button>
            <button
              type="button"
              onClick={() => setDietaryFilter('NON_VEG')}
              style={{
                border: 'none',
                background: dietaryFilter === 'NON_VEG' ? '#fee2e2' : 'transparent',
                fontWeight: dietaryFilter === 'NON_VEG' ? 700 : 500,
                color: dietaryFilter === 'NON_VEG' ? '#991b1b' : '#64748b',
                padding: '2px 8px',
                borderRadius: '6px',
                cursor: 'pointer',
              }}
            >
              🔴 Non-Veg
            </button>
          </div>

          <span style={{ color: '#94a3b8', fontSize: '0.74rem' }}>
            Showing {filteredItems.length} items
          </span>
        </div>

        {/* ── Menu Items List ── */}
        {menuLoading ? (
          <div style={{ padding: '2rem 0', textAlign: 'center', color: '#64748b' }}>
            <p style={{ margin: 0, fontSize: '0.88rem' }}>Loading restaurant menu items…</p>
          </div>
        ) : filteredItems.length === 0 ? (
          <div style={{ padding: '2rem 1rem', textAlign: 'center', background: '#f8fafc', borderRadius: '10px', border: '1px dashed #cbd5e1' }}>
            <span style={{ fontSize: '1.75rem', display: 'block', marginBottom: '6px' }}>🍽️</span>
            <div style={{ fontWeight: 600, color: '#334155', fontSize: '0.9rem' }}>No dishes found</div>
            <div style={{ fontSize: '0.78rem', color: '#64748b', marginTop: '2px' }}>
              {searchQuery ? `No results matching "${searchQuery}"` : 'No items in this category'}
            </div>
            {(searchQuery || activeCuisine !== 'All' || dietaryFilter !== 'ALL') && (
              <button
                type="button"
                className="btn btn-sm btn-secondary"
                style={{ marginTop: '10px', fontSize: '0.75rem' }}
                onClick={() => {
                  setSearchQuery('')
                  setActiveCuisine('All')
                  setDietaryFilter('ALL')
                }}
              >
                Reset All Filters
              </button>
            )}
          </div>
        ) : (
          <div className="take-order-item-list">
            {filteredItems.map((item) => {
              const qty = quantities[item.id] ?? 0
              const isSelected = qty > 0
              const dType = getDietaryType(item)
              const hasNote = Boolean(itemNotes[item.id])

              return (
                <div
                  key={item.id}
                  className={`take-order-item-card ${isSelected ? 'take-order-item-card--active' : ''}`}
                  style={{ flexDirection: 'column', alignItems: 'stretch' }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                    <div style={{ flex: 1, minWidth: 0, paddingRight: '12px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                        <span title={dType === 'veg' ? 'Vegetarian' : dType === 'non-veg' ? 'Non-Vegetarian' : 'Bar / Liquor'}>
                          {dType === 'veg' ? '🟢' : dType === 'non-veg' ? '🔴' : '🍸'}
                        </span>
                        <strong style={{ fontSize: '0.92rem', color: '#0f172a' }}>{item.name}</strong>
                        {item.itemCode && (
                          <span style={{ fontSize: '0.68rem', background: '#e2e8f0', color: '#475569', padding: '1px 5px', borderRadius: '4px', fontWeight: 700 }}>
                            {item.itemCode}
                          </span>
                        )}
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '3px' }}>
                        <span style={{ fontWeight: 700, fontSize: '0.9rem', color: '#2563eb' }}>
                          ₹{item.price.toFixed(2)}
                        </span>
                        {item.category && (
                          <span style={{ fontSize: '0.72rem', color: '#64748b', background: '#f1f5f9', padding: '1px 6px', borderRadius: '4px' }}>
                            {item.category}
                          </span>
                        )}
                        {item.prepTimeMinutes && (
                          <span style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
                            ⏱️ {item.prepTimeMinutes}m
                          </span>
                        )}
                      </div>

                      {item.description && (
                        <p
                          style={{
                            margin: '3px 0 0',
                            fontSize: '0.74rem',
                            color: '#64748b',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            maxWidth: '380px',
                          }}
                          title={item.description}
                        >
                          {item.description}
                        </p>
                      )}
                    </div>

                    {/* Quantity Stepper Controls */}
                    <div className={`take-order-stepper ${isSelected ? 'take-order-stepper--active' : ''}`}>
                      <button
                        type="button"
                        className="take-order-stepper-btn"
                        onClick={() => setQty(item.id, qty - 1)}
                        title="Decrease quantity"
                        disabled={qty <= 0}
                        style={{ opacity: qty <= 0 ? 0.35 : 1 }}
                      >
                        −
                      </button>
                      <span className="take-order-stepper-qty" style={{ color: isSelected ? '#2563eb' : '#0f172a' }}>
                        {qty}
                      </span>
                      <button
                        type="button"
                        className="take-order-stepper-btn"
                        onClick={() => setQty(item.id, qty + 1)}
                        title="Add one more"
                      >
                        +
                      </button>
                    </div>
                  </div>

                  {/* ── Item Cooking / Kitchen Note Feature ── */}
                  {isSelected && (
                    <div style={{ marginTop: '6px', paddingTop: '6px', borderTop: '1px dashed #e2e8f0' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '6px' }}>
                        {hasNote ? (
                          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', background: '#ecfdf5', border: '1px solid #a7f3d0', padding: '3px 8px', borderRadius: '6px', fontSize: '0.75rem', color: '#065f46' }}>
                            <span>📝</span>
                            <span style={{ fontWeight: 600 }}>Note: "{itemNotes[item.id]}"</span>
                            <button
                              type="button"
                              onClick={() => setExpandedNoteItemId(expandedNoteItemId === item.id ? null : item.id)}
                              style={{ background: 'none', border: 'none', color: '#047857', cursor: 'pointer', padding: 0, fontSize: '0.72rem', textDecoration: 'underline' }}
                            >
                              Edit
                            </button>
                            <button
                              type="button"
                              onClick={() =>
                                setItemNotes((prev) => {
                                  const next = { ...prev }
                                  delete next[item.id]
                                  return next
                                })
                              }
                              style={{ background: 'none', border: 'none', color: '#991b1b', cursor: 'pointer', padding: 0, fontSize: '0.72rem' }}
                              title="Remove note"
                            >
                              ✕
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => setExpandedNoteItemId(expandedNoteItemId === item.id ? null : item.id)}
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              background: 'none',
                              border: 'none',
                              color: '#2563eb',
                              fontSize: '0.75rem',
                              fontWeight: 600,
                              cursor: 'pointer',
                              padding: 0,
                            }}
                          >
                            <span>📝</span>
                            <span>+ Add Cooking Note / Allergy</span>
                          </button>
                        )}
                      </div>

                      {expandedNoteItemId === item.id && (
                        <div className="take-order-item-note-box">
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                            <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#475569' }}>
                              Cooking note for {item.name}:
                            </span>
                            <button
                              type="button"
                              onClick={() => setExpandedNoteItemId(null)}
                              style={{ background: 'none', border: 'none', fontSize: '0.75rem', color: '#2563eb', cursor: 'pointer', fontWeight: 700 }}
                            >
                              Done ✓
                            </button>
                          </div>

                          <input
                            type="text"
                            className="take-order-item-note-input"
                            placeholder="e.g. Less spicy, no onion, extra sauce, crispy..."
                            value={itemNotes[item.id] || ''}
                            onChange={(e) => setItemNotes((prev) => ({ ...prev, [item.id]: e.target.value }))}
                            autoFocus
                          />

                          {/* Quick preset chips */}
                          <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '6px' }}>
                            {['🌶️ Extra Spicy', '🌿 Less Spicy', '🚫 No Onion / Garlic', '🌾 Gluten Free', '🔥 Extra Crispy', '🧀 Extra Cheese', '🧂 Low Salt'].map((preset) => (
                              <span
                                key={preset}
                                className="take-order-preset-chip"
                                onClick={() => {
                                  const current = (itemNotes[item.id] || '').trim()
                                  const updated = current ? `${current}, ${preset}` : preset
                                  setItemNotes((prev) => ({ ...prev, [item.id]: updated }))
                                }}
                              >
                                {preset}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {/* ── General Order / Kitchen Note ── */}
        <div className="take-order-order-note-wrap">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <button
              type="button"
              onClick={() => setShowOrderNoteInput((v) => !v)}
              style={{
                background: 'none',
                border: 'none',
                color: orderNote ? '#047857' : '#475569',
                fontWeight: 700,
                fontSize: '0.8rem',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                cursor: 'pointer',
                padding: 0,
              }}
            >
              <span>📝</span>
              <span>
                {orderNote ? `Kitchen Note: "${orderNote}"` : 'Add Kitchen Note (KOT Instructions)'}
              </span>
              <span style={{ fontSize: '0.72rem', color: '#2563eb' }}>
                {showOrderNoteInput ? '▲ Hide' : '▼ Expand'}
              </span>
            </button>

            {orderNote && !showOrderNoteInput && (
              <button
                type="button"
                onClick={() => setOrderNote('')}
                style={{ background: 'none', border: 'none', color: '#dc2626', fontSize: '0.72rem', cursor: 'pointer' }}
              >
                Clear
              </button>
            )}
          </div>

          {showOrderNoteInput && (
            <div style={{ marginTop: '6px' }}>
              <input
                type="text"
                className="take-order-item-note-input"
                placeholder="e.g. VIP guest, serve starters first, severe peanut allergy, anniversary..."
                value={orderNote}
                onChange={(e) => setOrderNote(e.target.value)}
              />
              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '6px' }}>
                {['⭐ VIP Table', '🥗 Starters First', '🎂 Birthday / Celebration', '⚡ Rush Order', '🍽️ Serve All Together'].map((preset) => (
                  <span
                    key={preset}
                    className="take-order-preset-chip"
                    onClick={() => {
                      const current = orderNote.trim()
                      setOrderNote(current ? `${current}, ${preset}` : preset)
                    }}
                  >
                    {preset}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ── Order Summary & Cart Totals ── */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0.75rem 0.9rem',
            background: '#f8fafc',
            borderRadius: '10px',
            border: '1px solid #e2e8f0',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontWeight: 800, fontSize: '1.05rem', color: '#0f172a' }}>
                Total: ₹{total.toFixed(2)}
              </span>
              {selectedItemsCount > 0 && (
                <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#059669', background: '#dcfce7', padding: '2px 7px', borderRadius: '6px' }}>
                  {selectedItemsCount} {selectedItemsCount === 1 ? 'item' : 'items'} ({totalItemQuantity} qty)
                </span>
              )}
            </div>
            {selectedItemsCount > 0 && (
              <button
                type="button"
                onClick={handleClearAll}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#dc2626',
                  fontSize: '0.72rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  padding: 0,
                  marginTop: '2px',
                  textDecoration: 'underline',
                }}
              >
                Clear all selections
              </button>
            )}
          </div>

          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <button type="button" className="btn btn-ghost" onClick={onClose}>
              Cancel
            </button>
            <button
              type="button"
              className="btn btn-primary"
              disabled={submitting || selectedItems.length === 0}
              onClick={handleSubmit}
              style={{
                minWidth: '130px',
                fontWeight: 700,
                background: selectedItems.length === 0 ? undefined : '#2563eb',
                borderColor: selectedItems.length === 0 ? undefined : '#2563eb',
              }}
            >
              {submitting ? 'Placing…' : selectedItems.length === 0 ? 'Place Order' : `Place Order (₹${total.toFixed(2)})`}
            </button>
          </div>
        </div>

        {error && <p className="form-error" style={{ margin: 0, fontSize: '0.8rem' }}>{error}</p>}
      </div>
    </div>,
    document.body,
  )
}