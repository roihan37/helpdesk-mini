"use client";

import { apiRequest, login as loginRequest, logout as logoutRequest, onAuthLost, refreshAccessToken } from "@/lib/api";
import { createQueryClient, queryKeys } from "@/lib/query";
import type { CurrentUser } from "@/types/api";
import { QueryClientProvider } from "@tanstack/react-query";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";

type AuthState = "bootstrapping" | "authenticated" | "anonymous" | "unavailable";
interface AuthContextValue { state: AuthState; user: CurrentUser | null; signIn: (email: string, password: string) => Promise<CurrentUser>; signOut: () => Promise<void>; retryBootstrap: () => Promise<void> }
const AuthContext = createContext<AuthContextValue | null>(null);

export function AppProviders({ children }: { children: ReactNode }) {
  const [queryClient] = useState(createQueryClient);
  const [state, setState] = useState<AuthState>("bootstrapping");
  const [user, setUser] = useState<CurrentUser | null>(null);
  const bootstrap = useCallback(async () => {
    try {
      await refreshAccessToken();
      const currentUser = await apiRequest<CurrentUser>("/auth/me", { retryAuth: false });
      setUser(currentUser);
      queryClient.setQueryData(queryKeys.me, currentUser);
      setState("authenticated");
    } catch (error) {
      setUser(null);
      queryClient.clear();
      setState(error instanceof TypeError ? "unavailable" : "anonymous");
    }
  }, [queryClient]);
  useEffect(() => { const timer = window.setTimeout(() => void bootstrap(), 0); return () => window.clearTimeout(timer); }, [bootstrap]);
  useEffect(() => onAuthLost(() => { setUser(null); queryClient.clear(); setState("anonymous"); }), [queryClient]);
  const signIn = useCallback(async (email: string, password: string) => {
    const currentUser = await loginRequest(email, password);
    setUser(currentUser);
    queryClient.setQueryData(queryKeys.me, currentUser);
    setState("authenticated");
    return currentUser;
  }, [queryClient]);
  const signOut = useCallback(async () => {
    await logoutRequest();
    setUser(null);
    queryClient.clear();
    setState("anonymous");
  }, [queryClient]);
  const retryBootstrap = useCallback(async () => { setState("bootstrapping"); await bootstrap(); }, [bootstrap]);
  const value = useMemo(() => ({ state, user, signIn, signOut, retryBootstrap }), [retryBootstrap, signIn, signOut, state, user]);
  return <QueryClientProvider client={queryClient}><AuthContext.Provider value={value}>{children}</AuthContext.Provider></QueryClientProvider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used within AppProviders");
  return value;
}
