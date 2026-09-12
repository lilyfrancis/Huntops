import { api } from "../api-client";
import type {
  AdminAnalytics,
  AlertMailbox,
  AlertSender,
  IntegrationStatus,
  EmailSyncRun,
  IngestionRun,
  Job,
  JobLane,
  MailboxSyncResult,
  MailboxTestResult,
  User,
} from "../types";

export interface MailboxUpsertPayload {
  email_address: string;
  market: string;
  imap_host: string;
  imap_port?: number;
  imap_username?: string;
  /* Omit on edit to keep the stored one — the API never returns it, so a form
     cannot round-trip it. */
  imap_password?: string;
  imap_use_ssl?: boolean;
  imap_folder?: string;
  label?: string;
  lanes?: JobLane[];
}

export interface MailboxUpdatePayload {
  label?: string;
  market?: string;
  lanes?: JobLane[];
  is_active?: boolean;
}

export const adminApi = {
  users: (skip = 0, limit = 50) => api.get<User[]>(`/api/admin/users?skip=${skip}&limit=${limit}`),
  approveUser: (userId: string) => api.put<User>(`/api/admin/users/${userId}/approve`),
  suspendUser: (userId: string) => api.put<User>(`/api/admin/users/${userId}/suspend`),

  pendingJobs: () => api.get<Job[]>("/api/admin/jobs/pending"),
  approveJob: (jobId: string) => api.put<Job>(`/api/admin/jobs/${jobId}/approve`),
  rejectJob: (jobId: string, reason: string) => api.put<Job>(`/api/admin/jobs/${jobId}/reject`, { reason }),

  triggerAggregation: () => api.post<Record<string, { fetched: number; inserted: number; status: string }>>(
    "/api/admin/jobs/aggregate"
  ),
  rescanGhosts: () =>
    api.post<{ scanned: number; clean: number; caution: number; likely_ghost: number }>(
      "/api/admin/jobs/rescan-ghosts"
    ),
  aggregationRuns: () => api.get<IngestionRun[]>("/api/admin/jobs/aggregation-runs"),
  emailSyncRuns: () => api.get<EmailSyncRun[]>("/api/admin/email-sync-runs"),
  analytics: () => api.get<AdminAnalytics>("/api/admin/analytics"),

  mailboxes: () => api.get<AlertMailbox[]>("/api/admin/mailboxes"),
  upsertMailbox: (payload: MailboxUpsertPayload) => api.put<AlertMailbox>("/api/admin/mailboxes", payload),
  testMailbox: (id: string) => api.post<MailboxTestResult>(`/api/admin/mailboxes/${id}/test`),
  updateMailbox: (id: string, payload: MailboxUpdatePayload) =>
    api.patch<AlertMailbox>(`/api/admin/mailboxes/${id}`, payload),
  deleteMailbox: (id: string) => api.delete<void>(`/api/admin/mailboxes/${id}`),
  syncMailbox: (id: string) => api.post<MailboxSyncResult>(`/api/admin/mailboxes/${id}/sync`),
  syncAllMailboxes: () => api.post<MailboxSyncResult[]>("/api/admin/mailboxes/sync"),

  integrations: () => api.get<IntegrationStatus[]>("/api/admin/integrations"),
  testIntegration: (name: string) => api.post<IntegrationStatus>(`/api/admin/integrations/${name}/test`),

  alertSenders: () => api.get<AlertSender[]>("/api/admin/alert-senders"),
  addAlertSender: (domain: string, note?: string) =>
    api.post<AlertSender>("/api/admin/alert-senders", { domain, note }),
  deleteAlertSender: (id: string) => api.delete<void>(`/api/admin/alert-senders/${id}`),
};
