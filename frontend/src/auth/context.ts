import { createContext } from 'react';
import type { Me } from '../api/types';

export interface AuthState {
  me: Me | null;
  loading: boolean;
  sessionExpired: boolean;
  setMe: (me: Me | null) => void;
  refresh: () => Promise<Me | null>;
  signOut: () => Promise<void>;
  clearExpired: () => void;
}

export const AuthContext = createContext<AuthState | null>(null);
