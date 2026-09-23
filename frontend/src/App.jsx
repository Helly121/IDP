/**
 * App â€” Root component with React Router, AuthProvider, Layout shell, and AgentPanel.
 */

import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout/Layout';
import Dashboard from './pages/Dashboard';
import NewProject from './pages/NewProject';
import ApprovalsDashboard from './pages/ApprovalsDashboard';
import LoginPage from './pages/LoginPage';
import AgentPage from './pages/AgentPage';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Layout>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/new-project"
              element={
                <ProtectedRoute>
                  <NewProject />
                </ProtectedRoute>
              }
            />
            <Route
              path="/approvals"
              element={
                <ProtectedRoute roles={['guide', 'admin']}>
                  <ApprovalsDashboard />
                </ProtectedRoute>
              }
            />
                      <Route
              path="/agent"
              element={
                <ProtectedRoute>
                  <AgentPage />
                </ProtectedRoute>
              }
            />
          </Routes>
        </Layout>
        
      </AuthProvider>
    </BrowserRouter>
  );
}

