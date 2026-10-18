import { SERVER_BASE_URL } from "../../api/gradingApiBase";
import { apiFetch } from "../../api/authApi";
import type { AssessmentMode } from "./types";
/** Viva sessions API — the label every upload / live recording is filed under.
 * Isolated from other client backends, mirroring vivaMarksApi.ts. */

export type VivaCategory = "technical" | "non_technical";

export interface Viva {
  viva_id: string;
  name: string;
  subject_code: string;
  subject_name: string;
  category: VivaCategory;
  year: number;
  semester: number;
  notes?: string | null;
  /** What this viva is marked out of (its official marks and the technical score). */
  total_marks: number;
  examiner_email: string;
  created_at?: string;
  /** e.g. "SE3040-ER Viva - semester 2 - 2026" */
  label: string;
  assessment_mode: AssessmentMode;
  mark_count?: number;
  published_count?: number;
}

export interface CreateVivaInput {
  name: string;
  subject_code: string;
  subject_name: string;
  category: VivaCategory;
  year: number;
  semester: number;
  /** Left out, the server default applies. */
  total_marks?: number;
  notes?: string;
}

async function readError(response: Response): Promise<string> {
  let detail = `HTTP ${response.status}`;
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string" && body.detail.trim()) detail = body.detail.trim();
    else if (Array.isArray(body.detail)) detail = "Check the viva details and try again.";
  } catch {
    // non-JSON error body — keep the status line
  }
  return detail;
}

export async function createViva(input: CreateVivaInput): Promise<Viva> {
  const response = await apiFetch(`${SERVER_BASE_URL}/api/vivas`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()) as Viva;
}

/** The signed-in lecturer's vivas, or everyone's when `all` is set. */
export async function listVivas(options: { all?: boolean; subjectCode?: string; category?: VivaCategory } = {}): Promise<Viva[]> {
  const params = new URLSearchParams();
  if (options.all) params.set("all", "true");
  if (options.subjectCode) params.set("subject_code", options.subjectCode);
  if (options.category) params.set("category", options.category);
  const response = await apiFetch(`${SERVER_BASE_URL}/api/vivas?${params.toString()}`);
  if (!response.ok) throw new Error(await readError(response));
  const body = (await response.json()) as { items?: Viva[] };
  return body.items ?? [];
}

export async function fetchViva(vivaId: string): Promise<Viva> {
  const response = await apiFetch(`${SERVER_BASE_URL}/api/vivas/${encodeURIComponent(vivaId)}`);
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()) as Viva;
}
