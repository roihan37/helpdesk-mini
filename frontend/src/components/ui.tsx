import {
  forwardRef,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes
} from "react";
import { Icon } from "@/components/icon";

type ButtonVariant = "primary" | "secondary" | "quiet" | "danger";
export const Button = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }>(function Button({ variant = "primary", className = "", ...props }, ref) {
  return <button ref={ref} className={`button button-${variant} ${className}`} {...props} />;
});
interface FieldProps {
  label: string;
  name: string;
  error?: string;
  help?: string;
  children: ReactNode
}
export function Field({ label, name, error, help, children }: FieldProps) {
  return <div className="field">
    <label htmlFor={name}>{label}</label>
    {children}
    {error ? <p className="field-error" id={`${name}-error`}>{error}</p> : null}
    {!error && help ? <p className="field-help" id={`${name}-help`}>{help}</p> : null}
  </div>;
}
export function Input({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`control ${className}`} {...props} />;
}
export function Textarea({ className = "", ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={`control textarea ${className}`} {...props} />;
}
export function Select({ className = "", ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={`control select ${className}`} {...props} />;
}
export function Alert({ children, tone = "info" }: {
  children: ReactNode;
  tone?: "info" | "success" | "warning" | "error"
}) {
  return <div className={`alert alert-${tone}`} role={tone === "error" ? "alert" : "status"}>{children}</div>;
}
export function Badge({ children, kind }: {
  children: ReactNode;
  kind: string
}) {
  return <span className={`badge badge-${kind}`}>{children}</span>;
}
export function Skeleton({ className = "" }: { className?: string }) {
  return <span className={`skeleton ${className}`} aria-hidden="true" />;
}
export function EmptyState({ title, children, action }: {
  title: string;
  children: ReactNode;
  action?: ReactNode
}) {
  return <div className="empty-state">
    <span className="empty-icon"><Icon name="tickets" /></span>
    <h2>{title}</h2>
    <p>{children}</p>
    {action}
  </div>;
}

export function Avatar({ name, small = false }: {
  name: string;
  small?: boolean
}) {
  const initials = name.trim().split(/\s+/).slice(0, 2).map((part) => Array.from(part)[0] ?? "").join("")
    .toLocaleUpperCase();
  return <span className={`avatar${small ? " avatar-small" : ""}`} aria-hidden="true">{initials}</span>;
}
