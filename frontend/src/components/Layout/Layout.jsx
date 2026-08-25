/**
 * Layout — DevHub (Internal Developer Platform)
 * Exact Spotify for Backstage Navigation Bar & Shell
 */

import { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import api from '../../api/client';
import './Layout.css';

export default function Layout({ children }) {
  const location = useLocation();
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

  return (
    <div className="layout">
      {/* Top Banner Notice (as seen in Spotify Portal) */}
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
          {/* Exact Brand Logo from Spotify Backstage */}
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
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noreferrer"
              className="layout-nav-link"
            >
              API Docs
            </a>
            <a
              href="http://localhost:8000/redoc"
              target="_blank"
              rel="noreferrer"
              className="layout-nav-link"
            >
              ReDoc
            </a>
          </nav>

          {/* Right Action / Status Pill */}
          <div className="layout-actions">
            <div className={`layout-account-pill ${isConnected ? 'live' : 'offline'}`}>
              <span className="account-dot"></span>
              <span className="account-text">{isConnected ? 'System Live' : 'Offline'}</span>
            </div>
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
