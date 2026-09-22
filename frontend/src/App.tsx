import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { FloorProvider } from './context/FloorContext'
import { SocketProvider } from './context/SocketContext'
import { ProtectedRoute } from './components/auth/ProtectedRoute'
import { OwnerRoute } from './components/auth/OwnerRoute'
import { ManagerRoute } from './components/auth/ManagerRoute'
import { AppShell } from './components/layout/AppShell'
import { LoginPage } from './pages/LoginPage'
import { FloorPage } from './pages/FloorPage'
import { UsersPage } from './pages/UsersPage'
import { SessionsPage } from './pages/SessionsPage'
import { MenuPage } from './pages/MenuPage'
import { ReservationsPage } from './pages/ReservationsPage'

import { ReportsPage } from './pages/ReportsPage'
import { CameraSetupPage } from './pages/CameraSetupPage'
import { BillsPage } from './pages/BillsPage'
import { PaymentsPage } from './pages/PaymentsPage'
import { CashierShiftPage } from './pages/CashierShiftPage'
import { RefundsPage } from './pages/RefundsPage'
import { RevenuePage } from './pages/RevenuePage'
import { AuditLogsPage } from './pages/AuditLogsPage'
import { OwnerDashboard } from './pages/OwnerDashboard'
import { ManagerDashboard } from './pages/ManagerDashboard'
import { HostDashboard } from './pages/HostDashboard'
import { CashierDashboard } from './pages/CashierDashboard'
import { WaiterDashboard } from './pages/WaiterDashboard'
import { RolesPage } from './pages/RolesPage'
import { OverridesPage } from './pages/OverridesPage'
import { StaffSessionsPage } from './pages/StaffSessionsPage'
import { SettingsPage } from './pages/SettingsPage'
import { InsightsPage } from './pages/InsightsPage'
import { TablePayPage } from './pages/TablePayPage'
import { BillDetailPage } from './pages/BillDetailPage'
import { KDSPage } from './pages/KDSPage'
import { KitchenPage } from './pages/KitchenPage'
import { ExpoMenuManagementPage } from './pages/ExpoMenuManagementPage'
import { AIBookingPage } from './pages/AIBookingPage'

function DashboardSwitcher() {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />

  switch (user.role) {
    case 'OWNER':
      return <OwnerDashboard />
    case 'MANAGER':
      return <ManagerDashboard />
    case 'HOST':
      return <HostDashboard />
    case 'CASHIER':
      return <CashierDashboard />
    case 'WAITER':
      return <WaiterDashboard />
    case 'CHEF':
      return <KitchenPage />
    default:
      return <Navigate to="/floor" replace />
  }
}


import { ErrorBoundary } from './components/common/ErrorBoundary'

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <SocketProvider>
            <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/book" element={<AIBookingPage />} />
            <Route path="/customer/book" element={<AIBookingPage />} />
            <Route path="/pay/:billId" element={<TablePayPage />} />
            <Route path="/table-pay/:billId" element={<TablePayPage />} />
            <Route element={<ProtectedRoute />}>
              <Route
                element={
                  <FloorProvider>
                    <AppShell />
                  </FloorProvider>
                }
              >
                <Route index element={<Navigate to="/dashboard" replace />} />
                <Route path="dashboard" element={<DashboardSwitcher />} />
                <Route path="floor" element={<FloorPage />} />
                <Route path="sessions" element={<SessionsPage />} />
                <Route path="billing" element={<BillsPage />} />
                <Route path="billing/:billId" element={<BillDetailPage />} />
                <Route path="bills/:billId" element={<BillDetailPage />} />
                <Route path="payments" element={<PaymentsPage />} />
                <Route path="shifts" element={<CashierShiftPage />} />
                <Route path="refunds" element={<RefundsPage />} />
                <Route path="revenue" element={<RevenuePage />} />
                <Route path="reservations" element={<ReservationsPage />} />
                <Route path="menu" element={<MenuPage />} />

                <Route path="reports" element={<ReportsPage />} />
                <Route path="audit-logs" element={<AuditLogsPage />} />
                <Route path="insights" element={<InsightsPage />} />
                <Route path="kitchen" element={<KitchenPage />} />
                <Route path="kds" element={<KDSPage />} />
                <Route path="expo" element={<ExpoMenuManagementPage />} />
                <Route path="booking" element={<AIBookingPage />} />
                <Route path="users" element={<UsersPage />} />
                <Route element={<OwnerRoute />}>
                  <Route path="roles" element={<RolesPage />} />
                  <Route path="overrides" element={<OverridesPage />} />
                  <Route path="staff-sessions" element={<StaffSessionsPage />} />
                  <Route path="settings" element={<SettingsPage />} />
                </Route>
                <Route element={<ManagerRoute />}>
                  <Route path="camera-setup" element={<CameraSetupPage />} />
                </Route>
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </SocketProvider>
      </AuthProvider>
    </BrowserRouter>
  </ErrorBoundary>
  )
}

