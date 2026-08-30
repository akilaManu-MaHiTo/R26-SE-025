/** Viva mark publish API — isolated from other client backends. */

import type { AssessmentMode } from "./types";

const backendBaseUrl =
  ((import.meta as ImportMeta & { env?: { VITE_BACKEND_URL?: string } }).env?.VITE_BACKEND_URL) ??
  "http://localhost:8001";

const apiKey =
  ((import.meta as ImportMeta & { env?: { VITE_GRADEX_API_KEY?: string } }).env?.VITE_GRADEX_API_KEY) ??
  "";

export interface VivaPublishPayload {
  assessment_mode: AssessmentMode;
  technical_accuracy: number | null;
  student_id: string | null;
  published: boolean;
}

export interface VivaPublishResponse {
  mark_id: string;
  published: boolean;
  final_score?: number | null;
  final_grade?: string | null;
  assessment_mode?: string;
}

function authHeaders(): Record<string, string> {
  return {
    "Content-Type": "application/json",
    ...(apiKey ? { "X-API-Key": apiKey } : {}),
  };
}

export async function publishVivaMark(
  markId: string,
  payload: VivaPublishPayload,
): Promise<VivaPublishResponse> {
  const response = await fetch(`${backendBaseUrl}/api/viva-marks/${markId}/publish`, {
    method: "PATCH",
    headers: authHeaders(),
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
