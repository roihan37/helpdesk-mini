import { AppShell } from "@/components/app-shell";
import { ProtectedGuard } from "@/features/auth/guards";
import type { ReactNode } from "react";

export default function ProtectedLayout({ children }: { children: ReactNode }) {
  return <ProtectedGuard><AppShell>{children}</AppShell></ProtectedGuard>;
}
