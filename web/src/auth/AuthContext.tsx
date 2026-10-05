import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, clearTokens, getAccessToken, setTokens, setUnauthorizedHandler } from '../api/client';
import type { User } from '../api/types';

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (name: string, email: string, password: string) => Promise<string>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const refreshUser = useCallback(async () => {
    if (!getAccessToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api.me();
      setUser(me);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      navigate('/login', { replace: true });
    });
    void refreshUser();
    return () => setUnauthorizedHandler(null);
  }, [navigate, refreshUser]);

  const login = useCallback(
    async (email: string, password: string) => {
      const pair = await api.login(email, password);
      setTokens(pair.access_token, pair.refresh_token);
      const me = await api.me();
      setUser(me);
    },
    [],
  );

  const signup = useCallback(async (name: string, email: string, password: string) => {
    const res = await api.signup(name, email, password);
    return res.message ?? 'Account created. Please check your email to verify it, then log in.';
  }, []);

  const logout = useCallback(async () => {
    const rt = localStorage.getItem('ga_refresh_token');
    try {
      if (rt) await api.logout(rt);
    } catch {
      /* logout is best-effort */
    }
    clearTokens();
    setUser(null);
    navigate('/login', { replace: true });
  }, [navigate]);

  const value = useMemo(
    () => ({ user, loading, login, signup, logout, refreshUser }),
    [user, loading, login, signup, logout, refreshUser],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
