"use client";

import { Brand, Icon, type IconName } from "@/components/icon";
import { Alert, Avatar, Button } from "@/components/ui";
import { useAuth } from "@/features/auth/auth-provider";
import { friendlyError } from "@/lib/api";
import { roleLabels } from "@/lib/domain";
import type { Role } from "@/types/api";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useEffect, useRef, useState } from "react";

function Navigation({ role, pathname, onNavigate }: {
  role: Role;
  pathname: string;
  onNavigate?: () => void
}) {
  const items = role === "admin"
    ? [{ href: "/tickets", label: "Tickets" }, { href: "/admin/users", label: "Team" }]
    : [{ href: "/tickets", label: role === "customer" ? "My tickets" : "Tickets" }];
  return <nav aria-label="Primary navigation" className="primary-nav">
    <span className="nav-label">Workspace</span>
    {items.map((item) => {
      const active = pathname === item.href || (item.href === "/tickets" && pathname.startsWith("/tickets"));
      const icon: IconName = item.href === "/tickets" ? "tickets" : "users";
      return <Link
        key={item.href}
        href={item.href}
        className={active ? "nav-link active" : "nav-link"}
        aria-current={active ? "page" : undefined}
        onClick={onNavigate}
      >
        <Icon name={icon} />
        {item.label}
      </Link>;
    })}
    {role === "customer"
      ? <Link className="button button-secondary nav-action" href="/tickets/new" onClick={onNavigate}><Icon name="plus" />New ticket</Link>
      : null}
  </nav>;
}

export function AppShell({ children }: { children: ReactNode }) {
  const { signOut, user } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [signOutError, setSignOutError] = useState("");
  const menuButton = useRef<HTMLButtonElement>(null);
  const drawer = useRef<HTMLDivElement>(null);
  const account = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!drawerOpen) return;
    const trigger = menuButton.current;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    drawer.current?.querySelector<HTMLElement>("a, button")?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setDrawerOpen(false);
      if (event.key !== "Tab" || !drawer.current) return;
      const focusable = [...drawer.current.querySelectorAll<HTMLElement>("a, button")];
      const first = focusable[0], last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      }
      else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", keydown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", keydown);
      trigger?.focus();
    };
  }, [drawerOpen]);

  useEffect(() => {
    if (!accountOpen) return;
    const dismiss = (event: MouseEvent) => {
      if (!account.current?.contains(event.target as Node)) setAccountOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setAccountOpen(false);
    };
    document.addEventListener("mousedown", dismiss);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", dismiss);
      document.removeEventListener("keydown", escape);
    };
  }, [accountOpen]);

  const handleSignOut = async () => {
    setSigningOut(true);
    setSignOutError("");
    try {
      await signOut();
      router.replace("/login");
      router.refresh();
    } catch (error) {
      setSignOutError(friendlyError(error, "Could not sign out. Try again."));
      setSigningOut(false);
    }
  };

  if (!user) return null;
  const section = pathname.startsWith("/admin") ? "Team" : "Tickets";
  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to main content</a>
    <aside className="sidebar">
      <Link href="/tickets" className="brand"><Brand /></Link>
      <Navigation role={user.role} pathname={pathname} />
      <div className="workspace-card">
        <Avatar name={user.business.name} />
        <div>
          <strong>{user.business.name}</strong>
          <span>{roleLabels[user.role]} workspace</span>
        </div>
      </div>
    </aside>
    <div className="app-column">
      <header className="topbar">
        <button
          ref={menuButton}
          type="button"
          className="menu-button"
          aria-label="Open navigation"
          aria-expanded={drawerOpen}
          onClick={() => setDrawerOpen(true)}
        >
          <Icon name="menu" />
        </button>
        <Link href="/tickets" className="mobile-brand"><Brand /></Link>
        <div className="topbar-context">
          <span className="business-name">{user.business.name}</span>
          <span className="context-divider" aria-hidden="true">/</span>
          <span>{section}</span>
        </div>
        <div className="account-wrap" ref={account}>
          <Button
            variant="quiet"
            className="account-trigger"
            aria-label={`Account: ${user.name}`}
            aria-expanded={accountOpen}
            aria-haspopup="dialog"
            onClick={() => setAccountOpen((open) => !open)}
          >
            <Avatar name={user.name} />
            <span className="account-label">
              <strong>{user.name}</strong>
              <span>{roleLabels[user.role]}</span>
            </span>
            <Icon name="chevron" />
          </Button>
          {accountOpen
            ? <div className="account-menu" role="dialog" aria-label="Account details">
              <strong>{user.name}</strong>
              <span>{user.email}</span>
              <span>{roleLabels[user.role]} · {user.business.name}</span>
              <p><Icon name="lock" /> Secure session</p>
              {signOutError ? <Alert tone="error">{signOutError}</Alert> : null}
              <Button variant="secondary" disabled={signingOut} onClick={() => void handleSignOut()}>
                <Icon name="logout" />
                {signingOut ? "Signing out…" : "Sign out"}
              </Button>
            </div>
            : null}
        </div>
      </header>
      <main id="main-content" className="main-content" tabIndex={-1}>{children}</main>
    </div>
    {drawerOpen
      ? <div
        className="drawer-backdrop"
        role="presentation"
        onMouseDown={(event) => {
          if (event.target === event.currentTarget) setDrawerOpen(false);
        }}
      >
        <div ref={drawer} className="drawer" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="drawer-heading">
            <span className="brand"><Brand /></span>
            <button
              type="button"
              className="icon-button"
              aria-label="Close navigation"
              onClick={() => setDrawerOpen(false)}
            >
              <Icon name="close" />
            </button>
          </div>
          <Navigation role={user.role} pathname={pathname} onNavigate={() => setDrawerOpen(false)} />
          <div className="workspace-card">
            <Avatar name={user.business.name} />
            <div>
              <strong>{user.business.name}</strong>
              <span>{roleLabels[user.role]} workspace</span>
            </div>
          </div>
        </div>
      </div>
      : null}
  </div>;
}
