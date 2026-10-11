export type Role = "admin" | "agent" | "customer";
export type TicketStatus = "open" | "in_progress" | "resolved" | "closed";
export type TicketPriority = "low" | "medium" | "high";

export interface Business {
  id: string;
  name: string;
  slug: string;
}

export interface CurrentUser {
  id: string;
  name: string;
  email: string;
  role: Role;
  business: Business;
}

export interface User {
  id: string;
  business_id: string;
  name: string;
  email: string;
  role: Role;
  created_at: string;
}

export interface UserSummary {
  id: string;
  name: string;
}

export interface TicketListResponse {
  data: TicketListItem[];
  pagination: {
    page: number;
    page_size: number;
    total_items: number;
    total_pages: number;
  };
}

export interface TicketListItem {
  id: string;
  business_id: string;
  customer_id: string;
  assigned_agent_id: string | null;
  subject: string;
  category: string;
  priority: TicketPriority;
  status: TicketStatus;
  created_at: string;
  updated_at: string;
  assigned_agent: UserSummary | null;
  unread_count?: number;
}

export type TicketPublic = Omit<TicketListItem, "assigned_agent" | "unread_count">;

export interface TicketDetail extends Omit<TicketListItem, "unread_count"> {
  customer: UserSummary;
}

export interface Message {
  id: string;
  /** Decimal PostgreSQL position; optional only for pre-B5 cached responses. */
  sequence?: string;
  ticket_id: string;
  sender_id: string;
  sender_name: string;
  sender_role: Role;
  body: string;
  created_at: string;
  /** Recipient-specific receipts, returned only for the viewer's own messages. */
  read_by?: MessageReader[];
}

export interface MessageReader {
  user_id: string;
  name: string;
  role: "agent" | "customer";
}

export interface MessageReadData extends MessageReader {
  ticket_id: string;
  last_read_sequence: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
}

export interface AccessTokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
}

export interface RegistrationResponse {
  business: Business;
  admin: User;
}

export type ErrorDetails = unknown;

export interface ApiErrorPayload {
  error?: {
    code?: string;
    message?: string;
    details?: ErrorDetails;
  };
}

export type WebSocketEvent =
  | {
    type: "typing.start" | "typing.stop";
    data: MessageReader & { ticket_id: string };
  }
  | {
    type: "message.read";
    data: MessageReadData;
  }
  | {
    type: "message.created";
    data: Message
  }
  | {
    type: "ticket.status_changed";
    data: {
      ticket_id: string;
      status: TicketStatus;
      updated_at: string
    };
  }
  | {
    type: "error";
    data: {
      code: string;
      message: string
    }
  };

export interface TicketListEvent {
  type: "ticket.created" | "ticket.message_created" | "ticket.status_changed" | "ticket.assignment_changed" | "ticket.read";
  data: { ticket_id: string; updated_at: string };
}
