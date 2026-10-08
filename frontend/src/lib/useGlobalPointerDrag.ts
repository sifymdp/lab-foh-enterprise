import { useCallback, useEffect, useRef, useState } from 'react'

const MIN_SIZE = 40

export type DragMode = 'move' | 'resize-se' | 'resize-e' | 'resize-s'

interface DragState {
  mode: DragMode
  startX: number
  startY: number
  origX: number
  origY: number
  origW: number
  origH: number
}

export interface DragRect {
  x: number
  y: number
  width: number
  height: number
}

/** Drag/resize with window listeners so movement works smoothly with the mouse. */
export function useGlobalPointerDrag(
  rect: DragRect,
  onChange: (next: DragRect) => void,
  onCommit: (next: DragRect) => void,
  enabled: boolean,
) {
  const rectRef = useRef(rect)
  rectRef.current = rect
  const dragRef = useRef<DragState | null>(null)
  const [dragging, setDragging] = useState(false)

  const endDrag = useCallback(() => {
    if (!dragRef.current) return
    dragRef.current = null
    setDragging(false)
    onCommit(rectRef.current)
  }, [onCommit])

  useEffect(() => {
    if (!dragging) return

    const onMove = (e: PointerEvent) => {
      const d = dragRef.current
      if (!d) return
      const dx = e.clientX - d.startX
      const dy = e.clientY - d.startY
      let next: DragRect
      switch (d.mode) {
        case 'move':
          next = {
            x: Math.max(0, d.origX + dx),
            y: Math.max(0, d.origY + dy),
            width: d.origW,
            height: d.origH,
          }
          break
        case 'resize-se':
          next = {
            x: d.origX,
            y: d.origY,
            width: Math.max(MIN_SIZE, d.origW + dx),
            height: Math.max(MIN_SIZE, d.origH + dy),
          }
          break
        case 'resize-e':
          next = {
            x: d.origX,
            y: d.origY,
            width: Math.max(MIN_SIZE, d.origW + dx),
            height: d.origH,
          }
          break
        case 'resize-s':
          next = {
            x: d.origX,
            y: d.origY,
            width: d.origW,
            height: Math.max(MIN_SIZE, d.origH + dy),
          }
          break
        default:
          return
      }
      rectRef.current = next
      onChange(next)
    }

    const onUp = () => endDrag()

    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    window.addEventListener('pointercancel', onUp)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      window.removeEventListener('pointercancel', onUp)
    }
  }, [dragging, onChange, endDrag])

  const begin = useCallback(
    (e: React.PointerEvent, mode: DragMode) => {
      if (!enabled) return
      e.preventDefault()
      e.stopPropagation()
      const r = rectRef.current
      dragRef.current = {
        mode,
        startX: e.clientX,
        startY: e.clientY,
        origX: r.x,
        origY: r.y,
        origW: r.width,
        origH: r.height,
      }
      setDragging(true)
    },
    [enabled],
  )

  return {
    startMove: (e: React.PointerEvent) => begin(e, 'move'),
    startResizeSE: (e: React.PointerEvent) => begin(e, 'resize-se'),
    startResizeE: (e: React.PointerEvent) => begin(e, 'resize-e'),
    startResizeS: (e: React.PointerEvent) => begin(e, 'resize-s'),
    dragging,
  }
}
