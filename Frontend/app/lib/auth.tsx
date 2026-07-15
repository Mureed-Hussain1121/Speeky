"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api, clearTokens, getAccess, getRefresh, setTokens, User } from "./api";

type AuthState = {
  user: User | null;
  loading: boolean;
  setSession: (access: string, refresh: string, user: User) => void;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  async function loadUser() {
    if (!getAccess()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api.me();
      setUser(me);
    } catch {
      clearTokens();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadUser();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function setSession(access: string, refresh: string, u: User) {
    setTokens(access, refresh);
    setUser(u);
  }

  async function refresh() {
    await loadUser();
  }

  async function logout() {
    const r = getRefresh();
    try {
      if (r) await api.logout(r);
    } catch {
      /* ignore */
    }
    clearTokens();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, setSession, refresh, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
