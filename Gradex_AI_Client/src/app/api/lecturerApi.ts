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
}

export interface TopicPerformance {
  topic: string;
  average_percentage: number;
  status: string;
}

export interface BloomPerformance {
  level: string;
  average_percentage: number;
}

export interface QuestionPerformance {
  question_id: string;
  question_no: string;
  topic: string;
  bloom_level: string;
  average_percentage: number;
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

/* ─── API Functions ────────────────────────────────────────────────────── */

export async function fetchExams(): Promise<ExamListItem[]> {
  const res = await fetch(`${API_BASE}/api/lecturers/exams`);
  if (!res.ok) throw new Error("Failed to fetch exams");
  return res.json();
}

export async function fetchExamAnalytics(
  courseCode: string,
  sessionName: string,
): Promise<ExamAnalytics> {
  const encoded = encodeURIComponent(sessionName);
  const res = await fetch(
    `${API_BASE}/api/lecturers/exams/${courseCode}/${encoded}/analytics`,
  );
  if (!res.ok) throw new Error("Failed to fetch exam analytics");
  return res.json();
}

export async function fetchExamStudents(
  courseCode: string,
  sessionName: string,
): Promise<StudentRow[]> {
  const encoded = encodeURIComponent(sessionName);
  const res = await fetch(
    `${API_BASE}/api/lecturers/exams/${courseCode}/${encoded}/students`,
  );
  if (!res.ok) throw new Error("Failed to fetch students");
  return res.json();
}

export async function fetchTeachingActions(
  courseCode: string,
  sessionName: string,
): Promise<TeachingAction[]> {
  const res = await fetch(
    `${API_BASE}/api/lecturers/exams/${encodeURIComponent(courseCode)}/${encodeURIComponent(sessionName)}/teaching-actions`,
  );
  if (!res.ok) throw new Error("Failed to fetch teaching actions");
  return res.json();
}
