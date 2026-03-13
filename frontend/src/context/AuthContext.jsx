import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { apiClient } from '../api/client';

const AuthContext = createContext(null);

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const applyCsrfToken = () => {
    const stored = localStorage.getItem('mp_csrf');
    if (stored) {
      apiClient.defaults.headers.common['X-CSRF-Token'] = stored;
    }
  };

  // Validate existing session on mount
  useEffect(() => {
    applyCsrfToken();
    apiClient
      .get('/auth/me')
      .then((res) => setUser(res.data))
      .catch(() => {
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const login = useCallback(async (email, password) => {
    const res = await apiClient.post('/auth/login', { email, password }, { withCredentials: true });
    const { user: userData, csrf_token: csrfToken } = res.data || {};
    if (csrfToken) {
      localStorage.setItem('mp_csrf', csrfToken);
      apiClient.defaults.headers.common['X-CSRF-Token'] = csrfToken;
    }

    setUser(userData);

    return userData;
  }, []);

  const register = useCallback(async (email, password, organizationName) => {
    const res = await apiClient.post('/auth/register', {
      email,
      password,
      organization_name: organizationName,
    }, { withCredentials: true });
    const { user: userData, csrf_token: csrfToken } = res.data || {};
    if (csrfToken) {
      localStorage.setItem('mp_csrf', csrfToken);
      apiClient.defaults.headers.common['X-CSRF-Token'] = csrfToken;
    }
    setUser(userData);
    return userData;
  }, []);

  const logout = useCallback(async () => {
    try { await apiClient.post('/auth/logout'); } catch { /* ignore */ }
    setUser(null);
    localStorage.removeItem('mp_csrf');
    delete apiClient.defaults.headers.common['X-CSRF-Token'];
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, isAdmin: user?.role === 'admin' }}>
      {children}
    </AuthContext.Provider>
  );
};
