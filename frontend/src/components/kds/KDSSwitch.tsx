import { useNavigate } from 'react-router-dom'

interface KDSSwitchProps {
  currentView: 'kds' | 'kitchen'
}

export function KDSSwitch({ currentView }: KDSSwitchProps) {
  const navigate = useNavigate()

  return (
    <button
      type="button"
      onClick={() => navigate(currentView === 'kds' ? '/kitchen' : '/kds')}
      className="kds-switch-btn"
      title={`Switch to ${currentView === 'kds' ? 'Kitchen Queue' : 'KDS Board'} view`}
    >
      <span className="kds-switch-btn__icon">🔀</span>
      <span className="kds-switch-btn__text">
        {currentView === 'kds' ? 'Switch to Kitchen Queue' : 'Switch to KDS Board'}
      </span>
    </button>
  )
}