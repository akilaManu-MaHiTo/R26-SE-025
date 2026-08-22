import React, { useState, useEffect, useCallback } from "react";
import {
  ArrowLeft,
  BarChart3,
  BookOpen,
  Brain,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  AlertCircle,
  RefreshCw,
  Users,
  TrendingUp,
  TrendingDown,
  Target,
  Lightbulb,
} from "lucide-react";
import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Skeleton } from "./ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./ui/tabs";
import { Progress } from "./ui/progress";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "./ui/table";
import { AIPageBanner } from "./AIBrand";
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
import {
  fetchExams,
  fetchExamAnalytics,
  fetchExamStudents,
  type ExamListItem,
  type ExamAnalytics,
  type StudentRow,
} from "../api/lecturerApi";

/* ─── Colour helpers ──────────────────────────────────────────────────── */

const statusColor = (analyzed: boolean) =>
  analyzed
    ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300 border-0"
    : "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300 border-0";

const performanceColor = (status: string) => {
  const s = status.toLowerCase();
  if (s === "strong" || s === "high")
    return "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300 border-0";
  if (s === "developing" || s === "medium")
    return "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300 border-0";
  if (s === "needs improvement")
    return "bg-orange-100 text-orange-800 dark:bg-orange-500/15 dark:text-orange-300 border-0";
  return "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300 border-0";
};

const topicColor = (status: string) => {
  const s = status.toLowerCase();
  if (s === "strong" || s === "high") return "text-emerald-600 dark:text-emerald-400";
  if (s === "developing" || s === "medium") return "text-amber-600 dark:text-amber-400";
  return "text-red-600 dark:text-red-400";
};

const chartColors = [
  "#3b82f6",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#8b5cf6",
  "#06b6d4",
  "#ec4899",
  "#14b8a6",
];

/* ─── Exam List View ──────────────────────────────────────────────────── */

function ExamListView({
  exams,
  loading,
  error,
  onSelect,
}: {
  exams: ExamListItem[];
  loading: boolean;
  error: string | null;
  onSelect: (exam: ExamListItem) => void;
}) {
  if (loading) {
    return (
      <Card className="border-border overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <div className="text-foreground">Available Exams</div>
          <div className="text-xs text-muted-foreground mt-0.5">
            Select an exam to view detailed analytics
          </div>
        </div>
        <div className="p-5 space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex items-center gap-4">
              <Skeleton className="h-5 w-20" />
              <Skeleton className="h-5 w-48" />
              <Skeleton className="h-5 w-12" />
              <Skeleton className="h-5 w-16" />
              <Skeleton className="h-5 w-16" />
              <Skeleton className="h-5 w-16" />
            </div>
          ))}
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="border-border overflow-hidden">
        <div className="p-8 text-center">
          <AlertCircle className="size-10 mx-auto mb-3 text-red-400" />
          <div className="text-foreground">Failed to load exams</div>
          <div className="text-sm text-muted-foreground mt-1">{error}</div>
        </div>
      </Card>
    );
  }

  if (exams.length === 0) {
    return (
      <Card className="border-border overflow-hidden">
        <div className="p-8 text-center">
          <BookOpen className="size-10 mx-auto mb-3 text-muted-foreground" />
          <div className="text-foreground">No exams found</div>
          <div className="text-sm text-muted-foreground mt-1">
            Upload exam data and submissions to see them here
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card className="border-border overflow-hidden">
      <div className="px-5 py-4 border-b border-border">
        <div className="text-foreground">Available Exams</div>
        <div className="text-xs text-muted-foreground mt-0.5">
          Select an exam to view detailed analytics
        </div>
      </div>
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead>Course</TableHead>
            <TableHead>Session</TableHead>
            <TableHead>Year</TableHead>
            <TableHead>Students</TableHead>
            <TableHead>Avg Score</TableHead>
            <TableHead>Pass Rate</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {exams.map((exam) => (
            <TableRow
              key={`${exam.course_code}-${exam.session_name}-${exam.year}`}
              className="cursor-pointer"
              onClick={() => onSelect(exam)}
            >
              <TableCell>
                <div>
                  <div className="font-medium text-foreground">
                    {exam.course_code}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {exam.subject_name}
                  </div>
                </div>
              </TableCell>
              <TableCell className="text-foreground">
                {exam.session_name}
              </TableCell>
              <TableCell className="text-foreground">{exam.year}</TableCell>
              <TableCell>
                <div className="flex items-center gap-1.5">
                  <Users className="size-3.5 text-muted-foreground" />
                  <span className="text-foreground">{exam.student_count}</span>
                </div>
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-2">
                  <span className="text-foreground">
                    {exam.average_percentage.toFixed(1)}%
                  </span>
                  <Progress
                    value={exam.average_percentage}
                    className="w-16 h-1.5"
                  />
                </div>
              </TableCell>
              <TableCell className="text-foreground">
                {exam.pass_rate.toFixed(1)}%
              </TableCell>
              <TableCell>
                <Badge className={statusColor(exam.analyzed)}>
                  {exam.analyzed ? (
                    <>
                      <CheckCircle2 className="size-3 mr-1" /> Analyzed
                    </>
                  ) : (
                    "Pending"
                  )}
                </Badge>
              </TableCell>
              <TableCell className="text-right">
                <ChevronRight className="size-4 text-muted-foreground" />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

/* ─── Exam Analytics View ─────────────────────────────────────────────── */

function ExamAnalyticsView({
  courseCode,
  sessionName,
  onBack,
}: {
  courseCode: string;
  sessionName: string;
  onBack: () => void;
}) {
  const [analytics, setAnalytics] = useState<ExamAnalytics | null>(null);
  const [students, setStudents] = useState<StudentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [analyticsData, studentsData] = await Promise.all([
        fetchExamAnalytics(courseCode, sessionName),
        fetchExamStudents(courseCode, sessionName),
      ]);
      setAnalytics(analyticsData);
      setStudents(studentsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load analytics");
    } finally {
      setLoading(false);
    }
  }, [courseCode, sessionName]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <Skeleton className="h-8 w-8" />
          <Skeleton className="h-8 w-64" />
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <Card key={i} className="p-5 border-border">
              <Skeleton className="h-4 w-24 mb-3" />
              <Skeleton className="h-8 w-16 mb-2" />
              <Skeleton className="h-3 w-32" />
            </Card>
          ))}
        </div>
        <Card className="p-5 border-border">
          <Skeleton className="h-64 w-full" />
        </Card>
      </div>
    );
  }

  if (error || !analytics) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={onBack}>
            <ArrowLeft className="size-4 mr-1" /> Back
          </Button>
        </div>
        <Card className="border-border overflow-hidden">
          <div className="p-8 text-center">
            <AlertCircle className="size-10 mx-auto mb-3 text-red-400" />
            <div className="text-foreground">Failed to load analytics</div>
            <div className="text-sm text-muted-foreground mt-1">
              {error || "No data available"}
            </div>
            <Button
              variant="outline"
              size="sm"
              className="mt-4"
              onClick={loadData}
            >
              <RefreshCw className="size-3.5 mr-1.5" /> Retry
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  const stats = analytics.statistics;
  const distData = [
    { band: "0-39", count: 0, fill: "#ef4444" },
    { band: "40-54", count: 0, fill: "#f59e0b" },
    { band: "55-69", count: 0, fill: "#3b82f6" },
    { band: "70-84", count: 0, fill: "#10b981" },
    { band: "85-100", count: 0, fill: "#059669" },
  ];
  students.forEach((s) => {
    const pct = s.score.percentage;
    if (pct < 40) distData[0].count++;
    else if (pct < 55) distData[1].count++;
    else if (pct < 70) distData[2].count++;
    else if (pct < 85) distData[3].count++;
    else distData[4].count++;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={onBack}
            className="gap-1.5"
          >
            <ArrowLeft className="size-4" /> Back
          </Button>
          <div>
            <h2 className="tracking-tight text-foreground">
              {analytics.subject_name}
            </h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              {analytics.session_name} · {analytics.year} · Semester{" "}
              {analytics.semester}
            </p>
          </div>
        </div>
        <Badge className="bg-accent text-primary border-0">
          <BarChart3 className="size-3 mr-1" /> Analytics
        </Badge>
      </div>

      {/* Summary Cards */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-5 border-border relative overflow-hidden">
          <div className="absolute right-2 bottom-2 h-12 w-28 opacity-90">
            <ResponsiveContainer>
              <BarChart data={distData}>
                <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                  {distData.map((d, idx) => (
                    <Cell key={`dist-${idx}`} fill={d.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="size-10 rounded-lg text-blue-600 dark:text-blue-300 bg-blue-50 dark:bg-blue-500/15 flex items-center justify-center">
            <Users className="size-5" />
          </div>
          <div className="mt-4 text-sm text-muted-foreground">
            Total Students
          </div>
          <div className="tracking-tight text-foreground mt-1">
            {stats.total_students}
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            Avg {stats.average_percentage.toFixed(1)}%
          </div>
        </Card>

        <Card className="p-5 border-border">
          <div className="size-10 rounded-lg text-emerald-600 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-500/15 flex items-center justify-center">
            <TrendingUp className="size-5" />
          </div>
          <div className="mt-4 text-sm text-muted-foreground">Pass Rate</div>
          <div className="tracking-tight text-foreground mt-1">
            {stats.pass_rate.toFixed(1)}%
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            {stats.highest_score} highest · {stats.lowest_score} lowest
          </div>
        </Card>

        <Card className="p-5 border-border">
          <div className="size-10 rounded-lg text-amber-600 dark:text-amber-300 bg-amber-50 dark:bg-amber-500/15 flex items-center justify-center">
            <Target className="size-5" />
          </div>
          <div className="mt-4 text-sm text-muted-foreground">
            Attention Areas
          </div>
          <div className="tracking-tight text-foreground mt-1">
            {analytics.attention_areas.length}
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            Topics needing focus
          </div>
        </Card>

        <Card className="p-5 border-border">
          <div className="size-10 rounded-lg text-orange-600 dark:text-orange-300 bg-orange-50 dark:bg-orange-500/15 flex items-center justify-center">
            <Lightbulb className="size-5" />
          </div>
          <div className="mt-4 text-sm text-muted-foreground">Insights</div>
          <div className="tracking-tight text-foreground mt-1">
            {analytics.insights.length}
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            AI-generated recommendations
          </div>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="students" className="space-y-4">
        <TabsList className="bg-muted">
          <TabsTrigger value="students">Students</TabsTrigger>
          <TabsTrigger value="questions">Questions</TabsTrigger>
          <TabsTrigger value="topics">Topics</TabsTrigger>
          <TabsTrigger value="insights">Insights</TabsTrigger>
        </TabsList>

        {/* Students Tab */}
        <TabsContent value="students" className="m-0">
          <Card className="border-border overflow-hidden">
            <div className="px-5 py-4 border-b border-border">
              <div className="text-foreground">Student Performance</div>
              <div className="text-xs text-muted-foreground mt-0.5">
                {students.length} students · Click a row to expand
              </div>
            </div>
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>Student ID</TableHead>
                  <TableHead>Score</TableHead>
                  <TableHead>Percentage</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Submitted</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {students.map((s) => (
                  <TableRow key={s.student_id}>
                    <TableCell>
                      <span className="font-medium text-foreground">
                        {s.student_id}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className="text-foreground">
                        {s.score.obtained} / {s.score.maximum}
                      </span>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <span className="text-foreground">
                          {s.score.percentage.toFixed(1)}%
                        </span>
                        <Progress
                          value={s.score.percentage}
                          className="w-20 h-1.5"
                        />
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge className={performanceColor(s.status)}>
                        {s.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {s.submitted_at
                        ? new Date(s.submitted_at).toLocaleDateString()
                        : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </TabsContent>

        {/* Questions Tab */}
        <TabsContent value="questions" className="m-0 space-y-4">
          <Card className="p-5 border-border">
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="text-foreground">Question Performance</div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  Average percentage by question
                </div>
              </div>
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={analytics.question_performance.map((q) => ({
                    name: `Q${q.question_no}`,
                    avg: q.average_percentage,
                    topic: q.topic,
                  }))}
                  margin={{ top: 10, right: 10, left: 0, bottom: 20 }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="#f1f5f9"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 11, fill: "#94a3b8" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: "#94a3b8" }}
                    axisLine={false}
                    tickLine={false}
                    domain={[0, 100]}
                  />
                  <Tooltip
                    contentStyle={{
                      borderRadius: 8,
                      fontSize: 12,
                      border: "1px solid #e2e8f0",
                    }}
                    formatter={(value: number) => [
                      `${value.toFixed(1)}%`,
                      "Avg Score",
                    ]}
                    labelFormatter={(label: string) => {
                      const q = analytics.question_performance.find(
                        (q) => `Q${q.question_no}` === label,
                      );
                      return q ? `${label} — ${q.topic}` : label;
                    }}
                  />
                  <Bar dataKey="avg" radius={[4, 4, 0, 0]}>
                    {analytics.question_performance.map((q, idx) => (
                      <Cell
                        key={`q-${idx}`}
                        fill={
                          q.average_percentage >= 70
                            ? "#10b981"
                            : q.average_percentage >= 50
                              ? "#f59e0b"
                              : "#ef4444"
                        }
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {/* Bloom Performance */}
          <Card className="p-5 border-border">
            <div className="text-foreground mb-3">Bloom's Taxonomy</div>
            <div className="space-y-2">
              {analytics.bloom_performance.map((b) => (
                <div key={b.level} className="flex items-center gap-3">
                  <div className="w-24 text-sm text-muted-foreground">
                    {b.level}
                  </div>
                  <div className="flex-1 h-7 rounded-md bg-muted overflow-hidden">
                    <div
                      className="h-full flex items-center justify-end pr-2 text-xs text-white"
                      style={{
                        width: `${b.average_percentage}%`,
                        backgroundColor:
                          b.average_percentage >= 70
                            ? "#10b981"
                            : b.average_percentage >= 50
                              ? "#f59e0b"
                              : "#ef4444",
                      }}
                    >
                      {b.average_percentage.toFixed(1)}%
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </TabsContent>

        {/* Topics Tab */}
        <TabsContent value="topics" className="m-0 space-y-4">
          <Card className="p-5 border-border">
            <div className="text-foreground mb-4">Topic Performance</div>
            <div className="space-y-3">
              {analytics.topic_performance.map((t) => (
                <div key={t.topic} className="flex items-center gap-3">
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm text-foreground">{t.topic}</span>
                      <span
                        className={`text-sm font-medium ${topicColor(t.status)}`}
                      >
                        {t.average_percentage.toFixed(1)}%
                      </span>
                    </div>
                    <Progress
                      value={t.average_percentage}
                      className="h-2"
                    />
                  </div>
                  <Badge className={performanceColor(t.status)}>
                    {t.status}
                  </Badge>
                </div>
              ))}
            </div>
          </Card>

          {/* Attention Areas */}
          {analytics.attention_areas.length > 0 && (
            <Card className="border-border overflow-hidden">
              <div className="px-5 py-4 border-b border-border">
                <div className="text-foreground">Attention Areas</div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  Topics and questions that need focus
                </div>
              </div>
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead>Type</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead>Avg Score</TableHead>
                    <TableHead>Priority</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {analytics.attention_areas.map((a, idx) => (
                    <TableRow key={idx}>
                      <TableCell className="text-muted-foreground capitalize">
                        {a.type}
                      </TableCell>
                      <TableCell className="text-foreground font-medium">
                        {a.name}
                      </TableCell>
                      <TableCell className="text-foreground">
                        {a.average_percentage.toFixed(1)}%
                      </TableCell>
                      <TableCell>
                        <Badge
                          className={
                            a.priority === "High"
                              ? "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300 border-0"
                              : "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300 border-0"
                          }
                        >
                          {a.priority}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          )}
        </TabsContent>

        {/* Insights Tab */}
        <TabsContent value="insights" className="m-0">
          <Card className="p-5 border-border">
            <div className="flex items-center gap-2 mb-4">
              <Lightbulb className="size-5 text-primary" />
              <div className="text-foreground">AI-Generated Insights</div>
            </div>
            {analytics.insights.length === 0 ? (
              <div className="text-sm text-muted-foreground">
                No insights available
              </div>
            ) : (
              <div className="space-y-3">
                {analytics.insights.map((insight, idx) => (
                  <div
                    key={idx}
                    className="flex items-start gap-3 p-3 rounded-lg bg-muted/50"
                  >
                    <ChevronRight className="size-4 mt-0.5 text-primary shrink-0" />
                    <span className="text-sm text-foreground">{insight}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

/* ─── Main AnalyticsPage ──────────────────────────────────────────────── */

export function AnalyticsPage() {
  const [exams, setExams] = useState<ExamListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedExam, setSelectedExam] = useState<ExamListItem | null>(null);

  const loadExams = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchExams();
      setExams(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load exams");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadExams();
  }, [loadExams]);

  return (
    <div className="p-8 space-y-6">
      <AIPageBanner model="pulse" />

      {selectedExam ? (
        <ExamAnalyticsView
          courseCode={selectedExam.course_code}
          sessionName={selectedExam.session_name}
          onBack={() => setSelectedExam(null)}
        />
      ) : (
        <>
          <div className="flex items-start justify-between flex-wrap gap-3">
            <div>
              <h2 className="tracking-tight text-foreground">
                Exam Analytics
              </h2>
              <p className="text-sm text-muted-foreground mt-1">
                Select an exam to view detailed analytics and student
                performance
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={loadExams}
              disabled={loading}
              className="gap-1.5"
            >
              {loading ? (
                <RefreshCw className="size-3.5 animate-spin" />
              ) : (
                <RefreshCw className="size-3.5" />
              )}
              {loading ? "Loading..." : "Refresh"}
            </Button>
          </div>
          <ExamListView
            exams={exams}
            loading={loading}
            error={error}
            onSelect={setSelectedExam}
          />
        </>
      )}
    </div>
  );
}
