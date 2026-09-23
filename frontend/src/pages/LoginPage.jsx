/**
 * LoginPage — DevHub Authentication Portal
 *
 * Supports:
 * - Email & Password Sign In
 * - Email & Password Sign Up (STUDENT accounts only)
 * - Real Google Sign-In via Google Identity Services (GSI)
 *   Gracefully disabled if GOOGLE_CLIENT_ID is not configured.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api from '../api/client';
import './LoginPage.css';

export default function LoginPage() {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const { user, login, googleConfig } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const googleBtnRef = useRef(null);

  const from = location.state?.from?.pathname || '/';

  // If already authenticated, redirect
  useEffect(() => {
    if (user) {
      navigate(from, { replace: true });
    }
  }, [user, navigate, from]);

  // Handle Google Sign-In response
  const handleGoogleCredentialResponse = useCallback(async (response) => {
    if (!response || !response.credential) {
      setError('No credential received from Google.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await api.googleAuth(response.credential);
      login(data);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err.message || 'Google authentication failed.');
    } finally {
      setLoading(false);
    }
  }, [from, login, navigate]);

  // Initialize and render Google button if enabled
  useEffect(() => {
    if (!googleConfig.enabled || !googleConfig.clientId) return;

    const initGoogle = () => {
      if (window.google?.accounts?.id && googleBtnRef.current) {
        try {
          window.google.accounts.id.initialize({
            client_id: googleConfig.clientId,
            callback: handleGoogleCredentialResponse,
            auto_select: false,
            cancel_on_tap_outside: true,
          });

          // Clear previous render if any
          googleBtnRef.current.innerHTML = '';

          window.google.accounts.id.renderButton(googleBtnRef.current, {
            theme: 'filled_black',
            size: 'large',
            shape: 'rectangular',
            width: 320,
            text: isRegister ? 'signup_with' : 'signin_with',
          });
        } catch (e) {
          console.error('Failed to render Google Sign-In button', e);
        }
      }
    };

    // Retry if GSI library is still loading
    if (window.google?.accounts?.id) {
      initGoogle();
    } else {
      const timer = setInterval(() => {
        if (window.google?.accounts?.id) {
          clearInterval(timer);
          initGoogle();
        }
      }, 300);
      return () => clearInterval(timer);
    }
  }, [googleConfig.enabled, googleConfig.clientId, isRegister, handleGoogleCredentialResponse]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (isRegister) {
        const payload = {
          email,
          password,
          full_name: fullName.trim() || undefined,
        };
        const data = await api.register(payload);
        login(data);
        navigate(from, { replace: true });
      } else {
        const data = await api.login({ email, password });
        login(data);
        navigate(from, { replace: true });
      }
    } catch (err) {
      setError(err.message || 'Authentication failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        {/* Brand Header */}
        <div className="login-brand">
          <div className="login-eclipse-logo">
            <svg width="36" height="36" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="16" cy="16" r="14" stroke="#ffffff" strokeWidth="2.5" />
              <path
                d="M16 4C9.37258 4 4 9.37258 4 16C4 22.6274 9.37258 28 16 28C22.6274 28 28 22.6274 28 16C28 12.5 26.5 9 24 6.5C21.5 4 18.5 4 16 4Z"
                fill="#ffffff"
              />
              <circle cx="18.5" cy="14.5" r="9.5" fill="#000000" />
            </svg>
          </div>
          <h2>{isRegister ? 'Create an Account' : 'Welcome to DevHub'}</h2>
          <p className="login-subtitle">
            {isRegister
              ? 'Join the academic self-service cloud platform'
              : 'Sign in to access your cloud resources and AI agent'}
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="login-error-alert" role="alert">
            <span className="error-icon">⚠️</span>
            <span>{error}</span>
          </div>
        )}

        {/* Google Sign-In Section */}
        <div className="google-auth-section">
          {googleConfig.enabled ? (
            <div className="google-btn-wrapper" ref={googleBtnRef} />
          ) : (
            <div className="google-disabled-pill" title="Set GOOGLE_CLIENT_ID in the backend environment to enable Google authentication">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12.545 10.239v3.821h5.445c-.712 2.315-2.647 3.972-5.445 3.972-3.332 0-6.033-2.701-6.033-6.032s2.701-6.032 6.033-6.032c1.498 0 2.866.549 3.921 1.453l2.814-2.814C17.503 2.988 15.139 2 12.545 2 7.021 2 2.543 6.477 2.543 12s4.478 10 10.002 10c8.396 0 10.249-7.85 9.426-11.761l-9.426-.001z"/>
              </svg>
              <span>Google Sign-In unavailable (unconfigured)</span>
            </div>
          )}
        </div>

        <div className="login-divider">
          <span>or continue with email</span>
        </div>

        {/* Email & Password Form */}
        <form className="login-form" onSubmit={handleSubmit}>
          {isRegister && (
            <div className="form-group">
              <label htmlFor="fullName">Full Name</label>
              <input
                id="fullName"
                type="text"
                placeholder="Jane Doe"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                autoComplete="name"
              />
            </div>
          )}

          <div className="form-group">
            <label htmlFor="email">Email Address</label>
            <input
              id="email"
              type="email"
              placeholder="student@university.edu"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              autoComplete={isRegister ? 'new-password' : 'current-password'}
            />
          </div>

          {isRegister && (
            <div className="registration-notice">
              ℹ️ Public signups receive <strong>Student</strong> access. Role elevations to <strong>Guide</strong> or <strong>Admin</strong> are granted by administrators.
            </div>
          )}

          <button
            type="submit"
            className="btn btn-primary login-submit-btn"
            disabled={loading}
          >
            {loading ? (
              <span className="btn-spinner">Processing...</span>
            ) : isRegister ? (
              'Create Student Account'
            ) : (
              'Sign In'
            )}
          </button>
        </form>

        {/* Toggle between Login and Register */}
        <div className="login-footer">
          {isRegister ? (
            <p>
              Already have an account?{' '}
              <button
                type="button"
                className="link-btn"
                onClick={() => {
                  setIsRegister(false);
                  setError(null);
                }}
              >
                Sign In
              </button>
            </p>
          ) : (
            <p>
              Need an account?{' '}
              <button
                type="button"
                className="link-btn"
                onClick={() => {
                  setIsRegister(true);
                  setError(null);
                }}
              >
                Sign Up
              </button>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
