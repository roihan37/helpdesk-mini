import type { Metadata } from "next";
import { Suspense, type ReactNode } from "react";
import { AppProviders } from "@/features/auth/auth-provider";
import { WorkspaceSkeleton } from "@/components/loading-skeletons";
import "./globals.css";

export const metadata: Metadata = {
  title: "HelpDesk Mini",
  description: "A secure multi-tenant support ticketing application",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Suspense fallback={<WorkspaceSkeleton />}>
          <AppProviders>{children}</AppProviders>
        </Suspense>
      </body>
    </html>
  );
}
