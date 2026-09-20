import { api } from "../api-client";
import type { CreditPack, Plan, SubscriptionStatus, SubscriptionTier } from "../types";

export const billingApi = {
  creditPacks: () => api.get<CreditPack[]>("/api/billing/credit-packs"),
  buyCredits: (pack: string) =>
    api.post<{ checkout_url: string }>("/api/billing/buy-credits", { pack }),
  checkoutSession: (tier: Exclude<SubscriptionTier, "free">) =>
    api.post<{ checkout_url: string }>("/api/billing/checkout-session", { tier }),
  /** Paystack's hosted manage page: update the card, or cancel there. */
  portal: () => api.get<{ portal_url: string }>("/api/billing/portal"),
  cancel: () => api.post<void>("/api/billing/cancel"),
  status: () => api.get<SubscriptionStatus>("/api/billing/status"),
  /** Public — the landing page's pricing table, so it can't drift from what
      the card is actually charged. */
  plans: () => api.get<Plan[]>("/api/billing/plans", { skipAuth: true }),
};
