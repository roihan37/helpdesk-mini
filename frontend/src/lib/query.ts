import { QueryClient } from "@tanstack/react-query";

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 15_000,
        retry: (count, error) =>
          count < 1 && (!(error instanceof Error) || !("status" in error) || Number(error.status) >= 500),
        refetchOnWindowFocus: false,
      },
      mutations: { retry: false },
    },
  });
}

export const queryKeys = {
  me: ["me"] as const,
  tickets: (status?: string) => ["tickets", { status: status || "all" }] as const,
  ticket: (id: string) => ["ticket", id] as const,
  messages: (id: string) => ["ticket-messages", id] as const,
  users: ["users"] as const,
};
