import { useState } from 'react'
import type { Floor, TableShape, TableType } from '../../types'

interface AddTableModalProps {
  floor: Floor
  onClose: () => void
  onAdd: (payload: {
    number: string
    capacity: number
    sectionId: string
    type: TableType
    shape: TableShape
  }) => Promise<unknown>
}

export function AddTableModal({ floor, onClose, onAdd }: AddTableModalProps) {
  const [number, setNumber] = useState('')
  const [capacity, setCapacity] = useState(4)
  const [sectionId, setSectionId] = useState(floor.sections[0]?.id ?? '')
  const [type, setType] = useState<TableType>('STANDARD')
  const [shape, setShape] = useState<TableShape>('RECTANGLE')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      await onAdd({ number, capacity, sectionId, type, shape })
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add table')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal">
        <h3>Add table</h3>
        <form onSubmit={handleSubmit}>
          <label className="field" htmlFor="add-table-number">
            <span>Table number</span>
            <input
              id="add-table-number"
              name="tableNumber"
              aria-label="Table number"
              className="input"
              value={number}
              onChange={(e) => setNumber(e.target.value)}
              required
              placeholder="e.g. 12"
            />
          </label>
          <label className="field" htmlFor="add-table-capacity">
            <span>Capacity</span>
            <input
              id="add-table-capacity"
              name="tableCapacity"
              aria-label="Table capacity"
              type="number"
              className="input"
              min={1}
              max={20}
              value={capacity}
              onChange={(e) => setCapacity(Number(e.target.value))}
              required
            />
          </label>
          <label className="field" htmlFor="add-table-section">
            <span>Section</span>
            <select
              id="add-table-section"
              name="tableSection"
              aria-label="Table section"
              className="input"
              value={sectionId}
              onChange={(e) => setSectionId(e.target.value)}
            >
              {floor.sections.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field" htmlFor="add-table-type">
            <span>Type</span>
            <select
              id="add-table-type"
              name="tableType"
              aria-label="Table type"
              className="input"
              value={type}
              onChange={(e) => setType(e.target.value as TableType)}
            >
              <option value="STANDARD">Standard</option>
              <option value="BOOTH">Booth</option>
              <option value="BAR">Bar</option>
              <option value="VIP">VIP</option>
            </select>
          </label>
          <label className="field" htmlFor="add-table-shape">
            <span>Shape</span>
            <select
              id="add-table-shape"
              name="tableShape"
              aria-label="Table shape"
              className="input"
              value={shape}
              onChange={(e) => setShape(e.target.value as TableShape)}
            >
              <option value="RECTANGLE">Rectangle</option>
              <option value="CIRCLE">Circle</option>
            </select>
          </label>
          {error && <p className="form-error">{error}</p>}
          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Adding…' : 'Add table'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
