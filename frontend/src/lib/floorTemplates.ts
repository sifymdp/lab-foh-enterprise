import type { Floor, FloorLabel, RectBounds, Section } from '../types'

/** Blank canvas — start fresh */
export function createEmptyFloor(
  existing?: Pick<Floor, 'id' | 'name' | 'width' | 'height'>,
): Floor {
  const w = existing?.width ?? 1000
  const h = existing?.height ?? 620
  return {
    id: existing?.id ?? 'floor-1',
    name: existing?.name ?? 'Main Dining',
    width: w,
    height: h,
    sections: [],
    labels: [
      {
        id: `lbl-${Date.now()}-ent`,
        kind: 'ENTRANCE',
        text: 'Entrance',
        bounds: { x: w / 2 - 100, y: h - 56, width: 200, height: 44 },
      },
      {
        id: `lbl-${Date.now()}-kit`,
        kind: 'KITCHEN',
        text: 'Kitchen',
        bounds: { x: w - 140, y: 12, width: 120, height: 44 },
      },
    ],
    tables: [],
  }
}

export const SECTION_COLORS = ['#818cf8', '#38bdf8', '#fbbf24', '#34d399', '#f472b6', '#a78bfa']

export function defaultSectionBounds(
  index: number,
  floorW: number,
  floorH: number,
): RectBounds {
  const cols = 2
  const col = index % cols
  const row = Math.floor(index / cols)
  const pad = 40
  const cellW = (floorW - pad * 3) / cols
  const cellH = (floorH - pad * 3) / 2
  return {
    x: pad + col * (cellW + pad),
    y: pad + row * (cellH + pad),
    width: cellW,
    height: cellH,
  }
}

export function newSection(name: string, floorW: number, floorH: number, index: number): Section {
  return {
    id: `sec-${Date.now()}`,
    name,
    color: SECTION_COLORS[index % SECTION_COLORS.length],
    bounds: defaultSectionBounds(index, floorW, floorH),
  }
}

export function newLabel(
  kind: FloorLabel['kind'],
  text: string,
  floorW: number,
  floorH: number,
): FloorLabel {
  const defaults: Record<FloorLabel['kind'], RectBounds> = {
    ENTRANCE: { x: floorW / 2 - 100, y: floorH - 56, width: 200, height: 44 },
    KITCHEN: { x: floorW - 140, y: 12, width: 120, height: 44 },
    BAR: { x: floorW - 280, y: 12, width: 120, height: 80 },
    CUSTOM: { x: 40, y: 40, width: 120, height: 44 },
  }
  return {
    id: `lbl-${Date.now()}`,
    kind,
    text,
    bounds: defaults[kind],
  }
}
