// @ts-ignore: allow implicit any for react module when types are not installed
import React, { useState, useCallback, useEffect } from "react";
import {
  AlertTriangle,
  Users,
  BookOpen,
  Brain,
  BarChart3,
  RefreshCw,
  ChevronRight,
  AlertCircle,
  Sparkles,
  Eye,
  EyeOff,
  TrendingUp,
  TrendingDown,
  Minus,
} from "lucide-react";
import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Progress } from "./ui/progress";
import { Separator } from "./ui/separator";
import { AIPageBanner, AIBadgePill } from "./AIBrand";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  CartesianGrid,
  Tooltip,
  Cell,
} from "recharts";

/* ─── V2 Engine Types ───────────────────────────────────────────────────── */

type PerformanceStatus = "Strong" | "Developing" | "Needs Improvement" | "Critical";
type BloomLevel = "Remember" | "Understand" | "Apply" | "Analyze" | "Evaluate" | "Create";
type RecommendationPriority = "Critical" | "High" | "Medium" | "Low";

interface ExamInfo {
  session_name: string;
  total_marks: number;
  question_count: number;
}

interface ExamStatistics {
  total_students: number;
  attempted_students: number;
  average_score: number;
  average_percentage: number;
  pass_rate: number;
  highest_score: number;
  lowest_score: number;
}

interface TopicPerformanceSummary {
  topic: string;
  average_percentage: number;
  status: PerformanceStatus;
}

interface BloomPerformanceSummary {
  level: BloomLevel;
  average_percentage: number;
}

interface QuestionPerformanceSummary {
  question_id: string;
  question_no: string;
  topic: string;
  bloom_level: BloomLevel;
  average_percentage: number;
}

interface AttentionArea {
  type: string;
  name: string;
  average_percentage: number;
  priority: RecommendationPriority;
}

interface ExamAnalyticsDocument {
  subject_code: string;
  subject_name: string;
  year: number;
  month: number;
  semester: number;
  session_name: string;
  exam: ExamInfo;
  statistics: ExamStatistics;
  topic_performance: TopicPerformanceSummary[];
  bloom_performance: BloomPerformanceSummary[];
  question_performance: QuestionPerformanceSummary[];
  attention_areas: AttentionArea[];
  insights: string[];
  generated_at: string;
  analytics_version: string;
}

interface ExamCatalogEntry {
  subject_code: string;
  subject_name: string;
  year: number;
  session_name: string;
  analyzed: string;
}

interface StudentRow {
  student_id: string;
  score: { obtained: number; maximum: number; percentage: number };
  status: PerformanceStatus;
  analysis_status: string;
  submitted_at: string | null;
}

interface BloomAnalysis {
  level: BloomLevel;
  confidence: number;
  reason: string;
}

interface QuestionPerformanceDetail {
  question_id: string;
  question_no: string;
  question_text: string;
  topic: string;
  subtopic: string;
  bloom_analysis: BloomAnalysis;
  performance: { score: number; max_score: number; percentage: number };
}

interface TopicPerformanceDetail {
  topic: string;
  questions_attempted: number;
  score: number;
  max_score: number;
  percentage: number;
  status: PerformanceStatus;
}

interface BloomPerformanceDetail {
  level: BloomLevel;
  questions_attempted: number;
  average_score: number;
  status: PerformanceStatus;
}

interface LearningGap {
  topic: string;
  subtopic: string;
  priority: RecommendationPriority;
}

interface LearningAnalysis {
  overall_performance: PerformanceStatus;
  strong_topics: string[];
  developing_topics: string[];
  weak_topics: string[];
  critical_topics: string[];
  learning_gaps: LearningGap[];
}

interface Recommendation {
  topic: string;
  priority: RecommendationPriority;
  action: string;
}

interface StudentAnalyticsDocument {
  student_id: string;
  subject_code: string;
  subject_name: string;
  year: number;
  session_name: string;
  overall_performance: {
    score: number;
    maximum: number;
    percentage: number;
    status: PerformanceStatus;
  };
  question_performance: QuestionPerformanceDetail[];
  topic_performance: TopicPerformanceDetail[];
  bloom_performance: BloomPerformanceDetail[];
  learning_analysis: LearningAnalysis;
  recommendations: Recommendation[];
  generated_at: string;
  analysis_version: string;
}

/* ─── Bloom level numeric mapping ──────────────────────────────────────── */
const bloomLevel: Record<string, number> = {
  remember: 1,
  understand: 2,
  apply: 3,
  analyze: 4,
  evaluate: 5,
  create: 6,
};

/* ─── Colour helpers ───────────────────────────────────────────────────── */
const statusColor: Record<PerformanceStatus, string> = {
  Strong: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
  Developing: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  "Needs Improvement": "bg-orange-100 text-orange-800 dark:bg-orange-500/15 dark:text-orange-300",
  Critical: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
};

const priorityColor: Record<RecommendationPriority, string> = {
  Critical: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
  High: "bg-orange-100 text-orange-800 dark:bg-orange-500/15 dark:text-orange-300",
  Medium: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  Low: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
};

const topicMasteryColor = (v: number) => {
  if (v >= 80) return "bg-emerald-500 text-white";
  if (v >= 65) return "bg-emerald-200 text-emerald-900";
  if (v >= 50) return "bg-amber-200 text-amber-900";
  if (v >= 35) return "bg-orange-300 text-orange-900";
  return "bg-red-400 text-white";
};

const bloomBarColors: Record<number, string> = {
  1: "#10b981",
  2: "#34d399",
  3: "#22c55e",
  4: "#3b82f6",
  5: "#6366f1",
  6: "#8b5cf6",
};

const bloomBarTailwind: Record<number, string> = {
  1: "bg-emerald-300",
  2: "bg-emerald-400",
  3: "bg-emerald-500",
  4: "bg-blue-500",
  5: "bg-indigo-500",
  6: "bg-violet-500",
};

const bandStyle: Record<PerformanceStatus, string> = {
  Strong: "bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-500/15 dark:text-emerald-300 dark:border-emerald-500/20",
  Developing: "bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-500/15 dark:text-amber-300 dark:border-amber-500/20",
  "Needs Improvement": "bg-orange-100 text-orange-800 border-orange-200 dark:bg-orange-500/15 dark:text-orange-300 dark:border-orange-500/20",
  Critical: "bg-red-100 text-red-800 border-red-200 dark:bg-red-500/15 dark:text-red-300 dark:border-red-500/20",
};

const statusIcon = (status: PerformanceStatus) => {
  if (status === "Strong") return TrendingUp;
  if (status === "Critical") return TrendingDown;
  return Minus;
};

/* ─── Main AnalyticsPage ─────────────────────────────────────────────────── */
export function AnalyticsPage() {
  const backendBaseUrl =
    ((import.meta as ImportMeta & { env?: { VITE_BACKEND_URL?: string } }).env?.VITE_BACKEND_URL) ??
    "http://localhost:8000";

  // Catalog state
  const [exams, setExams] = useState<ExamCatalogEntry[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [selectedCourse, setSelectedCourse] = useState<string>("");
  const [selectedSession, setSelectedSession] = useState<string>("");

  // Analytics state
  const [analytics, setAnalytics] = useState<ExamAnalyticsDocument | null>(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsError, setAnalyticsError] = useState<string | null>(null);

  // Student list state
  const [students, setStudents] = useState<StudentRow[]>([]);
  const [studentsLoading, setStudentsLoading] = useState(false);

  // Student detail state
  const [selectedStudentId, setSelectedStudentId] = useState<string | null>(null);
  const [studentDetail, setStudentDetail] = useState<StudentAnalyticsDocument | null>(null);
  const [studentDetailLoading, setStudentDetailLoading] = useState(false);
  const [studentDetailError, setStudentDetailError] = useState<string | null>(null);

  // Expanded student row
  const [expandedStudent, setExpandedStudent] = useState<string | null>(null);

  // Upload panel toggle (kept for consistency)
  const [showDetailPanel, setShowDetailPanel] = useState(true);

  /* ─── Load exam catalog ─────────────────────────────────────────────── */
  const loadCatalog = useCallback(async () => {
    setCatalogLoading(true);
    try {
      const response = await fetch(`${backendBaseUrl}/api/analytics/exams`);
      if (!response.ok) {
        setExams([]);
        return;
      }
      const data = (await response.json()) as ExamCatalogEntry[];
      setExams(data);
      if (data.length > 0 && !selectedCourse) {
        const first = data[0];
        setSelectedCourse(first.subject_code);
        setSelectedSession(first.session_name);
      }
    } catch {
      setExams([]);
    } finally {
      setCatalogLoading(false);
    }
  }, [backendBaseUrl, selectedCourse]);

  useEffect(() => {
    void loadCatalog();
  }, [loadCatalog]);

  /* ─── Load analytics for selected exam ──────────────────────────────── */
  const loadAnalytics = useCallback(async () => {
    if (!selectedCourse || !selectedSession) return;
    setAnalyticsLoading(true);
    setAnalyticsError(null);
    setAnalytics(null);
    setStudents([]);
    setSelectedStudentId(null);
    setStudentDetail(null);
    try {
      const [analyticsRes, studentsRes] = await Promise.allSettled([
        fetch(
          `${backendBaseUrl}/api/analytics/exams/${encodeURIComponent(selectedCourse)}/${encodeURIComponent(selectedSession)}/analytics`,
        ),
        fetch(
          `${backendBaseUrl}/api/analytics/exams/${encodeURIComponent(selectedCourse)}/${encodeURIComponent(selectedSession)}/students`,
        ),
      ]);

      if (analyticsRes.status === "fulfilled" && analyticsRes.value.ok) {
        const data = (await analyticsRes.value.json()) as ExamAnalyticsDocument;
        setAnalytics(data);
      } else {
        const msg =
          analyticsRes.status === "rejected"
            ? String(analyticsRes.reason)
            : analyticsRes.status === "fulfilled"
              ? await analyticsRes.value.text()
              : "Failed to load analytics";
        setAnalyticsError(msg || "Analytics unavailable for this exam.");
      }

      if (studentsRes.status === "fulfilled" && studentsRes.value.ok) {
        const data = (await studentsRes.value.json()) as StudentRow[];
        setStudents(data);
      }
    } catch (err) {
      setAnalyticsError(err instanceof Error ? err.message : "Failed to load analytics.");
    } finally {
      setAnalyticsLoading(false);
      setStudentsLoading(false);
    }
  }, [backendBaseUrl, selectedCourse, selectedSession]);

  useEffect(() => {
    if (selectedCourse && selectedSession) {
      void loadAnalytics();
    }
  }, [selectedCourse, selectedSession, loadAnalytics]);

  /* ─── Load student detail ───────────────────────────────────────────── */
  const loadStudentDetail = useCallback(
    async (studentId: string) => {
      if (!selectedCourse || !selectedSession) return;
      setSelectedStudentId(studentId);
      setStudentDetailLoading(true);
      setStudentDetailError(null);
      setStudentDetail(null);
      try {
        const response = await fetch(
          `${backendBaseUrl}/api/analytics/exams/${encodeURIComponent(selectedCourse)}/${encodeURIComponent(selectedSession)}/student/${encodeURIComponent(studentId)}`,
        );
        if (!response.ok) {
          const text = await response.text();
          throw new Error(text || "Student detail unavailable.");
        }
        const data = (await response.json()) as StudentAnalyticsDocument;
        setStudentDetail(data);
      } catch (err) {
        setStudentDetailError(err instanceof Error ? err.message : "Student detail unavailable.");
      } finally {
        setStudentDetailLoading(false);
      }
    },
    [backendBaseUrl, selectedCourse, selectedSession],
  );

  /* ─── Derived data ──────────────────────────────────────────────────── */
  const S = analytics?.statistics;
  const topicPerf = analytics?.topic_performance ?? [];
  const bloomPerf = analytics?.bloom_performance ?? [];
  const questionPerf = analytics?.question_performance ?? [];
  const attentionAreas = analytics?.attention_areas ?? [];
  const insights = analytics?.insights ?? [];

  // Unique courses for the selector
  const uniqueCourses = Array.from(
    new Map(exams.map((e) => [e.subject_code, e])).values(),
  );

  // Sessions for the selected course
  const sessionsForCourse = exams.filter((e) => e.subject_code === selectedCourse);

  // Student detail maps
  const studentTopicPerf = studentDetail?.topic_performance ?? [];
  const studentBloomPerf = studentDetail?.bloom_performance ?? [];
  const studentLearning = studentDetail?.learning_analysis;
  const studentRecommendations = studentDetail?.recommendations ?? [];
  const studentQuestionPerf = studentDetail?.question_performance ?? [];

  // Summary cards
  const summaryCards = S
    ? [
        {
          title: "Total Students",
          value: S.total_students,
          icon: Users,
          color: "blue",
          note: `${S.attempted_students} attempted`,
        },
        {
          title: "Average Score",
          value: `${S.average_percentage.toFixed(1)}%`,
          icon: BarChart3,
          color: "emerald",
          note: `${S.average_score.toFixed(1)} / ${analytics?.exam.total_marks ?? "—"}`,
        },
        {
          title: "Pass Rate",
          value: `${S.pass_rate.toFixed(1)}%`,
          icon: TrendingUp,
          color: S.pass_rate >= 60 ? "emerald" : "amber",
          note: `Highest: ${S.highest_score.toFixed(1)}`,
        },
        {
          title: "At-Risk Students",
          value: students.filter((st) => st.status === "Critical" || st.status === "Needs Improvement").length,
          icon: AlertTriangle,
          color: "red",
          note: `Lowest: ${S.lowest_score.toFixed(1)}`,
        },
      ]
    : [];

  const colorMap: Record<string, string> = {
    blue: "text-primary bg-accent",
    emerald: "text-emerald-600 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-500/15",
    amber: "text-amber-600 dark:text-amber-300 bg-amber-50 dark:bg-amber-500/15",
    red: "text-red-600 dark:text-red-300 bg-red-50 dark:bg-red-500/15",
  };

  return (
    <div className="p-8 space-y-6">
      {/* AI Page Banner */}
      <AIPageBanner model="pulse" />

      {/* Page header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h2 className="tracking-tight text-foreground">Student Analytics</h2>
          <p className="text-sm text-muted-foreground mt-1">
            {analytics
              ? `${analytics.subject_name} · ${analytics.session_name} · Year ${analytics.year}`
              : "Select an exam to view analytics"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <AIBadgePill model="pulse" />
          <Button
            variant="outline"
            size="sm"
            onClick={() => void loadCatalog()}
            disabled={catalogLoading}
            className="gap-1.5"
          >
            {catalogLoading ? (
              <RefreshCw className="size-3.5 animate-spin" />
            ) : (
              <Sparkles className="size-3.5" />
            )}
            {catalogLoading ? "Syncing" : "Refresh"}
          </Button>
        </div>
      </div>

      {/* ── Exam Selector ─────────────────────────────────────────────── */}
      <Card className="border-border overflow-hidden">
        <div className="px-5 py-4 bg-gradient-to-r from-muted to-accent/40 border-b border-border flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="size-8 rounded-lg bg-primary flex items-center justify-center">
              <BookOpen className="size-4 text-primary-foreground" />
            </div>
            <div>
              <div className="text-foreground">Select exam</div>
              <div className="text-xs text-muted-foreground mt-0.5">
                Choose a course and session to view V2 engine analytics
              </div>
            </div>
          </div>
          {analyticsLoading && (
            <Badge className="bg-accent text-primary border-0">
              <RefreshCw className="size-3 mr-1 animate-spin" /> Loading analytics
            </Badge>
          )}
          {analytics && !analyticsLoading && (
            <Badge className="bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300 border-0">
              <Sparkles className="size-3 mr-1" /> Analytics ready
            </Badge>
          )}
        </div>

        <div className="p-5 flex items-end gap-4 flex-wrap">
          <div className="w-64">
            <label className="text-xs text-muted-foreground mb-1 block">Course</label>
            <Select value={selectedCourse} onValueChange={(v) => { setSelectedCourse(v); setSelectedSession(""); }}>
              <SelectTrigger>
                <SelectValue placeholder="Select course" />
              </SelectTrigger>
              <SelectContent>
                {uniqueCourses.map((e) => (
                  <SelectItem key={e.subject_code} value={e.subject_code}>
                    {e.subject_code} — {e.subject_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="w-64">
            <label className="text-xs text-muted-foreground mb-1 block">Session</label>
            <Select value={selectedSession} onValueChange={setSelectedSession} disabled={!selectedCourse}>
              <SelectTrigger>
                <SelectValue placeholder="Select session" />
              </SelectTrigger>
              <SelectContent>
                {sessionsForCourse.map((e) => (
                  <SelectItem key={e.session_name} value={e.session_name}>
                    {e.session_name} (Year {e.year})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {analyticsError && (
          <div className="px-5 pb-4">
            <Badge className="bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300 border-0">
              <AlertCircle className="size-3 mr-1" /> {analyticsError}
            </Badge>
          </div>
        )}
      </Card>

      {/* ── Summary Cards ─────────────────────────────────────────────── */}
      {S && (
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {summaryCards.map((card, i) => {
            const Icon = card.icon;
            const tone = colorMap[card.color];
            const [text, bg] = tone.split(" ");
            return (
              <Card key={card.title} className="p-5 border-border relative overflow-hidden">
                {i === 1 && (
                  <div className="absolute right-2 bottom-2 h-12 w-28 opacity-90">
                    <ResponsiveContainer>
                      <BarChart data={bloomPerf}>
                        <Bar dataKey="average_percentage" radius={[3, 3, 0, 0]}>
                          {bloomPerf.map((b, idx) => (
                            <Cell
                              key={`bloom-cell-${idx}`}
                              fill={bloomBarColors[bloomLevel[b.level.toLowerCase()] ?? 3] ?? "#3b82f6"}
                            />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
                <div className={`size-10 rounded-lg ${bg} flex items-center justify-center ${text}`}>
                  <Icon className="size-5" />
                </div>
                <div className="mt-4 text-sm text-muted-foreground">{card.title}</div>
                <div className="tracking-tight text-foreground mt-1">{card.value}</div>
                <div className="text-xs text-muted-foreground mt-1">{card.note}</div>
              </Card>
            );
          })}
        </div>
      )}

      {/* ── Student List ──────────────────────────────────────────────── */}
      {students.length > 0 && (
        <Card className="border-border">
          <div className="px-5 py-4 border-b border-border flex items-center justify-between gap-3 flex-wrap">
            <div>
              <div className="text-foreground">Student performance</div>
              <div className="text-xs text-muted-foreground mt-0.5">
                {students.length} students · Click a row for detailed V2 analysis
              </div>
            </div>
          </div>

          <table className="w-full text-sm">
            <thead className="bg-muted text-muted-foreground text-xs uppercase tracking-wide">
              <tr>
                <th className="text-left px-5 py-3">Student ID</th>
                <th className="text-left px-5 py-3">Score</th>
                <th className="text-left px-5 py-3">Percentage</th>
                <th className="text-left px-5 py-3">Status</th>
                <th className="text-left px-5 py-3">Analysis</th>
                <th className="text-right px-5 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {students.map((s) => {
                const isOpen = expandedStudent === s.student_id;
                return (
                  <React.Fragment key={s.student_id}>
                    <tr
                      onClick={() => {
                        setExpandedStudent(isOpen ? null : s.student_id);
                        if (!isOpen) void loadStudentDetail(s.student_id);
                      }}
                      className="border-t border-border hover:bg-muted cursor-pointer"
                    >
                      <td className="px-5 py-3 text-foreground font-medium">{s.student_id}</td>
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-2">
                          <span className="text-foreground">
                            {s.score.obtained}/{s.score.maximum}
                          </span>
                        </div>
                      </td>
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-2">
                          <span className="text-foreground">{s.score.percentage}%</span>
                          <Progress value={s.score.percentage} className="w-24 h-1.5" />
                        </div>
                      </td>
                      <td className="px-5 py-3">
                        <Badge variant="outline" className={bandStyle[s.status]}>
                          {s.status}
                        </Badge>
                      </td>
                      <td className="px-5 py-3">
                        <Badge
                          className={
                            s.analysis_status === "generated"
                              ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300 border-0"
                              : "bg-muted text-muted-foreground border-0"
                          }
                        >
                          {s.analysis_status}
                        </Badge>
                      </td>
                      <td className="px-5 py-3 text-right">
                        <ChevronRight
                          className={`size-4 text-muted-foreground transition-transform ${isOpen ? "rotate-90" : ""}`}
                        />
                      </td>
                    </tr>
                    {isOpen && (
                      <tr className="bg-muted/60 border-t border-border">
                        <td colSpan={6} className="p-5">
                          {studentDetailLoading && (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                              <RefreshCw className="size-4 animate-spin" /> Loading student analysis…
                            </div>
                          )}
                          {studentDetailError && (
                            <p className="text-sm text-red-500">{studentDetailError}</p>
                          )}
                          {studentDetail && (
                            <StudentDetailPanel detail={studentDetail} />
                          )}
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </Card>
      )}

      {/* ── Detailed Tabs ──────────────────────────────────────────────── */}
      {analytics && (
        <Tabs defaultValue="topics" className="space-y-4">
          <TabsList className="bg-muted">
            <TabsTrigger value="topics">Topic performance</TabsTrigger>
            <TabsTrigger value="bloom">Bloom's taxonomy</TabsTrigger>
            <TabsTrigger value="questions">Question analysis</TabsTrigger>
            <TabsTrigger value="attention">Attention areas</TabsTrigger>
            <TabsTrigger value="insights">Insights</TabsTrigger>
          </TabsList>

          {/* ── Topic Performance ──────────────────────────────────────── */}
          <TabsContent value="topics" className="m-0">
            <Card className="p-5 border-border">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <div className="text-foreground">Topic performance</div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    Average percentage across all students per topic
                  </div>
                </div>
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  {[
                    ["bg-emerald-500", "≥80%"],
                    ["bg-amber-200", "50–79%"],
                    ["bg-red-400", "<50%"],
                  ].map(([c, l]) => (
                    <div key={l} className="flex items-center gap-1">
                      <div className={`size-3 rounded ${c}`} />
                      {l}
                    </div>
                  ))}
                </div>
              </div>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={topicPerf} margin={{ top: 5, right: 20, left: 0, bottom: 60 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                    <XAxis
                      dataKey="topic"
                      tick={{ fontSize: 10, fill: "#94a3b8" }}
                      axisLine={false}
                      tickLine={false}
                      angle={-35}
                      textAnchor="end"
                      height={80}
                    />
                    <YAxis
                      domain={[0, 100]}
                      tick={{ fontSize: 10, fill: "#94a3b8" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      formatter={(v: number) => [`${v.toFixed(1)}%`, "Average"]}
                      contentStyle={{ borderRadius: 8, fontSize: 12 }}
                    />
                    <Bar dataKey="average_percentage" radius={[4, 4, 0, 0]}>
                      {topicPerf.map((entry, idx) => (
                        <Cell
                          key={`topic-bar-${idx}`}
                          fill={
                            entry.average_percentage >= 80
                              ? "#10b981"
                              : entry.average_percentage >= 50
                                ? "#f59e0b"
                                : "#ef4444"
                          }
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="mt-4 grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {topicPerf.map((t) => (
                  <div key={t.topic} className="flex items-center justify-between p-3 bg-muted rounded-lg border border-border text-xs">
                    <div className="flex-1 min-w-0">
                      <div className="truncate text-foreground">{t.topic}</div>
                      <div className="text-muted-foreground mt-0.5">{t.average_percentage.toFixed(1)}%</div>
                    </div>
                    <Badge className={`${statusColor[t.status]} border-0 ml-2`}>{t.status}</Badge>
                  </div>
                ))}
              </div>
            </Card>
          </TabsContent>

          {/* ── Bloom's Taxonomy ───────────────────────────────────────── */}
          <TabsContent value="bloom" className="m-0">
            <div className="grid lg:grid-cols-2 gap-4">
              <Card className="p-5 border-border">
                <div className="text-foreground">Bloom's Taxonomy ladder</div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  Class average per cognitive level
                </div>
                <div className="mt-4 space-y-2">
                  {[...bloomPerf]
                    .sort((a, b) => (bloomLevel[b.level.toLowerCase()] ?? 0) - (bloomLevel[a.level.toLowerCase()] ?? 0))
                    .map((b) => {
                      const level = bloomLevel[b.level.toLowerCase()] ?? 3;
                      return (
                        <div key={b.level} className="flex items-center gap-3">
                          <div className="w-24 text-sm text-muted-foreground">{b.level}</div>
                          <div className="flex-1 h-7 rounded-md bg-muted overflow-hidden">
                            <div
                              className={`${bloomBarTailwind[level] ?? "bg-blue-500"} h-full flex items-center justify-end pr-2 text-xs text-white`}
                              style={{ width: `${b.average_percentage}%` }}
                            >
                              {b.average_percentage.toFixed(1)}%
                            </div>
                          </div>
                        </div>
                      );
                    })}
                </div>
              </Card>

              <Card className="p-5 border-border">
                <div className="text-foreground">Bloom's distribution</div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  Average percentage per cognitive level
                </div>
                <div className="h-64 mt-4">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={bloomPerf} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                      <XAxis
                        dataKey="level"
                        tick={{ fontSize: 10, fill: "#94a3b8" }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        domain={[0, 100]}
                        tick={{ fontSize: 10, fill: "#94a3b8" }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <Tooltip
                        formatter={(v: number) => [`${v.toFixed(1)}%`, "Average"]}
                        contentStyle={{ borderRadius: 8, fontSize: 12 }}
                      />
                      <Bar dataKey="average_percentage" radius={[4, 4, 0, 0]}>
                        {bloomPerf.map((entry, idx) => {
                          const lvl = bloomLevel[entry.level.toLowerCase()] ?? 3;
                          return <Cell key={`bloom-chart-${idx}`} fill={bloomBarColors[lvl] ?? "#3b82f6"} />;
                        })}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </Card>
            </div>
          </TabsContent>

          {/* ── Question Analysis ───────────────────────────────────────── */}
          <TabsContent value="questions" className="m-0">
            <Card className="border-border overflow-hidden">
              <div className="px-5 py-4 border-b border-border text-foreground">
                Question performance
              </div>
              {questionPerf.length === 0 ? (
                <div className="px-5 py-8 text-center text-muted-foreground text-sm">
                  No question data available.
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-muted text-muted-foreground text-xs uppercase tracking-wide">
                    <tr>
                      <th className="text-left px-5 py-3">Question</th>
                      <th className="text-left px-5 py-3">Topic</th>
                      <th className="text-left px-5 py-3">Bloom Level</th>
                      <th className="text-left px-5 py-3">Avg Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {questionPerf.map((q) => (
                      <tr key={q.question_id} className="border-t border-border">
                        <td className="px-5 py-3 text-foreground">
                          Q{q.question_no}
                        </td>
                        <td className="px-5 py-3 text-muted-foreground">{q.topic}</td>
                        <td className="px-5 py-3">
                          <Badge className="bg-accent text-primary border-0">{q.bloom_level}</Badge>
                        </td>
                        <td className="px-5 py-3">
                          <div className="flex items-center gap-2">
                            <span className="text-foreground">{q.average_percentage.toFixed(1)}%</span>
                            <Progress value={q.average_percentage} className="w-24 h-1.5" />
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>
          </TabsContent>

          {/* ── Attention Areas ─────────────────────────────────────────── */}
          <TabsContent value="attention" className="m-0">
            <Card className="p-5 border-border">
              <div className="text-foreground">Attention areas</div>
              <div className="text-xs text-muted-foreground mt-0.5">
                Topics and questions requiring focused improvement
              </div>
              {attentionAreas.length === 0 ? (
                <div className="mt-4 text-sm text-muted-foreground">No attention areas identified.</div>
              ) : (
                <div className="mt-4 space-y-3">
                  {attentionAreas.map((area, i) => (
                    <div key={`area-${i}`} className="rounded-lg border border-border p-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="text-sm text-foreground font-medium">{area.name}</div>
                          <div className="text-xs text-muted-foreground mt-0.5">
                            {area.type} · {area.average_percentage.toFixed(1)}% average
                          </div>
                        </div>
                        <Badge className={`${priorityColor[area.priority]} border-0`}>
                          {area.priority}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </TabsContent>

          {/* ── Insights ────────────────────────────────────────────────── */}
          <TabsContent value="insights" className="m-0">
            <Card className="p-5 border-border">
              <div className="text-foreground">AI-generated insights</div>
              <div className="text-xs text-muted-foreground mt-0.5">
                Key observations from the V2 prediction engine
              </div>
              {insights.length === 0 ? (
                <div className="mt-4 text-sm text-muted-foreground">No insights available.</div>
              ) : (
                <div className="mt-4 space-y-3">
                  {insights.map((insight, i) => (
                    <div key={`insight-${i}`} className="flex items-start gap-3 p-3 bg-muted rounded-lg border border-border">
                      <Sparkles className="size-4 text-primary mt-0.5 shrink-0" />
                      <span className="text-sm text-foreground">{insight}</span>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </TabsContent>
        </Tabs>
      )}

      {/* ── Empty state ────────────────────────────────────────────────── */}
      {!analytics && !analyticsLoading && !analyticsError && (
        <Card className="p-12 border-border text-center">
          <BarChart3 className="size-12 mx-auto mb-3 text-muted-foreground opacity-50" />
          <div className="text-foreground">Select an exam to view analytics</div>
          <div className="text-sm text-muted-foreground mt-1">
            Choose a course and session from the selector above to load V2 engine analytics
          </div>
        </Card>
      )}
    </div>
  );
}

/* ─── Student Detail Panel ──────────────────────────────────────────────── */
function StudentDetailPanel({ detail }: { detail: StudentAnalyticsDocument }) {
  const op = detail.overall_performance;
  const learning = detail.learning_analysis;
  const recs = detail.recommendations;
  const topicPerf = detail.topic_performance;
  const bloomPerf = detail.bloom_performance;
  const questionPerf = detail.question_performance;

  return (
    <div className="grid lg:grid-cols-3 gap-4">
      {/* Overall performance card */}
      <Card className="p-4 border-border bg-card">
        <div className="text-xs uppercase tracking-wide text-muted-foreground">Overall performance</div>
        <div className="mt-2">
          <div className="text-2xl font-bold text-foreground">{op.percentage.toFixed(1)}%</div>
          <div className="text-sm text-muted-foreground mt-1">
            {op.score}/{op.maximum} marks
          </div>
          <Badge className={`${statusColor[op.status]} border-0 mt-2`}>{op.status}</Badge>
        </div>
        <Separator className="my-3" />
        <div className="text-xs uppercase tracking-wide text-muted-foreground">Topic mastery</div>
        <div className="mt-2 space-y-2">
          {topicPerf.slice(0, 5).map((t) => (
            <div key={t.topic}>
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span className="truncate">{t.topic}</span>
                <span>{t.percentage.toFixed(1)}%</span>
              </div>
              <Progress value={t.percentage} className="h-1.5 mt-1" />
            </div>
          ))}
        </div>
      </Card>

      {/* Learning analysis card */}
      <Card className="p-4 border-border bg-card">
        <div className="text-xs uppercase tracking-wide text-muted-foreground">Learning analysis</div>
        <div className="mt-2 space-y-2">
          {learning.strong_topics.length > 0 && (
            <div>
              <div className="text-xs text-emerald-600 font-medium">Strong topics</div>
              <div className="mt-1 flex flex-wrap gap-1">
                {learning.strong_topics.map((t) => (
                  <span key={t} className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300 text-xs">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}
          {learning.developing_topics.length > 0 && (
            <div>
              <div className="text-xs text-amber-600 font-medium">Developing topics</div>
              <div className="mt-1 flex flex-wrap gap-1">
                {learning.developing_topics.map((t) => (
                  <span key={t} className="px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300 text-xs">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}
          {learning.weak_topics.length > 0 && (
            <div>
              <div className="text-xs text-orange-600 font-medium">Weak topics</div>
              <div className="mt-1 flex flex-wrap gap-1">
                {learning.weak_topics.map((t) => (
                  <span key={t} className="px-1.5 py-0.5 rounded bg-orange-100 text-orange-800 dark:bg-orange-500/15 dark:text-orange-300 text-xs">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}
          {learning.critical_topics.length > 0 && (
            <div>
              <div className="text-xs text-red-600 font-medium">Critical topics</div>
              <div className="mt-1 flex flex-wrap gap-1">
                {learning.critical_topics.map((t) => (
                  <span key={t} className="px-1.5 py-0.5 rounded bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300 text-xs">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
        {learning.learning_gaps.length > 0 && (
          <>
            <Separator className="my-3" />
            <div className="text-xs uppercase tracking-wide text-muted-foreground">Learning gaps</div>
            <div className="mt-2 space-y-1">
              {learning.learning_gaps.slice(0, 4).map((gap, i) => (
                <div key={`gap-${i}`} className="flex items-center justify-between text-xs">
                  <span className="text-foreground">{gap.topic} — {gap.subtopic}</span>
                  <Badge className={`${priorityColor[gap.priority]} border-0 text-[10px]`}>{gap.priority}</Badge>
                </div>
              ))}
            </div>
          </>
        )}
      </Card>

      {/* Bloom performance + Recommendations */}
      <Card className="p-4 border-border bg-card">
        <div className="text-xs uppercase tracking-wide text-muted-foreground">Bloom performance</div>
        <div className="mt-2 space-y-2">
          {bloomPerf.map((b) => (
            <div key={b.level}>
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>{b.level}</span>
                <span>{b.average_score.toFixed(1)}% · {b.questions_attempted} Qs</span>
              </div>
              <Progress value={b.average_score} className="h-1.5 mt-1" />
            </div>
          ))}
        </div>
        {recs.length > 0 && (
          <>
            <Separator className="my-3" />
            <div className="text-xs uppercase tracking-wide text-muted-foreground">Recommendations</div>
            <div className="mt-2 space-y-2">
              {recs.slice(0, 4).map((rec, i) => (
                <div key={`rec-${i}`} className="rounded-lg border border-border p-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-foreground">{rec.action}</span>
                    <Badge className={`${priorityColor[rec.priority]} border-0 text-[10px]`}>{rec.priority}</Badge>
                  </div>
                  <div className="text-[11px] text-muted-foreground mt-0.5">{rec.topic}</div>
                </div>
              ))}
            </div>
          </>
        )}
      </Card>

      {/* Question-level breakdown */}
      {questionPerf.length > 0 && (
        <Card className="p-4 border-border bg-card lg:col-span-3">
          <div className="text-xs uppercase tracking-wide text-muted-foreground">Question-level breakdown</div>
          <div className="mt-2 overflow-auto">
            <table className="text-sm w-full">
              <thead className="text-xs text-muted-foreground uppercase tracking-wide">
                <tr>
                  <th className="text-left px-3 py-2">Question</th>
                  <th className="text-left px-3 py-2">Topic</th>
                  <th className="text-left px-3 py-2">Subtopic</th>
                  <th className="text-left px-3 py-2">Bloom</th>
                  <th className="text-left px-3 py-2">Score</th>
                  <th className="text-left px-3 py-2">%</th>
                </tr>
              </thead>
              <tbody>
                {questionPerf.map((q) => (
                  <tr key={q.question_id} className="border-t border-border">
                    <td className="px-3 py-2 text-foreground">Q{q.question_no}</td>
                    <td className="px-3 py-2 text-muted-foreground">{q.topic}</td>
                    <td className="px-3 py-2 text-muted-foreground">{q.subtopic}</td>
                    <td className="px-3 py-2">
                      <Badge className="bg-accent text-primary border-0 text-[10px]">
                        {q.bloom_analysis.level}
                      </Badge>
                    </td>
                    <td className="px-3 py-2 text-foreground">
                      {q.performance.score}/{q.performance.max_score}
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2">
                        <span className="text-foreground">{q.performance.percentage.toFixed(1)}%</span>
                        <Progress value={q.performance.percentage} className="w-16 h-1.5" />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
