import { useCallback, useMemo, useState, type ReactNode } from 'react';
import { AuthContext, type AuthUser } from './context';

const STORAGE_KEY = 'lectureflow.session';

function readSession(): AuthUser | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as AuthUser) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(readSession);

  const login = useCallback(async (identifier: string, password: string) => {
    if (!identifier.trim() || !password) {
      throw new Error('Enter your username or email and your password.');
    }
    const next: AuthUser = {
      identifier: identifier.trim(),
      name: identifier.trim().split('@')[0],
    };
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      /* storage unavailable: session lasts until reload */
    }
    setUser(next);
  }, []);

  const logout = useCallback(() => {
    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, login, logout }), [user, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
