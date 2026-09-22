import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { canEditFloor } from '../../lib/permissions'

export function ManagerRoute() {
  const { user } = useAuth()
  if (!user || !canEditFloor(user.role, user)) {
    return <Navigate to="/floor" replace />
  }
  return <Outlet />
}
