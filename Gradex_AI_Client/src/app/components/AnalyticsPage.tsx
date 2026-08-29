import React, { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowLeft, Download, FileText, BarChart3, Users, ChevronRight, Sparkles, CheckCircle2, Clock, Search, SlidersHorizontal, ArrowUpRight, UserSearch, Eye, AlertCircle, Loader2, GraduationCap, BookOpen, Brain, Award, User } from "lucide-react";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import { Input } from "./ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "./ui/dialog";
import { ProgressLoader, type LoadStep } from "./ProgressLoader";
import { AIPageBanner } from "./AIBrand";
import {
  fetchExams,
  fetchExamAnalytics,
  fetchExamAnalyticsStream,
  fetchTeachingActions,
  fetchExamStudents,
  fetchLecturerStudentDetail,
  fetchLecturerStudentDetailStream,
  type ExamListItem,
  type ExamAnalytics,
  type CanonicalTopic,
  type TeachingAction,
  type StudentRow,
  type LecturerStudentDetail,
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
import { DiagramAnalysisPanel } from "./analytics/DiagramAnalysisPanel";
import { TopicDetailModal } from "./analytics/TopicDetailModal";
import { QuestionDetailModal } from "./analytics/QuestionDetailModal";

function PremiumLoader({
  steps,
  currentStep,
  liveMessage,
}: {
  steps: LoadStep[];
  currentStep: number;
  liveMessage?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 space-y-6">
      <motion.div
        animate={{ rotate: 360 }}
        transition={{ duration: 1.2, repeat: Infinity, ease: "linear" }}
        className="size-10 rounded-full border-2 border-primary/20 border-t-primary"
      />
      <div className="space-y-2 text-center max-w-xl">
        <motion.p
          key={currentStep}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-sm font-medium"
        >
          {steps[currentStep]?.label || "Loading..."}
        </motion.p>
        {liveMessage && (
          <motion.p
            key={liveMessage}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-xs text-muted-foreground font-mono bg-muted/50 rounded-lg px-3 py-2 border"
          >
            {liveMessage}
          </motion.p>
        )}
        <div className="flex gap-1.5 justify-center">
          {steps.map((_, i) => (
            <motion.div
              key={i}
              className={`h-1.5 rounded-full ${i === currentStep ? "bg-primary w-6" : i < currentStep ? "bg-primary/60 w-1.5" : "bg-muted w-1.5"}`}
              animate={{ scale: i === currentStep ? 1.2 : 1 }}
              transition={{ duration: 0.3 }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

export default function AnalyticsPage() {
  const [exams, setExams] = useState<ExamListItem[]>([]);
  const [selectedExam, setSelectedExam] = useState<ExamListItem | null>(null);
  const [analytics, setAnalytics] = useState<ExamAnalytics | null>(null);
  const [teachingActions, setTeachingActions] = useState<TeachingAction[]>([]);
  const [loadingExams, setLoadingExams] = useState(true);
  const [loadingAnalytics, setLoadingAnalytics] = useState(false);
  const [loadingActions, setLoadingActions] = useState(false);
  const [loadSteps, setLoadSteps] = useState<LoadStep[]>([]);
  const [currentLoadStep, setCurrentLoadStep] = useState(0);
  const [liveModelMessage, setLiveModelMessage] = useState<string>("PULSE·AI — Initializing...");
  const [selectedTopic, setSelectedTopic] = useState<CanonicalTopic | null>(null);
  const [selectedQuestion, setSelectedQuestion] = useState<any>(null);
  // dense table filters
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "analyzed" | "pending">("all");
  const [yearFilter, setYearFilter] = useState<string>("all");
  const [semesterFilter, setSemesterFilter] = useState<string>("all");
  // lecturer student finder (inside analyzed exam)
  const [students, setStudents] = useState<StudentRow[]>([]);
  const [loadingStudents, setLoadingStudents] = useState(false);
  const [studentSearch, setStudentSearch] = useState("");
  const [selectedStudentId, setSelectedStudentId] = useState<string | null>(null);
  const [studentDetail, setStudentDetail] = useState<LecturerStudentDetail | null>(null);
  const [loadingStudentDetail, setLoadingStudentDetail] = useState(false);
  const [studentDetailError, setStudentDetailError] = useState<string | null>(null);

  useEffect(() => {
    setLoadSteps([{ label: "Fetching exams..." }]);
    setCurrentLoadStep(0);
    fetchExams().then((data) => { setExams(data); setLoadingExams(false); }).catch(console.error);
  }, []);

  const handleSelectExam = useCallback(async (exam: ExamListItem) => {
    setSelectedExam(exam);
    setLoadingAnalytics(true);
    setAnalytics(null);
    setLiveModelMessage("PULSE·AI — Starting analysis...");
    // reset student finder
    setStudents([]);
    setStudentSearch("");
    setSelectedStudentId(null);
    setStudentDetail(null);
    setStudentDetailError(null);

    const steps: LoadStep[] = [
      { label: "PULSE·AI — Ingesting submissions..." },
      { label: "PULSE·AI — Checking Bloom levels & classifying topics..." },
      { label: "PULSE·AI — Computing statistics & insights..." },
    ];
    setLoadSteps(steps);
    setCurrentLoadStep(0);

    try {
      setCurrentLoadStep(0);
      setLiveModelMessage("PULSE·AI — Connecting to model...");
      // Try streaming for real-time Bloom/topic messages, fallback to plain fetch
      let data: ExamAnalytics;
      try {
        data = await fetchExamAnalyticsStream(
          exam.course_code,
          exam.session_name,
          exam.year,
          exam.month,
          exam.semester,
          (msg) => {
            setLiveModelMessage(msg);
            // Advance loader step based on message content
            if (msg.includes("Ingesting") || msg.includes("Analyzing student")) setCurrentLoadStep(0);
            else if (msg.includes("Bloom") || msg.includes("Topic") || msg.includes("Q")) setCurrentLoadStep(1);
            else if (msg.includes("Computing") || msg.includes("weak") || msg.includes("Finalizing") || msg.includes("Saving")) setCurrentLoadStep(2);
          },
        );
      } catch {
        setLiveModelMessage("PULSE·AI — Streaming unavailable, loading...");
        data = await fetchExamAnalytics(exam.course_code, exam.session_name, exam.year, exam.month, exam.semester);
      }
      setAnalytics(data);
      setLiveModelMessage("PULSE·AI — Analysis complete");
      setCurrentLoadStep(2);

      setLoadingActions(true);
      fetchTeachingActions(exam.course_code, exam.session_name, exam.year, exam.month, exam.semester)
        .then(setTeachingActions)
        .catch(() => setTeachingActions([]))
        .finally(() => setLoadingActions(false));

      // Also fetch students for this exam (for lecturer student finder)
      setLoadingStudents(true);
      fetchExamStudents(exam.course_code, exam.session_name, exam.year, exam.month, exam.semester)
        .then(setStudents)
        .catch(() => setStudents([]))
        .finally(() => setLoadingStudents(false));
    } catch (err) {
      console.error(err);
      setLiveModelMessage("PULSE·AI — Analysis failed");
    } finally {
      setLoadingAnalytics(false);
    }
  }, []);

  const handleSelectStudent = useCallback(async (studentId: string) => {
    if (!selectedExam) return;
    setSelectedStudentId(studentId);
    setLoadingStudentDetail(true);
    setStudentDetail(null);
    setStudentDetailError(null);
    const dispatchTopbar = (active: boolean, message?: string, progress?: number) => {
      window.dispatchEvent(new CustomEvent("topbar-student-analysis", { detail: { active, studentId, message: message || "", progress } }));
    };
    dispatchTopbar(true, `PULSE·AI — Starting analysis for ${studentId}…`, 0);
    try {
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
          (msg, prog) => {
            dispatchTopbar(true, msg, prog);
          },
          false
        );
      } catch {
        dispatchTopbar(true, `PULSE·AI — Analyzing ${studentId}…`, 45);
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
      setStudentDetail(detail);
      dispatchTopbar(true, `PULSE·AI — ${studentId} analysis complete`, 100);
      // Update row status optimistically
      setStudents((prev) => prev.map((r) => r.student_id === studentId ? { ...r, analysis_status: "generated" } : r));
      setTimeout(() => dispatchTopbar(false), 2500);
    } catch (e) {
      setStudentDetailError(e instanceof Error ? e.message : "Failed to load student detail");
      dispatchTopbar(true, `Analysis failed for ${studentId}`, 0);
      setTimeout(() => dispatchTopbar(false), 3000);
    } finally {
      setLoadingStudentDetail(false);
    }
  }, [selectedExam]);

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
          <PremiumLoader steps={loadSteps} currentStep={currentLoadStep} />
        ) : exams.length === 0 ? (
          <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }}>
            <Card className="p-12 text-center border-border bg-gradient-to-b from-card to-muted/20">
              <BarChart3 className="h-12 w-12 mx-auto mb-4 text-muted-foreground/40" />
              <p className="text-muted-foreground">No exams found</p>
              <p className="text-xs text-muted-foreground mt-1">Exams appear once a rubric is created and submissions are graded.</p>
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
                              <Users className="size-3 text-muted-foreground" /> {exam.student_count}
                            </span>
                          </TableCell>
                          <TableCell className="py-3 text-center">
                            <div className="flex flex-col items-center gap-1">
                              <span className={`text-sm font-semibold tabular-nums ${exam.average_percentage >= 50 ? "text-emerald-700" : "text-amber-700"}`}>{exam.average_percentage.toFixed(1)}%</span>
                              <div className="hidden sm:block h-1 w-12 bg-muted rounded-full overflow-hidden">
                                <div className={`h-full rounded-full ${exam.average_percentage >= 50 ? "bg-emerald-500" : "bg-amber-500"}`} style={{ width: `${Math.min(exam.average_percentage, 100)}%` }} />
                              </div>
                            </div>
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
          <Button variant="ghost" size="sm" className="ml-auto" onClick={() => setSelectedExam(null)}>Back</Button>
        </div>
        <div className="flex items-center justify-between">
          <div>
            <h2 className="tracking-tight text-foreground bg-gradient-to-r from-foreground via-foreground to-foreground/60 bg-clip-text">{selectedExam.subject_name}</h2>
            <p className="text-sm text-muted-foreground mt-1">{selectedExam.session_name} · {selectedExam.year}</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" disabled title="Coming soon" className="backdrop-blur">
              <Download className="h-4 w-4 mr-1" /> Export
            </Button>
            <Button variant="outline" size="sm" disabled title="Coming soon" className="backdrop-blur">
              <FileText className="h-4 w-4 mr-1" /> Report
            </Button>
          </div>
        </div>
      </motion.div>

      {loadingAnalytics ? (
        <PremiumLoader steps={loadSteps} currentStep={currentLoadStep} liveMessage={liveModelMessage} />
      ) : analytics ? (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.4 }} className="space-y-6">
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
            <KpiCards statistics={analytics.statistics} />
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}>
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
                disabled={loadingStudents || !analytics}
              />
            </div>
          </div>

          {loadingStudents ? (
            <div className="p-8 flex items-center justify-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" /> Loading students…
            </div>
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
                    <TableHead className="text-center text-xs uppercase tracking-wider font-semibold text-muted-foreground">Score</TableHead>
                    <TableHead className="text-center text-xs uppercase tracking-wider font-semibold text-muted-foreground">%</TableHead>
                    <TableHead className="text-xs uppercase tracking-wider font-semibold text-muted-foreground">Status</TableHead>
                    <TableHead className="text-xs uppercase tracking-wider font-semibold text-muted-foreground">Analyzed</TableHead>
                    <TableHead className="w-[88px] text-right pr-4 text-xs uppercase tracking-wider font-semibold text-muted-foreground">View</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {students
                    .filter((s) => !studentSearch.trim() || s.student_id.toLowerCase().includes(studentSearch.trim().toLowerCase()))
                    .map((s) => (
                      <TableRow key={s.student_id} onClick={() => handleSelectStudent(s.student_id)} className="group cursor-pointer h-12 hover:bg-muted/50">
                        <TableCell className="py-2">
                          <div className="flex items-center gap-2">
                            <div className="size-7 rounded-md bg-primary/10 text-primary flex items-center justify-center shrink-0">
                              <User className="size-4" />
                            </div>
                            <span className="text-sm font-medium font-mono">{s.student_id}</span>
                          </div>
                        </TableCell>
                        <TableCell className="py-2 text-center text-sm tabular-nums">
                          {s.score.obtained.toFixed(1)} / {s.score.maximum.toFixed(1)}
                        </TableCell>
                        <TableCell className="py-2 text-center">
                          <Badge variant="outline" className={`text-xs tabular-nums ${s.score.percentage >= 50 ? "bg-emerald-500/10 text-emerald-700 border-emerald-500/20" : "bg-amber-500/10 text-amber-700 border-amber-500/20"}`}>
                            {s.score.percentage.toFixed(1)}%
                          </Badge>
                        </TableCell>
                        <TableCell className="py-2">
                          <Badge variant="outline" className="text-xs">{s.status}</Badge>
                        </TableCell>
                        <TableCell className="py-2">
                          {s.analysis_status === "generated" ? (
                            <span className="inline-flex items-center gap-1 text-xs text-emerald-700"><CheckCircle2 className="size-3" /> Ready</span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-xs text-amber-700"><Clock className="size-3" /> Pending</span>
                          )}
                        </TableCell>
                        <TableCell className="py-2 text-right pr-4">
                          {loadingStudentDetail && selectedStudentId === s.student_id ? (
                            <span className="inline-flex items-center gap-1.5 text-xs font-medium text-primary">
                              <Loader2 className="size-3 animate-spin" />
                              <span className="animate-pulse">Analyzing…</span>
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-xs font-medium text-primary group-hover:underline">
                              <Eye className="size-3" /> View <ChevronRight className="size-3" />
                            </span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
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

      {/* Student detail dialog — excludes AI tips */}
      <Dialog open={!!selectedStudentId} onOpenChange={(open) => { if (!open) { setSelectedStudentId(null); setStudentDetail(null); setStudentDetailError(null); }}}>
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <GraduationCap className="size-5 text-primary" />
              {selectedStudentId ?? "Student"} — Performance
              <Badge variant="outline" className="ml-1 text-xs font-normal">Lecturer view · no AI tips</Badge>
            </DialogTitle>
            <DialogDescription>
              {selectedExam?.course_code} · {selectedExam?.session_name} · {selectedExam?.year} — raw scores, topics and Bloom levels only.
            </DialogDescription>
          </DialogHeader>

          {loadingStudentDetail ? (
            <div className="py-10 flex flex-col items-center gap-3">
              <Loader2 className="size-6 animate-spin text-primary" />
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
                        <TableRow key={q.question_id} className="h-10">
                          <TableCell className="font-medium text-xs">{q.question_no}</TableCell>
                          <TableCell className="text-xs max-w-[160px] truncate" title={q.topic}>{q.topic}<span className="text-muted-foreground"> · {q.subtopic}</span></TableCell>
                          <TableCell className="text-xs"><Badge variant="outline" className="text-xs">{q.bloom_analysis.level}</Badge></TableCell>
                          <TableCell className="text-xs text-right tabular-nums">{q.performance.score.toFixed(1)} / {q.performance.max_score.toFixed(1)}</TableCell>
                          <TableCell className="text-xs text-right tabular-nums">{q.performance.percentage.toFixed(1)}%</TableCell>
                        </TableRow>
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

              <div className="text-xs text-muted-foreground text-center">Generated {new Date(studentDetail.generated_at).toLocaleString()} · {studentDetail.model_metadata.bloom_model} ({studentDetail.model_metadata.grading_source})</div>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>

      <TopicDetailModal topic={selectedTopic} open={!!selectedTopic} onClose={() => setSelectedTopic(null)} />
      <QuestionDetailModal question={selectedQuestion} open={!!selectedQuestion} onClose={() => setSelectedQuestion(null)} />
    </div>
  );
}

