/**
 * Layout — DevHub (Internal Developer Platform)
 * Navigation Bar & Shell with Authenticated User State & Role Badges
 */

import { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import api from '../../api/client';
import './Layout.css';

export default function Layout({ children }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [isConnected, setIsConnected] = useState(true);

  useEffect(() => {
    let isMounted = true;
    const checkHealth = () => {
      api.healthCheck()
        .then((res) => {
          if (isMounted) setIsConnected(res?.status === 'healthy');
        })
        .catch(() => {
          if (isMounted) setIsConnected(false);
        });
    };

    checkHealth();
    const interval = setInterval(checkHealth, 15000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isGuideOrAdmin = user && (user.role === 'guide' || user.role === 'admin');

  return (
    <div className="layout">
      {/* Top Banner Notice */}
      <div className="layout-top-banner">
        <div className="container layout-banner-content">
          <span>See DevHub in action with live cluster telemetry.</span>
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
            className="layout-banner-link"
          >
            Explore API Documentation &gt;
          </a>
        </div>
      </div>

      {/* Main Navbar */}
      <header className="layout-header">
        <div className="layout-header-inner container">
          {/* Brand Logo */}
          <Link to="/" className="layout-brand">
            <div className="layout-eclipse-logo">
              <svg width="28" height="28" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="16" cy="16" r="14" stroke="#ffffff" strokeWidth="2.5" />
                <path
                  d="M16 4C9.37258 4 4 9.37258 4 16C4 22.6274 9.37258 28 16 28C22.6274 28 28 22.6274 28 16C28 12.5 26.5 9 24 6.5C21.5 4 18.5 4 16 4Z"
                  fill="#ffffff"
                />
                <circle cx="18.5" cy="14.5" r="9.5" fill="#000000" />
              </svg>
            </div>
            <div className="layout-brand-text">
              <span className="brand-main">DevHub</span>
              <span className="brand-sub">Platform</span>
            </div>
          </Link>

          {/* Navigation Links */}
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
              Create Service
            </Link>
            {isGuideOrAdmin && (
              <Link
                to="/approvals"
                className={`layout-nav-link ${location.pathname === '/approvals' ? 'active' : ''}`}
              >
                ⏳ Approvals
              </Link>
            )}
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noreferrer"
              className="layout-nav-link"
            >
              API Docs
            </a>
          </nav>

          {/* Right Actions / User Status */}
          <div className="layout-actions">
            <div className={`layout-account-pill ${isConnected ? 'live' : 'offline'}`} title="Backend cluster connectivity">
              <span className="account-dot"></span>
              <span className="account-text">{isConnected ? 'System Live' : 'Offline'}</span>
            </div>

            {user ? (
              <div className="user-profile-menu">
                <div className="user-info-badge">
                  <span className="user-avatar">
                    {(user.full_name || user.email || 'U')[0].toUpperCase()}
                  </span>
                  <div className="user-meta">
                    <span className="user-name">{user.full_name || user.email.split('@')[0]}</span>
                    <span className={`user-role-tag role-${user.role}`}>
                      {user.role.toUpperCase()}
                    </span>
                  </div>
                </div>
                <button
                  type="button"
                  className="btn-signout"
                  onClick={handleLogout}
                  title="Sign out of DevHub"
                >
                  Sign Out
                </button>
              </div>
            ) : (
              <Link to="/login" className="btn-signin-nav">
                Sign In
              </Link>
            )}
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="layout-main">
        {children}
      </main>

      {/* Footer */}
      <footer className="layout-footer">
        <div className="container layout-footer-inner">
          <div className="footer-left">
            <span className="footer-brand">DevHub</span>
            <span className="footer-desc">Internal Developer Platform powered by Kubernetes & AI</span>
          </div>
          <div className="footer-right">
            <span className="footer-copy">© 2026 DevHub Platform Engineering</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
