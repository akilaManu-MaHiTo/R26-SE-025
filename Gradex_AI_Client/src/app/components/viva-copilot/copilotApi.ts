export type CopilotPhase = "idle" | "presentation" | "viva" | "ended";

export type SuggestionPriority = "high" | "medium" | "low";
export type SuggestionDifficulty = "basic" | "intermediate" | "advanced";
export type BloomLevel = "Understand" | "Apply" | "Analyze" | "Evaluate" | "Remember" | "Create";

export interface CopilotSuggestion {
  question: string;
  reason: string;
  difficulty: SuggestionDifficulty;
  priority: SuggestionPriority;
  bloom_level?: BloomLevel;
  category?: string;
}

export interface CopilotAnalysis {
  topics: string[];
  concepts?: string[];
  technologies?: string[];
  claims?: string[];
  gaps?: string[];
}

export interface TranscriptTurn {
  speaker: "candidate" | "interviewer" | string;
  text: string;
  final?: boolean;
  timestamp?: number;
}

export interface ProjectContext {
  project: string;
  module: string;
  notes: string;
}

export interface SessionStateData {
  phase?: CopilotPhase;
  projectContext?: ProjectContext;
  mainPoints?: string[];
  currentQuestion?: string | null;
  suggestions?: CopilotSuggestion[];
  suggestion?: unknown;
  analysis?: CopilotAnalysis;
  transcript?: TranscriptTurn[];
  askedQuestions?: string[];
  points?: string[];
}

export interface CopilotEvent {
  event: string;
  sessionId?: string;
  speaker?: string;
  text?: string;
  phase?: string;
  message?: string;
  answerId?: string;
  data?: SessionStateData;
}

const backendBaseUrl =
  ((import.meta as ImportMeta & { env?: { VITE_BACKEND_URL?: string } }).env?.VITE_BACKEND_URL) ??
  "http://localhost:8000";

const apiKey =
  ((import.meta as ImportMeta & { env?: { VITE_GRADEX_API_KEY?: string } }).env?.VITE_GRADEX_API_KEY) ??
  "";

function authHeaders(): Record<string, string> {
  return apiKey ? { "X-API-Key": apiKey } : {};
}

export function normalizeAnalysis(value: unknown): CopilotAnalysis | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  const asList = (item: unknown): string[] =>
    Array.isArray(item) ? item.map((entry) => String(entry)).filter(Boolean) : [];
  return {
    topics: asList(raw.topics),
    concepts: asList(raw.concepts),
    technologies: asList(raw.technologies),
    claims: asList(raw.claims),
    gaps: asList(raw.gaps),
  };
}

export function normalizeSuggestion(value: unknown): CopilotSuggestion | null {
  const [first] = normalizeSuggestions([value]);
  return first ?? null;
}

export function normalizeSuggestions(value: unknown): CopilotSuggestion[] {
  if (!Array.isArray(value)) return [];
  const out: CopilotSuggestion[] = [];
  for (const item of value) {
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    const question = String(row.question || "").trim();
    if (!question) continue;
    const rawBloom = String(row.bloom_level || row.bloom || "").trim();
    const bloom_level = (["Understand", "Apply", "Analyze", "Evaluate", "Remember", "Create"].includes(rawBloom)
      ? rawBloom
      : "Analyze") as BloomLevel;
    out.push({
      question,
      reason: String(row.reason || "").trim(),
      difficulty: (["basic", "intermediate", "advanced"].includes(String(row.difficulty))
        ? row.difficulty
        : "intermediate") as SuggestionDifficulty,
      priority: (["high", "medium", "low"].includes(String(row.priority))
        ? row.priority
        : "medium") as SuggestionPriority,
      bloom_level,
      category: row.category ? String(row.category).trim() : undefined,
    });
  }
  return out;
}

export function copilotHttpBase(): string {
  return backendBaseUrl.replace(/\/$/, "");
}

export function copilotWsUrl(sessionId: string): string {
  const http = copilotHttpBase();
  const ws = http.startsWith("https") ? http.replace(/^https/, "wss") : http.replace(/^http/, "ws");
  const base = `${ws}/api/viva-copilot/ws/${sessionId}`;
  if (!apiKey) return base;
  return `${base}?api_key=${encodeURIComponent(apiKey)}`;
}

async function parseError(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    if (typeof payload?.detail === "string") return payload.detail;
  } catch {
    // ignore
  }
  return `HTTP ${response.status}`;
}

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${copilotHttpBase()}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...authHeaders(),
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new Error(
      `Cannot reach ${copilotHttpBase()}. Start Gradex_AI_Server on that port, or set VITE_BACKEND_URL.`,
    );
  }
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(
        "Live viva API not found (404). Restart the FastAPI server so /api/viva-copilot is loaded.",
      );
    }
    throw new Error(await parseError(response));
  }
  return response.json() as Promise<T>;
}

export function createCopilotSession(projectContext?: ProjectContext) {
  return jsonFetch<{ sessionId: string; phase: CopilotPhase }>("/api/viva-copilot/sessions", {
    method: "POST",
    body: JSON.stringify(projectContext ? { projectContext } : {}),
  });
}

export function setCopilotPhase(sessionId: string, phase: "presentation" | "viva") {
  return jsonFetch<{ sessionId: string; phase: CopilotPhase }>(
    `/api/viva-copilot/sessions/${sessionId}/phase`,
    { method: "POST", body: JSON.stringify({ phase }) },
  );
}

export function askCopilotQuestion(sessionId: string, question: string) {
  return jsonFetch<{ sessionId: string; currentQuestion: string }>(
    `/api/viva-copilot/sessions/${sessionId}/ask`,
    { method: "POST", body: JSON.stringify({ question }) },
  );
}

export function finalizeCopilotUtterance(sessionId: string) {
  return jsonFetch<{ ok: boolean }>(`/api/viva-copilot/sessions/${sessionId}/finalize`, {
    method: "POST",
  });
}

export function updateCopilotContext(sessionId: string, projectContext: ProjectContext) {
  return jsonFetch(`/api/viva-copilot/sessions/${sessionId}/context`, {
    method: "POST",
    body: JSON.stringify({ projectContext }),
  });
}

export type CopilotAssessmentMode = "WITH_TECHNICAL_ACCURACY" | "WITHOUT_TECHNICAL_ACCURACY";

export interface AnalyzeSessionOptions {
  assessmentMode: CopilotAssessmentMode;
  subjectCode?: string;
  studentId?: string;
  progressId?: string;
}

/** Upload the full session recording and run the same analysis+scoring chain
 * as an uploaded viva video. Returns the engine result (assessment, grade,
 * audio_analysis, timeline, ...) exactly as /api/viva-analyze does. */
export async function analyzeCopilotSession(
  sessionId: string,
  recording: Blob,
  options: AnalyzeSessionOptions,
): Promise<Record<string, unknown>> {
  const form = new FormData();
  const ext = recording.type.includes("mp4") ? "mp4" : "webm";
  form.append("video", recording, `live-viva-${sessionId}.${ext}`);
  form.append("assessment_mode", options.assessmentMode);
  if (options.subjectCode) form.append("subject_code", options.subjectCode);
  if (options.studentId) form.append("student_id", options.studentId);
  if (options.progressId) form.append("progress_id", options.progressId);

  const url = `${copilotHttpBase()}/api/viva-copilot/sessions/${sessionId}/analyze`;
  let response: Response;
  try {
    // No Content-Type header: the browser sets the multipart boundary itself.
    response = await fetch(url, {
      method: "POST",
      headers: { Accept: "application/json", ...authHeaders() },
      body: form,
    });
  } catch {
    throw new Error(
      `Cannot reach ${copilotHttpBase()}. Start Gradex_AI_Server on that port, or set VITE_BACKEND_URL.`,
    );
  }
  if (!response.ok) throw new Error(await parseError(response));
  return response.json() as Promise<Record<string, unknown>>;
}

export function getCopilotTranscript(sessionId: string) {
  return jsonFetch<Record<string, unknown>>(
    `/api/viva-copilot/sessions/${sessionId}/transcript`,
  );
}

export function endCopilotSession(sessionId: string) {
  return jsonFetch<{ ok: boolean }>(`/api/viva-copilot/sessions/${sessionId}`, { method: "DELETE" });
}
