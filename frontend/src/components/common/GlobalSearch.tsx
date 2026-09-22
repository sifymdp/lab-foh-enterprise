import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import { reservationsApi } from '../../api/extensions'

interface SearchResult {
  id: string
  type: 'table' | 'bill' | 'reservation' | 'order'
  title: string
  subtitle: string
  link: string
}

export function GlobalSearch() {
  const [isOpen, setIsOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)

  // Keyboard shortcut Ctrl+K / Cmd+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setIsOpen((prev) => !prev)
      } else if (e.key === 'Escape') {
        setIsOpen(false)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50)
    } else {
      setQuery('')
      setResults([])
    }
  }, [isOpen])

  useEffect(() => {
    if (!query.trim()) {
      setResults([])
      return
    }

    const timer = setTimeout(async () => {
      try {
        setLoading(true)
        const q = query.toLowerCase().trim()
        const [floorRes, bills, resList] = await Promise.all([
          api.getFloor().catch(() => null),
          api.getBills().catch(() => []),
          reservationsApi.list().catch(() => []),
        ])

        const tables = floorRes?.tables || []
        const reservations = Array.isArray(resList) ? resList : []
        const matched: SearchResult[] = []

        // Search Tables
        for (const t of (tables as any[])) {
          if (
            t.number?.toLowerCase().includes(q) ||
            t.id?.toLowerCase().includes(q) ||
            t.status?.toLowerCase().includes(q)
          ) {
            matched.push({
              id: t.id,
              type: 'table',
              title: `Table ${t.number}`,
              subtitle: `Status: ${t.status} | Capacity: ${t.capacity}`,
              link: '/floor',
            })
          }
        }

        // Search Bills
        for (const b of (bills as any[])) {
          const bNum = b.billNumber || b.bill_number || b.id
          if (bNum.toLowerCase().includes(q) || b.status?.toLowerCase().includes(q)) {
            matched.push({
              id: b.id,
              type: 'bill',
              title: `Bill ${bNum}`,
              subtitle: `Status: ${b.status} | Total: ₹${Number(b.total || 0).toFixed(2)}`,
              link: `/billing/${b.id}`,
            })
          }
        }

        // Search Reservations
        for (const r of (reservations as any[])) {
          if (
            r.guestName?.toLowerCase().includes(q) ||
            r.guest_name?.toLowerCase().includes(q) ||
            r.notes?.toLowerCase().includes(q)
          ) {
            matched.push({
              id: r.id,
              type: 'reservation',
              title: `Reservation: ${r.guestName || r.guest_name}`,
              subtitle: `Party: ${r.partySize || r.party_size} | Status: ${r.status}`,
              link: '/reservations',
            })
          }
        }

        setResults(matched.slice(0, 8))
      } catch (err) {
        console.error('Search error', err)
      } finally {
        setLoading(false)
      }
    }, 200)

    return () => clearTimeout(timer)
  }, [query])

  const handleSelect = (result: SearchResult) => {
    setIsOpen(false)
    navigate(result.link)
  }

  return (
    <>
      {/* Search trigger button */}
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          padding: '0.35rem 0.75rem',
          borderRadius: 'var(--radius)',
          border: '1px solid var(--border)',
          background: 'var(--surface-2)',
          color: 'var(--text-secondary)',
          cursor: 'pointer',
          fontSize: '0.85rem',
        }}
        title="Global Search (Ctrl+K)"
      >
        <span>🔍</span>
        <span>Quick Search...</span>
        <kbd
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            borderRadius: '4px',
            padding: '0.1rem 0.35rem',
            fontSize: '0.7rem',
            color: 'var(--text-muted)',
          }}
        >
          Ctrl+K
        </kbd>
      </button>

      {/* Modal Dialog */}
      {isOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.65)',
            backdropFilter: 'blur(4px)',
            zIndex: 9999,
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'center',
            paddingTop: '12vh',
          }}
          onClick={() => setIsOpen(false)}
        >
          <div
            style={{
              background: 'var(--bg-elevated, #ffffff)',
              border: '1px solid var(--border, #e2e8f0)',
              borderRadius: '12px',
              width: '100%',
              maxWidth: '560px',
              boxShadow: '0 20px 40px rgba(0,0,0,0.2)',
              overflow: 'hidden',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', alignItems: 'center', padding: '0.75rem 1rem', borderBottom: '1px solid var(--border)' }}>
              <span style={{ fontSize: '1.2rem', marginRight: '0.5rem' }}>🔍</span>
              <input
                ref={inputRef}
                type="text"
                placeholder="Search tables, bills, orders, or guests..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                style={{
                  border: 'none',
                  outline: 'none',
                  width: '100%',
                  fontSize: '1rem',
                  background: 'transparent',
                  color: 'inherit',
                }}
              />
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                style={{ background: 'transparent', border: 'none', cursor: 'pointer', fontSize: '1.1rem', color: 'var(--text-muted)' }}
              >
                ✕
              </button>
            </div>

            <div style={{ maxHeight: '360px', overflowY: 'auto', padding: '0.5rem' }}>
              {loading && <p style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-muted)', margin: 0 }}>Searching...</p>}
              {!loading && query.trim() && results.length === 0 && (
                <p style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-muted)', margin: 0 }}>No matches found</p>
              )}
              {!loading && !query.trim() && (
                <p style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-muted)', margin: 0, fontSize: '0.85rem' }}>
                  Type a table number, bill ID, or guest name to quickly jump to it.
                </p>
              )}

              {results.map((r) => (
                <div
                  key={`${r.type}-${r.id}`}
                  onClick={() => handleSelect(r)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0.65rem 0.85rem',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-2, #f1f5f9)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  <div>
                    <strong style={{ display: 'block', fontSize: '0.95rem' }}>{r.title}</strong>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{r.subtitle}</span>
                  </div>
                  <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', opacity: 0.6 }}>
                    {r.type} &rarr;
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
