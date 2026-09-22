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
      title={`Switch to ${currentView === 'kds' ? 'Station Queue' : 'Kanban Board'} view`}
    >
      <span className="kds-switch-btn__icon">🔀</span>
      <span className="kds-switch-btn__text">
        {currentView === 'kds' ? 'Switch to Station Queue' : 'Switch to Kanban Board'}
      </span>
    </button>
  )
}