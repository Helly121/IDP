/**
 * App — Root component with React Router, AuthProvider, Layout shell, and AgentPanel.
 */

import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout/Layout';
import Dashboard from './pages/Dashboard';
import NewProject from './pages/NewProject';
import ApprovalsDashboard from './pages/ApprovalsDashboard';
import LoginPage from './pages/LoginPage';
import AgentPanel from './components/AgentPanel/AgentPanel';

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
          </Routes>
        </Layout>
        {/* Floating AI Agent Panel — accessible for authenticated users */}
        <AgentPanel />
      </AuthProvider>
    </BrowserRouter>
  );
}
