/**
 * API base URLs for Gradex AI Server (common backend).
 * Matches teammate modules: viva/diagram use VITE_BACKEND_URL + /api/...
 */
const env = (import.meta as { env?: Record<string, string> }).env ?? {};

/** Server root — same env var as viva (`VITE_BACKEND_URL`), fallback `VITE_API_BASE_URL`. */
export const SERVER_BASE_URL = (
  env.VITE_BACKEND_URL?.trim() ||
  env.VITE_API_BASE_URL?.trim() ||
  "http://127.0.0.1:8000"
).replace(/\/$/, "");

/** Handwritten grading (GradingEngine mounted at /api/grading). */
export const GRADING_API_BASE_URL = `${SERVER_BASE_URL}/api/grading`;

/** Build a grading API path, e.g. gradingApi("/grading-jobs/ongoing"). */
export function gradingApi(path: string): string {
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${GRADING_API_BASE_URL}${suffix}`;
}
