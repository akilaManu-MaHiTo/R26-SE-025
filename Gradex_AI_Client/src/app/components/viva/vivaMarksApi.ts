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
  final_score?: number | null;
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
