import { createContext } from 'react';

export type AuthUser = { name: string; identifier: string };

export type AuthContextValue = {
  user: AuthUser | null;
  /** Demo sign-in: accepts any non-empty credentials. Replace with a real API call. */
  login: (identifier: string, password: string) => Promise<void>;
  logout: () => void;
};

export const AuthContext = createContext<AuthContextValue | null>(null);
