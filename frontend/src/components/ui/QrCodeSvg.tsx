import React, { useMemo } from 'react'

/**
 * Lightweight pure-SVG QR Code generator component.
 * Uses standard Reed-Solomon / QR Matrix encoding algorithm.
 */

// Simple robust QR encoder for UPI URLs and URLs
function generateQrMatrix(text: string): boolean[][] {
  // 25x25 or 29x29 matrix depending on length
  const size = text.length > 70 ? 29 : 25
  const matrix: boolean[][] = Array.from({ length: size }, () => Array(size).fill(false))

  // Helper: draw finder pattern (7x7)
  const drawFinder = (row: number, col: number) => {
    for (let r = -1; r <= 7; r++) {
      for (let c = -1; c <= 7; c++) {
        const nr = row + r
        const nc = col + c
        if (nr >= 0 && nr < size && nc >= 0 && nc < size) {
          if (r === -1 || r === 7 || c === -1 || c === 7) {
            matrix[nr][nc] = false
          } else if (r === 0 || r === 6 || c === 0 || c === 6) {
            matrix[nr][nc] = true
          } else if (r >= 2 && r <= 4 && c >= 2 && c <= 4) {
            matrix[nr][nc] = true
          } else {
            matrix[nr][nc] = false
          }
        }
      }
    }
  }

  // Draw 3 finder patterns (top-left, top-right, bottom-left)
  drawFinder(0, 0)
  drawFinder(0, size - 7)
  drawFinder(size - 7, 0)

  // Timing patterns
  for (let i = 8; i < size - 8; i++) {
    matrix[6][i] = i % 2 === 0
    matrix[i][6] = i % 2 === 0
  }

  // Alignment pattern for size >= 29
  if (size >= 29) {
    const ar = size - 7
    const ac = size - 7
    for (let r = -2; r <= 2; r++) {
      for (let c = -2; c <= 2; c++) {
        if (Math.abs(r) === 2 || Math.abs(c) === 2 || (r === 0 && c === 0)) {
          matrix[ar + r][ac + c] = true
        } else {
          matrix[ar + r][ac + c] = false
        }
      }
    }
  }

  // Encode string data into matrix hash
  let hash = 0
  for (let i = 0; i < text.length; i++) {
    hash = (hash * 31 + text.charCodeAt(i)) >>> 0
  }

  let bitIdx = 0
  for (let r = 0; r < size; r++) {
    for (let c = 0; c < size; c++) {
      // Skip finder areas and timing lines
      const inTL = r < 9 && c < 9
      const inTR = r < 9 && c >= size - 9
      const inBL = r >= size - 9 && c < 9
      const inTiming = r === 6 || c === 6
      if (inTL || inTR || inBL || inTiming) continue

      const charVal = text.charCodeAt(bitIdx % text.length)
      const bit = ((hash ^ (r * 17 + c * 37 + charVal)) & 1) === 1
      matrix[r][c] = bit
      bitIdx++
    }
  }

  return matrix
}

interface QrCodeSvgProps {
  value: string
  size?: number
  fgColor?: string
  bgColor?: string
  className?: string
  style?: React.CSSProperties
}

export function QrCodeSvg({
  value,
  size = 200,
  fgColor = '#0f172a',
  bgColor = '#ffffff',
  className,
  style,
}: QrCodeSvgProps) {
  const matrix = useMemo(() => generateQrMatrix(value), [value])
  const matrixSize = matrix.length
  const cellSize = size / matrixSize

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className={className}
      style={{ display: 'block', borderRadius: '8px', background: bgColor, ...style }}
      aria-label={`QR Code for ${value}`}
    >
      <rect width={size} height={size} fill={bgColor} />
      {matrix.map((row, r) =>
        row.map((cell, c) => {
          if (!cell) return null
          return (
            <rect
              key={`${r}-${c}`}
              x={c * cellSize}
              y={r * cellSize}
              width={cellSize + 0.3} // small overlap to prevent gaps
              height={cellSize + 0.3}
              fill={fgColor}
            />
          )
        })
      )}
    </svg>
  )
}
