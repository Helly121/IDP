/**
 * App — Root component with React Router and Layout shell.
 */

import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout/Layout';
import Dashboard from './pages/Dashboard';
import NewProject from './pages/NewProject';

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/new-project" element={<NewProject />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
