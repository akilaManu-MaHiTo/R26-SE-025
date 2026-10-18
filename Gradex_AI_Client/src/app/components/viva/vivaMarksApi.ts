import { SERVER_BASE_URL } from "../../api/gradingApiBase";
import { apiFetch } from "../../api/authApi";
/** Viva mark publish API — isolated from other client backends. */

import type { AssessmentMode } from "./types";

const backendBaseUrl = SERVER_BASE_URL;


export interface VivaPublishPayload {
  assessment_mode: AssessmentMode;
  technical_accuracy: number | null;
  student_id: string | null;
  published: boolean;
}

export interface VivaPublishResponse {
  mark_id: string;
  published: boolean;
  /** 0-100 percentage the official mark is derived from. */
  final_score?: number | null;
  /** The official mark, out of `final_mark_max` (the scale it was given on). */
  final_mark?: number | null;
  final_mark_max?: number | null;
  final_grade?: string | null;
  assessment_mode?: string;
}



export async function publishVivaMark(
  markId: string,
  payload: VivaPublishPayload,
): Promise<VivaPublishResponse> {
  const response = await apiFetch(`${backendBaseUrl}/api/viva-marks/${markId}/publish`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (typeof body.detail === "string" && body.detail.trim()) {
        detail = body.detail.trim();
      }
    } catch {
      // ignore
    }
    throw new Error(detail);
  }

  return (await response.json()) as VivaPublishResponse;
}


/** One row of the saved-results list (GET /api/viva-marks). */
export interface VivaMarkSummary {
  mark_id: string;
  video_filename: string | null;
  student_id: string | null;
  subject_code?: string | null;
  subject_name?: string | null;
  viva_id?: string | null;
  /** What the viva was marked out of when this recording was analysed. */
  viva_total_marks?: number | null;
  /** Technical vivas: the technical share (percent) the final mark was calculated with. */
  viva_technical_percent?: number | null;
  viva_label?: string | null;
  viva_category?: string | null;
  examiner_email?: string | null;
  published_by?: string | null;
  processed_at?: string | null;
  published: boolean;
  published_at?: string | null;
  assessment_mode?: string | null;
  video_status?: string | null;
  ai_performance_score?: number | null;
  /** Out of the scale's technical maximum. */
  technical_accuracy?: number | null;
  /** 0-100 percentage the official mark is derived from. */
  final_score?: number | null;
  /** The official mark, out of `final_mark_max` (the scale it was given on). */
  final_mark?: number | null;
  final_mark_max?: number | null;
  ai_performance_mark?: number | null;
  final_grade?: string | null;
  status?: string | null;
  scoring_version?: string | null;
}

/** A full saved mark (GET /api/viva-marks/{id}). `result` is the stored analysis. */
export interface VivaMarkDocument extends Omit<VivaMarkSummary, "mark_id"> {
  _id: string;
  human_published?: boolean;
  assessment?: Record<string, unknown>;
  result?: Record<string, unknown>;
}

async function readMarksError(response: Response): Promise<string> {
  let detail = `HTTP ${response.status}`;
  try {
    const body = (await response.json()) as { detail?: string };
    if (typeof body.detail === "string" && body.detail.trim()) detail = body.detail.trim();
  } catch {
    // non-JSON error body — keep the status line
  }
  return detail;
}

/** Newest first. The server caps `limit` at 100. */
export async function listVivaMarks(
  limit = 100,
  studentId?: string,
  vivaId?: string,
): Promise<VivaMarkSummary[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (vivaId?.trim()) params.set("viva_id", vivaId.trim());
  if (studentId?.trim()) params.set("student_id", studentId.trim());
  const response = await apiFetch(`${backendBaseUrl}/api/viva-marks?${params.toString()}`);
  if (!response.ok) throw new Error(await readMarksError(response));
  const body = (await response.json()) as { items?: VivaMarkSummary[] };
  return body.items ?? [];
}

export async function fetchVivaMark(markId: string): Promise<VivaMarkDocument> {
  const response = await apiFetch(
    `${backendBaseUrl}/api/viva-marks/${encodeURIComponent(markId)}`,
  );
  if (!response.ok) throw new Error(await readMarksError(response));
  return (await response.json()) as VivaMarkDocument;
}

/** Assign a saved mark to a student; pass null/"" to clear it. */
export async function setVivaMarkStudent(
  markId: string,
  studentId: string | null,
): Promise<{ mark_id: string; student_id: string | null }> {
  const response = await apiFetch(
    `${backendBaseUrl}/api/viva-marks/${encodeURIComponent(markId)}/student`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ student_id: studentId?.trim() || null }),
    },
  );
  if (!response.ok) throw new Error(await readMarksError(response));
  return (await response.json()) as { mark_id: string; student_id: string | null };
}

/** Server timestamps are UTC but arrive without a zone suffix; read them as UTC. */
export function formatServerDate(value?: string | null): string {
  if (!value) return "";
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
  const parsed = new Date(hasZone ? value : `${value}Z`);
  return Number.isNaN(parsed.getTime()) ? "" : parsed.toLocaleString();
}
