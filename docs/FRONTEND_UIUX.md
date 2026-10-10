# HelpDesk Mini - Frontend UI/UX Specification

**Milestone:** M6

**Status:** Proposed for review
**Design direction:** Calm, efficient B2B support workspace

## 1. Product Experience

HelpDesk Mini should feel like a focused operations tool: information-dense enough for support work,
quiet enough for long sessions, and straightforward enough that a first-time Customer understands
the next action. Hierarchy comes from typography, spacing, and borders—not decorative dashboards.

The interface uses plain, direct language. Every visible control maps to an existing backend
capability. There are no KPI cards, charts, hero illustrations, glass effects, gradients, promotional
panels, or speculative modules.

### Experience principles

1. **Conversation is primary.** Ticket detail emphasizes the message history and composer.
2. **State is explicit.** Status, assignment, connection, pending work, and errors are visible in
   text, not color alone.
3. **Actions are contextual.** Users see only actions their role can normally perform.
4. **Failures are recoverable.** Keep safe input, explain the problem, and offer a precise retry.
5. **Security is quiet but strict.** Inaccessible Tickets use the same generic not-found treatment;
   no UI copy reveals another tenant or Customer.

## 2. Visual System

### 2.1 Color tokens

| Token | Value | Use |
|---|---|---|
| `--color-primary` | `#203A5B` | Primary actions, active navigation |
| `--color-primary-hover` | `#172F4B` | Primary hover/pressed |
| `--color-canvas` | `#F7F8FA` | Application background |
| `--color-surface` | `#FFFFFF` | Forms, tables, conversation surfaces |
| `--color-border` | `#E2E5E9` | Dividers, inputs, quiet boundaries |
| `--color-text` | `#172033` | Primary copy |
| `--color-text-muted` | `#64748B` | Secondary metadata |
| `--color-success` | `#157A60` | Success and resolved state |
| `--color-warning` | `#8A5A00` | Warnings and in-progress state |
| `--color-danger` | `#B42318` | Errors and destructive/closed warnings |
| `--color-info` | `#1D4ED8` | Informational and open state |
| `--color-focus` | `#2563EB` | Two-pixel focus ring |

Semantic badges use a pale background, dark text, and optional border. Their written labels remain
visible, so meaning never depends on hue.

| State | Text | Background | Border |
|---|---|---|---|
| Open | `#1D4ED8` | `#EFF6FF` | `#BFDBFE` |
| In progress | `#8A5A00` | `#FFFBEB` | `#FDE68A` |
| Resolved | `#157A60` | `#ECFDF5` | `#A7F3D0` |
| Closed | `#475569` | `#F1F5F9` | `#CBD5E1` |
| High priority | `#B42318` | `#FEF3F2` | `#FECDCA` |
| Medium priority | `#8A5A00` | `#FFFBEB` | `#FDE68A` |
| Low priority | `#475569` | `#F8FAFC` | `#CBD5E1` |

### 2.2 Typography

No Geist or Inter asset is currently installed. Use a dependency-free system stack that prefers a
locally available `Geist` or `Inter`, followed by `ui-sans-serif`, system fonts, and `sans-serif`.
Never load a remote font at runtime.

| Style | Size / line height | Weight | Use |
|---|---|---:|---|
| Page title | 24 / 32px | 650-700 | One per page |
| Section title | 18 / 26px | 600 | Meaningful page sections |
| Card/dialog title | 16 / 24px | 600 | Local headings |
| Body | 14 / 22px | 400 | Default product copy |
| Emphasized body | 14 / 22px | 600 | Names and primary row values |
| Metadata | 12 / 18px | 400-500 | Dates, roles, helper text |

Avoid all-uppercase headings. Use sentence case throughout.

### 2.3 Spacing and geometry

- Base scale: 4, 8, 12, 16, 20, 24, 32, 40, and 48px.
- Desktop content padding: 32px; compact desktop/tablet: 24px; mobile: 16px.
- Sidebar: 240px. Topbar: 64px. Main content maximum width: 1440px.
- Standard controls: 40px high; compact filters/table controls: 36px; touch targets: at least 44px
  through padding or hit area on mobile.
- Ticket table rows: 56px minimum.
- Radius: 6px controls and badges, 8px panels/dialogs. Do not use pill shapes except badges.
- Shadow: none for normal content; one subtle shadow only for floating menus/dialogs.
- Borders and whitespace separate content. Do not wrap every section in a card.

### 2.4 Interaction states

All interactive controls define default, hover, active, focus-visible, disabled, and pending states.
Focus uses a 2px blue ring with 2px offset. Disabled controls retain readable labels and explain the
reason nearby when the restriction is not obvious. Pending buttons retain their width and use a verb
such as “Signing in…” or “Creating ticket…”.

Motion is limited to 120-180ms color/opacity/disclosure transitions and honors
`prefers-reduced-motion`. Do not animate route content or incoming messages for decoration.

## 3. Shared Components

Implement only the primitives needed by required pages:

- **Button:** primary, secondary, quiet, and danger semantics; icon-only buttons require an accessible
  name and tooltip/title where useful.
- **Input / Textarea / Select:** persistent visible label, optional helper, inline error linked through
  `aria-describedby`, and `aria-invalid` on failure.
- **StatusBadge / PriorityBadge / RoleBadge:** compact text badges with semantic palettes.
- **Alert:** inline page or section feedback for info, success, warning, and error. Prefer this over
  transient toasts for errors the user must act on.
- **Skeleton:** layout-matched, `aria-hidden`; pair the region with a readable loading status.
- **EmptyState:** short heading, one explanatory sentence, and one valid action at most.
- **Dialog:** only for Admin Create User; labelled, focus-trapped, Escape closable, and focus-returning.
- **Drawer:** mobile navigation with the same focus/close behavior as Dialog.
- **ConnectionStatus:** compact text plus indicator; never indicator-only.

Use native `button`, `a`, `form`, `label`, `table`, `nav`, `main`, `aside`, `dialog`/accessible dialog
pattern, and disclosure semantics where possible. Inline SVG icons are optional and decorative icons
must be hidden from assistive technology. Do not add an icon package solely for common chevrons.

## 4. Authenticated Application Shell

### Desktop (1024px and wider)

- Persistent 240px left sidebar on the canvas edge.
- Brand at the top, followed by a short role-specific primary navigation.
- Compact 64px topbar above main content, containing the Business name and Account trigger.
- Main area uses 32px padding and a 1440px maximum width; Ticket detail may use the full available
  width within that maximum.
- Current navigation has a navy-tinted background, navy text, and a left marker—not color alone.

### Tablet (768-1023px)

- Sidebar collapses to a topbar-triggered drawer.
- Main padding is 24px.
- Tables retain essential columns; less critical metadata moves into a second line before the layout
  becomes horizontally scrollable.

### Mobile (below 768px)

- 56-64px topbar with brand, page context, and menu button.
- Navigation is a modal drawer; it closes on selection, Escape, and outside activation.
- Main padding is 16px with no page-level horizontal scrolling.
- Ticket tables become semantic compact lists. Actions stack or span full width when needed.
- Ticket detail prioritizes chat; metadata/actions live in an accessible “Ticket details” disclosure.

### Navigation by role

| Role | Primary navigation | Contextual action |
|---|---|---|
| Admin | Tickets, Team | Account identity menu |
| Agent | Tickets | Account identity menu |
| Customer | My tickets | New ticket, Account identity menu |

The Account menu shows name, email, role, and Business. It has no Sign out control until the backend
can clear/revoke its HttpOnly refresh cookie; clearing only memory would be misleading because the
session would return on refresh.

Every authenticated layout starts with a “Skip to main content” link.

## 5. Page Specifications

### 5.1 Login — `/login`

**Layout:** A centered 400-440px authentication panel on a quiet canvas. Product wordmark and the
sentence “Sign in to manage support tickets” appear above the form. No split-screen artwork.

**Fields and actions:** Email, Password, password visibility toggle, primary Sign in button, and a
text link “Register a business”. Use browser autocomplete `email` and `current-password`.

**Behavior:**

- Validate required email format and password presence before submission.
- Disable duplicate submit and announce “Signing in…”.
- On success, resolve `/auth/me`, then navigate to the validated local return path or `/tickets`.
- Invalid credentials use the backend's generic message; do not reveal whether an email exists.
- Retain email after failure, clear or retain password only in component memory, and never log it.

**States:** Auth bootstrap replaces the form briefly; network failure offers Retry; authenticated
visitors go to Tickets. On mobile the panel loses decorative outer chrome and uses the full width.

### 5.2 Business registration — `/register`

**Layout:** One coherent form, 560-640px wide, split by two plain section headings: “Business” and
“Administrator”. Avoid a wizard because the API performs one atomic request.

**Fields:**

- Business name: trimmed, 1-255 characters.
- Business slug: trimmed lowercase kebab case, 1-255 characters, with short format help.
- Admin name: trimmed, 1-255 characters.
- Admin email: normalized email.
- Password: 8-128 characters with visibility control and concise length help.

**Actions:** Primary “Create business”, secondary “Back to sign in”. Submission preserves safe fields
on 409/422. A duplicate slug/email error is shown at the relevant field when details identify it,
otherwise at form level. Success shows a compact confirmation and navigates to login; registration
does not assume tokens were issued.

### 5.3 Ticket list — `/tickets`

**Header:** Role-aware title (“Tickets” for staff, “My tickets” for Customer), one-line context, and
Customer-only “New ticket” primary action.

**Filter:** Labelled Status select with All, Open, In progress, Resolved, and Closed. The selected
value is represented in the URL. No search, pagination, sorting control, bulk action, or analytics.

**Desktop table columns:** Subject, Status, Priority, Assigned to, Latest activity. The complete row
is a navigation target without nesting invalid interactive controls. Display “Unassigned” plainly.
Latest activity uses localized date/time with the full ISO-derived local value available to assistive
technology or via a semantic `time` element.

**Mobile row:** Subject first; status and priority badges second; assignee and latest activity as
muted metadata. Use a list, not a squeezed table.

**States:**

- Loading: header/filter remain; render 5 row-shaped skeletons.
- Empty unfiltered: Customer sees “No tickets yet” plus New ticket; staff sees “No tickets in this
  business yet” without invented actions.
- Empty filtered: “No tickets match this status” plus Clear filter.
- Error: concise inline Alert with Retry; keep current filter.
- Refetch: keep existing rows and show subtle “Updating…” status rather than blanking the page.

### 5.4 New Ticket — `/tickets/new`

**Layout:** A single-column form up to 720px wide with visible labels and a short explanation that
the first message begins the conversation.

**Fields:** Subject (1-150), Category (1-100), Priority (`low`, `medium`, `high`), Initial message
(1-5000 after trim). Show character counts near the upper limit, not constantly as visual noise.

**Actions:** Primary “Create ticket” and secondary “Cancel” back to Tickets. While pending, all
submission controls are disabled and the button reads “Creating ticket…”. On 201, navigate directly
to `/tickets/{id}` and invalidate the Ticket list. Do not create an optimistic Ticket.

**Access/error:** Non-Customers are returned to Tickets by the presentation guard; a backend 403 is
still rendered if encountered. 422 errors map to fields. Network failures preserve the draft for an
explicit retry. Do not store message drafts beyond the mounted session.

### 5.5 Ticket detail — `/tickets/[id]`

#### Desktop composition

- Header contains Back to Tickets, subject, status and priority badges, and compact connection state.
- Below it, a two-column grid uses roughly 68% conversation and 32% details with a 24px gap.
- Conversation is one bordered surface with history above and composer anchored after/below the
  scroll region. Details are a quiet side panel, not several nested cards.

#### Conversation

- Messages are grouped only when it improves scanning; every displayed message still exposes sender
  name, role, text, and timestamp.
- Current-user messages may align right with a restrained navy tint; others align left on neutral
  surface. Admin read-only viewing retains the same semantics.
- Render bodies as React text with preserved line breaks; never interpret HTML or Markdown.
- Initial history is ordered by `(created_at, id)`. On first load, move to the newest message without
  stealing keyboard focus. New events auto-scroll only when the reader is already near the bottom;
  otherwise show “New messages” control.
- An empty history state says “No messages yet”; it must not imply messages can always be sent.

#### Composer

- Agent and owning Customer receive a multiline labelled input and Send button while connected and
  permitted. `Enter` sends only if this convention is clearly exposed; `Shift+Enter` creates a line
  break. For safer accessibility, a visible Send button always remains available.
- Body is trimmed and limited to 5000 characters.
- Sending does not append an optimistic success bubble. Show a compact pending state until the
  matching server `message.created` arrives; prevent accidental duplicate submission.
- Disconnected: disable input/send and show “Reconnecting to conversation…” or “Connection lost.
  Messages cannot be sent.”
- Closed: replace composer with “This ticket is closed. Conversation history is read-only.”
- Admin: omit the input and show “Admins can review this conversation but cannot send messages.”

#### Details and actions

Show Customer name, Category, Assigned Agent, Created, and Latest activity. IDs and `business_id`
are not useful primary UI and are not shown.

Only these action choices appear:

| Current state | Admin | Agent | Customer |
|---|---|---|---|
| `open` | Assign permitted Agent; move to In progress | Take unassigned Ticket; move to In progress | None |
| `in_progress` | Assign permitted Agent; move to Resolved | Take if unassigned; move to Resolved | None |
| `resolved` | Assign permitted Agent; move to Closed | Take if unassigned; move to Closed | Reopen own Ticket |
| `closed` | None | None | None |

Agent assignment never offers other Agents. Admin assignment options come from same-business `/users`
records filtered to role Agent. Do not offer unassignment because the update contract rejects null.
Actions show pending text and disable while running. A 409 refreshes Ticket data and explains that
the state changed; do not silently retry a mutation.

#### Mobile composition

Use compact header, conversation first, then sticky/practical composer at the bottom of its content
region. A “Ticket details” disclosure contains metadata and actions and remains reachable without
covering the composer. Respect safe-area inset and keep the textarea visible when the software
keyboard opens; do not force full viewport heights that trap content.

#### Failure states

- Detail/history loading: header and message skeletons.
- Generic 404: “Ticket not found or unavailable” with Back to Tickets. Do not distinguish why.
- 401: auth recovery, then login if unavailable.
- 403: “You do not have permission to perform this action”; do not leak additional data.
- WebSocket error event: inline conversation feedback based on documented safe message/code.
- Status event: update badge/actions without a toast; preserve the reading position.

### 5.6 Team — `/admin/users`

**Header:** “Team” and primary “Create user”. Supporting copy explains that Admin can add Agents and
Customers in the current Business.

**Desktop table:** Name, Email, Role, Created. There is no actions column because edit, delete,
invite, and reset are unsupported. Mobile uses compact rows with email wrapping safely.

**Create flow:** An accessible compact dialog on desktop and near-full-width dialog on mobile.
Fields are Name (1-255), Email, Password (8-128 with visibility control), and Role limited to Agent or
Customer. On success, close the dialog, place focus back on Create user, refresh the list, and show a
small inline success confirmation. Never display the submitted password again.

**States:** Row skeletons, “No Agents or Customers yet” empty state, inline Retry on list failure,
field/form errors on 409/422, disabled pending submit, and a role guard plus server 403 handling.

## 6. Real-Time Experience Contract

### Connection sequence

```text
Authenticate → load Ticket → load persisted history → open Ticket socket
                                              ↓ socket open
                              refetch/merge history by message ID
                                              ↓
                          process confirmed messages/status events
```

One detail view owns one socket. Navigation, auth loss, Ticket change, and unmount close it. An
unexpected disconnect enters controlled reconnect with bounded backoff. Each successful reconnect
refetches Ticket and history before normal operation. A policy/authorization closure does not spin in
an endless reconnect loop.

### Event behavior

- `message.created`: validate event shape, merge by UUID, sort by `(created_at, id)`, update latest
  activity where known, and clear the matching local pending-send state.
- `ticket.status_changed`: update Ticket detail/list cache and recompute action/composer availability.
- `error`: show a safe inline message. `TICKET_CLOSED` disables the composer and refetches detail;
  authorization/auth failures stop sending and invoke the relevant auth/error path.
- Unknown event types are ignored safely and may be logged only in development without token or
  message content.

The UI never equates a successful socket `send()` call with persistence. Only server-confirmed data
is displayed as sent.

### Connection language

| State | Visible copy | Send behavior |
|---|---|---|
| Connecting | Connecting… | Disabled |
| Connected | Live | Enabled if role/status allow |
| Reconnecting | Reconnecting… | Disabled |
| Offline | Connection lost | Disabled; explicit retry if automatic attempts stop |
| Unauthorized | Session expired or access unavailable | Disabled; recover auth or return to login |

## 7. Error and Feedback Language

Prefer specific inline language and one next action:

- Network list failure: “Tickets could not be loaded. Check your connection and try again.”
- Generic Ticket 404: “Ticket not found or unavailable.”
- 403 action: “You do not have permission to perform this action.”
- 409 state: “This ticket changed since you opened it. The latest details have been loaded.”
- 422 form: “Check the highlighted fields and try again.”
- Unexpected error: “Something went wrong. Try again.”

Do not expose stack traces or raw response bodies. Avoid toast queues; use page alerts, field errors,
or a single nearby status. Confirmation dialogs are unnecessary for create/send/valid transition
actions because none are destructive deletion operations.

## 8. Accessibility Requirements

- Meet WCAG 2.1 AA intent for contrast, keyboard operation, focus visibility, names, roles, and
  status announcements.
- Use one `h1` per page and sequential heading levels.
- Associate every input with a visible label; placeholder text is never the only label.
- Announce form summaries, connection changes, and asynchronous completion with appropriately calm
  live regions. Do not announce every incoming message aggressively.
- Use semantic tables with headers on desktop and semantic lists on mobile.
- Keep source/DOM order logical when visual layouts change.
- All controls are keyboard reachable; menus, drawer, dialog, disclosure, and password toggles have
  correct expanded/pressed state where applicable.
- Do not use color alone for status, priority, validation, current navigation, or connectivity.
- Use `time` elements and localized visible dates; preserve an unambiguous full datetime label.
- Render message content as selectable text and support long words/URLs without page overflow.
- Maintain at least 44px effective mobile targets and avoid pointer-only hover interactions.

## 9. Responsive and Content Edge Cases

Verify at 320, 375, 768, 1024, and 1440 CSS pixels, including:

- Long Business, user, subject, category, and email values.
- Maximum 5000-character multiline messages and unbroken URLs/strings.
- Empty assignee and every status/priority label.
- Browser zoom at 200% without lost controls or horizontal page overflow.
- Mobile software keyboard with Ticket composer.
- Slow requests, a disconnected socket, duplicate events, and status changing in another browser.
- UTC timestamps displayed in local time across day boundaries.

Desktop data surfaces may scroll within a clearly bounded region only when unavoidable; the page
itself must not rely on horizontal scrolling.

## 10. UX Security Boundaries

- Hidden navigation and controls are usability decisions, never authorization controls.
- Do not ask for, expose, or let users edit `business_id`, Customer identity, sender identity, or JWT
  claims.
- Clear protected TanStack Query data whenever authentication is lost.
- Use one generic inaccessible/not-found Ticket view for tenant and ownership failures.
- Never save passwords, tokens, or message drafts to Web Storage.
- Do not use `dangerouslySetInnerHTML`; message bodies, names, subjects, and errors render as text.
- Never include the WebSocket URL/token in user-facing errors or production logs.
- Production deployment requires HTTPS/WSS, exact configured origins, secure refresh cookies, and
  WebSocket query-string redaction.

## 11. Explicit Non-Features

M6 does not design or implement Analytics, Billing, Reports, Notifications Center, Settings,
pagination, search, Ticket deletion, user edit/delete/invite/reset, typing indicators, read receipts,
attachments, presence, unread badges, or backend logout/revocation. Empty visual space must not be
filled with fake product functionality.

## 12. Design Review Checklist

- All six routes and every required state are represented.
- Navigation and actions match Admin, Agent, and Customer backend permissions.
- Ticket list uses only fields returned by the API.
- Ticket transitions and assignment controls match the backend state machine.
- Admin chat and closed Ticket behavior are visibly read-only.
- Real-time messages appear only after server confirmation and remain consistent after reconnect.
- Mobile places conversation first and keeps Ticket details/actions accessible.
- Tokens, spacing, type, borders, radii, and focus styles are consistent.
- No unsupported feature, unnecessary dependency, decorative dashboard block, or fake logout appears.
- Security-sensitive errors do not reveal tenant/resource existence or tokens.
