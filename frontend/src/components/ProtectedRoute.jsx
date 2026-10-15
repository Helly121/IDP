/**
 * ProtectedRoute — Guards routes that require authentication or a specific role.
 *
 * Usage:
 *   // Require any authenticated user
 *   <ProtectedRoute><Dashboard /></ProtectedRoute>
 *
 *   // Require guide or admin role
 *   <ProtectedRoute roles={['guide', 'admin']}><ApprovalsDashboard /></ProtectedRoute>
 *
 * Redirects:
 *   - Unauthenticated users → /login
 *   - Wrong role            → / (dashboard)
 */

import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function ProtectedRoute({ children, roles }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        background: 'var(--color-bg, #0b0f19)',
        color: 'var(--color-text-secondary, #94a3b8)',
      }}>
        <div style={{ textAlign: 'center' }}>
          <div className="spinner" style={{ margin: '0 auto 1rem' }} />
          <p>Verifying authentication...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (roles && !roles.includes(user.role)) {
    return <Navigate to="/" replace />;
  }

  return children;
}
