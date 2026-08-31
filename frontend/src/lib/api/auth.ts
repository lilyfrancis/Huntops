import { api } from "../api-client";
import type { TokenPair, User, UserRole } from "../types";

export interface RegisterPayload {
  email: string;
  password: string;
  full_name: string;
  role: Exclude<UserRole, "admin">;
  company_name?: string;
}

export const authApi = {
  register: (payload: RegisterPayload) => api.post<TokenPair>("/api/auth/register", payload, { skipAuth: true }),
  login: (email: string, password: string) =>
    api.post<TokenPair>("/api/auth/login", { email, password }, { skipAuth: true }),
  me: () => api.get<User>("/api/auth/me"),
  updateProfile: (payload: {
    full_name?: string;
    company_name?: string;
    home_market?: string;
    positioning_statement?: string;
  }) => api.put<User>("/api/users/profile", payload),
};
