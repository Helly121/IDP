/**
 * Layout — Application shell with navigation header and main content area.
 */

import { Link, useLocation } from 'react-router-dom';
import './Layout.css';

export default function Layout({ children }) {
  const location = useLocation();

  return (
    <div className="layout">
      <header className="layout-header glass">
        <div className="layout-header-inner container">
          <Link to="/" className="layout-logo">
            <span className="layout-logo-icon">◆</span>
            <span className="layout-logo-text">Academic IDP</span>
          </Link>

          <nav className="layout-nav">
            <Link
              to="/"
              className={`layout-nav-link ${location.pathname === '/' ? 'active' : ''}`}
            >
              Dashboard
            </Link>
            <Link
              to="/new-project"
              className={`layout-nav-link ${location.pathname === '/new-project' ? 'active' : ''}`}
            >
              New Project
            </Link>
          </nav>

          <div className="layout-actions">
            <div className="layout-status">
              <span className="layout-status-dot"></span>
              <span className="layout-status-text">Connected</span>
            </div>
          </div>
        </div>
      </header>

      <main className="layout-main container">
        {children}
      </main>
    </div>
  );
}
