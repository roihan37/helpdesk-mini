"use client";

import { Alert, Button } from "@/components/ui";
import { AuthSkeleton, WorkspaceSkeleton } from "@/components/loading-skeletons";
import { useAuth } from "@/features/auth/auth-provider";
import { safeReturnPath } from "@/lib/domain";
import type { Role } from "@/types/api";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { type ReactNode, useEffect } from "react";

export function ProtectedGuard({ children, roles }: {
  children: ReactNode;
  roles?: Role[]
}) {
  const auth = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  useEffect(() => {
    if (auth.state === "anonymous") {
      const query = searchParams.toString();
      router.replace(`/login?next=${encodeURIComponent(query ? `${pathname}?${query}` : pathname)}`);
    }
  }, [auth.state, pathname, router, searchParams]);
  if (auth.state === "bootstrapping") return <WorkspaceSkeleton label="Restoring your session…" pathname={pathname} />;
  if (auth.state === "unavailable") return <div className="centered-state">
    <Alert tone="error">The service could not be reached. Check your connection and try again.</Alert>
    <Button onClick={() => void auth.retryBootstrap()}>Retry</Button>
  </div>;
  if (auth.state !== "authenticated" || !auth.user) return <AuthSkeleton label="Opening sign in…" />;
  if (roles && !roles.includes(auth.user.role)) return <div className="centered-state">
    <Alert tone="warning">You do not have permission to view this page.</Alert>
    <Button variant="secondary" onClick={() => router.replace("/tickets")}>Back to tickets</Button>
  </div>;
  return children;
}

export function PublicOnly({ children }: { children: ReactNode }) {
  const auth = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  useEffect(() => {
    if (auth.state === "authenticated" && auth.user) router.replace(safeReturnPath(searchParams.get("next"), auth.user.role));
  }, [auth.state, auth.user, router, searchParams]);
  if (auth.state === "bootstrapping") return <AuthSkeleton label="Checking your session…" registration={pathname === "/register"} />;
  if (auth.state === "authenticated") return <WorkspaceSkeleton label="Opening tickets…" />;
  return children;
}
