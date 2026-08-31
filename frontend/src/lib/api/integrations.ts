import { api } from "../api-client";
import type { GmailStatus } from "../types";

export const integrationsApi = {
  gmailConnect: () => api.get<{ authorization_url: string }>("/api/integrations/gmail/connect"),
  gmailStatus: () => api.get<GmailStatus>("/api/integrations/gmail/status"),
  gmailDisconnect: () => api.delete<void>("/api/integrations/gmail"),
  gmailSync: () => api.post<{ status: string; fetched: number; extracted: number; inserted: number }>(
    "/api/integrations/gmail/sync"
  ),
};
