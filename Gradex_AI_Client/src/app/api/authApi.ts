import { SERVER_BASE_URL } from "./gradingApiBase";

export interface AuthUser {
  email: string;
  role: "lecturer" | "student";
  student_id: string | null;
}

export async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const response = await fetch(input, { ...init, credentials: "include" });
  if (response.status === 401) window.dispatchEvent(new Event("gradex:unauthorized"));
  return response;
}

export async function login(email: string, password: string): Promise<AuthUser> {
  const response = await apiFetch(`${SERVER_BASE_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Could not sign in");
  return data;
}

export async function currentUser(): Promise<AuthUser | null> {
  const response = await apiFetch(`${SERVER_BASE_URL}/api/auth/me`);
  if (response.status === 401) return null;
  if (!response.ok) throw new Error("Could not check your session. Please retry.");
  return response.json();
}

export async function logout(): Promise<void> {
  const response = await apiFetch(`${SERVER_BASE_URL}/api/auth/logout`, { method: "POST" });
  if (!response.ok && response.status !== 401) throw new Error("Could not sign out. Please retry.");
}
