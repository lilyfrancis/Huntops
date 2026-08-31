// Access + refresh tokens live in localStorage, which is readable by any
// script on the page (XSS risk) — the more secure alternative is the backend
// setting httpOnly cookies instead of returning tokens in the JSON body.
// That's a real upgrade worth making before this handles real user data at
// scale; for now it matches how the API is actually built (Bearer tokens in
// the response body, not Set-Cookie).

const ACCESS_KEY = "huntops.access_token";
const REFRESH_KEY = "huntops.refresh_token";

export const tokenStorage = {
  getAccess: () => localStorage.getItem(ACCESS_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_KEY),
  set: (access: string, refresh: string) => {
    localStorage.setItem(ACCESS_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
  },
  setAccess: (access: string) => localStorage.setItem(ACCESS_KEY, access),
  clear: () => {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};
