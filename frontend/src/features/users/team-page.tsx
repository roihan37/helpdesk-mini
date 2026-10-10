"use client";

import { Alert, Badge, Button, EmptyState, Field, Input, LoadingPanel, Select } from "@/components/ui";
import { ProtectedGuard } from "@/features/auth/guards";
import { ApiError, apiRequest, friendlyError, validationErrors } from "@/lib/api";
import { formatDateTime, roleLabels } from "@/lib/domain";
import { queryKeys } from "@/lib/query";
import type { Role, User } from "@/types/api";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";

export function TeamPage() {
  return <ProtectedGuard roles={["admin"]}><TeamWorkspace /></ProtectedGuard>;
}

function TeamWorkspace() {
  const queryClient = useQueryClient();
  const users = useQuery({ queryKey: queryKeys.users, queryFn: () => apiRequest<User[]>("/users") });
  const [dialogOpen, setDialogOpen] = useState(false);
  const [notice, setNotice] = useState("");
  const createButton = useRef<HTMLButtonElement>(null);
  const team = users.data?.filter((user) => user.role !== "admin") ?? [];
  const closeDialog = useCallback(() => { setDialogOpen(false); requestAnimationFrame(() => createButton.current?.focus()); }, []);
  return <div className="page-stack"><header className="page-header"><div><h1>Team</h1><p>Add Agents and Customers to your business.</p></div><Button ref={createButton} onClick={() => { setNotice(""); setDialogOpen(true); }}>Create user</Button></header>{notice ? <Alert tone="success">{notice}</Alert> : null}{users.isLoading ? <LoadingPanel label="Loading team…" /> : null}{users.isError ? <Alert tone="error">Team members could not be loaded. <Button variant="quiet" onClick={() => void users.refetch()}>Retry</Button></Alert> : null}{users.data && team.length === 0 ? <EmptyState title="No Agents or Customers yet">Create a user to start building your support team.</EmptyState> : null}{team.length > 0 ? <UserRows users={team} /> : null}{dialogOpen ? <CreateUserDialog close={closeDialog} onCreated={(created) => { queryClient.setQueryData<User[]>(queryKeys.users, (current = []) => [...current, created]); setNotice(`${created.name} was created as ${roleLabels[created.role]}.`); closeDialog(); }} /> : null}</div>;
}

function UserRows({ users }: { users: User[] }) {
  return <><div className="table-wrap team-table"><table><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Created</th></tr></thead><tbody>{users.map((user) => <tr key={user.id}><td>{user.name}</td><td>{user.email}</td><td><Badge kind={user.role}>{roleLabels[user.role]}</Badge></td><td><time dateTime={user.created_at}>{formatDateTime(user.created_at)}</time></td></tr>)}</tbody></table></div><ul className="team-list-mobile">{users.map((user) => <li key={user.id}><strong>{user.name}</strong><span>{user.email}</span><span><Badge kind={user.role}>{roleLabels[user.role]}</Badge> <time dateTime={user.created_at}>{formatDateTime(user.created_at)}</time></span></li>)}</ul></>;
}

function CreateUserDialog({ close, onCreated }: { close: () => void; onCreated: (user: User) => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "agent" as Exclude<Role, "admin"> });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showPassword, setShowPassword] = useState(false);
  useEffect(() => { const node = dialog.current; node?.showModal(); const cancel = (event: Event) => { event.preventDefault(); close(); }; node?.addEventListener("cancel", cancel); return () => node?.removeEventListener("cancel", cancel); }, [close]);
  const mutation = useMutation({ mutationFn: () => apiRequest<User>("/users", { method: "POST", body: JSON.stringify({ name: form.name.trim(), email: form.email.trim().toLowerCase(), password: form.password, role: form.role }) }), onSuccess: (created) => { setForm((current) => ({ ...current, password: "" })); onCreated(created); }, onError: (reason) => { const fields = validationErrors(reason); setErrors({ ...fields, form: reason instanceof ApiError && reason.status === 409 ? reason.message : friendlyError(reason, "The user could not be created. Try again.") }); } });
  function submit(event: FormEvent) { event.preventDefault(); if (mutation.isPending) return; setErrors({}); mutation.mutate(); }
  return <dialog ref={dialog} className="dialog" aria-labelledby="create-user-title"><form className="dialog-panel form-stack" onSubmit={submit}><div className="dialog-header"><div><h2 id="create-user-title">Create user</h2><p>Add an Agent or Customer to this business.</p></div><button type="button" className="icon-button" aria-label="Close dialog" onClick={close}>×</button></div>{errors.form ? <Alert tone="error">{errors.form}</Alert> : null}<fieldset className="form-stack" disabled={mutation.isPending}><Field label="Name" name="user-name" error={errors.name}><Input id="user-name" autoFocus value={form.name} minLength={1} maxLength={255} required autoComplete="name" aria-invalid={Boolean(errors.name)} aria-describedby={errors.name ? "user-name-error" : undefined} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} /></Field><Field label="Email" name="user-email" error={errors.email}><Input id="user-email" type="email" value={form.email} required autoComplete="email" aria-invalid={Boolean(errors.email)} aria-describedby={errors.email ? "user-email-error" : undefined} onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))} /></Field><Field label="Role" name="user-role" error={errors.role}><Select id="user-role" value={form.role} onChange={(event) => setForm((current) => ({ ...current, role: event.target.value as Exclude<Role, "admin"> }))}><option value="agent">Agent</option><option value="customer">Customer</option></Select></Field><Field label="Password" name="user-password" error={errors.password} help="Use 8 to 128 characters."><div className="password-control"><Input id="user-password" type={showPassword ? "text" : "password"} value={form.password} minLength={8} maxLength={128} required autoComplete="new-password" aria-invalid={Boolean(errors.password)} aria-describedby={errors.password ? "user-password-error" : "user-password-help"} onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))} /><button className="password-toggle" type="button" aria-pressed={showPassword} onClick={() => setShowPassword((visible) => !visible)}>{showPassword ? "Hide" : "Show"}</button></div></Field></fieldset><div className="form-actions dialog-actions"><Button type="submit" disabled={mutation.isPending}>{mutation.isPending ? "Creating user…" : "Create user"}</Button><Button type="button" variant="secondary" disabled={mutation.isPending} onClick={close}>Cancel</Button></div></form></dialog>;
}
