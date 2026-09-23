/**
 * AuthContext — Global authentication state for DevHub.
 *
 * Provides:
 *   - user          : The authenticated user object (id, email, role, full_name) or null
 *   - token         : The raw JWT string or null
 *   - loading       : Initial validation loading state
 *   - googleConfig  : { enabled: boolean, clientId: string | null }
 *   - login         : Persist session from a TokenResponse
 *   - logout        : Clear session and state
 *   - refreshUser   : Re-fetch latest user record from /auth/me
 *
 * State is persisted in localStorage so sessions survive page reloads.
 * Use the `useAuth()` hook anywhere inside <AuthProvider>.
 */

import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import api from '../api/client';

const AuthContext = createContext(null);

/** Read a value from localStorage, returning null on any parse error. */
function safeRead(key) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => safeRead('idp_user'));
  const [token, setToken] = useState(() => localStorage.getItem('idp_token'));
  const [loading, setLoading] = useState(true);
  const [googleConfig, setGoogleConfig] = useState({
    enabled: false,
    clientId: import.meta.env.VITE_GOOGLE_CLIENT_ID || null,
  });

  // Fetch backend auth config (checks if GOOGLE_CLIENT_ID is configured)
  useEffect(() => {
    let mounted = true;
    api.getAuthConfig()
      .then((cfg) => {
        if (mounted && cfg) {
          setGoogleConfig({
            enabled: Boolean(cfg.google_auth_enabled && cfg.google_client_id),
            clientId: cfg.google_client_id || import.meta.env.VITE_GOOGLE_CLIENT_ID || null,
          });
        }
      })
      .catch(() => {
        // Fallback to build-time env variable if server config request fails
        const envId = import.meta.env.VITE_GOOGLE_CLIENT_ID;
        if (mounted) {
          setGoogleConfig({
            enabled: Boolean(envId),
            clientId: envId || null,
          });
        }
      });
    return () => { mounted = false; };
  }, []);

  // Validate existing token on mount
  useEffect(() => {
    let mounted = true;
    if (token) {
      api.getMe()
        .then((userData) => {
          if (mounted) {
            setUser(userData);
            localStorage.setItem('idp_user', JSON.stringify(userData));
          }
        })
        .catch(() => {
          // Token invalid or expired
          if (mounted) {
            localStorage.removeItem('idp_token');
            localStorage.removeItem('idp_user');
            setToken(null);
            setUser(null);
          }
        })
        .finally(() => {
          if (mounted) setLoading(false);
        });
    } else {
      setLoading(false);
    }
    return () => { mounted = false; };
  }, [token]);

  /**
   * Call after a successful login / register / google-auth API response.
   * @param {{ access_token: string, user: object }} tokenData
   */
  const login = useCallback((tokenData) => {
    const { access_token, user: userData } = tokenData;
    localStorage.setItem('idp_token', access_token);
    localStorage.setItem('idp_user', JSON.stringify(userData));
    setToken(access_token);
    setUser(userData);
  }, []);

  /** Clear the session from memory and localStorage. */
  const logout = useCallback(() => {
    localStorage.removeItem('idp_token');
    localStorage.removeItem('idp_user');
    setToken(null);
    setUser(null);
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const updated = await api.getMe();
      setUser(updated);
      localStorage.setItem('idp_user', JSON.stringify(updated));
      return updated;
    } catch {
      return null;
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, loading, googleConfig, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

/**
 * Hook to access auth state anywhere inside <AuthProvider>.
 */
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be called inside <AuthProvider>');
  }
  return ctx;
}
