import { api } from "../api-client";
import type { WhatsAppConnection } from "../types";

export const whatsappApi = {
  /** Whether WhatsApp can actually reach this user, which is not the same
      question as whether they saved a number. */
  connection: () => api.get<WhatsAppConnection>("/api/whatsapp/connection"),
};
