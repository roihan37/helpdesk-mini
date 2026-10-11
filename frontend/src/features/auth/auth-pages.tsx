"use client";

import { Alert, Button, Field, Input } from "@/components/ui";
import { Brand, Icon } from "@/components/icon";
import { useAuth } from "@/features/auth/auth-provider";
import { PublicOnly } from "@/features/auth/guards";
import { apiRequest, friendlyError, validationErrors } from "@/lib/api";
import { safeReturnPath } from "@/lib/domain";
import type { RegistrationResponse } from "@/types/api";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, useState } from "react";

function PasswordInput({ id, value, onChange, autoComplete, error, help, disabled }: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: string;
  error?: string;
  help?: string;
  disabled?: boolean
}) {
  const [visible, setVisible] = useState(false);
  return <Field label="Password" name={id} error={error} help={help}>
    <div className="password-control">
      <Input
        id={id}
        name={id}
        type={visible ? "text" : "password"}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        autoComplete={autoComplete}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : help ? `${id}-help` : undefined}
        minLength={autoComplete === "new-password" ? 8 : undefined}
        maxLength={autoComplete === "new-password" ? 128 : undefined}
        placeholder="Enter your password"
        disabled={disabled}
        required
      />
      <button
        className="password-toggle"
        type="button"
        aria-pressed={visible}
        disabled={disabled}
        onClick={() => setVisible((current) => !current)}
      >
        {visible ? "Hide" : "Show"}
      </button>
    </div>
  </Field>;
}

export function LoginPage() {
  const auth = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    setPending(true);
    setError("");
    try {
      await auth.signIn(email.trim().toLowerCase(), password);
      router.replace(safeReturnPath(searchParams.get("next")));
    } catch (reason) {
      setError(friendlyError(reason, "Sign in failed. Check your details and try again."));
    } finally {
      setPending(false);
    }
  }
  return <PublicOnly>
    <main className="auth-page">
      <div className="auth-layout">
        <Link className="wordmark" href="/"><Brand /></Link>
        <section className="auth-panel" aria-labelledby="login-title">
          <header className="auth-heading">
            <h1 id="login-title">Welcome back</h1>
            <p className="auth-intro">Sign in to your support workspace.</p>
          </header>
          {searchParams.get("registered") === "1"
            ? <Alert tone="success">Business created. Sign in with your administrator account.</Alert>
            : null}
          {error ? <Alert tone="error">{error}</Alert> : null}
          <form className="form-stack" onSubmit={submit}>
            <Field label="Email address" name="email">
              <Input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                placeholder="you@company.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
                disabled={pending}
              />
            </Field>
            <PasswordInput
              id="password"
              value={password}
              onChange={setPassword}
              autoComplete="current-password"
              disabled={pending}
            />
            <Button type="submit" disabled={pending}>
              {pending ? "Signing in…" : "Sign in"}
              <Icon name="arrowRight" />
            </Button>
          </form>
          <p className="auth-footer">New to HelpDesk? <Link href="/register">Register a business</Link></p>
        </section>
        <p className="auth-caption"><Icon name="lock" /> A private workspace for your team and customers.</p>
      </div>
    </main>
  </PublicOnly>;
}

export function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({ businessName: "", slug: "", adminName: "", email: "", password: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState("");
  const [pending, setPending] = useState(false);
  const update = (field: keyof typeof form, value: string) => setForm((current) => ({ ...current, [field]: value }));
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    setPending(true);
    setErrors({});
    setFormError("");
    try {
      await apiRequest<RegistrationResponse>(
        "/auth/register-business",
        {
          method: "POST",
          auth: false,
          retryAuth: false,
          body: JSON.stringify({
            business: { name: form.businessName.trim(), slug: form.slug.trim().toLowerCase() },
            admin: { name: form.adminName.trim(), email: form.email.trim().toLowerCase(), password: form.password }
          })
        }
      );
      setForm((current) => ({ ...current, password: "" }));
      router.replace("/login?registered=1");
    } catch (reason) {
      const apiFields = validationErrors(reason);
      setErrors({
        businessName: apiFields["business.name"],
        slug: apiFields.slug,
        adminName: apiFields["admin.name"],
        email: apiFields.email,
        password: apiFields.password
      });
      setFormError(friendlyError(reason, "Registration failed. Check the highlighted fields and try again."));
    } finally {
      setPending(false);
    }
  }
  return <PublicOnly>
    <main className="auth-page">
      <div className="auth-layout auth-layout-wide">
        <Link className="wordmark" href="/"><Brand /></Link>
        <section className="auth-panel" aria-labelledby="register-title">
          <header className="auth-heading">
            <h1 id="register-title">Create your workspace</h1>
            <p className="auth-intro">Set up your business and its first administrator.</p>
          </header>
          {formError ? <Alert tone="error">{formError}</Alert> : null}
          <form className="form-stack" onSubmit={submit}>
            <fieldset className="form-section" disabled={pending}>
              <legend>Business details</legend>
              <div className="form-stack">
                <Field label="Business name" name="businessName" error={errors.businessName}>
                  <Input
                    id="businessName"
                    placeholder="Your company name"
                    value={form.businessName}
                    onChange={(e) => update("businessName", e.target.value)}
                    minLength={1}
                    maxLength={255}
                    required
                    aria-invalid={Boolean(errors.businessName)}
                    aria-describedby={errors.businessName ? "businessName-error" : undefined}
                  />
                </Field>
                <Field
                  label="Business slug"
                  name="slug"
                  error={errors.slug}
                  help="A unique identifier. Use lowercase letters, numbers, and hyphens."
                >
                  <Input
                    id="slug"
                    placeholder="your-company"
                    value={form.slug}
                    onChange={(e) => update("slug", e.target.value.toLowerCase())}
                    pattern="[a-z0-9]+(?:-[a-z0-9]+)*"
                    maxLength={255}
                    required
                    aria-invalid={Boolean(errors.slug)}
                    aria-describedby={errors.slug ? "slug-error" : "slug-help"}
                  />
                </Field>
              </div>
            </fieldset>
            <fieldset className="form-section" disabled={pending}>
              <legend>Administrator account</legend>
              <div className="form-stack">
                <div className="form-pair">
                  <Field label="Full name" name="adminName" error={errors.adminName}>
                    <Input
                      id="adminName"
                      placeholder="Your full name"
                      value={form.adminName}
                      onChange={(e) => update("adminName", e.target.value)}
                      maxLength={255}
                      autoComplete="name"
                      required
                      aria-invalid={Boolean(errors.adminName)}
                      aria-describedby={errors.adminName ? "adminName-error" : undefined}
                    />
                  </Field>
                  <Field label="Email address" name="registerEmail" error={errors.email}>
                    <Input
                      id="registerEmail"
                      placeholder="you@company.com"
                      type="email"
                      value={form.email}
                      onChange={(e) => update("email", e.target.value)}
                      autoComplete="email"
                      required
                      aria-invalid={Boolean(errors.email)}
                      aria-describedby={errors.email ? "registerEmail-error" : undefined}
                    />
                  </Field>
                </div>
                <PasswordInput
                  id="registerPassword"
                  value={form.password}
                  onChange={(value) => update("password", value)}
                  autoComplete="new-password"
                  error={errors.password}
                  help="Use 8 to 128 characters."
                  disabled={pending}
                />
              </div>
            </fieldset>
            <Button type="submit" disabled={pending}>
              {pending ? "Creating business…" : "Create business"}
              <Icon name="arrowRight" />
            </Button>
          </form>
          <p className="auth-footer">Already have an account? <Link href="/login">Sign in</Link></p>
        </section>
      </div>
    </main>
  </PublicOnly>;
}
