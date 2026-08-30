const API_BASE =
  (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_BASE_URL ??
  "http://127.0.0.1:8000";

export interface StudentExam {
  subject_code: string;
  subject_name: string;
  session_name: string;
  year: number;
  month: number;
  semester: number;
  question_count: number;
  analyzed?: boolean;
  analyzed_at?: string | null;
}

export interface StudentProfile {
  student_id: string;
  email: string;
  exam_count: number;
  exams: StudentExam[];
}

export interface StudentAnalytics {
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
  recommendations: Array<{ topic: string; priority: string; action: string }>;
  next_question_strategy: { recommended_topics: string[]; recommended_bloom_levels: string[]; recommended_difficulty: string; number_of_questions: number };
  model_metadata: { bloom_model: string; bloom_model_type: string; grading_source: string; rag_context_used: boolean };
  generated_at: string;
  analysis_version: string;
}

export async function studentLogin(email: string, password: string): Promise<{ student_id: string; email: string }> {
  const res = await fetch(`${API_BASE}/api/students/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || "Invalid credentials");
  }
  return res.json();
}

export async function fetchStudentExams(studentId: string): Promise<StudentExam[]> {
  const res = await fetch(`${API_BASE}/api/students/${encodeURIComponent(studentId)}/exams`);
  if (!res.ok) throw new Error("Failed to fetch student exams");
  return res.json();
}

export async function fetchStudentProfile(studentId: string): Promise<StudentProfile> {
  const res = await fetch(`${API_BASE}/api/students/${encodeURIComponent(studentId)}/profile`);
  if (!res.ok) throw new Error("Failed to fetch student profile");
  return res.json();
}

export async function fetchStudentDashboard(
  studentId: string,
  courseCode: string,
  sessionName: string,
  year?: number,
  month?: number,
  semester?: number,
): Promise<StudentAnalytics> {
  const params = new URLSearchParams({ course_code: courseCode, session_name: sessionName });
  if (year !== undefined) params.set("year", String(year));
  if (month !== undefined) params.set("month", String(month));
  if (semester !== undefined) params.set("semester", String(semester));
  const res = await fetch(`${API_BASE}/api/students/${encodeURIComponent(studentId)}/dashboard?${params}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    // 423 = not yet analyzed, surface specific message
    if (res.status === 423) throw new Error(body.detail || "Wait for lecture to analyze your data");
    throw new Error(body.detail || "Failed to fetch dashboard");
  }
  return res.json();
}
