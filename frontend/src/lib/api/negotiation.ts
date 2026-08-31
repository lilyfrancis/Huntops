import { api } from "../api-client";
import type { CurrencyCoverage, NegotiationReview } from "../types";

export interface NegotiationPayload {
  role_title: string;
  company_name?: string;
  location: string;
  currency: string;
  base_salary: number;
  equity?: string;
  other_terms?: string;
  has_competing_offer: boolean;
  lane?: string;
  experience_level?: string;
}

export const negotiationApi = {
  review: (payload: NegotiationPayload) => api.post<NegotiationReview>("/api/negotiation", payload),
  mine: () => api.get<NegotiationReview[]>("/api/negotiation"),
  get: (id: string) => api.get<NegotiationReview>(`/api/negotiation/${id}`),
  coverage: () => api.get<CurrencyCoverage[]>("/api/negotiation/coverage"),
};
