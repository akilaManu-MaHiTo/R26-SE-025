import React, { useState, useEffect, useCallback, useRef } from "react";
import { useSearchParams } from "react-router";
import { BrandOrb } from "./BrandOrb";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowLeft, FileText, BarChart3, Users, ChevronRight, Sparkles, CheckCircle2, Clock, Search, SlidersHorizontal, ArrowUpRight, UserSearch, Eye, AlertCircle, Loader2, GraduationCap, BookOpen, Brain, Award, User } from "lucide-react";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import { Input } from "./ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";
import { AnalysisLoader } from "./AnalysisLoader";
import { AIPageBanner } from "./AIBrand";
import { toast } from "sonner";
import {
  fetchExams,
  fetchExamAnalytics,
  fetchExamAnalyticsStream,
  fetchTeachingActions,
  fetchExamStudents,
  fetchLecturerStudentDetail,
  fetchLecturerStudentDetailStream,
  fetchLlmHealth,
  fetchBloomHealth,
  reanalyseExam,
  type ExamListItem,
  type ExamAnalytics,
  type CanonicalTopic,
  type TeachingAction,
  type StudentRow,
  type LecturerStudentDetail,
  type QuestionPerformance,
} from "../api/lecturerApi";
import { KpiCards } from "./analytics/KpiCards";
import { DistributionHistogram } from "./analytics/DistributionHistogram";
import { TopicBloomHeatmap } from "./analytics/TopicBloomHeatmap";
import { CanonicalTopicTable } from "./analytics/CanonicalTopicTable";
import { AttentionAreasPanel } from "./analytics/AttentionAreasPanel";
import { BloomChart } from "./analytics/BloomChart";
import { QuestionPerformanceTable } from "./analytics/QuestionPerformanceTable";
import { InsightsPanel } from "./analytics/InsightsPanel";
import { TeachingActions } from "./analytics/TeachingActions";
import { ERDiagramViewer } from "./analytics/ERDiagramViewer";
import { DiagramAnalysisPanel } from "./analytics/DiagramAnalysisPanel";
import { GradingOverview, StudentGradingCells, canViewStudent, ExamInventoryScore } from "./analytics/GradingStatus";
import { TopicDetailModal } from "./analytics/TopicDetailModal";
import { QuestionDetailModal } from "./analytics/QuestionDetailModal";
import { ExamPaperModal } from "./analytics/ExamPaperModal";
import { StudentQuestionRow } from "./analytics/StudentQuestionRow";

export default function AnalyticsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedStudentId = searchParams.get("student");
  const [exams, setExams] = useState<ExamListItem[]>([]);
  const [selectedExam, setSelectedExam] = useState<ExamListItem | null>(null);
  const [paperOpen, setPaperOpen] = useState(false);
  const [analytics, setAnalytics] = useState<ExamAnalytics | null>(null);
  const [teachingActions, setTeachingActions] = useState<TeachingAction[]>([]);
  const [loadingExams, setLoadingExams] = useState(true);
  const [examListError, setExamListError] = useState(false);
  const [examReload, setExamReload] = useState(0);
  const [loadingAnalytics, setLoadingAnalytics] = useState(false);
  const finishAnalyticsLoading = useCallback(() => setLoadingAnalytics(false), []);
  const [loadingActions, setLoadingActions] = useState(false);
  const [selectedTopic, setSelectedTopic] = useState<CanonicalTopic | null>(null);
  const [selectedQuestion, setSelectedQuestion] = useState<QuestionPerformance | null>(null);
  // dense table filters
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "analyzed" | "pending">("all");
  const [yearFilter, setYearFilter] = useState<string>("all");
  const [semesterFilter, setSemesterFilter] = useState<string>("all");
  // lecturer student finder (inside analyzed exam)
  const [students, setStudents] = useState<StudentRow[]>([]);
  const [loadingStudents, setLoadingStudents] = useState(false);
  const [studentListError, setStudentListError] = useState<string | null>(null);
  const [studentSearch, setStudentSearch] = useState("");
  const [selectedStudentId, setSelectedStudentId] = useState<string | null>(null);
  const [studentDetail, setStudentDetail] = useState<LecturerStudentDetail | null>(null);
  const [loadingStudentDetail, setLoadingStudentDetail] = useState(false);
  const [studentDetailError, setStudentDetailError] = useState<string | null>(null);
  const studentRequest = useRef<object | null>(null);

  useEffect(() => () => {
    studentRequest.current = null;
    window.dispatchEvent(new CustomEvent("topbar-student-analysis", { detail: { active: false } }));
  }, []);

  useEffect(() => {
    setLoadingExams(true);
    setExamListError(false);
    let ignore = false;
    fetchExams().then(value => { if (!ignore) setExams(value); })
      .catch(() => { if (!ignore) setExamListError(true); })
      .finally(() => { if (!ignore) setLoadingExams(false); });
    return () => { ignore = true; };
  }, [examReload]);

  const handleSelectExam = useCallback(async (exam: ExamListItem, opts?: { forceReanalyse?: boolean }) => {
    setPaperOpen(false);
    setTeachingActions([]);
    setLoadingActions(false);
    studentRequest.current = null;
    window.dispatchEvent(new CustomEvent("topbar-student-analysis", { detail: { active: false } }));
    setLoadingStudentDetail(false);
    setSelectedTopic(null);
    setSelectedQuestion(null);
    // Core analytics does NOT require Ollama — only ModernBERT for new classification.
    // Cached snapshot loads even if both models offline. We let backend decide freshness.
    const requestId = `${exam.course_code}-${exam.session_name}-${exam.year}-${exam.month}-${exam.semester}-${Date.now()}`;
    // store current request id for stale-response guard
    (handleSelectExam as any)._lastRequestId = requestId;

    setSelectedExam(exam);
    setLoadingAnalytics(true);
    setLoadingStudents(true);
    setStudentListError(null);
    setAnalytics(null);
    // reset student finder
    setStudents([]);
    setStudentSearch("");
    setSelectedStudentId(null);
    setStudentDetail(null);
    setStudentDetailError(null);

    // Status does not require model analysis; load it even when analytics fails.
    const studentsPromise = fetchExamStudents(exam.course_code, exam.session_name, exam.year, exam.month, exam.semester)
      .then(rows => {
        if ((handleSelectExam as any)._lastRequestId === requestId) setStudents(rows);
      })
      .catch(() => {
        if ((handleSelectExam as any)._lastRequestId === requestId) {
          setStudents([]);
          setStudentListError("Could not load grading status. Reopen the exam to retry.");
        }
      })
      .finally(() => {
        if ((handleSelectExam as any)._lastRequestId === requestId) setLoadingStudents(false);
      });
    void studentsPromise;

    let receivedAnalytics = false;
    try {
      // Reanalysis failures must surface; a cached read would conceal the failure.
      let data: ExamAnalytics;
      if (opts?.forceReanalyse) {
        data = await reanalyseExam(exam.course_code, exam.session_name, exam.year, exam.month, exam.semester);
      } else {
        try {
          data = await fetchExamAnalyticsStream(
            exam.course_code,
            exam.session_name,
            exam.year,
            exam.month,
            exam.semester,
            () => {},
          );
        } catch {
          if ((handleSelectExam as any)._lastRequestId !== requestId) return;
          data = await fetchExamAnalytics(exam.course_code, exam.session_name, exam.year, exam.month, exam.semester);
        }
      }
      // Stale-response guard: only apply if still the latest requested exam
      if ((handleSelectExam as any)._lastRequestId !== requestId) return;
      setAnalytics(data);
      receivedAnalytics = true;

      // Grading status is already loading independently; only teaching remains.
      setLoadingActions(true);
      const teachingPromise = fetchTeachingActions(exam.course_code, exam.session_name, exam.year, exam.month, exam.semester)
        .then((actions) => {
          if ((handleSelectExam as any)._lastRequestId !== requestId) return;
          setTeachingActions(actions);
        })
        .catch(() => {
          if ((handleSelectExam as any)._lastRequestId !== requestId) return;
          setTeachingActions([]);
        })
        .finally(() => {
          if ((handleSelectExam as any)._lastRequestId === requestId) setLoadingActions(false);
        });

      void teachingPromise;
    } catch (err) {
      if ((handleSelectExam as any)._lastRequestId !== requestId) return;
      console.error(err);
      const msg = err instanceof Error ? err.message : String(err);
      // Separate ModernBERT (core) vs Ollama (optional) health
      if (msg.toLowerCase().includes("bloom") || msg.toLowerCase().includes("modernbert")) {
        try {
          const bh = await fetchBloomHealth();
          if (!bh.available) toast.error(`Bloom model unavailable: ${bh.detail} — core analytics cannot be computed.`);
          else toast.error(msg);
        } catch { toast.error(msg); }
      } else if (msg.toLowerCase().includes("ollama") || msg.toLowerCase().includes("model unavailable")) {
        // Teaching actions are optional; core analytics may still have succeeded but actions failed — show core error only
        toast.error("Model unavailable, please retry when model comes online.");
      } else {
        toast.error(msg);
      }
    } finally {
      if ((handleSelectExam as any)._lastRequestId === requestId && !receivedAnalytics) setLoadingAnalytics(false);
    }
  }, []);

  const handleSelectStudent = useCallback(async (studentId: string) => {
    if (!selectedExam) return;
    const request = {};
    studentRequest.current = request;
    const isCurrent = () => studentRequest.current === request;
    const targetRow = students.find((r) => r.student_id === studentId);
    const needsAnalysis = !targetRow || targetRow.analysis_status !== "generated";
    setSelectedStudentId(studentId);
    setLoadingStudentDetail(true);
    setStudentDetail(null);
    setStudentDetailError(null);
    if (searchParams.get("student") !== studentId) {
      setSearchParams({
        student: studentId,
        course: selectedExam.course_code,
        session: selectedExam.session_name,
        year: String(selectedExam.year),
        month: String(selectedExam.month),
        semester: String(selectedExam.semester),
      });
    }
    if (needsAnalysis) {
      try {
        const health = await fetchLlmHealth();
        if (!health.online || !health.model_available) throw new Error("Model unavailable");
      } catch {
        if (!isCurrent()) return;
        const message = "Model unavailable, please retry when model comes online.";
        setStudentDetailError(message);
        setLoadingStudentDetail(false);
        toast.error(message);
        return;
      }
    }
    const dispatchTopbar = (active: boolean, message?: string, progress?: number, status = "analyzing") => {
      if (!needsAnalysis) return;
      const jobId = JSON.stringify([studentId, selectedExam.course_code, selectedExam.session_name, selectedExam.year, selectedExam.month, selectedExam.semester]);
      const examLabel = `${selectedExam.course_code} · ${selectedExam.session_name} · ${selectedExam.year}/${selectedExam.month} · Semester ${selectedExam.semester}`;
      window.dispatchEvent(new CustomEvent("topbar-student-analysis", { detail: { active, studentId, jobId, examLabel, message: message || "", progress, status } }));
    };
    dispatchTopbar(true, `Submitting analysis for ${studentId}…`, 0, "queued");
    try {
      if (!needsAnalysis) {
        const detail = await fetchLecturerStudentDetail(
          selectedExam.course_code,
          selectedExam.session_name,
          studentId,
          selectedExam.year,
          selectedExam.month,
          selectedExam.semester,
          false,
          false,
        );
        if (!isCurrent()) return;
        setStudentDetail(detail);
        setStudents((prev) => prev.map((r) => r.student_id === studentId ? { ...r, analysis_status: detail.analysis_status ?? "generated" } : r));
        return;
      }
      // Try streaming for live progress (topbar + row spinner), fallback to plain fetch
      let detail: LecturerStudentDetail;
      try {
        detail = await fetchLecturerStudentDetailStream(
          selectedExam.course_code,
          selectedExam.session_name,
          studentId,
          selectedExam.year,
          selectedExam.month,
          selectedExam.semester,
          (msg, prog, phase) => {
            dispatchTopbar(true, msg, prog, phase === "queued" ? "queued" : "analyzing");
          },
          false
        );
      } catch {
        dispatchTopbar(true, `Reconnecting to analysis for ${studentId}…`, 0, "queued");
        detail = await fetchLecturerStudentDetail(
          selectedExam.course_code,
          selectedExam.session_name,
          studentId,
          selectedExam.year,
          selectedExam.month,
          selectedExam.semester,
          false
        );
      }
      dispatchTopbar(false, `Analysis complete for ${studentId}`, 100, "complete");
      if (!isCurrent()) return;
      setStudentDetail(detail);
      // Update row status optimistically
      setStudents((prev) => prev.map((r) => r.student_id === studentId ? { ...r, analysis_status: detail.analysis_status ?? "generated" } : r));
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to load student detail";
      dispatchTopbar(false, `Analysis failed for ${studentId}: ${msg}`, 0, "failed");
      if (!isCurrent()) return;
      setStudentDetailError(msg);
      // Fallback: if pending student failed due to model down, toast
      if (needsAnalysis) {
        const lower = msg.toLowerCase();
        if (lower.includes("model") || lower.includes("ollama") || lower.includes("unavailable")) {
          toast.error("Model unavailable, please retry when model comes online.");
        } else {
          try {
            const h = await fetchLlmHealth();
            if (!isCurrent()) return;
            if (!h.online || !h.model_available) toast.error("Model unavailable, please retry when model comes online.");
          } catch {
            // ignore — already showed detail error
          }
        }
      }
    } finally {
      if (isCurrent()) setLoadingStudentDetail(false);
    }
  }, [selectedExam, students, searchParams, setSearchParams]);

  useEffect(() => {
    if (!requestedStudentId) {
      studentRequest.current = null;
      window.dispatchEvent(new CustomEvent("topbar-student-analysis", { detail: { active: false } }));
      setSelectedStudentId(null);
      setStudentDetail(null);
      setStudentDetailError(null);
      setLoadingStudentDetail(false);
    }
    if (searchParams.has("course")) {
      const exam = exams.find((item) =>
        item.course_code === searchParams.get("course") &&
        item.session_name === searchParams.get("session") &&
        String(item.year) === searchParams.get("year") &&
        String(item.month) === searchParams.get("month") &&
        String(item.semester) === searchParams.get("semester")
      );
      if (exam && exam !== selectedExam) {
        void handleSelectExam(exam);
        return;
      }
    }
    if (requestedStudentId && selectedExam && !loadingAnalytics && !loadingStudents && selectedStudentId !== requestedStudentId) {
      void handleSelectStudent(requestedStudentId);
    }
  }, [requestedStudentId, searchParams, selectedExam, exams, loadingAnalytics, loadingStudents, selectedStudentId, handleSelectExam, handleSelectStudent]);

  if (requestedStudentId) {
    const selectionMatches = selectedStudentId === requestedStudentId && selectedExam && (
      !searchParams.has("course") || (
        selectedExam.course_code === searchParams.get("course") &&
        selectedExam.session_name === searchParams.get("session") &&
        String(selectedExam.year) === searchParams.get("year") &&
        String(selectedExam.month) === searchParams.get("month") &&
        String(selectedExam.semester) === searchParams.get("semester")
      )
    );
    return (
      <div className="p-6 md:p-8 space-y-6">
        <Button variant="ghost" size="sm" onClick={() => {
          const params = new URLSearchParams(searchParams);
          params.delete("student");
          setSearchParams(params);
        }}>
          <ArrowLeft className="size-4 mr-2" /> Back to exam
        </Button>
        {!selectedExam && !loadingExams ? (
          <p className="text-sm text-muted-foreground">The exam for this student could not be found.</p>
        ) : (
        <div className="space-y-6">
          <header className="space-y-2">
            <h2 className="flex flex-wrap items-center gap-2 text-xl font-semibold">
              <GraduationCap className="size-5 text-primary" />
              {requestedStudentId} — Performance
              <Badge variant="outline" className="ml-1 text-xs font-normal">Lecturer view · no AI tips</Badge>
            </h2>
            <p className="text-sm text-muted-foreground">
              {selectedExam?.course_code} · {selectedExam?.session_name} · {selectedExam?.year} — raw scores, topics and Bloom levels only.
            </p>
          </header>

          {!selectionMatches || loadingStudentDetail || (!studentDetail && !studentDetailError) ? (
            <div className="py-10 flex flex-col items-center gap-3">
              <BrandOrb state="searching" size={64} aria-label="Loading student performance" />
              <p className="text-sm text-muted-foreground">Loading performance…</p>
            </div>
          ) : studentDetailError ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 dark:bg-amber-950/20 p-4 flex gap-3">
              <AlertCircle className="size-5 text-amber-600 shrink-0" />
              <div className="space-y-1">
                <p className="text-sm font-medium text-amber-800 dark:text-amber-300">{studentDetailError.includes("423") || studentDetailError.toLowerCase().includes("not yet generated") ? "Not yet analyzed" : "Could not load"}</p>
                <p className="text-sm text-amber-700 dark:text-amber-400">{studentDetailError}</p>
              </div>
            </div>
          ) : studentDetail ? (
            <div className="space-y-5">
              {/* Overall */}
              <Card className="p-4 bg-muted/30">
                <div className="flex items-center gap-2 text-sm font-medium"><Award className="size-4 text-primary" /> Overall Performance</div>
                <div className="mt-3 flex flex-wrap items-end gap-4">
                  <div>
                    <div className="text-2xl font-semibold tabular-nums">{studentDetail.overall_performance.score.toFixed(1)} <span className="text-base text-muted-foreground">/ {studentDetail.overall_performance.maximum.toFixed(1)}</span></div>
                    <div className="text-xs text-muted-foreground mt-0.5">{studentDetail.overall_performance.status} · {studentDetail.overall_performance.percentage.toFixed(1)}%</div>
                  </div>
                  <Badge className="ml-auto border text-xs">{studentDetail.overall_performance.status}</Badge>
                </div>
                <div className="h-2 bg-background rounded-full overflow-hidden mt-3">
                  <div className="h-full bg-primary rounded-full" style={{ width: `${studentDetail.overall_performance.percentage}%` }} />
                </div>
              </Card>

              {/* Question performance */}
              <div className="space-y-2">
                <h4 className="text-sm font-semibold flex items-center gap-2"><FileText className="size-4 text-primary" /> Question Breakdown</h4>
                <p className="text-xs text-muted-foreground">Select a question number to review the written answer, marking criteria and grading feedback.</p>
                <div className="rounded-lg border overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-muted/40">
                        <TableHead className="text-xs">Q</TableHead>
                        <TableHead className="text-xs">Topic</TableHead>
                        <TableHead className="text-xs">Bloom</TableHead>
                        <TableHead className="text-xs text-right">Score</TableHead>
                        <TableHead className="text-xs text-right">%</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {studentDetail.question_performance.map((q) => (
                        <StudentQuestionRow key={`${studentDetail.student_id}-${studentDetail.subject_code}-${studentDetail.session_name}-${studentDetail.year}-${studentDetail.month}-${studentDetail.semester}-${q.question_id}`}
                          question={q} studentId={studentDetail.student_id}
                          exam={{ course_code: studentDetail.subject_code, session_name: studentDetail.session_name,
                            year: studentDetail.year, month: studentDetail.month, semester: studentDetail.semester }} />
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>

              {/* Topic performance */}
              <div className="grid md:grid-cols-2 gap-4">
                <Card className="p-4">
                  <div className="text-sm font-medium flex items-center gap-2"><BookOpen className="size-4 text-primary" /> Topic Performance</div>
                  <div className="mt-3 space-y-2.5">
                    {studentDetail.topic_performance.length === 0 ? <p className="text-xs text-muted-foreground">No topic data</p> : studentDetail.topic_performance.map((t) => (
                      <div key={t.topic} className="flex items-center gap-2">
                        <div className="flex-1 min-w-0">
                          <div className="text-xs truncate">{t.topic}</div>
                          <div className="h-1.5 bg-muted rounded-full overflow-hidden mt-1"><div className="h-full bg-primary rounded-full" style={{ width: `${t.percentage}%` }} /></div>
                        </div>
                        <div className="text-xs tabular-nums font-medium shrink-0">{t.percentage.toFixed(1)}%</div>
                        <Badge variant="outline" className="text-[10px] shrink-0">{t.status}</Badge>
                      </div>
                    ))}
                  </div>
                </Card>
                <Card className="p-4">
                  <div className="text-sm font-medium flex items-center gap-2"><Brain className="size-4 text-primary" /> Bloom Performance</div>
                  <div className="mt-3 space-y-2.5">
                    {studentDetail.bloom_performance.length === 0 ? <p className="text-xs text-muted-foreground">No Bloom data</p> : studentDetail.bloom_performance.map((b) => (
                      <div key={b.level} className="flex items-center gap-2">
                        <div className="flex-1 min-w-0">
                          <div className="text-xs">{b.level}</div>
                          <div className="h-1.5 bg-muted rounded-full overflow-hidden mt-1"><div className="h-full bg-primary rounded-full" style={{ width: `${b.average_score}%` }} /></div>
                        </div>
                        <div className="text-xs tabular-nums font-medium shrink-0">{b.average_score.toFixed(1)}%</div>
                        <Badge variant="outline" className="text-[10px] shrink-0">{b.status}</Badge>
                      </div>
                    ))}
                  </div>
                </Card>
              </div>

              {/* Learning analysis (no AI gaps/tips) */}
              <Card className="p-4">
                <div className="text-sm font-medium flex items-center gap-2"><GraduationCap className="size-4 text-primary" /> Learning Summary</div>
                <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                  <div><span className="text-muted-foreground">Overall:</span> <span className="font-medium">{studentDetail.learning_analysis.overall_performance}</span></div>
                  <div className="col-span-2"><span className="text-muted-foreground">Strong:</span> {studentDetail.learning_analysis.strong_topics.join(", ") || "—"}</div>
                  <div className="col-span-2"><span className="text-muted-foreground">Developing:</span> {studentDetail.learning_analysis.developing_topics.join(", ") || "—"}</div>
                  <div className="col-span-2"><span className="text-muted-foreground">Weak:</span> {studentDetail.learning_analysis.weak_topics.join(", ") || "—"}</div>
                  <div className="col-span-2"><span className="text-muted-foreground">Critical:</span> {studentDetail.learning_analysis.critical_topics.join(", ") || "—"}</div>
                </div>
                <p className="text-xs text-muted-foreground mt-3 border-t pt-2">AI improvement tips (recommendations, next-question strategy) are intentionally hidden in lecturer view.</p>
              </Card>

              {/* ——— Student Diagram ——— from diagram_evaluation / diagram_marking */}
              {(() => {
                const diagEval: any = (studentDetail as any).diagram_evaluation || (studentDetail as any).diagram?.evaluation;
                const diagMark: any = (studentDetail as any).diagram_marking || (studentDetail as any).diagram?.marking;
                if (!diagEval && !diagMark) return null;
                const ev = diagEval?.evaluation_result || {};
                const criteria: any[] = ev.criteria_results || [];
                const total = ev.total_score ?? diagMark?.diagram_marks ?? 0;
                const max = ev.max_score ?? 20;
                const pct = max ? (total / max) * 100 : 0;
                const diagramDetails = diagEval?.diagram_details || diagMark?.diagram_details;
                const detections: any[] = diagramDetails?.detections || [];
                const entities: any[] = diagramDetails?.entities || diagEval?.diagram_entity_relations || diagMark?.diagram_entity_relations || [];
                const rels: any[] = diagramDetails?.relationships || diagEval?.diagram_relations || diagMark?.diagram_relations || [];
                return (
                  <Card className="p-4 space-y-3 border-violet-200 bg-violet-50/30 dark:bg-violet-950/10">
                    <div className="flex items-center gap-2 text-sm font-medium">
                      <div className="size-7 rounded-md bg-violet-500/10 text-violet-600 flex items-center justify-center"><FileText className="size-4" /></div>
                      Diagram — EER / ER Scores
                      <Badge variant="outline" className="ml-auto text-xs tabular-nums">{total} / {max} · {pct.toFixed(1)}%</Badge>
                    </div>

                    <ERDiagramViewer
                      key={studentDetail.student_id}
                      entities={entities.map((entity: any) => ({
                        ...entity,
                        primary_keys: entity.primary_keys
                          ?? diagramDetails?.structure?.entities?.[entity.entity_name]?.primary_keys
                          ?? (diagEval?.diagram_entity_relations || diagMark?.diagram_entity_relations || []).find((item: any) => item.entity_name === entity.entity_name)?.primary_keys,
                      }))}
                      relationships={rels}
                      image={ev.annotated_image}
                    />
                    <p className="text-xs text-muted-foreground">{detections.length} detected elements</p>
                    {entities.length === 0 && detections.length > 0 && <ul className="text-xs space-y-1">
                      {detections.map((detection: any, index: number) => <li key={detection.id ?? index}>{detection.label}: {detection.text || "No readable label"}</li>)}
                    </ul>}

                    {/* Entities / Relationships summary */}
                    {(entities.length > 0 || rels.length > 0) && (
                      <div className="grid md:grid-cols-2 gap-3 text-xs">
                        {entities.length > 0 && (
                          <div className="rounded-lg border bg-card p-3">
                            <div className="font-medium mb-1.5">Entities & Attributes</div>
                            <div className="space-y-1.5">
                              {entities.map((e: any, i: number) => (
                                <div key={i} className="flex gap-2">
                                  <span className="font-medium shrink-0">{e.entity_name}:</span>
                                  <span className="text-muted-foreground">{(e.attributes || []).join(", ") || "—"}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        {rels.length > 0 && (
                          <div className="rounded-lg border bg-card p-3">
                            <div className="font-medium mb-1.5">Relationships</div>
                            <div className="space-y-1">
                              {rels.map((r: any, i: number) => (
                                <div key={i} className="flex gap-2">
                                  <span className="font-medium">{r.relation_name || r.name || `R${i+1}`}:</span>
                                  <span className="text-muted-foreground">{(r.entities || []).join(" — ") || "—"}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Criteria */}
                    {criteria.length > 0 && (
                      <div className="rounded-lg border overflow-hidden">
                        <Table>
                          <TableHeader>
                            <TableRow className="bg-muted/40">
                              <TableHead className="text-xs">Criterion</TableHead>
                              <TableHead className="text-xs text-center">Awarded</TableHead>
                              <TableHead className="text-xs text-center">Status</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {criteria.map((c: any) => (
                              <TableRow key={c.criterion_id} className="h-9">
                                <TableCell className="text-xs max-w-[220px]"><div className="truncate" title={c.criterion}>{c.criterion}</div><div className="text-[10px] text-muted-foreground truncate">{c.remarks}</div></TableCell>
                                <TableCell className="text-xs text-center tabular-nums">{c.awarded_marks} / {c.max_marks}</TableCell>
                                <TableCell className="text-xs text-center"><Badge variant="outline" className={`text-[10px] ${c.status === "pass" ? "bg-emerald-500/10 text-emerald-700 border-emerald-500/20" : c.status === "partial" ? "bg-amber-500/10 text-amber-700 border-amber-500/20" : "bg-red-500/10 text-red-700 border-red-500/20"}`}>{c.status}</Badge></TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    )}

                    {ev.overall_feedback && (
                      <div className="rounded-lg bg-muted/40 border p-3 text-xs leading-relaxed">{ev.overall_feedback}</div>
                    )}
                    <div className="text-[11px] text-muted-foreground">Source: {ev.grading_source || diagMark?.source || "diagram_evaluation"} · {diagEval?.exam_code || ""} · {new Date(diagEval?.created_at || "").toLocaleDateString()}</div>
                  </Card>
                );
              })()}

              <div className="text-xs text-muted-foreground text-center">Generated {new Date(studentDetail.generated_at).toLocaleString()} · {studentDetail.model_metadata.bloom_model} ({studentDetail.model_metadata.grading_source})</div>
            </div>
          ) : null}
        </div>
        )}
      </div>
    );
  }

  // Exam Selection — dense, scannable table with filters
  if (!selectedExam) {
    const analyzedCount = exams.filter((e) => e.analyzed).length;
    const notAnalyzedCount = exams.length - analyzedCount;

    const yearOptions = Array.from(new Set(exams.map((e) => e.year))).sort((a, b) => b - a);
    const semesterOptions = Array.from(new Set(exams.map((e) => e.semester))).sort((a, b) => a - b);

    const filteredExams = exams.filter((exam) => {
      const q = searchQuery.trim().toLowerCase();
      const matchesSearch =
        !q ||
        exam.course_code.toLowerCase().includes(q) ||
        exam.subject_name.toLowerCase().includes(q) ||
        exam.session_name.toLowerCase().includes(q);
      const matchesStatus =
        statusFilter === "all" ? true : statusFilter === "analyzed" ? exam.analyzed : !exam.analyzed;
      const matchesYear = yearFilter === "all" ? true : String(exam.year) === yearFilter;
      const matchesSem = semesterFilter === "all" ? true : String(exam.semester) === semesterFilter;
      return matchesSearch && matchesStatus && matchesYear && matchesSem;
    });

    const hasActiveFilters = searchQuery || statusFilter !== "all" || yearFilter !== "all" || semesterFilter !== "all";

    const clearFilters = () => {
      setSearchQuery("");
      setStatusFilter("all");
      setYearFilter("all");
      setSemesterFilter("all");
    };

    return (
      <div className="p-6 md:p-8 space-y-5">
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
          <AIPageBanner model="pulse" />
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: 0.06 }} className="space-y-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <BarChart3 className="size-4" /> Analytics
            <ChevronRight className="size-4" /> Exam Selection
          </div>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-1">
              <h2 className="tracking-tight text-foreground bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text">Lecturer Analytics</h2>
              <p className="text-sm text-muted-foreground max-w-2xl">
                Dense, scannable list of all exams. Filter by status, search by course, or select a row to view/generate insights.
              </p>
            </div>
            {exams.length > 0 && (
              <div className="flex items-center gap-2 shrink-0">
                <div className="hidden sm:flex items-center gap-1.5 rounded-full border bg-card px-3 py-1.5">
                  <span className="size-2 rounded-full bg-emerald-500" />
                  <span className="text-xs font-medium">{analyzedCount} Analyzed</span>
                  <span className="text-muted-foreground text-xs">·</span>
                  <span className="size-2 rounded-full bg-amber-500" />
                  <span className="text-xs font-medium">{notAnalyzedCount} Pending</span>
                </div>
                <div className="sm:hidden flex items-center gap-1">
                  <Badge className="bg-emerald-500/10 text-emerald-700 border-emerald-500/20 text-xs"><CheckCircle2 className="size-3 mr-1" />{analyzedCount}</Badge>
                  <Badge variant="outline" className="bg-amber-500/10 text-amber-700 border-amber-500/20 text-xs"><Clock className="size-3 mr-1" />{notAnalyzedCount}</Badge>
                </div>
              </div>
            )}
          </div>
        </motion.div>

        {loadingExams ? (
          <AnalysisLoader label="Loading exams" />
        ) : examListError ? (
          <Card className="p-8 space-y-3" role="alert">
            <p>Could not load exams. Check the analytics service and retry.</p>
            <Button variant="outline" onClick={() => setExamReload(value => value + 1)}>Retry</Button>
          </Card>
        ) : exams.length === 0 ? (
          <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }}>
            <Card className="p-12 text-center border-border bg-gradient-to-b from-card to-muted/20">
              <BarChart3 className="h-12 w-12 mx-auto mb-4 text-muted-foreground/40" />
              <p className="text-muted-foreground">No exams found</p>
              <p className="text-xs text-muted-foreground mt-1">Exams appear once an essay rubric is saved. Grades are shown when available.</p>
            </Card>
          </motion.div>
        ) : (
          <>
            {/* Dense filter bar */}
            <Card className="p-3 flex flex-col gap-3 border-border bg-card/80 backdrop-blur">
              <div className="flex flex-col lg:flex-row gap-3">
                <div className="relative flex-1 min-w-0">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                  <Input
                    placeholder="Search course, subject or session…"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-9 h-9 bg-background"
                  />
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <div className="flex items-center gap-1 rounded-lg border bg-muted/40 p-1">
                    {(["all", "analyzed", "pending"] as const).map((v) => (
                      <button
                        key={v}
                        onClick={() => setStatusFilter(v)}
                        className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${statusFilter === v ? "bg-background shadow-sm border text-foreground" : "text-muted-foreground hover:text-foreground"}`}
                      >
                        {v === "all" ? "All" : v === "analyzed" ? "Analyzed" : "Not analyzed"}
                      </button>
                    ))}
                  </div>
                  <Select value={yearFilter} onValueChange={setYearFilter}>
                    <SelectTrigger className="w-[118px] h-9">
                      <SelectValue placeholder="Year" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All years</SelectItem>
                      {yearOptions.map((y) => (
                        <SelectItem key={y} value={String(y)}>Year {y}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Select value={semesterFilter} onValueChange={setSemesterFilter}>
                    <SelectTrigger className="w-[130px] h-9">
                      <SelectValue placeholder="Semester" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All semesters</SelectItem>
                      {semesterOptions.map((s) => (
                        <SelectItem key={s} value={String(s)}>Sem {s}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {hasActiveFilters && (
                    <Button variant="ghost" size="sm" onClick={clearFilters} className="h-9">
                      <SlidersHorizontal className="size-4 mr-1" /> Clear
                    </Button>
                  )}
                </div>
              </div>
              <div className="flex items-center justify-between text-xs text-muted-foreground border-t pt-2">
                <span>Showing <span className="font-medium text-foreground tabular-nums">{filteredExams.length}</span> of {exams.length} exams</span>
                <span className="hidden sm:inline">Click a row to {statusFilter === "pending" ? "generate" : "view"} analytics →</span>
              </div>
            </Card>

            {/* Dense table */}
            <Card className="overflow-hidden border-border bg-card/80 backdrop-blur">
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-muted/40 hover:bg-muted/40 border-b">
                      <TableHead className="w-[22%] text-xs font-semibold tracking-wider uppercase text-muted-foreground">Course</TableHead>
                      <TableHead className="text-xs font-semibold tracking-wider uppercase text-muted-foreground">Session</TableHead>
                      <TableHead className="text-xs font-semibold tracking-wider uppercase text-muted-foreground">Term</TableHead>
                      <TableHead className="text-center text-xs font-semibold tracking-wider uppercase text-muted-foreground">Students</TableHead>
                      <TableHead className="text-center text-xs font-semibold tracking-wider uppercase text-muted-foreground">Avg</TableHead>
                      <TableHead className="text-xs font-semibold tracking-wider uppercase text-muted-foreground">Status</TableHead>
                      <TableHead className="w-[96px] text-right pr-4 text-xs font-semibold tracking-wider uppercase text-muted-foreground">Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                      {filteredExams.map((exam) => (
                        <TableRow
                          key={`${exam.course_code}-${exam.session_name}-${exam.year}-${exam.month}-${exam.semester}`}
                          onClick={() => handleSelectExam(exam)}
                          className={`group cursor-pointer h-14 border-b last:border-0 transition-colors ${exam.analyzed ? "border-l-2 border-l-emerald-500/40 hover:bg-emerald-500/[0.03]" : "border-l-2 border-l-amber-500/60 hover:bg-amber-500/[0.04] bg-amber-500/[0.015]"}`}
                        >
                          <TableCell className="py-3">
                            <div className="flex items-center gap-2.5">
                              <div className={`size-7 rounded-md flex items-center justify-center shrink-0 ${exam.analyzed ? "bg-emerald-500/10 text-emerald-700" : "bg-amber-500/10 text-amber-700"}`}>
                                <BarChart3 className="size-3.5" />
                              </div>
                              <div className="min-w-0">
                                <div className="text-sm font-semibold leading-none truncate">{exam.course_code}</div>
                                <div className="text-xs text-muted-foreground truncate max-w-[180px]">{exam.subject_name}</div>
                              </div>
                            </div>
                          </TableCell>
                          <TableCell className="py-3 max-w-[200px]">
                            <div className="text-sm truncate" title={exam.session_name}>{exam.session_name}</div>
                          </TableCell>
                          <TableCell className="py-3">
                            <div className="flex items-center gap-1.5 text-xs">
                              <span className="tabular-nums font-medium">{exam.year}</span>
                              <span className="text-muted-foreground/40">·</span>
                              <span className="text-muted-foreground">M{exam.month}</span>
                              <span className="text-muted-foreground/40">·</span>
                              <span className="text-muted-foreground">S{exam.semester}</span>
                            </div>
                            <div className="text-xs text-muted-foreground">{exam.question_count} Q · {exam.total_marks} marks</div>
                          </TableCell>
                          <TableCell className="py-3 text-center">
                            <span className="inline-flex items-center gap-1 text-sm tabular-nums font-medium">
                              <Users className="size-3 text-muted-foreground" /> {exam.student_count ?? "Unavailable"}
                            </span>
                          </TableCell>
                          <TableCell className="py-3 text-center">
                            <ExamInventoryScore exam={exam} />
                          </TableCell>
                          <TableCell className="py-3">
                            {exam.analyzed ? (
                              <div className="space-y-0.5">
                                <Badge className="bg-emerald-500/10 text-emerald-700 border border-emerald-500/20 text-xs gap-1 font-medium px-1.5 py-0">
                                  <CheckCircle2 className="size-3" /> Analyzed
                                </Badge>
                                {exam.analyzed_at && (
                                  <div className="text-xs text-muted-foreground tabular-nums">{new Date(exam.analyzed_at).toLocaleDateString()}</div>
                                )}
                              </div>
                            ) : (
                              <div className="space-y-0.5">
                                <Badge variant="outline" className="bg-amber-500/10 text-amber-700 border-amber-500/20 text-xs gap-1 font-medium px-1.5 py-0">
                                  <Clock className="size-3" /> Pending
                                </Badge>
                                <div className="text-xs text-amber-700/70">Not yet analyzed</div>
                              </div>
                            )}
                          </TableCell>
                          <TableCell className="py-3 text-right pr-4">
                            <div className="flex items-center justify-end gap-1">
                              <span className={`hidden sm:inline-flex items-center gap-1 text-xs font-medium ${exam.analyzed ? "text-emerald-700 group-hover:text-emerald-800" : "text-amber-700 group-hover:text-amber-800"}`}>
                                {exam.analyzed ? "View" : "Analyze"} <ArrowUpRight className="size-3" />
                              </span>
                              <ChevronRight className="size-4 text-muted-foreground group-hover:text-foreground transition-colors" />
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                  </TableBody>
                </Table>
              </div>
              {filteredExams.length === 0 && (
                <div className="p-10 text-center border-t bg-muted/20">
                  <Search className="size-8 mx-auto text-muted-foreground/30 mb-2" />
                  <p className="text-sm font-medium">No exams match filters</p>
                  <p className="text-xs text-muted-foreground mt-1">Try clearing filters or searching differently.</p>
                  <Button variant="outline" size="sm" className="mt-3" onClick={clearFilters}>Clear filters</Button>
                </div>
              )}
            </Card>
            <div className="flex items-center justify-between text-xs text-muted-foreground px-1">
              <span>{filteredExams.length} exam{filteredExams.length !== 1 ? "s" : ""} • Scroll horizontally on small screens</span>
              <span className="hidden sm:inline">Analyzed rows have a green accent · Pending rows amber</span>
            </div>
          </>
        )}
      </div>
    );
  }

  // Analytics View — premium staggered sections
  return (
    <div className="p-6 md:p-8 space-y-6">
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-2">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <BarChart3 className="size-4" /> Analytics
          <ChevronRight className="size-4" /> {selectedExam.course_code}
          <Button variant="ghost" size="sm" className="ml-auto" onClick={() => { setSearchParams({}); setSelectedExam(null); }}>Back</Button>
        </div>
        <div className="flex items-center justify-between">
          <div>
            <h2 className="tracking-tight text-foreground bg-gradient-to-r from-foreground via-foreground to-foreground/60 bg-clip-text">{selectedExam.subject_name}</h2>
            <p className="text-sm text-muted-foreground mt-1">{selectedExam.session_name} · {selectedExam.year} {analytics ? `· Generated ${new Date(analytics.generated_at).toLocaleString()}` : ""}</p>
            {analytics && (analytics as any).unclassified_coverage && (
              <p className="text-xs text-amber-700 mt-1">Topic assignment pending: {analytics.unclassified_coverage.attempt_count} attempts at {analytics.unclassified_coverage.average_percentage}% — open a question below to review its topic</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setPaperOpen(true)}>
              <FileText className="h-4 w-4 mr-1" /> View question paper
            </Button>
            <Button variant="outline" size="sm" onClick={() => selectedExam && handleSelectExam(selectedExam, { forceReanalyse: true })} disabled={loadingAnalytics} title="Recompute analytics for this exam (ignores cache)">
              {loadingAnalytics ? <BrandOrb state="solving" size={20} aria-label="Reanalysing exam" /> : <Loader2 className="h-4 w-4 mr-1" />} Reanalyse
            </Button>

          </div>
        </div>
      </motion.div>

      {studentListError ? <p role="alert" className="text-sm text-destructive">{studentListError}</p>
        : !loadingStudents && <GradingOverview students={students} />}
      {!!analytics?.excluded_submissions?.length && <div role="alert" className="rounded-md border border-amber-300 p-3 text-sm">
        <p className="font-medium">Some essay results were excluded from analytics because their grading evidence needs review.</p>
        <ul className="list-disc pl-5">{analytics.excluded_submissions.map((item, i) => <li key={i}>{item.student_id}: {item.reason}</li>)}</ul>
      </div>}
      {analytics?.snapshot_status === "stale" && <p role="alert" className="rounded-md border border-amber-300 p-3 text-sm">{analytics.refresh_warning}</p>}

      {loadingAnalytics ? (
        <AnalysisLoader
          key={(handleSelectExam as any)._lastRequestId}
          complete={analytics !== null}
          onComplete={finishAnalyticsLoading}
        />
      ) : analytics ? (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.4 }} className="space-y-6">
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
            <h3 className="mb-2 text-sm font-semibold">Essay analytics · {analytics.statistics.total_students} graded submissions</h3>
            <KpiCards statistics={analytics.statistics} />
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}>
            <h3 className="mb-2 text-sm font-semibold">Essay score distribution</h3>
            <div className="rounded-xl border bg-card/50 backdrop-blur p-1"><DistributionHistogram statistics={analytics.statistics} /></div>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12 }} className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="rounded-xl border bg-card/50 backdrop-blur p-1"><CanonicalTopicTable topics={analytics.canonical_topic_performance} onSelectTopic={setSelectedTopic} /></div>
            <div className="rounded-xl border bg-card/50 backdrop-blur p-1"><AttentionAreasPanel areas={analytics.canonical_attention_areas} /></div>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.18 }} className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="rounded-xl border bg-card/50 backdrop-blur p-1"><BloomChart bloomPerformance={analytics.bloom_performance} /></div>
            <div className="rounded-xl border bg-card/50 backdrop-blur p-1"><QuestionPerformanceTable questions={analytics.question_performance} onSelectQuestion={setSelectedQuestion} /></div>
          </motion.div>

          {analytics.topic_bloom_matrix && analytics.topic_bloom_matrix.length > 0 && (
            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.20 }}>
              <div className="rounded-xl border bg-card/50 backdrop-blur p-1"><TopicBloomHeatmap topic_bloom_matrix={analytics.topic_bloom_matrix} /></div>
            </motion.div>
          )}

          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.24 }}>
            <InsightsPanel insights={analytics.canonical_insights} />
          </motion.div>

          {analytics.diagram_analysis && (
            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.26 }}>
              <div className="rounded-xl border bg-card/50 backdrop-blur p-1">
                <div className="px-4 pt-4 pb-2">
                  <div className="flex items-center gap-2">
                    <div className="size-8 rounded-lg bg-violet-500/10 text-violet-600 flex items-center justify-center">
                      <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold">Diagram Analysis</h3>
                      <p className="text-xs text-muted-foreground">Rubric-based evaluation of diagram submissions</p>
                    </div>
                  </div>
                </div>
                <DiagramAnalysisPanel diagramAnalysis={analytics.diagram_analysis} />
              </div>
            </motion.div>
          )}

          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.30 }}>
            <TeachingActions actions={teachingActions} loading={loadingActions} />
          </motion.div>
        </motion.div>
      ) : null}

      {/* ——— Lecturer Individual Student Finder (search + detail, no AI tips) ——— */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.34 }}>
        <Card className="overflow-hidden border-border bg-card/80 backdrop-blur">
          <div className="p-4 border-b flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <div className="size-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center">
                <UserSearch className="size-4" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-semibold leading-none">Individual Students</h3>
                <p className="text-xs text-muted-foreground mt-1">Search by student ID, view raw performance — AI improvement tips are hidden for lecturer view.</p>
              </div>
              <Badge variant="secondary" className="shrink-0 tabular-nums">
                <Users className="size-3 mr-1" /> {students.length} students
              </Badge>
            </div>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
              <Input
                placeholder="Search student ID… e.g. S001"
                value={studentSearch}
                onChange={(e) => setStudentSearch(e.target.value)}
                className="pl-9 h-9 bg-background"
                disabled={loadingStudents}
              />
            </div>
          </div>

          {loadingStudents ? (
            <div className="p-8 flex items-center justify-center gap-2 text-sm text-muted-foreground">
              <BrandOrb state="searching" size={20} aria-label="Loading students" /> Loading students…
            </div>
          ) : studentListError ? (
            <p role="alert" className="p-4 text-sm text-destructive">{studentListError}</p>
          ) : students.length === 0 ? (
            <div className="p-8 text-center">
              <GraduationCap className="size-8 mx-auto text-muted-foreground/30" />
              <p className="text-sm font-medium mt-2">No students found for this exam</p>
              <p className="text-xs text-muted-foreground mt-1">Students appear after submissions are graded.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/40 hover:bg-muted/40">
                    <TableHead className="text-xs uppercase tracking-wider font-semibold text-muted-foreground">Student</TableHead>
                    <TableHead className="text-center text-xs uppercase tracking-wider font-semibold text-muted-foreground">Essay</TableHead>
                    <TableHead className="text-center text-xs uppercase tracking-wider font-semibold text-muted-foreground">Diagram</TableHead>
                    <TableHead className="text-center text-xs uppercase tracking-wider font-semibold text-muted-foreground">Overall</TableHead>
                    <TableHead className="text-xs uppercase tracking-wider font-semibold text-muted-foreground">Grading status</TableHead>
                    <TableHead className="text-xs uppercase tracking-wider font-semibold text-muted-foreground">Analyzed</TableHead>
                    <TableHead className="w-[88px] text-right pr-4 text-xs uppercase tracking-wider font-semibold text-muted-foreground">View</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {students
                    .filter((s) => !studentSearch.trim() || s.student_id.toLowerCase().includes(studentSearch.trim().toLowerCase()))
                    .map((s) => {
                      const canView = canViewStudent(s);
                      return (
                      <TableRow key={s.student_id} aria-disabled={!canView} tabIndex={canView ? 0 : undefined}
                        onClick={canView ? () => handleSelectStudent(s.student_id) : undefined}
                        onKeyDown={canView ? e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); void handleSelectStudent(s.student_id); } } : undefined}
                        className={`group h-12 ${canView ? "cursor-pointer hover:bg-muted/50" : "text-muted-foreground"}`}>
                        <TableCell className="py-2">
                          <div className="flex items-center gap-2">
                            <div className="size-7 rounded-md bg-primary/10 text-primary flex items-center justify-center shrink-0">
                              <User className="size-4" />
                            </div>
                            <span className="text-sm font-medium font-mono">{s.student_id}</span>
                          </div>
                        </TableCell>
                        <StudentGradingCells student={s} />
                        <TableCell className="py-2">
                          {s.analysis_status === "generated" ? (
                            <span className="inline-flex items-center gap-1 text-xs text-emerald-700"><CheckCircle2 className="size-3" /> Ready</span>
                          ) : s.analysis_status === "diagram_only" ? (
                            <span className="inline-flex items-center gap-1 text-xs text-amber-700"><Eye className="size-3" /> Diagram only</span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-xs text-amber-700"><Clock className="size-3" /> Pending</span>
                          )}
                        </TableCell>
                        <TableCell className="py-2 text-right pr-4">
                          {!canView ? <span className="text-xs text-muted-foreground">Awaiting grades</span> : loadingStudentDetail && selectedStudentId === s.student_id ? (
                            <span className="inline-flex items-center gap-1.5 text-xs font-medium text-primary">
                              <BrandOrb state="solving" size={20} aria-label="Analysing student" />
                              <span>{s.analysis_status === "generated" ? "Loading…" : "Analyzing…"}</span>
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-xs font-medium text-primary group-hover:underline">
                              <Eye className="size-3" /> View <ChevronRight className="size-3" />
                            </span>
                          )}
                        </TableCell>
                      </TableRow>
                    ); })}
                </TableBody>
              </Table>
              {students.filter((s) => !studentSearch.trim() || s.student_id.toLowerCase().includes(studentSearch.trim().toLowerCase())).length === 0 && (
                <div className="p-6 text-center text-sm text-muted-foreground border-t">
                  No students match “{studentSearch}”
                </div>
              )}
            </div>
          )}
          <div className="px-4 py-2 bg-muted/20 border-t text-xs text-muted-foreground flex items-center justify-between">
            <span>Click a row to see question, topic and Bloom breakdown (no AI tips)</span>
            <span className="hidden sm:inline">{students.filter((s) => !studentSearch.trim() || s.student_id.toLowerCase().includes(studentSearch.trim().toLowerCase())).length} shown</span>
          </div>
        </Card>
      </motion.div>

      <TopicDetailModal topic={selectedTopic} open={!!selectedTopic} onClose={() => setSelectedTopic(null)} />
      <ExamPaperModal exam={selectedExam} open={paperOpen} onClose={() => setPaperOpen(false)} />
      <QuestionDetailModal
        key={`${selectedExam?.course_code}-${selectedExam?.session_name}-${selectedExam?.year}-${selectedExam?.month}-${selectedExam?.semester}-${selectedQuestion?.question_no}`}
        question={selectedQuestion}
        exam={selectedExam}
        open={!!selectedQuestion}
        onClose={() => setSelectedQuestion(null)}
        onTopicSaved={() => { if (selectedExam) void handleSelectExam(selectedExam, { forceReanalyse: true }); }}
      />
    </div>
  );
}

