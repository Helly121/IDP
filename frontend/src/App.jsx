/**
 * App — Root component with React Router, Layout shell, and AgentPanel.
 */

import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout/Layout';
import Dashboard from './pages/Dashboard';
import NewProject from './pages/NewProject';
import ApprovalsDashboard from './pages/ApprovalsDashboard';
import AgentPanel from './components/AgentPanel/AgentPanel';

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/new-project" element={<NewProject />} />
          <Route path="/approvals" element={<ApprovalsDashboard />} />
        </Routes>
      </Layout>
      {/* Floating AI Agent Panel — accessible from every page */}
      <AgentPanel />
    </BrowserRouter>
  );
}
