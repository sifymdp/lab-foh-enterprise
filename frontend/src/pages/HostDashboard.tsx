import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { reservationsApi, type Reservation } from '../api/extensions'
import { useSocket } from '../context/SocketContext'
import { PhoneFrameContainer } from '../components/common/PhoneFrameContainer'

export function HostDashboard() {
  const { on } = useSocket()

  const [activeTab, setActiveTab] = useState<'overview' | 'seat' | 'reservations'>('overview')
  const [tables, setTables] = useState<any[]>([])
  const [reservations, setReservations] = useState<Reservation[]>([])
  const [loading, setLoading] = useState(false)
  const [statusMessage, setStatusMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null)

  // Fast Seating state
  const [seatPartySize, setSeatPartySize] = useState<number>(2)
  const [seatGuestName, setSeatGuestName] = useState<string>('')
  const [selectedTableId, setSelectedTableId] = useState<string>('')
  const [seatingLoading, setSeatingLoading] = useState(false)

  const showToast = (text: string, type: 'success' | 'error' = 'success') => {
    setStatusMessage({ text, type })
    setTimeout(() => setStatusMessage(null), 4000)
  }

  const fetchData = useCallback(async () => {
    try {
      setLoading(true)
      const [floorRes, resList] = await Promise.all([
        api.getFloor().then((f) => f.tables || []),
        reservationsApi.list().catch(() => []),
      ])
      setTables(floorRes)
      setReservations(resList || [])
    } catch (err) {
      console.error('Failed to load host stand statistics', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Real-time socket events
  useEffect(() => {
    const unsub1 = on('table_updated', () => fetchData())
    const unsub2 = on('reservation_created', () => fetchData())
    const unsub3 = on('walkout_detected', () => fetchData())
    return () => {
      unsub1()
      unsub2()
      unsub3()
    }
  }, [on, fetchData])

  const stats = {
    total: tables.length,
    available: tables.filter((t) => t.status === 'AVAILABLE').length,
    seated: tables.filter((t) => ['SEATED', 'ACTIVE', 'OCCUPIED'].includes(t.status)).length,
    reserved: tables.filter((t) => t.status === 'RESERVED').length,
    cleaning: tables.filter((t) => t.status === 'CLEANING').length,
  }

  // Eligible available tables for fast walk-in seating
  const availableTables = tables.filter((t) => t.status === 'AVAILABLE')
  const matchingTables = availableTables.filter((t) => t.capacity >= seatPartySize)

  const handleFastSeat = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedTableId) {
      showToast('Please select an available table', 'error')
      return
    }

    setSeatingLoading(true)
    try {
      await api.createSession({
        tableId: selectedTableId,
        partySize: seatPartySize,
        guestName: seatGuestName.trim() || `Walk-in (${seatPartySize}p)`,
      })
      showToast(`✓ Guests seated successfully at Table ${tables.find((t) => t.id === selectedTableId)?.number || ''}!`, 'success')
      setSelectedTableId('')
      setSeatGuestName('')
      await fetchData()
      setActiveTab('overview')
    } catch (err: any) {
      showToast(err?.message || 'Failed to seat guests', 'error')
    } finally {
      setSeatingLoading(false)
    }
  }

  const handleSeatReservation = async (res: Reservation) => {
    try {
      await api.createSession({
        tableId: res.tableId,
        partySize: res.partySize,
        guestName: res.guestName,
      })
      showToast(`✓ Reserved guest ${res.guestName} seated!`, 'success')
      await fetchData()
    } catch (err: any) {
      showToast(err?.message || 'Failed to seat reservation party', 'error')
    }
  }

  const handleMarkCleaned = async (tableId: string) => {
    try {
      await api.patchTableStatus(tableId, 'AVAILABLE')
      showToast('✓ Table marked as clean & available!', 'success')
      await fetchData()
    } catch (err: any) {
      showToast(err?.message || 'Failed to update table status', 'error')
    }
  }

  return (
    <PhoneFrameContainer
      title="Host Reception Stand"
      roleSubtitle="Front of House Seating & Guest Welcome"
      roleBadge="HOST"
      badgeColor="#047857"
      onRefresh={fetchData}
      activeTabCount={reservations.length}
    >
      {/* Toast Alert */}
      {statusMessage && (
        <div
          style={{
            position: 'sticky',
            top: '8px',
            zIndex: 9999,
            padding: '10px 14px',
            borderRadius: '8px',
            fontWeight: 700,
            fontSize: '0.82rem',
            marginBottom: '10px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            background: statusMessage.type === 'success' ? '#15803d' : '#b91c1c',
            color: '#ffffff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span>{statusMessage.text}</span>
          <button
            onClick={() => setStatusMessage(null)}
            style={{ background: 'none', border: 'none', color: '#fff', fontSize: '1rem', cursor: 'pointer' }}
          >
            ✕
          </button>
        </div>
      )}

      {/* ─── SEGMENTED PHONE TABS BAR ─── */}
      <div
        style={{
          display: 'flex',
          background: 'var(--surface-2)',
          borderRadius: '12px',
          padding: '4px',
          marginBottom: '1rem',
          border: '1px solid var(--border)',
          gap: '4px',
        }}
      >
        <button
          type="button"
          onClick={() => setActiveTab('overview')}
          style={{
            flex: 1,
            padding: '8px 4px',
            border: 'none',
            borderRadius: '9px',
            fontSize: '0.82rem',
            fontWeight: activeTab === 'overview' ? 800 : 600,
            cursor: 'pointer',
            background: activeTab === 'overview' ? '#ffffff' : 'transparent',
            color: activeTab === 'overview' ? '#047857' : 'var(--text-muted)',
            boxShadow: activeTab === 'overview' ? '0 1px 4px rgba(0,0,0,0.08)' : 'none',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '4px',
            transition: 'all 0.15s ease',
          }}
        >
          <span>📊 Stand</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('seat')}
          style={{
            flex: 1,
            padding: '8px 4px',
            border: 'none',
            borderRadius: '9px',
            fontSize: '0.82rem',
            fontWeight: activeTab === 'seat' ? 800 : 600,
            cursor: 'pointer',
            background: activeTab === 'seat' ? '#ffffff' : 'transparent',
            color: activeTab === 'seat' ? '#047857' : 'var(--text-muted)',
            boxShadow: activeTab === 'seat' ? '0 1px 4px rgba(0,0,0,0.08)' : 'none',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '4px',
            transition: 'all 0.15s ease',
          }}
        >
          <span>🪑 Fast Seat</span>
          {availableTables.length > 0 && (
            <span
              style={{
                background: '#10b981',
                color: '#ffffff',
                fontSize: '0.68rem',
                fontWeight: 800,
                padding: '1px 5px',
                borderRadius: '8px',
              }}
            >
              {availableTables.length}
            </span>
          )}
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('reservations')}
          style={{
            flex: 1,
            padding: '8px 4px',
            border: 'none',
            borderRadius: '9px',
            fontSize: '0.82rem',
            fontWeight: activeTab === 'reservations' ? 800 : 600,
            cursor: 'pointer',
            background: activeTab === 'reservations' ? '#ffffff' : 'transparent',
            color: activeTab === 'reservations' ? '#047857' : 'var(--text-muted)',
            boxShadow: activeTab === 'reservations' ? '0 1px 4px rgba(0,0,0,0.08)' : 'none',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '4px',
            transition: 'all 0.15s ease',
          }}
        >
          <span>📅 Booking</span>
          {reservations.length > 0 && (
            <span
              style={{
                background: '#eab308',
                color: '#000000',
                fontSize: '0.68rem',
                fontWeight: 800,
                padding: '1px 5px',
                borderRadius: '8px',
              }}
            >
              {reservations.length}
            </span>
          )}
        </button>
      </div>

      {/* ─── TAB 1: STAND KPI OVERVIEW & TABLES ROSTER ─── */}
      {activeTab === 'overview' && (
        <div>
          {/* 2x2 KPI Grid for Mobile Phone */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px', marginBottom: '12px' }}>
            <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '10px', padding: '10px 12px' }}>
              <span style={{ fontSize: '0.72rem', color: '#166534', fontWeight: 600 }}>AVAILABLE</span>
              <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#15803d', marginTop: '2px' }}>
                {stats.available}
              </div>
            </div>

            <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '10px', padding: '10px 12px' }}>
              <span style={{ fontSize: '0.72rem', color: '#991b1b', fontWeight: 600 }}>SEATED GUESTS</span>
              <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#b91c1c', marginTop: '2px' }}>
                {stats.seated}
              </div>
            </div>

            <div style={{ background: '#fefce8', border: '1px solid #fef08a', borderRadius: '10px', padding: '10px 12px' }}>
              <span style={{ fontSize: '0.72rem', color: '#854d0e', fontWeight: 600 }}>RESERVED</span>
              <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#ca8a04', marginTop: '2px' }}>
                {stats.reserved}
              </div>
            </div>

            <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '10px', padding: '10px 12px' }}>
              <span style={{ fontSize: '0.72rem', color: '#475569', fontWeight: 600 }}>CLEANING</span>
              <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#64748b', marginTop: '2px' }}>
                {stats.cleaning}
              </div>
            </div>
          </div>

          {/* Quick Action Button */}
          <div style={{ marginBottom: '12px' }}>
            <button
              type="button"
              onClick={() => setActiveTab('seat')}
              className="btn btn-primary btn-block"
              style={{
                background: '#047857',
                borderColor: '#047857',
                padding: '10px',
                fontSize: '0.88rem',
                fontWeight: 700,
                borderRadius: '10px',
                minHeight: '44px',
              }}
            >
              + Seat Walk-in Party ({availableTables.length} Tables Open)
            </button>
          </div>

          {/* Table List with Instant Status Toggles */}
          <div style={{ background: '#ffffff', borderRadius: '12px', border: '1px solid var(--border)', padding: '10px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <strong style={{ fontSize: '0.85rem' }}>Dining Tables ({tables.length})</strong>
              <Link to="/floor" style={{ fontSize: '0.75rem', color: 'var(--primary)', textDecoration: 'none', fontWeight: 600 }}>
                Interactive Floor ◫
              </Link>
            </div>

            {loading ? (
              <p style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '1rem' }}>Loading tables...</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {tables.map((t) => {
                  const isAvailable = t.status === 'AVAILABLE'
                  const isCleaning = t.status === 'CLEANING'

                  return (
                    <div
                      key={t.id}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '8px 10px',
                        borderRadius: '8px',
                        background: isAvailable ? '#f0fdf4' : isCleaning ? '#fffbeb' : 'var(--surface-2)',
                        border: '1px solid var(--border)',
                      }}
                    >
                      <div>
                        <strong style={{ fontSize: '0.88rem', color: '#0f172a' }}>Table {t.number}</strong>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginLeft: '6px' }}>
                          ({t.capacity} seats)
                        </span>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span
                          className={`role-badge role-${(t.status || 'available').toLowerCase()}`}
                          style={{ fontSize: '0.68rem', padding: '2px 6px' }}
                        >
                          {t.status}
                        </span>

                        {isCleaning && (
                          <button
                            type="button"
                            onClick={() => handleMarkCleaned(t.id)}
                            style={{
                              background: '#16a34a',
                              color: '#fff',
                              border: 'none',
                              borderRadius: '6px',
                              padding: '4px 8px',
                              fontSize: '0.72rem',
                              fontWeight: 700,
                              cursor: 'pointer',
                            }}
                          >
                            Mark Ready ✓
                          </button>
                        )}

                        {isAvailable && (
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedTableId(t.id)
                              setSeatPartySize(t.capacity)
                              setActiveTab('seat')
                            }}
                            style={{
                              background: '#047857',
                              color: '#fff',
                              border: 'none',
                              borderRadius: '6px',
                              padding: '4px 8px',
                              fontSize: '0.72rem',
                              fontWeight: 700,
                              cursor: 'pointer',
                            }}
                          >
                            Seat →
                          </button>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ─── TAB 2: FAST WALK-IN SEATING (OPTIMIZED FOR PHONE) ─── */}
      {activeTab === 'seat' && (
        <div style={{ background: '#ffffff', borderRadius: '14px', border: '1px solid var(--border)', padding: '14px' }}>
          <h3 style={{ fontSize: '1.05rem', margin: '0 0 10px', color: '#047857', fontWeight: 700 }}>
            🪑 Fast Walk-In Seating
          </h3>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: '0 0 12px' }}>
            Select party size and assign an available table instantly.
          </p>

          <form onSubmit={handleFastSeat}>
            {/* Party Size Selector */}
            <div style={{ marginBottom: '14px' }}>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, marginBottom: '6px' }}>
                Party Size (Guests):
              </label>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                {[1, 2, 3, 4, 5, 6, 8].map((size) => (
                  <button
                    key={size}
                    type="button"
                    onClick={() => {
                      setSeatPartySize(size)
                      // Auto select first matching table
                      const match = availableTables.find((t) => t.capacity >= size)
                      if (match) setSelectedTableId(match.id)
                    }}
                    style={{
                      flex: 1,
                      minWidth: '40px',
                      padding: '8px 4px',
                      borderRadius: '8px',
                      border: '1.5px solid',
                      borderColor: seatPartySize === size ? '#047857' : 'var(--border)',
                      background: seatPartySize === size ? '#ecfdf5' : '#ffffff',
                      color: seatPartySize === size ? '#047857' : 'var(--text)',
                      fontWeight: 800,
                      fontSize: '0.9rem',
                      cursor: 'pointer',
                    }}
                  >
                    {size}
                  </button>
                ))}
              </div>
            </div>

            {/* Guest Name Input */}
            <div style={{ marginBottom: '14px' }}>
              <label htmlFor="host-seat-guest-name" style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, marginBottom: '4px' }}>
                Guest / Party Name:
              </label>
              <input
                id="host-seat-guest-name"
                name="hostSeatGuestName"
                aria-label="Guest or Party Name"
                type="text"
                placeholder="e.g. Smith (or leave blank)"
                value={seatGuestName}
                onChange={(e) => setSeatGuestName(e.target.value)}
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  borderRadius: '8px',
                  border: '1px solid var(--border)',
                  fontSize: '0.88rem',
                }}
              />
            </div>

            {/* Table Selection Cards */}
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, marginBottom: '6px' }}>
                Choose Available Table ({matchingTables.length} matching {seatPartySize}+ seats):
              </label>

              {matchingTables.length === 0 ? (
                <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px', padding: '10px', fontSize: '0.8rem', color: '#991b1b' }}>
                  ⚠️ No open tables currently have {seatPartySize}+ capacity. Please check cleaning or billing tables.
                </div>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px' }}>
                  {matchingTables.map((t) => {
                    const isSelected = selectedTableId === t.id
                    return (
                      <div
                        key={t.id}
                        onClick={() => setSelectedTableId(t.id)}
                        style={{
                          padding: '10px',
                          borderRadius: '10px',
                          border: '2px solid',
                          borderColor: isSelected ? '#047857' : 'var(--border)',
                          background: isSelected ? '#ecfdf5' : '#ffffff',
                          cursor: 'pointer',
                          textAlign: 'center',
                        }}
                      >
                        <strong style={{ fontSize: '0.95rem', color: isSelected ? '#047857' : '#0f172a' }}>
                          Table {t.number}
                        </strong>
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                          Capacity: {t.capacity}p
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={seatingLoading || !selectedTableId}
              className="btn btn-primary btn-block"
              style={{
                background: '#047857',
                borderColor: '#047857',
                padding: '12px',
                fontSize: '0.95rem',
                fontWeight: 800,
                borderRadius: '10px',
                minHeight: '48px',
                cursor: seatingLoading || !selectedTableId ? 'not-allowed' : 'pointer',
              }}
            >
              {seatingLoading ? 'Seating Party...' : '🪑 Seat Guests Now'}
            </button>
          </form>
        </div>
      )}

      {/* ─── TAB 3: RESERVATIONS STAND ─── */}
      {activeTab === 'reservations' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <strong style={{ fontSize: '0.9rem' }}>Active Reservations</strong>
            <Link to="/reservations" style={{ fontSize: '0.75rem', color: 'var(--primary)', textDecoration: 'none', fontWeight: 600 }}>
              Full Stand 📅
            </Link>
          </div>

          {reservations.length === 0 ? (
            <div
              style={{
                textAlign: 'center',
                padding: '2.5rem 1rem',
                background: '#ffffff',
                borderRadius: '14px',
                border: '1px dashed var(--border)',
              }}
            >
              <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>📅</div>
              <strong style={{ display: 'block', fontSize: '0.95rem' }}>No Active Reservations</strong>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                Upcoming table reservations will be listed here with quick seating options.
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {reservations.map((r) => {
                const targetTable = tables.find((t) => t.id === r.tableId)
                const tableNumber = targetTable?.number || String(r.tableId).replace('t-', '')

                return (
                  <div
                    key={r.id}
                    style={{
                      background: '#ffffff',
                      border: '1px solid var(--border)',
                      borderRadius: '10px',
                      padding: '10px 12px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div>
                        <strong style={{ fontSize: '0.9rem', color: '#0f172a' }}>{r.guestName}</strong>
                        <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                          Party of {r.partySize} • Assigned Table {tableNumber}
                        </div>
                      </div>
                      <span
                        style={{
                          background: '#fef3c7',
                          color: '#92400e',
                          fontWeight: 700,
                          fontSize: '0.68rem',
                          padding: '2px 6px',
                          borderRadius: '4px',
                        }}
                      >
                        RESERVED
                      </span>
                    </div>

                    <div style={{ marginTop: '8px', display: 'flex', gap: '6px' }}>
                      <button
                        type="button"
                        onClick={() => handleSeatReservation(r)}
                        className="btn btn-primary"
                        style={{
                          flex: 1,
                          background: '#047857',
                          borderColor: '#047857',
                          padding: '6px',
                          fontSize: '0.78rem',
                          fontWeight: 700,
                          minHeight: '36px',
                        }}
                      >
                        Seat Party ✓
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* Quick Navigation Footer */}
      <div
        style={{
          marginTop: '1.5rem',
          paddingTop: '1rem',
          borderTop: '1px solid var(--border)',
          display: 'flex',
          justifyContent: 'space-around',
        }}
      >
        <Link
          to="/floor"
          style={{ textDecoration: 'none', color: 'var(--text-muted)', fontSize: '0.78rem', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px' }}
        >
          <span style={{ fontSize: '1.2rem' }}>◫</span>
          <span>Seating Plan</span>
        </Link>
        <Link
          to="/reservations"
          style={{ textDecoration: 'none', color: 'var(--text-muted)', fontSize: '0.78rem', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px' }}
        >
          <span style={{ fontSize: '1.2rem' }}>📅</span>
          <span>Bookings</span>
        </Link>
        <Link
          to="/booking"
          style={{ textDecoration: 'none', color: 'var(--text-muted)', fontSize: '0.78rem', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px' }}
        >
          <span style={{ fontSize: '1.2rem' }}>🤖</span>
          <span>AI Waitlist</span>
        </Link>
      </div>
    </PhoneFrameContainer>
  )
}
