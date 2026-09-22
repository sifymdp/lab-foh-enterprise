import type { Floor, FloorLabel, Section, Table } from '../types'

export function pointInRect(
  x: number,
  y: number,
  rect: { x: number; y: number; width: number; height: number },
): boolean {
  return x >= rect.x && x <= rect.x + rect.width && y >= rect.y && y <= rect.y + rect.height
}

export function findTableAt(floor: Floor, x: number, y: number): Table | undefined {
  return [...floor.tables]
    .reverse()
    .find((t) => pointInRect(x, y, t))
}

export function findSectionAt(floor: Floor, x: number, y: number): Section | undefined {
  return [...floor.sections]
    .reverse()
    .find((s) => pointInRect(x, y, s.bounds))
}

export function findLabelAt(floor: Floor, x: number, y: number): FloorLabel | undefined {
  return [...floor.labels]
    .reverse()
    .find((l) => pointInRect(x, y, l.bounds))
}

/** Tables win over sections; sections only when click is not on a table. */
export function hitTestCanvas(
  floor: Floor,
  canvasX: number,
  canvasY: number,
): CanvasSelection {
  const table = findTableAt(floor, canvasX, canvasY)
  if (table) return { type: 'table', id: table.id }

  const label = findLabelAt(floor, canvasX, canvasY)
  if (label) return { type: 'label', id: label.id }

  const section = findSectionAt(floor, canvasX, canvasY)
  if (section) return { type: 'section', id: section.id }

  return null
}

export type CanvasSelection =
  | { type: 'table'; id: string }
  | { type: 'section'; id: string }
  | { type: 'label'; id: string }
  | null

export function getCanvasPoint(
  e: React.PointerEvent | React.MouseEvent,
  canvasEl: HTMLElement,
): { x: number; y: number } {
  const rect = canvasEl.getBoundingClientRect()
  return {
    x: e.clientX - rect.left,
    y: e.clientY - rect.top,
  }
}
