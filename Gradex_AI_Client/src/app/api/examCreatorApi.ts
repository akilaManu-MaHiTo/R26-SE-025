import { SERVER_BASE_URL } from "./gradingApiBase";
import { apiFetch } from "./authApi";
import type { Recommendation } from "./lecturerApi";

export const BLOOM_LEVELS = ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"] as const;
export type Blueprint = {
  total_marks: number; duration_minutes: number; purpose: "final" | "revision";
  learning_outcomes: string; lecture_notes: string;
  topic_marks: Record<string, number>; bloom_percentages: Record<string, number>;
};
export const defaultBlueprint = (): Blueprint => ({
  total_marks: 100, duration_minutes: 180, purpose: "final", learning_outcomes: "", lecture_notes: "",
  topic_marks: {}, bloom_percentages: { Remember: 10, Understand: 20, Apply: 40, Analyze: 25, Evaluate: 5, Create: 0 },
});
export type MaterialSource = {
  source_id: string; kind: string; text: string;
  course_code?: string | null; filename?: string | null; page_number?: number | null;
  year?: number | null; rank_score?: number | null;
};
export type MaterialSearch = {
  status: "ok" | "unavailable"; mode: "hybrid" | "keyword" | "unavailable";
  warnings: string[]; sources: MaterialSource[];
};
export type GenerationRetrieval = { lectures: MaterialSearch; assessment_examples: MaterialSearch };
export type CreatorApiError = Error & { retrieval?: GenerationRetrieval };
export type Part = {
  part: string; question: string; max_marks: number; question_id?: string; bloom_level?: string;
  model_answer?: string; marking_scheme?: { criterion: string; marks: number }[];
  estimated_minutes?: number; review_status?: "needs_review" | "approved";
  sources?: MaterialSource[];
};
export type PaperQuestion = { question_number: number; topic: string; parts: Part[] };
export type Paper = {
  exam: string; year: number; questions: PaperQuestion[]; blueprint?: Blueprint;
  source_exam?: { session_name: string; year: number; month: number; semester: number } | null;
  rejected_questions?: { question_id: string; reason: string }[];
};
export type CreatorReview = {
  topics: string[]; analytics_available: boolean;
  recommendations: (Recommendation & { blueprint_reason: string; requires_marks: boolean; max_available_marks: number })[];
  review: {
    total_marks: number; remaining_marks: number; estimated_minutes: number; estimated_parts: number; part_count: number;
    topic_coverage: Record<string, { target: number; actual: number; remaining: number }>;
    bloom_coverage: Record<string, { target: number; actual: number }>;
    issues: { code: string; message: string }[];
  };
};
export type GeneratedCandidate = {
  text: string; topic: string; bloom_level: string; marks: number; question_id: string;
  model_answer: string; marking_scheme: NonNullable<Part["marking_scheme"]>;
  estimated_minutes: number; sources: NonNullable<Part["sources"]>; review_status: "needs_review";
};
export type Generation = {
  candidates: GeneratedCandidate[]; similarity_available: boolean; model: string;
  similarity_checks: { candidate_text: string; max_similarity: number; flagged: boolean }[];
  retrieval?: GenerationRetrieval;
};
const API_BASE = SERVER_BASE_URL;
async function post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const response = await apiFetch(`${API_BASE}/api/lecturers/exam-creator/${path}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal,
  });
  const data = await response.json();
  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail :
      typeof data.detail?.message === "string" ? data.detail.message :
      Array.isArray(data.detail) ? data.detail.map((item: { msg: string }) => item.msg).join("; ") : "Request failed";
    throw Object.assign(new Error(detail), { retrieval: data.detail?.retrieval });
  }
  return data;
}
export const reviewExamPaper = (course_code: string, paper: Paper, signal?: AbortSignal) =>
  post<CreatorReview>("review", { course_code, paper }, signal);
export const generateExamQuestions = (course_code: string, paper: Paper, topic: string, bloom_level: string, marks: number, signal?: AbortSignal) =>
  post<Generation>("generate", { course_code, paper, topic, bloom_level, marks, count: 2 }, signal);
