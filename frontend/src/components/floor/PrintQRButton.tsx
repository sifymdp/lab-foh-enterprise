/**
 * QR button — drop this anywhere a table is selected.
 * Opens the printable QR page in a new tab.
 *
 * Usage:
 *   import { PrintQRButton } from '../components/floor/PrintQRButton'
 *   <PrintQRButton tableId={table.id} tableNumber={table.number} />
 */

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

interface Props {
  tableId: string
  tableNumber: string
}

export function PrintQRButton({ tableId, tableNumber }: Props) {
  const handleClick = () => {
    window.open(`${API_URL}/tables/${tableId}/qr`, '_blank')
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        width: '100%',
        padding: '10px 14px',
        border: '1px solid #ddd',
        borderRadius: 8,
        background: '#fff',
        cursor: 'pointer',
        fontSize: 13,
        fontWeight: 500,
        color: '#333',
        marginTop: 8,
      }}
    >
      <span style={{ fontSize: 16 }}>📱</span>
      Print QR code for Table {tableNumber}
    </button>
  )
}
