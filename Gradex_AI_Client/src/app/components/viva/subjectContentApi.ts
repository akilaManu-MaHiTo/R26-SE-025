import { SERVER_BASE_URL } from "../../api/gradingApiBase";
import { apiFetch } from "../../api/authApi";
/** Subject concept-rubric API — the lecturer-facing side of the technical
 * viva flow. A rubric uploaded here is what /api/viva-analyze looks up by
 * subject code to produce the advisory technical-accuracy suggestion.
 * Isolated from other client backends, mirroring vivaMarksApi.ts. */

const backendBaseUrl = SERVER_BASE_URL;

/** Weight is 0–5 server-side (SubjectRubricConceptPayload in main.py). */
export const CONCEPT_WEIGHT_MIN = 0;
export const CONCEPT_WEIGHT_MAX = 5;

export interface SubjectConcept {
  id: string;
  name: string;
  description?: string;
  weight?: number;
  /** Stamped by the server so re-uploading one file replaces only its concepts. */
  source_file?: string;
}

export interface SubjectSourceFile {
  filename?: string;
  uploaded_at?: string;
  /** Text pypdf read out of the PDF. Detail responses only — the list omits it. */
  extracted_text?: string;
  /** Length before the storage cap, so truncation is visible. */
  extracted_chars?: number;
}

/** One row of the subject browser. Carries no concepts and no extracted text. */
export interface SubjectRubricSummary {
  subject_code: string;
  subject_name: string;
  concept_count: number;
  source_files?: SubjectSourceFile[];
  updated_at?: string;
  generated_at?: string;
}

export interface SubjectRubric {
  _id?: string;
  subject_code: string;
  subject_name: string;
  concepts: SubjectConcept[];
  source_files?: SubjectSourceFile[];
  generated_at?: string;
  updated_at?: string;
  version?: number;
}

async function readError(response: Response): Promise<string> {
  let detail = `HTTP ${response.status}`;
  try {
    const body = (await response.json()) as { detail?: string };
    if (typeof body.detail === "string" && body.detail.trim()) {
      detail = body.detail.trim();
    }
  } catch {
    // non-JSON error body — keep the status line
  }
  return detail;
}

/**
 * Upload a subject PDF. The server extracts its text with pypdf (no OCR), asks
 * the LLM to distil a concept list, and merges it into the subject's rubric —
 * so several files can contribute concepts to one subject code.
 */
export async function uploadSubjectContent(
  file: File,
  subjectCode: string,
  subjectName: string,
): Promise<SubjectRubric> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("subject_code", subjectCode);
  formData.append("subject_name", subjectName);

  const response = await apiFetch(`${backendBaseUrl}/api/subject-content/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()) as SubjectRubric;
}

/** Every stored subject, newest first. Summaries only — fetch one for concepts. */
export async function listSubjectContent(): Promise<SubjectRubricSummary[]> {
  const response = await apiFetch(`${backendBaseUrl}/api/subject-content`);

  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()) as SubjectRubricSummary[];
}

/** Returns null for 404 — "no rubric yet" is a normal state, not an error. */
export async function fetchSubjectContent(subjectCode: string): Promise<SubjectRubric | null> {
  const response = await apiFetch(
    `${backendBaseUrl}/api/subject-content/${encodeURIComponent(subjectCode)}`,
  );

  if (response.status === 404) return null;
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()) as SubjectRubric;
}

/** Full replace of the curated concept list (PUT /api/subject-content/{code}). */
export async function saveSubjectContent(
  subjectCode: string,
  subjectName: string,
  concepts: SubjectConcept[],
): Promise<SubjectRubric> {
  const response = await apiFetch(
    `${backendBaseUrl}/api/subject-content/${encodeURIComponent(subjectCode)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        subject_name: subjectName,
        concepts: concepts.map((concept) => ({
          id: concept.id,
          name: concept.name,
          description: concept.description ?? "",
          weight: concept.weight ?? 3,
        })),
      }),
    },
  );

  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()) as SubjectRubric;
}
