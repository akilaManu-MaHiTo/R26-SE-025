const API_BASE =
  (import.meta as { env?: Record<string, string> }).env?.VITE_API_BASE_URL ??
  "http://127.0.0.1:8000";

/* ─── Types ────────────────────────────────────────────────────────────── */

export interface ExamListItem {
  course_code: string;
  subject_name: string;
  session_name: string;
  year: number;
  month: number;
  semester: number;
  total_marks: number;
  question_count: number;
  student_count: number;
  average_score: number;
  average_percentage: number;
  highest_score: number;
  lowest_score: number;
  pass_rate: number;
  analyzed: boolean;
  analyzed_at: string | null;
}

export interface ExamStatistics {
  total_students: number;
  attempted_students: number;
  average_score: number;
  average_percentage: number;
  pass_rate: number;
  highest_score: number;
  lowest_score: number;
  median_score?: number;
  median_percentage?: number;
  std_score?: number;
  std_percentage?: number;
  iqr_percentage?: number;
  grade_distribution?: Record<string, number>;
}

export interface TopicPerformance {
  topic: string;
  average_percentage: number;
  status: string;
}

export interface BloomPerformance {
  level: string;
  average_percentage: number;
  evidence_status?: string;
  student_count?: number;
  attempt_count?: number;
}

export interface TopicBloomCell {
  topic: string;
  bloom_level: string;
  average_percentage: number;
  student_count: number;
  attempt_count: number;
  evidence_status: string;
}

export interface QuestionPerformance {
  question_id: string;
  question_no: string;
  topic: string;
  bloom_level: string;
  average_percentage: number;
  evidence_status?: string;
  student_count?: number;
  attempt_count?: number;
  p_value?: number;
  discrimination?: number;
  missed_criterion_rate?: number | null;
}

export interface AttentionArea {
  type: string;
  name: string;
  average_percentage: number;
  priority: string;
}

export interface ExamAnalytics {
  subject_code: string;
  subject_name: string;
  year: number;
  month: number;
  semester: number;
  session_name: string;
  exam: {
    session_name: string;
    total_marks: number;
    question_count: number;
  };
  statistics: ExamStatistics;
  topic_performance: TopicPerformance[];
  bloom_performance: BloomPerformance[];
  question_performance: QuestionPerformance[];
  topic_bloom_matrix?: TopicBloomCell[];
  attention_areas: AttentionArea[];
  insights: string[];
  canonical_topic_performance: CanonicalTopic[];
  canonical_attention_areas: CanonicalAttentionArea[];
  canonical_insights: string[];
  unmapped_topics: string[];
  generated_at: string;
  analytics_version: string;
}

export interface StudentRow {
  student_id: string;
  score: {
    obtained: number;
    maximum: number;
    percentage: number;
  };
  status: string;
  analysis_status: string;
  submitted_at: string | null;
}

export interface CanonicalTopic {
  topic: string;
  average_percentage: number;
  status: string;
  priority: string;
  question_count: number;
  student_count: number;
  contributing_fragments: string[];
  is_estimated: boolean;
}

export interface CanonicalAttentionArea {
  type: string;
  name: string;
  average_percentage: number;
  priority: string;
  question_count: number;
  student_count: number;
}

export interface TeachingAction {
  topic: string;
  priority: string;
  performance_percentage: number;
  actions: string[];
  generated_at: string;
}

export interface Recommendation {
  question_id: string;
  source_type: string;
  source_id: string;
  canonical_topic: string;
  subtopic: string;
  bloom_level: string;
  difficulty: string;
  marks: number;
  text: string;
  weakness: number;
  lecture_coverage: number;
  tutorial_evidence: number;
  exam_relevance: number;
  bloom_gap: number;
  recommendation_score: number;
  priority: string;
  reason: {
    weakness_pct: number;
    lecture: boolean;
    tutorial_count: number;
    exam_recent_count: number;
    bloom_gap: number;
  };
}

export interface RecommendationsResponse {
  exam_id: string;
  subject_code: string;
  session_name: string;
  year: number;
  month: number;
  semester: number;
  weakness_scores: Record<string, { average_percentage: number; weakness: number; status: string; priority: string }>;
  ranked_weak_topics: [string, number][];
  recommendations: Recommendation[];
  high_priority: Recommendation[];
  medium_priority: Recommendation[];
  total_candidates: number;
}

/* ─── API Functions ────────────────────────────────────────────────────── */

export async function fetchExams(): Promise<ExamListItem[]> {
  const res = await fetch(`${API_BASE}/api/lecturers/exams`);
  if (!res.ok) throw new Error("Failed to fetch exams");
  return res.json();
}

export async function fetchExamAnalytics(
  courseCode: string,
  sessionName: string,
  year: number,
  month: number,
  semester: number,
): Promise<ExamAnalytics> {
  const encoded = encodeURIComponent(sessionName);
  const params = new URLSearchParams({ year: String(year), month: String(month), semester: String(semester) });
  const res = await fetch(
    `${API_BASE}/api/lecturers/exams/${courseCode}/${encoded}/analytics?${params}`,
  );
  if (!res.ok) throw new Error("Failed to fetch exam analytics");
  return res.json();
}

export async function fetchExamAnalyticsStream(
  courseCode: string,
  sessionName: string,
  year: number,
  month: number,
  semester: number,
  onProgress: (msg: string) => void,
): Promise<ExamAnalytics> {
  const encoded = encodeURIComponent(sessionName);
  const params = new URLSearchParams({ year: String(year), month: String(month), semester: String(semester) });
  const url = `${API_BASE}/api/lecturers/exams/${courseCode}/${encoded}/analytics/stream?${params}`;
  const res = await fetch(url, { headers: { Accept: "text/event-stream" } });
  if (!res.ok || !res.body) throw new Error("Failed to stream exam analytics");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: ExamAnalytics | null = null;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const part of parts) {
      const lines = part.split("\n");
      let event = "message";
      let dataStr = "";
      for (const line of lines) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) dataStr += line.slice(5).trim();
      }
      if (!dataStr) continue;
      try {
        const data = JSON.parse(dataStr);
        if (event === "progress" || event === "ping") {
          if (data.message) onProgress(data.message);
        } else if (event === "result") {
          result = data as ExamAnalytics;
        } else if (event === "error") {
          throw new Error(data.detail || "Stream error");
        }
      } catch {
        // ignore parse errors for ping
      }
    }
    if (result) break;
  }
  if (!result) throw new Error("No analytics result from stream");
  return result;
}

export async function fetchExamStudents(
  courseCode: string,
  sessionName: string,
  year?: number,
  month?: number,
  semester?: number,
): Promise<StudentRow[]> {
  const encoded = encodeURIComponent(sessionName);
  const params = new URLSearchParams();
  if (year !== undefined) params.set("year", String(year));
  if (month !== undefined) params.set("month", String(month));
  if (semester !== undefined) params.set("semester", String(semester));
  const qs = params.toString() ? `?${params}` : "";
  const res = await fetch(
    `${API_BASE}/api/lecturers/exams/${courseCode}/${encoded}/students${qs}`,
  );
  if (!res.ok) throw new Error("Failed to fetch students");
  return res.json();
}

export interface LecturerStudentDetail {
  student_id: string;
  subject_code: string;
  subject_name: string;
  year: number;
  month: number;
  semester: number;
  session_name: string;
  overall_performance: { score: number; maximum: number; percentage: number; status: string };
  question_performance: Array<{
    question_id: string;
    question_no: string;
    question_text: string;
    topic: string;
    subtopic: string;
    bloom_analysis: { level: string; confidence: number; reason: string };
    performance: { score: number; max_score: number; percentage: number };
    criteria_performance: Array<{ criterion: string; max_marks: number; awarded_marks: number; achieved: boolean }>;
  }>;
  topic_performance: Array<{ topic: string; questions_attempted: number; score: number; max_score: number; percentage: number; status: string }>;
  bloom_performance: Array<{ level: string; questions_attempted: number; average_score: number; status: string }>;
  learning_analysis: {
    overall_performance: string;
    strong_topics: string[];
    developing_topics: string[];
    weak_topics: string[];
    critical_topics: string[];
    learning_gaps: Array<{ topic: string; subtopic: string; priority: string }>;
  };
  // recommendations & next_question_strategy are omitted when include_ai_tips=false (lecturer view)
  recommendations?: Array<{ topic: string; priority: string; action: string }>;
  next_question_strategy?: { recommended_topics: string[]; recommended_bloom_levels: string[]; recommended_difficulty: string; number_of_questions: number };
  model_metadata: { bloom_model: string; bloom_model_type: string; grading_source: string; rag_context_used: boolean };
  generated_at: string;
  analysis_version: string;
}

export async function fetchLecturerStudentDetail(
  courseCode: string,
  sessionName: string,
  studentId: string,
  year?: number,
  month?: number,
  semester?: number,
  includeAiTips = false,
): Promise<LecturerStudentDetail> {
  const encodedCourse = encodeURIComponent(courseCode);
  const encodedSession = encodeURIComponent(sessionName);
  const encodedStudent = encodeURIComponent(studentId);
  const params = new URLSearchParams();
  if (year !== undefined) params.set("year", String(year));
  if (month !== undefined) params.set("month", String(month));
  if (semester !== undefined) params.set("semester", String(semester));
  if (includeAiTips) params.set("include_ai_tips", "true");
  const qs = params.toString() ? `?${params}` : "";
  const res = await fetch(`${API_BASE}/api/lecturers/exams/${encodedCourse}/${encodedSession}/student/${encodedStudent}${qs}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Failed to fetch student detail (${res.status})`);
  }
  return res.json();
}

export async function fetchTeachingActions(
  courseCode: string,
  sessionName: string,
  year: number,
  month: number,
  semester: number,
): Promise<TeachingAction[]> {
  const params = new URLSearchParams({ year: String(year), month: String(month), semester: String(semester) });
  const res = await fetch(
    `${API_BASE}/api/lecturers/exams/${encodeURIComponent(courseCode)}/${encodeURIComponent(sessionName)}/teaching-actions?${params}`,
  );
  if (!res.ok) throw new Error("Failed to fetch teaching actions");
  return res.json();
}

export async function fetchRecommendations(
  courseCode: string,
  sessionName: string,
  year: number,
  month: number,
  semester: number,
  limit = 10,
): Promise<RecommendationsResponse> {
  const params = new URLSearchParams({
    year: String(year),
    month: String(month),
    semester: String(semester),
    limit: String(limit),
  });
  const res = await fetch(
    `${API_BASE}/api/lecturers/exams/${encodeURIComponent(courseCode)}/${encodeURIComponent(sessionName)}/recommendations?${params}`,
  );
  if (!res.ok) throw new Error("Failed to fetch recommendations");
  return res.json();
}

export interface QuestionBankItem {
  question_id: string;
  source_type: string;
  source_id: string;
  canonical_topic: string;
  canonical_id: string;
  subtopic: string;
  bloom_level: string;
  difficulty: string;
  marks: number;
  question_type: string;
  text: string;
  year: number;
}

export async function fetchQuestionBank(params: { source_type?: string; year?: number; canonical_topic?: string; limit?: number } = {}): Promise<QuestionBankItem[]> {
  const qs = new URLSearchParams();
  if (params.source_type) qs.set("source_type", params.source_type);
  if (params.year) qs.set("year", String(params.year));
  if (params.canonical_topic) qs.set("canonical_topic", params.canonical_topic);
  if (params.limit) qs.set("limit", String(params.limit));
  const res = await fetch(`${API_BASE}/api/lecturers/question-bank?${qs}`);
  if (!res.ok) throw new Error("Failed to fetch question bank");
  return res.json();
}

export interface ExamDraft {
  draft_id: string;
  subject_code: string;
  subject_name: string;
  paper: { exam: string; year: number; questions: { question_number: number; topic: string; parts: { part: string; question: string; max_marks: number }[] }[] };
  total_marks: number;
  question_count: number;
  created_at: string;
  updated_at: string;
}

export async function createExamDraft(subject_code: string, paper: { exam: string; year: number; questions: any[] }, draft_id?: string): Promise<ExamDraft> {
  const res = await fetch(`${API_BASE}/api/lecturers/exams/drafts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ subject_code, paper, draft_id }),
  });
  if (!res.ok) throw new Error("Failed to upload draft");
  return res.json();
}

export async function listExamDrafts(course_code?: string): Promise<ExamDraft[]> {
  const qs = course_code ? `?course_code=${encodeURIComponent(course_code)}` : "";
  const res = await fetch(`${API_BASE}/api/lecturers/exams/drafts${qs}`);
  if (!res.ok) throw new Error("Failed to fetch drafts");
  return res.json();
}

export async function getExamDraft(draft_id: string): Promise<ExamDraft> {
  const res = await fetch(`${API_BASE}/api/lecturers/exams/drafts/${encodeURIComponent(draft_id)}`);
  if (!res.ok) throw new Error("Failed to fetch draft");
  return res.json();
}

export interface LlmHealth {
  online: boolean;
  ollama_reachable: boolean;
  model: string;
  model_available: boolean;
  detail: string;
}

export async function fetchLlmHealth(): Promise<LlmHealth> {
  const res = await fetch(`${API_BASE}/api/lecturers/llm-health`);
  if (!res.ok) throw new Error("Failed to fetch LLM health");
  return res.json();
}
