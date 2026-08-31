import { api } from "../api-client";
import type { SubscriptionTier } from "../types";

export const billingApi = {
  checkoutSession: (tier: Exclude<SubscriptionTier, "free">) =>
    api.post<{ checkout_url: string }>("/api/billing/checkout-session", { tier }),
  portal: () => api.get<{ portal_url: string }>("/api/billing/portal"),
};
