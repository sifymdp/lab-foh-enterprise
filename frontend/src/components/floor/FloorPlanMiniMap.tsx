import { SECTION_ICONS, STATUS_CONFIG } from '../../services/tableConfig'
import type { Floor, Table } from '../../types'

interface FloorPlanMiniMapProps {
  floor: Floor
  selectedTableId: string | null
  onSelectTable: (tableId: string) => void
}

const MINI_MAP_WIDTH = 360
const MINI_MAP_MAX_HEIGHT = 300

export function FloorPlanMiniMap({
  floor,
  selectedTableId,
  onSelectTable,
}: FloorPlanMiniMapProps) {
  const scale = Math.min(MINI_MAP_WIDTH / floor.width, MINI_MAP_MAX_HEIGHT / floor.height)
  const width = Math.round(floor.width * scale)
  const height = Math.round(floor.height * scale)

  return (
    <aside className="floor-mini-map" aria-label="Floor plan table reference">
      <div className="floor-mini-map__header">
        <div>
          <p className="floor-mini-map__eyebrow">Floor plan</p>
          <h3 className="floor-mini-map__title">Table reference</h3>
        </div>
        <span className="floor-mini-map__count">{floor.tables.length} tables</span>
      </div>

      <div className="floor-mini-map__viewport">
        <div className="floor-mini-map__canvas" style={{ width, height }}>
          <div className="floor-mini-map__grid" aria-hidden />

          {floor.sections.map((section) => (
            <div
              key={section.id}
              className="floor-mini-map__section"
              style={{
                left: section.bounds.x * scale,
                top: section.bounds.y * scale,
                width: section.bounds.width * scale,
                height: section.bounds.height * scale,
                borderColor: section.color,
              }}
            >
              <span className="floor-mini-map__section-label">
                {SECTION_ICONS[section.name] ?? ''}
                {section.name}
              </span>
            </div>
          ))}

          {floor.labels.map((label) => (
            <div
              key={label.id}
              className={`floor-mini-map__label floor-mini-map__label--${label.kind.toLowerCase()}`}
              style={{
                left: label.bounds.x * scale,
                top: label.bounds.y * scale,
                width: label.bounds.width * scale,
                height: label.bounds.height * scale,
              }}
            >
              {label.text}
            </div>
          ))}

          {floor.tables.map((table) => (
            <MiniMapTable
              key={table.id}
              table={table}
              scale={scale}
              selected={table.id === selectedTableId}
              onSelect={() => onSelectTable(table.id)}
            />
          ))}
        </div>
      </div>
    </aside>
  )
}

function MiniMapTable({
  table,
  scale,
  selected,
  onSelect,
}: {
  table: Table
  scale: number
  selected: boolean
  onSelect: () => void
}) {
  const statusStyle = STATUS_CONFIG[table.status] ?? STATUS_CONFIG.AVAILABLE
  const minSize = table.shape === 'CIRCLE' ? 30 : 38
  const width = Math.max(table.width * scale, minSize)
  const height = Math.max(table.height * scale, table.shape === 'CIRCLE' ? minSize : 30)

  return (
    <button
      type="button"
      className={[
        'floor-mini-map__table',
        table.shape === 'CIRCLE' ? 'floor-mini-map__table--circle' : '',
        selected ? 'floor-mini-map__table--selected' : '',
      ]
        .filter(Boolean)
        .join(' ')}
      style={{
        left: table.x * scale,
        top: table.y * scale,
        width,
        height,
        backgroundColor: statusStyle.bg,
        borderColor: selected ? '#c41e3a' : statusStyle.border,
        color: statusStyle.text,
        transform: table.rotation ? `rotate(${table.rotation}deg)` : undefined,
      }}
      onClick={onSelect}
      aria-label={`Select table ${table.number}`}
    >
      <span className="floor-mini-map__table-number">T{table.number}</span>
      {table.cameraUrl && (
        <span
          className="floor-mini-map__camera-dot"
          title="Camera configured"
          aria-label="Camera configured"
        />
      )}
    </button>
  )
}
