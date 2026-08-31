import type { UserRole } from "./types";

export function homePathForRole(role: UserRole): string {
  switch (role) {
    case "job_seeker":
      return "/app";
    case "employer":
      return "/employer";
    case "admin":
      return "/admin";
  }
}
