import { useEffect, useState } from 'react'
import { api } from '../api/client'

/* ─── Types ─────────────────────────────────────────────────────────── */
interface Stage {
  stage: string
  icon: string
  current_min: number | null
  baseline_min: number | null
  pct_change: number | null
  severity: 'ok' | 'warning' | 'alert' | 'info'
  sample_count: number
  insight: string
}

interface SummaryBullet {
  level: 'ok' | 'warning' | 'alert' | 'info'
  text: string
}

interface Insights {
  generated_at: string
  overall_status: 'ok' | 'warning' | 'alert'
  occupancy: { total: number; active: number; cleaning: number; pct: number }
  upcoming_reservations: { guest: string; party_size: number; reserved_for: string }[]
  wait_time_estimate: { low: number; high: number; confidence: string; note: string }
  stages: Stage[]
  summary: SummaryBullet[]
  baseline_days: number
}

/* ─── Helpers ───────────────────────────────────────────────────────── */
const SEV_COLOR: Record<string, string>  = { alert: '#dc2626', warning: '#d97706', ok: '#16a34a', info: '#3b82f6' }
const SEV_BG:    Record<string, string>  = { alert: '#fef2f2', warning: '#fffbeb', ok:  '#f0fdf4', info: '#eff6ff' }
const SEV_BORDER:Record<string, string>  = { alert: '#fca5a5', warning: '#fcd34d', ok:  '#bbf7d0', info: '#bfdbfe' }
const SEV_ICON:  Record<string, string>  = { alert: '⚠️',       warning: '⚠',       ok:  '✓',       info: 'ℹ️' }

const CONF_COLOR: Record<string, string> = { high: '#16a34a', medium: '#d97706', low: '#dc2626' }

function fmt(min: number | null | undefined): string {
  if (min === null || min === undefined) return '—'
  return `${min} min`
}

function fmtPct(pct: number | null | undefined): string {
  if (pct === null || pct === undefined) return '—'
  const sign = pct >= 0 ? '+' : ''
  return `${sign}${pct}%`
}

function fmtTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
  } catch { return iso }
}

/* ─── Component ─────────────────────────────────────────────────────── */
export function InsightsPage() {
  const [data, setData]         = useState<Insights | null>(null)
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState<string | null>(null)
  const [partySize, setPartySize] = useState(2)

  useEffect(() => { load() }, [partySize])

  const load = async () => {
    setLoading(true); setError(null)
    try {
      const res = await api.getInsights(partySize)
      setData(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load insights')
    } finally {
      setLoading(false)
    }
  }

  const overallColor = data ? SEV_COLOR[data.overall_status] : '#6b7280'
  const overallLabel: Record<string, string> = { ok: 'All Systems Normal', warning: 'Some Issues Detected', alert: 'Operational Bottleneck' }

  return (
    <div style={{ padding: '1.75rem', maxWidth: '1100px', margin: '0 auto' }}>

      {/* ── Header ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.5rem' }}>
        <div>
          <h2 style={{ margin: 0 }}>Operational Insights</h2>
          <p className="muted" style={{ margin: '0.3rem 0 0' }}>
            Real-time analysis of your restaurant's workflow bottlenecks
          </p>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={load} disabled={loading}>
          {loading ? '↻ Refreshing…' : '↻ Refresh'}
        </button>
      </div>

      {error && (
        <div style={{ background: '#fef2f2', color: '#dc2626', padding: '0.75rem 1rem', borderRadius: '8px', border: '1px solid #fca5a5', marginBottom: '1rem' }}>
          ⚠ {error}
        </div>
      )}

      {loading && !data && (
        <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--text-muted)' }}>
          <div className="spinner" style={{ margin: '0 auto 0.75rem' }} />
          <p>Analysing today's operational data…</p>
        </div>
      )}

      {data && (
        <>
          {/* ══════════════════════════════════════════════════════
              ROW 1 — Overall status + Occupancy + Wait time
          ══════════════════════════════════════════════════════ */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>

            {/* Overall status */}
            <div style={{
              background: `${overallColor}12`, border: `2px solid ${overallColor}50`,
              borderRadius: '12px', padding: '1.25rem',
              display: 'flex', alignItems: 'center', gap: '1rem',
            }}>
              <span style={{ fontSize: '2.5rem' }}>
                {data.overall_status === 'ok' ? '✅' : data.overall_status === 'warning' ? '⚠️' : '🚨'}
              </span>
              <div>
                <p className="muted" style={{ margin: 0, fontSize: '0.78rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Status</p>
                <strong style={{ fontSize: '1rem', color: overallColor }}>{overallLabel[data.overall_status]}</strong>
                <p className="muted" style={{ margin: '0.2rem 0 0', fontSize: '0.78rem' }}>
                  Based on last {data.baseline_days}-day baseline
                </p>
              </div>
            </div>

            {/* Occupancy */}
            <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '12px', padding: '1.25rem' }}>
              <p className="muted" style={{ margin: '0 0 0.5rem', fontSize: '0.78rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Live Occupancy
              </p>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.35rem' }}>
                <span style={{ fontSize: '2rem', fontWeight: 800 }}>{data.occupancy.pct}%</span>
                <span className="muted" style={{ fontSize: '0.85rem' }}>({data.occupancy.active}/{data.occupancy.total} tables)</span>
              </div>
              {/* progress bar */}
              <div style={{ marginTop: '0.6rem', height: '6px', background: 'var(--border)', borderRadius: '3px', overflow: 'hidden' }}>
                <div style={{
                  height: '100%', width: `${data.occupancy.pct}%`,
                  background: data.occupancy.pct >= 90 ? '#dc2626' : data.occupancy.pct >= 75 ? '#d97706' : '#16a34a',
                  borderRadius: '3px', transition: 'width 0.4s',
                }} />
              </div>
              {data.occupancy.cleaning > 0 && (
                <p style={{ margin: '0.5rem 0 0', fontSize: '0.8rem', color: '#d97706' }}>
                  🧹 {data.occupancy.cleaning} table{data.occupancy.cleaning > 1 ? 's' : ''} cleaning
                </p>
              )}
            </div>

            {/* Walk-in wait time */}
            <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '12px', padding: '1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <p className="muted" style={{ margin: 0, fontSize: '0.78rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Walk-in Wait
                </p>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                  <span className="muted" style={{ fontSize: '0.75rem' }}>Party:</span>
                  <select
                    value={partySize}
                    onChange={e => setPartySize(Number(e.target.value))}
                    style={{ fontSize: '0.8rem', padding: '0.1rem 0.3rem', borderRadius: '4px', border: '1px solid var(--border)', background: 'var(--surface-2)' }}
                  >
                    {[1,2,3,4,5,6,8,10].map(n => <option key={n} value={n}>{n} pax</option>)}
                  </select>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.35rem' }}>
                <span style={{ fontSize: '1.9rem', fontWeight: 800 }}>
                  {data.wait_time_estimate.low === data.wait_time_estimate.high
                    ? `${data.wait_time_estimate.low}`
                    : `${data.wait_time_estimate.low}–${data.wait_time_estimate.high}`}
                </span>
                <span className="muted">min</span>
              </div>
              <p style={{ margin: '0.35rem 0 0', fontSize: '0.78rem', color: CONF_COLOR[data.wait_time_estimate.confidence] }}>
                ● {data.wait_time_estimate.confidence} confidence
              </p>
              <p className="muted" style={{ margin: '0.3rem 0 0', fontSize: '0.75rem' }}>{data.wait_time_estimate.note}</p>
            </div>
          </div>

          {/* ══════════════════════════════════════════════════════
              ROW 2 — Manager Summary bullets
          ══════════════════════════════════════════════════════ */}
          <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '12px', overflow: 'hidden', marginBottom: '1.5rem', boxShadow: 'var(--shadow-sm)' }}>
            <div style={{ padding: '0.85rem 1.25rem', background: 'var(--surface-2)', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <span style={{ fontSize: '1.1rem' }}>🧠</span>
              <strong>Today's AI Summary — What to look at</strong>
              <span className="muted" style={{ marginLeft: 'auto', fontSize: '0.78rem' }}>
                Updated {fmtTime(data.generated_at)}
              </span>
            </div>
            <div style={{ padding: '0.75rem 0' }}>
              {data.summary.map((b, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'flex-start', gap: '0.75rem',
                  padding: '0.6rem 1.25rem',
                  borderBottom: i < data.summary.length - 1 ? '1px solid var(--border)' : 'none',
                }}>
                  <span style={{ fontSize: '1rem', flexShrink: 0, marginTop: '1px' }}>{SEV_ICON[b.level]}</span>
                  <span style={{ fontSize: '0.88rem', color: SEV_COLOR[b.level], fontWeight: b.level === 'ok' ? 400 : 600 }}>
                    {b.text}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* ══════════════════════════════════════════════════════
              ROW 3 — Workflow Bottleneck stages
          ══════════════════════════════════════════════════════ */}
          <div style={{ marginBottom: '1.5rem' }}>
            <p style={{ margin: '0 0 0.75rem', fontSize: '0.78rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)' }}>
              Workflow Bottleneck Analysis
            </p>

            {/* Flow pipeline header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0', marginBottom: '1rem', overflowX: 'auto' }}>
              {['Booking', 'Seating', 'Ordering', 'Kitchen', 'Serving', 'Billing', 'Cleaning'].map((step, i, arr) => (
                <div key={step} style={{ display: 'flex', alignItems: 'center' }}>
                  <span style={{
                    fontSize: '0.78rem', fontWeight: 600,
                    padding: '0.25rem 0.65rem', borderRadius: '999px',
                    background: 'var(--surface-2)', border: '1px solid var(--border)',
                    color: 'var(--text-muted)', whiteSpace: 'nowrap',
                  }}>{step}</span>
                  {i < arr.length - 1 && (
                    <span style={{ color: 'var(--border)', fontSize: '1rem', margin: '0 0.2rem' }}>→</span>
                  )}
                </div>
              ))}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '0.85rem' }}>
              {data.stages.map(stage => (
                <div key={stage.stage} style={{
                  background: SEV_BG[stage.severity],
                  border: `1.5px solid ${SEV_BORDER[stage.severity]}`,
                  borderRadius: '10px', padding: '1rem',
                }}>
                  {/* Stage header */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.65rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                      <span style={{ fontSize: '1.25rem' }}>{stage.icon}</span>
                      <strong style={{ fontSize: '0.88rem' }}>{stage.stage}</strong>
                    </div>
                    <span style={{
                      fontSize: '0.72rem', fontWeight: 700, padding: '0.15rem 0.5rem', borderRadius: '999px',
                      background: SEV_BG[stage.severity],
                      color: SEV_COLOR[stage.severity],
                      border: `1px solid ${SEV_BORDER[stage.severity]}`,
                    }}>
                      {stage.severity.toUpperCase()}
                    </span>
                  </div>

                  {/* Metrics row */}
                  <div style={{ display: 'flex', gap: '1rem', marginBottom: '0.65rem' }}>
                    <div>
                      <p className="muted" style={{ margin: 0, fontSize: '0.72rem' }}>Today</p>
                      <strong style={{ fontSize: '1.1rem', color: SEV_COLOR[stage.severity] }}>
                        {fmt(stage.current_min)}
                      </strong>
                    </div>
                    <div>
                      <p className="muted" style={{ margin: 0, fontSize: '0.72rem' }}>Baseline</p>
                      <strong style={{ fontSize: '1.1rem' }}>{fmt(stage.baseline_min)}</strong>
                    </div>
                    <div>
                      <p className="muted" style={{ margin: 0, fontSize: '0.72rem' }}>Change</p>
                      <strong style={{ fontSize: '1.1rem', color: (stage.pct_change ?? 0) > 0 ? '#dc2626' : '#16a34a' }}>
                        {fmtPct(stage.pct_change)}
                      </strong>
                    </div>
                  </div>

                  {/* Insight text */}
                  <p style={{ margin: '0', fontSize: '0.8rem', color: SEV_COLOR[stage.severity], lineHeight: 1.4 }}>
                    {stage.insight}
                  </p>

                  {stage.sample_count > 0 && (
                    <p className="muted" style={{ margin: '0.4rem 0 0', fontSize: '0.72rem' }}>
                      Based on {stage.sample_count} data point{stage.sample_count !== 1 ? 's' : ''} today
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* ══════════════════════════════════════════════════════
              ROW 4 — Upcoming reservations
          ══════════════════════════════════════════════════════ */}
          {data.upcoming_reservations.length > 0 && (
            <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '12px', overflow: 'hidden', boxShadow: 'var(--shadow-sm)' }}>
              <div style={{ padding: '0.85rem 1.25rem', background: 'var(--surface-2)', borderBottom: '1px solid var(--border)' }}>
                <strong>📅 Upcoming Reservations (next 2 hours)</strong>
              </div>
              <div style={{ padding: '0.5rem 0' }}>
                {data.upcoming_reservations.map((r, i) => (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: '1rem',
                    padding: '0.6rem 1.25rem',
                    borderBottom: i < data.upcoming_reservations.length - 1 ? '1px solid var(--border)' : 'none',
                  }}>
                    <span style={{ fontSize: '1.1rem' }}>👥</span>
                    <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{r.guest}</span>
                    <span className="muted" style={{ fontSize: '0.82rem' }}>Party of {r.party_size}</span>
                    <span style={{ marginLeft: 'auto', fontWeight: 700, color: '#3b82f6', fontSize: '0.88rem' }}>
                      {fmtTime(r.reserved_for)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
