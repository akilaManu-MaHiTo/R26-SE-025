/** Diagram marking-guideline API — the lecturer-facing side of the diagram
 * grading flow. A guideline uploaded here lands in the same `diagram_marking`
 * collection that /api/diagram-evaluate reads its criteria from, so it becomes
 * immediately selectable when grading a submission.
 * Isolated from the other client backends, mirroring subjectContentApi.ts. */

const backendBaseUrl =
  ((import.meta as ImportMeta & { env?: { VITE_BACKEND_URL?: string } }).env?.VITE_BACKEND_URL) ??
  "http://localhost:8000";

const apiKey =
  ((import.meta as ImportMeta & { env?: { VITE_GRADEX_API_KEY?: string } }).env?.VITE_GRADEX_API_KEY) ??
  "";

/** Machine-checkable shape of one criterion. Keys vary by criterion type
 * (entity / attributes / primary key / relationship / connections / notation),
 * so this stays deliberately open. */
export type GuidelineExpected = Record<string, string | number | boolean | string[]>;

export interface GuidelineCriterion {
  id: number;
  criterion: string;
  description?: string;
  expected?: GuidelineExpected;
  marks: number;
}

export interface GuidelineSourceFile {
  filename?: string;
  uploaded_at?: string;
  /** Text pypdf read out of the PDF, so the lecturer can see what the AI read. */
  extracted_text?: string;
  extracted_chars?: number;
}

export interface DiagramGuideline {
  _id?: string;
  /** Present on an upload response; the list returns `_id` instead. */
  guideline_object_id?: string;
  status?: "created" | "updated";
  examCode: string;
  guideLines: GuidelineCriterion[];
  totalMarks: number;
  source_file?: GuidelineSourceFile;
  created_at?: string;
  updated_at?: string;
}

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  return { ...extra, ...(apiKey ? { "X-API-Key": apiKey } : {}) };
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
 * Upload a marking-guideline PDF. The server extracts its text with pypdf (no
 * OCR), asks the LLM to turn it into the {examCode, guideLines[], totalMarks}
 * structure, and upserts it against the exam code — re-uploading the same code
 * replaces its criteria rather than creating a second guideline.
 */
export async function uploadDiagramGuideline(
  file: File,
  examCode: string,
): Promise<DiagramGuideline> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("examCode", examCode);

  const response = await fetch(`${backendBaseUrl}/api/diagram-guidline`, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });

  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()) as DiagramGuideline;
}

/** Every stored guideline, newest first. */
export async function listDiagramGuidelines(): Promise<DiagramGuideline[]> {
  const response = await fetch(`${backendBaseUrl}/api/diagram-evaluate-guidelines`, {
    headers: authHeaders(),
  });

  if (!response.ok) throw new Error(await readError(response));
  const body = (await response.json()) as DiagramGuideline[];
  return Array.isArray(body) ? body : [];
}
