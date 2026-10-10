"use client";

import { Alert, Button, Field, Input, Select, Textarea } from "@/components/ui";
import { useAuth } from "@/features/auth/auth-provider";
import { ProtectedGuard } from "@/features/auth/guards";
import { apiRequest, friendlyError, validationErrors } from "@/lib/api";
import type { TicketPriority, TicketPublic } from "@/types/api";
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

export function NewTicketPage() {
  return <ProtectedGuard roles={["customer"]}><NewTicketForm /></ProtectedGuard>;
}

function NewTicketForm() {
  const { user } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ subject: "", category: "", priority: "medium" as TicketPriority, message: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState("");
  const [pending, setPending] = useState(false);
  const update = (field: keyof typeof form, value: string) => setForm((current) => ({ ...current, [field]: value }));
  async function submit(event: FormEvent) {
    event.preventDefault(); if (pending || user?.role !== "customer") return;
    setPending(true); setErrors({}); setFormError("");
    try {
      const ticket = await apiRequest<TicketPublic>("/tickets", { method: "POST", body: JSON.stringify({ subject: form.subject.trim(), category: form.category.trim(), priority: form.priority, message: form.message.trim() }) });
      await queryClient.invalidateQueries({ queryKey: ["tickets"] });
      router.push(`/tickets/${encodeURIComponent(ticket.id)}`);
    } catch (reason) {
      setErrors(validationErrors(reason));
      setFormError(friendlyError(reason, "The ticket could not be created. Check your connection and try again."));
    } finally { setPending(false); }
  }
  return <div className="page-stack form-page"><header className="page-header"><div><h1>New ticket</h1><p>Your initial message begins the conversation with support.</p></div></header>{formError ? <Alert tone="error">{formError}</Alert> : null}<form className="form-stack" onSubmit={submit}><fieldset disabled={pending} className="form-stack"><Field label="Subject" name="subject" error={errors.subject}><Input id="subject" value={form.subject} onChange={(e) => update("subject", e.target.value)} minLength={1} maxLength={150} required aria-invalid={Boolean(errors.subject)} /></Field><Field label="Category" name="category" error={errors.category}><Input id="category" value={form.category} onChange={(e) => update("category", e.target.value)} minLength={1} maxLength={100} required aria-invalid={Boolean(errors.category)} /></Field><Field label="Priority" name="priority" error={errors.priority}><Select id="priority" value={form.priority} onChange={(e) => update("priority", e.target.value)}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></Select></Field><Field label="Initial message" name="message" error={errors.message} help={form.message.length > 4500 ? `${form.message.length} / 5000 characters` : undefined}><Textarea id="message" rows={8} value={form.message} onChange={(e) => update("message", e.target.value)} minLength={1} maxLength={5000} required aria-invalid={Boolean(errors.message)} /></Field></fieldset><div className="form-actions"><Button type="submit" disabled={pending}>{pending ? "Creating ticket…" : "Create ticket"}</Button><Link className="button button-secondary" href="/tickets">Cancel</Link></div></form></div>;
}
