import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { canManageUsers } from '../../lib/permissions'

export function OwnerRoute() {
  const { user } = useAuth()
  if (!user || !canManageUsers(user.role, user)) {
    return <Navigate to="/floor" replace />
  }
  return <Outlet />
}
