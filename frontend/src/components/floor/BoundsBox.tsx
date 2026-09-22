import { useEffect, useState } from 'react'
import type { RectBounds } from '../../types'
import { useGlobalPointerDrag } from '../../lib/useGlobalPointerDrag'

interface BoundsBoxProps {
  bounds: RectBounds
  selected: boolean
  editable: boolean
  variant: 'section' | 'label'
  className: string
  borderColor?: string
  label: React.ReactNode
  onSelect: () => void
  onCommit: (bounds: RectBounds) => void
}

export function BoundsBox({
  bounds,
  selected,
  editable,
  variant,
  className,
  borderColor,
  label,
  onSelect,
  onCommit,
}: BoundsBoxProps) {
  const [live, setLive] = useState(bounds)
  const isSection = variant === 'section'

  useEffect(() => {
    setLive(bounds)
  }, [bounds.x, bounds.y, bounds.width, bounds.height])

  const { startMove, startResizeSE, startResizeE, startResizeS, dragging } = useGlobalPointerDrag(
    live,
    setLive,
    onCommit,
    editable,
  )

  const showHandles = editable && (selected || dragging)

  const beginMove = (e: React.PointerEvent) => {
    e.stopPropagation()
    onSelect()
    if (editable) startMove(e)
  }

  return (
    <div
      className={[
        className,
        'bounds-box',
        isSection ? 'bounds-box--section' : 'bounds-box--label',
        selected ? 'bounds-box--selected' : '',
        editable ? 'bounds-box--editable' : '',
        dragging ? 'bounds-box--dragging' : '',
      ]
        .filter(Boolean)
        .join(' ')}
      style={{
        left: live.x,
        top: live.y,
        width: live.width,
        height: live.height,
      }}
      role="presentation"
    >
      {/* Section interior does not capture clicks — tables on top get priority */}
      {isSection && (
        <div
          className="bounds-box__fill"
          style={{ borderColor: borderColor ?? '#94a3b8' }}
          aria-hidden
        />
      )}

      {isSection && (
        <>
          <div
            className="section-edge section-edge--top"
            onPointerDown={beginMove}
            title="Select section · drag to move"
          />
          <div
            className="section-edge section-edge--bottom"
            onPointerDown={beginMove}
            title="Select section · drag to move"
          />
          <div
            className="section-edge section-edge--left"
            onPointerDown={beginMove}
            title="Select section · drag to move"
          />
          <div
            className="section-edge section-edge--right"
            onPointerDown={beginMove}
            title="Select section · drag to move"
          />
        </>
      )}

      {editable && (
        <div
          className="bounds-box__drag-bar"
          onPointerDown={beginMove}
          title="Drag to move"
        >
          ⋮⋮
        </div>
      )}

      <span
        className="bounds-box__label"
        onPointerDown={(e) => {
          if (!isSection) beginMove(e)
          else {
            e.stopPropagation()
            onSelect()
          }
        }}
      >
        {label}
      </span>

      {!isSection && editable && (
        <div
          className="bounds-box__body-hit"
          onPointerDown={beginMove}
          title="Drag to move"
        />
      )}

      {showHandles && (
        <>
          <span
            className="resize-handle resize-handle--se"
            onPointerDown={(e) => {
              e.stopPropagation()
              onSelect()
              startResizeSE(e)
            }}
            title="Drag to resize"
          />
          <span
            className="resize-handle resize-handle--e"
            onPointerDown={(e) => {
              e.stopPropagation()
              onSelect()
              startResizeE(e)
            }}
            title="Drag width"
          />
          <span
            className="resize-handle resize-handle--s"
            onPointerDown={(e) => {
              e.stopPropagation()
              onSelect()
              startResizeS(e)
            }}
            title="Drag height"
          />
        </>
      )}
    </div>
  )
}
