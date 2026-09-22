import { useState } from 'react'
import type { Floor, FloorLabel, FloorLabelKind, RectBounds, Section } from '../../types'
type LayoutSelection = { type: 'section'; id: string } | { type: 'label'; id: string }

interface LayoutEditorPanelProps {
  floor: Floor
  selection: LayoutSelection
  onClose: () => void
  onSaveFloor: (floor: Floor) => Promise<void>
}

export function LayoutEditorPanel({
  floor,
  selection,
  onClose,
  onSaveFloor,
}: LayoutEditorPanelProps) {
  const [error, setError] = useState<string | null>(null)

  async function patchFloor(updater: (f: Floor) => Floor) {
    setError(null)
    try {
      await onSaveFloor(updater(floor))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed')
    }
  }

  if (selection.type === 'section') {
    const section = floor.sections.find((s) => s.id === selection.id)
    if (!section) return null
    return (
      <SectionPanel
        section={section}
        floor={floor}
        onClose={onClose}
        onPatch={patchFloor}
        error={error}
        setError={setError}
      />
    )
  }

  if (selection.type === 'label') {
    const label = floor.labels.find((l) => l.id === selection.id)
    if (!label) return null
    return (
      <LabelPanel
        label={label}
        onClose={onClose}
        onPatch={patchFloor}
        error={error}
        setError={setError}
      />
    )
  }

  return null
}

function PanelHeader({
  title,
  subtitle,
  onClose,
}: {
  title: string
  subtitle?: string
  onClose: () => void
}) {
  return (
    <div className="panel-header">
      <div>
        {subtitle && <p className="panel-eyebrow">{subtitle}</p>}
        <h2>{title}</h2>
      </div>
      <button type="button" className="btn-icon" onClick={onClose} aria-label="Close">
        ×
      </button>
    </div>
  )
}

function SectionPanel({
  section,
  floor,
  onClose,
  onPatch,
  error,
  setError,
}: {
  section: Section
  floor: Floor
  onClose: () => void
  onPatch: (u: (f: Floor) => Floor) => Promise<void>
  error: string | null
  setError: (s: string | null) => void
}) {
  const [name, setName] = useState(section.name)
  const [color, setColor] = useState(section.color)

  return (
    <aside className="table-panel layout-panel">
      <PanelHeader title="Dining section" subtitle="Layout" onClose={onClose} />
      <p className="muted panel-hint">Drag to move · corner handle to expand or shrink the zone.</p>
      <label className="field">
        <span>Name</span>
        <input
          className="input"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onBlur={() =>
            onPatch((f) => ({
              ...f,
              sections: f.sections.map((s) =>
                s.id === section.id ? { ...s, name } : s,
              ),
            }))
          }
        />
      </label>
      <label className="field">
        <span>Border color</span>
        <input
          type="color"
          className="input input-color"
          value={color}
          onChange={(e) => {
            setColor(e.target.value)
            onPatch((f) => ({
              ...f,
              sections: f.sections.map((s) =>
                s.id === section.id ? { ...s, color: e.target.value } : s,
              ),
            }))
          }}
        />
      </label>
      <BoundsFields
        bounds={section.bounds}
        onChange={(bounds) =>
          onPatch((f) => ({
            ...f,
            sections: f.sections.map((s) => (s.id === section.id ? { ...s, bounds } : s)),
          }))
        }
      />
      <button
        type="button"
        className="btn btn-ghost btn-block layout-delete-btn"
        onClick={async () => {
          const inSection = floor.tables.filter((t) => t.sectionId === section.id)
          const msg =
            inSection.length > 0
              ? `Remove "${section.name}"? ${inSection.length} table(s) will be deleted too.`
              : `Remove section "${section.name}"?`
          if (!confirm(msg)) return
          setError(null)
          try {
            await onPatch((f) => ({
              ...f,
              sections: f.sections.filter((s) => s.id !== section.id),
              tables: f.tables.filter((t) => t.sectionId !== section.id),
            }))
            onClose()
          } catch (e) {
            setError(e instanceof Error ? e.message : 'Could not remove section')
          }
        }}
      >
        Remove section
      </button>
      {error && <p className="form-error">{error}</p>}
    </aside>
  )
}

function LabelPanel({
  label,
  onClose,
  onPatch,
  error,
  setError,
}: {
  label: FloorLabel
  onClose: () => void
  onPatch: (u: (f: Floor) => Floor) => Promise<void>
  error: string | null
  setError: (s: string | null) => void
}) {
  const [text, setText] = useState(label.text)

  return (
    <aside className="table-panel layout-panel">
      <PanelHeader title="Floor marker" subtitle={label.kind} onClose={onClose} />
      <p className="muted panel-hint">Entrance, kitchen, bar, or custom areas on your floor plan.</p>
      <label className="field">
        <span>Label text</span>
        <input
          className="input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onBlur={() =>
            onPatch((f) => ({
              ...f,
              labels: f.labels.map((l) => (l.id === label.id ? { ...l, text } : l)),
            }))
          }
        />
      </label>
      <BoundsFields
        bounds={label.bounds}
        onChange={(bounds) =>
          onPatch((f) => ({
            ...f,
            labels: f.labels.map((l) => (l.id === label.id ? { ...l, bounds } : l)),
          }))
        }
      />
      <button
        type="button"
        className="btn btn-ghost btn-block layout-delete-btn"
        onClick={async () => {
          if (!confirm(`Remove "${label.text}" marker?`)) return
          try {
            await onPatch((f) => ({
              ...f,
              labels: f.labels.filter((l) => l.id !== label.id),
            }))
            onClose()
          } catch (e) {
            setError(e instanceof Error ? e.message : 'Could not remove marker')
          }
        }}
      >
        Remove marker
      </button>
      {error && <p className="form-error">{error}</p>}
    </aside>
  )
}

function BoundsFields({
  bounds,
  onChange,
}: {
  bounds: RectBounds
  onChange: (b: RectBounds) => void
}) {
  const set = (key: keyof RectBounds, val: number) =>
    onChange({ ...bounds, [key]: val })

  return (
    <div className="layout-fields layout-fields--grid">
      <label className="field">
        <span>X</span>
        <input
          type="number"
          className="input"
          value={Math.round(bounds.x)}
          onChange={(e) => set('x', Number(e.target.value))}
        />
      </label>
      <label className="field">
        <span>Y</span>
        <input
          type="number"
          className="input"
          value={Math.round(bounds.y)}
          onChange={(e) => set('y', Number(e.target.value))}
        />
      </label>
      <label className="field">
        <span>Width</span>
        <input
          type="number"
          className="input"
          min={40}
          value={Math.round(bounds.width)}
          onChange={(e) => set('width', Number(e.target.value))}
        />
      </label>
      <label className="field">
        <span>Height</span>
        <input
          type="number"
          className="input"
          min={40}
          value={Math.round(bounds.height)}
          onChange={(e) => set('height', Number(e.target.value))}
        />
      </label>
    </div>
  )
}

export function FloorLayoutToolbar({
  floor,
  editable,
  onAddSection,
  onAddLabel,
  onReset,
  onCanvasSize,
}: {
  floor: Floor
  editable: boolean
  onAddSection: () => void
  onAddLabel: (kind: FloorLabelKind) => void
  onReset: () => void
  onCanvasSize: (w: number, h: number) => void
}) {
  if (!editable) return null

  return (
    <div className="floor-layout-toolbar">
      <span className="floor-layout-toolbar__title">Layout editor</span>
      <div className="floor-layout-toolbar__actions">
        <button type="button" className="btn btn-secondary btn-sm" onClick={onAddSection}>
          + Section
        </button>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => onAddLabel('ENTRANCE')}
        >
          + Entrance
        </button>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => onAddLabel('KITCHEN')}
        >
          + Kitchen
        </button>
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => onAddLabel('BAR')}>
          + Bar area
        </button>
        <label className="canvas-size-field">
          <span>W</span>
          <input
            type="number"
            className="input input-xs"
            value={floor.width}
            onChange={(e) => onCanvasSize(Number(e.target.value), floor.height)}
          />
        </label>
        <label className="canvas-size-field">
          <span>H</span>
          <input
            type="number"
            className="input input-xs"
            value={floor.height}
            onChange={(e) => onCanvasSize(floor.width, Number(e.target.value))}
          />
        </label>
        <button type="button" className="btn btn-ghost btn-sm layout-reset-btn" onClick={onReset}>
          Start fresh
        </button>
      </div>
    </div>
  )
}
