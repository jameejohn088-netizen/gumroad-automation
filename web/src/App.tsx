import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import Accounts from './pages/Accounts';
import Automations from './pages/Automations';
import Customers from './pages/Customers';
import Dashboard from './pages/Dashboard';
import ForgotPassword from './pages/ForgotPassword';
import Licenses from './pages/Licenses';
import Login from './pages/Login';
import Logs from './pages/Logs';
import Memberships from './pages/Memberships';
import Notifications from './pages/Notifications';
import Products from './pages/Products';
import ResetPassword from './pages/ResetPassword';
import Sales from './pages/Sales';
import Scheduler from './pages/Scheduler';
import Settings from './pages/Settings';
import Signup from './pages/Signup';
import Subscribers from './pages/Subscribers';
import VerifyEmail from './pages/VerifyEmail';

export default function App() {
  return (
    <Routes>
      {/* Public auth pages */}
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/verify-email" element={<VerifyEmail />} />

      {/* Protected app */}
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="accounts" element={<Accounts />} />
          <Route path="products" element={<Products />} />
          <Route path="sales" element={<Sales />} />
          <Route path="customers" element={<Customers />} />
          <Route path="subscribers" element={<Subscribers />} />
          <Route path="licenses" element={<Licenses />} />
          <Route path="memberships" element={<Memberships />} />
          <Route path="automations" element={<Automations />} />
          <Route path="scheduler" element={<Scheduler />} />
          <Route path="notifications" element={<Notifications />} />
          <Route path="logs" element={<Logs />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
