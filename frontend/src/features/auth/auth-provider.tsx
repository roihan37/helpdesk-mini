"use client";

import { apiRequest, getAuthEpoch, login as loginRequest, logout as logoutRequest, onAuthLost, refreshAccessToken } from "@/lib/api";
import { createQueryClient, queryKeys } from "@/lib/query";
import { TicketListLiveProvider } from "@/features/tickets/ticket-list-live-provider";
import type { CurrentUser } from "@/types/api";
import { QueryClientProvider } from "@tanstack/react-query";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

type AuthState = "bootstrapping" | "authenticated" | "anonymous" | "unavailable";
interface AuthContextValue {
  state: AuthState;
  user: CurrentUser | null;
  signIn: (email: string, password: string) => Promise<CurrentUser>;
  signOut: () => Promise<void>;
  retryBootstrap: () => Promise<void>
}
const AuthContext = createContext<AuthContextValue | null>(null);

export function AppProviders({ children }: { children: ReactNode }) {
  const [queryClient] = useState(createQueryClient);
  const [state, setState] = useState<AuthState>("bootstrapping");
  const [user, setUser] = useState<CurrentUser | null>(null);
  const operation = useRef(0);
  const bootstrap = useCallback(async () => {
    const currentOperation = ++operation.current;
    const epoch = getAuthEpoch();
    try {
      await refreshAccessToken();
      if (currentOperation !== operation.current || epoch !== getAuthEpoch()) return;
      const currentUser = await apiRequest<CurrentUser>("/auth/me", { retryAuth: false });
      if (currentOperation !== operation.current || epoch !== getAuthEpoch()) return;
      setUser(currentUser);
      queryClient.setQueryData(queryKeys.me, currentUser);
      setState("authenticated");
    } catch (error) {
      if (currentOperation !== operation.current) return;
      setUser(null);
      queryClient.clear();
      setState(error instanceof TypeError ? "unavailable" : "anonymous");
    }
  }, [queryClient]);
  useEffect(() => {
    const timer = window.setTimeout(() => void bootstrap(), 0);
    return () => {
      window.clearTimeout(timer);
      operation.current += 1;
    };
  }, [bootstrap]);
  useEffect(() => onAuthLost(() => {
    operation.current += 1;
    setUser(null);
    queryClient.clear();
    setState("anonymous");
  }), [queryClient]);
  const signIn = useCallback(async (email: string, password: string) => {
    const currentOperation = ++operation.current;
    setUser(null);
    queryClient.clear();
    setState("anonymous");
    const currentUser = await loginRequest(email, password);
    if (currentOperation !== operation.current) throw new DOMException("The account session changed.", "AbortError");
    setUser(currentUser);
    queryClient.setQueryData(queryKeys.me, currentUser);
    setState("authenticated");
    return currentUser;
  }, [queryClient]);
  const signOut = useCallback(async () => {
    operation.current += 1;
    setUser(null);
    queryClient.clear();
    setState("anonymous");
    await logoutRequest();
  }, [queryClient]);
  const retryBootstrap = useCallback(async () => {
    setState("bootstrapping");
    await bootstrap();
  }, [bootstrap]);
  const value = useMemo(() => ({ state, user, signIn, signOut, retryBootstrap }), [retryBootstrap, signIn, signOut, state, user]);
  return <QueryClientProvider client={queryClient}>
    <AuthContext.Provider value={value}>
      <TicketListLiveProvider key={getAuthEpoch()} userId={state === "authenticated" ? user?.id ?? null : null}>{children}</TicketListLiveProvider>
    </AuthContext.Provider>
  </QueryClientProvider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used within AppProviders");
  return value;
}
