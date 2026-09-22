import { useCallback, useRef } from 'react'
import { SECTION_ICONS } from '../../services/tableConfig'
import { getCanvasPoint, hitTestCanvas, type CanvasSelection } from '../../lib/canvasHitTest'
import type { DiningSession, Floor, FloorLabel, RectBounds, Section, Table } from '../../types'
import { BoundsBox } from './BoundsBox'
import { TableMarker } from './TableMarker'

export type { CanvasSelection }

interface FloorPlanCanvasProps {
  floor: Floor
  sessions: DiningSession[]
  editable: boolean
  selection: CanvasSelection
  onSelect: (sel: CanvasSelection) => void
  onTableChange: (tableId: string, patch: Partial<Table>) => void
  onSectionChange: (sectionId: string, bounds: RectBounds) => void
  onLabelChange: (labelId: string, bounds: RectBounds) => void
}

export function FloorPlanCanvas({
  floor,
  sessions,
  editable,
  selection,
  onSelect,
  onTableChange,
  onSectionChange,
  onLabelChange,
}: FloorPlanCanvasProps) {
  const canvasRef = useRef<HTMLDivElement>(null)

  const handleTablePatch = useCallback(
    (tableId: string, patch: Partial<Table>) => {
      onTableChange(tableId, patch)
    },
    [onTableChange],
  )

  const handleCanvasPointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (!canvasRef.current) return
      const target = e.target as HTMLElement
      if (target.closest('.resize-handle')) return
      if (target.closest('.table-marker')) return
      if (target.closest('.section-edge')) return
      if (target.closest('.bounds-box__drag-bar')) return

      const { x, y } = getCanvasPoint(e, canvasRef.current)
      const hit = hitTestCanvas(floor, x, y)

      if (hit?.type === 'table') return

      if (hit) {
        e.stopPropagation()
        onSelect(hit)
      } else if (target === canvasRef.current || target.classList.contains('floor-plan-grid')) {
        onSelect(null)
      }
    },
    [floor, onSelect],
  )

  const labelClass = (kind: FloorLabel['kind']) => {
    if (kind === 'ENTRANCE') return 'floor-label floor-label--entrance'
    if (kind === 'KITCHEN') return 'floor-label floor-label--kitchen'
    if (kind === 'BAR') return 'floor-label floor-label--bar'
    return 'floor-label floor-label--custom'
  }

  const tableNodes = floor.tables.map((table) => {
    const session = sessions.find(
      (s) =>
        s.tableId === table.id && ['SEATED', 'ACTIVE', 'BILLING', 'PAID'].includes(s.status),
    )
    return (
      <TableMarker
        key={table.id}
        table={table}
        session={session}
        selected={selection?.type === 'table' && selection.id === table.id}
        editable={editable}
        onSelect={(id) => onSelect({ type: 'table', id })}
        onPatch={handleTablePatch}
      />
    )
  })

  const sectionNodes = floor.sections.map((section: Section) => (
    <BoundsBox
      key={section.id}
      variant="section"
      bounds={section.bounds}
      selected={selection?.type === 'section' && selection.id === section.id}
      editable={editable}
      className="floor-section-zone"
      borderColor={section.color}
      label={
        <>
          {SECTION_ICONS[section.name] ?? '•'} {section.name}
        </>
      }
      onSelect={() => onSelect({ type: 'section', id: section.id })}
      onCommit={(bounds) => onSectionChange(section.id, bounds)}
    />
  ))

  const labelNodes = floor.labels.map((label) => (
    <BoundsBox
      key={label.id}
      variant="label"
      bounds={label.bounds}
      selected={selection?.type === 'label' && selection.id === label.id}
      editable={editable}
      className={labelClass(label.kind)}
      label={label.text}
      onSelect={() => onSelect({ type: 'label', id: label.id })}
      onCommit={(bounds) => onLabelChange(label.id, bounds)}
    />
  ))

  return (
    <div className="floor-plan-viewport">
      <div
        ref={canvasRef}
        className={`floor-plan-canvas ${editable ? 'floor-plan-canvas--edit' : ''}`}
        style={{ width: floor.width, height: floor.height }}
        onPointerDown={handleCanvasPointerDown}
        role="presentation"
      >
        <div className="floor-plan-grid" aria-hidden />

        <div className="floor-layer floor-layer--layout">
          {sectionNodes}
          {labelNodes}
        </div>

        <div className="floor-layer floor-layer--tables">{tableNodes}</div>
      </div>
      {editable ? (
        <p className="canvas-edit-hint">
          Click a <strong>table</strong> to edit it · click <strong>section border</strong> or empty
          area inside a zone to edit the section
        </p>
      ) : (
        <p className="canvas-readonly-hint">
          Click a table to seat guests or update status
        </p>
      )}
    </div>
  )
}
