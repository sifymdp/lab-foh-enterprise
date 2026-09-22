import { useEffect, useState } from 'react'
import { aiApi } from '../../api/extensions'

interface Props {
  onClose: () => void
}

export function SeatingSuggestModal({ onClose }: Props) {
  const [partySize, setPartySize] = useState(2)
  const [suggestion, setSuggestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const handleSuggest = async () => {
    setLoading(true)
    setError('')
    setSuggestion('')
    try {
      const res = await aiApi.suggestSeating(partySize)
      setSuggestion(res.suggestion)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not get suggestion')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      role="presentation"
      onClick={onClose}
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
    >
      <div
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
        style={{ background: '#fff', borderRadius: 12, padding: 24, width: '100%', maxWidth: 480, boxShadow: '0 20px 60px rgba(0,0,0,0.2)' }}
      >
        <h3 style={{ margin: '0 0 16px', fontSize: 18 }}>Suggest seating</h3>
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', marginBottom: 16 }}>
          <div style={{ flex: 1 }}>
            <label style={{ fontSize: 13, fontWeight: 500, display: 'block', marginBottom: 4 }}>Party size</label>
            <input
              className="input"
              type="number"
              min={1}
              max={20}
              value={partySize}
              onChange={(e) => setPartySize(parseInt(e.target.value) || 1)}
              style={{ width: '100%' }}
            />
          </div>
          <button type="button" className="btn btn-primary" onClick={handleSuggest} disabled={loading}>
            {loading ? 'Thinking…' : 'Suggest'}
          </button>
        </div>
        {error && <p className="form-error">{error}</p>}
        {suggestion && (
          <p style={{ margin: '0 0 16px', fontSize: 14, lineHeight: 1.7, color: '#334155', whiteSpace: 'pre-wrap' }}>
            {suggestion}
          </p>
        )}
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button type="button" className="btn btn-ghost" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  )
}
