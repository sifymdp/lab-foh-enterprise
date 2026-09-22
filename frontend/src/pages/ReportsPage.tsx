import { useState } from 'react'
import { aiApi, type ShiftReport } from '../api/extensions'

export function ReportsPage() {
  const [report, setReport] = useState<ShiftReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [date, setDate] = useState(new Date().toISOString().split('T')[0])

  const handleGenerate = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await aiApi.getShiftReport(date)
      setReport(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to generate report')
    } finally {
      setLoading(false)
    }
  }

  const stats = report?.stats as Record<string, unknown> | undefined

  return (
    <div style={{ padding: '0 24px 40px' }}>
      <div className="page-header" style={{ padding: '24px 0 20px' }}>
        <div>
          <h2 style={{ margin: 0 }}>Shift Reports</h2>
          <p className="muted" style={{ margin: '4px 0 0' }}>Llama writes a plain-English summary from today's session data</p>
        </div>
      </div>

      {error && (
        <div style={{ background: '#fee', border: '1px solid #fcc', borderRadius: 8, padding: '10px 16px', marginBottom: 16, color: '#c00' }}>
          {error}
        </div>
      )}

      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 24 }}>
        <input
          type="date"
          className="input"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          style={{ width: 180 }}
        />
        <button className="btn btn-primary" onClick={handleGenerate} disabled={loading}>
          {loading ? 'Generating…' : 'Generate report'}
        </button>
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#888' }}>
          <div className="spinner" style={{ margin: '0 auto 12px' }} />
          <p>Llama is writing your shift summary…</p>
        </div>
      )}

      {report && !loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Stats grid */}
          {stats && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12 }}>
              {[
                { label: 'Total covers', value: String(stats.total_covers ?? 0) },
                { label: 'Sessions', value: String(stats.total_sessions ?? 0) },
                { label: 'Avg duration', value: `${Math.round(Number(stats.avg_duration_minutes ?? 0))} min` },
                { label: 'Peak hour', value: String(stats.peak_hour ?? 'N/A') },
                { label: 'Wait alerts', value: String(stats.wait_alerts ?? 0) },
                { label: 'Revenue', value: `₹${Number(stats.total_revenue ?? 0).toFixed(2)}` },
              ].map(({ label, value }) => (
                <div key={label} style={{
                  background: '#fff', border: '1px solid #eee', borderRadius: 10,
                  padding: '14px 16px', textAlign: 'center',
                }}>
                  <div style={{ fontSize: 22, fontWeight: 700, color: '#1a1a1a' }}>{value}</div>
                  <div style={{ fontSize: 12, color: '#888', marginTop: 2 }}>{label}</div>
                </div>
              ))}
            </div>
          )}

          {/* Llama summary */}
          <div style={{
            background: '#fff', border: '1px solid #eee', borderRadius: 10, padding: 20,
            borderLeft: '4px solid #1a73e8',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: '#1a73e8' }}>AI Summary</span>
              <span style={{ fontSize: 12, color: '#888' }}>— {report.reportDate}</span>
            </div>
            <p style={{ margin: 0, fontSize: 14, lineHeight: 1.7, color: '#333', whiteSpace: 'pre-wrap' }}>
              {report.content}
            </p>
          </div>
        </div>
      )}

      {!report && !loading && (
        <div style={{ textAlign: 'center', padding: '60px 0', color: '#888' }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>📊</div>
          <p style={{ fontSize: 16 }}>Select a date and generate your shift report</p>
          <p style={{ fontSize: 13 }}>Llama reads session data and writes a plain-English summary</p>
        </div>
      )}
    </div>
  )
}
