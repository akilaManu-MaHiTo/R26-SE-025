import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { TrendingUp, Award, BookOpen, Target, Brain, ChevronRight, AlertCircle, CheckCircle2, Clock } from "lucide-react";
import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { ProgressLoader, type LoadStep } from "./ProgressLoader";
import { fetchStudentDashboard, fetchStudentExams, fetchStudentProfile, type StudentAnalytics, type StudentExam } from "../api/studentApi";

const statusTone: Record<string, string> = {
  Strong: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300 border-emerald-200",
  Developing: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300 border-amber-200",
  "Needs Improvement": "bg-orange-100 text-orange-800 dark:bg-orange-500/15 dark:text-orange-300 border-orange-200",
  Critical: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300 border-red-200",
};

const priorityTone: Record<string, string> = {
  Critical: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
  High: "bg-orange-100 text-orange-800 dark:bg-orange-500/15 dark:text-orange-300",
  Medium: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  Low: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
};

function initialsFor(studentId: string) {
  const clean = studentId.replace(/[^A-Za-z0-9]/g, "");
  return clean.slice(0, 2).toUpperCase() || "ST";
}

export function StudentDashboard({ studentId }: { studentId: string }) {
  const [profile, setProfile] = useState<{ email: string; examCount: number } | null>(null);
  const [exams, setExams] = useState<StudentExam[]>([]);
  const [selectedExam, setSelectedExam] = useState<StudentExam | null>(null);
  const [analytics, setAnalytics] = useState<StudentAnalytics | null>(null);
  const [loadingExams, setLoadingExams] = useState(true);
  const [loadingAnalytics, setLoadingAnalytics] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadSteps] = useState<LoadStep[]>([
    { label: "Fetching your profile..." },
    { label: "Analyzing your submissions in background..." },
    { label: "Generating personalized insights..." },
  ]);
  const [currentStep, setCurrentStep] = useState(0);

  // Fetch profile + exam list on mount / studentId change
  useEffect(() => {
    let cancelled = false;
    setLoadingExams(true);
    setError(null);
    setCurrentStep(0);
    fetchStudentProfile(studentId)
      .then((p) => {
        if (cancelled) return;
        setProfile({ email: p.email, examCount: p.exam_count });
        setExams(p.exams);
        if (p.exams.length > 0) {
          // Prefer most recent *analyzed* exam; backend now returns analyzed flag sorted by year desc
          const sorted = [...p.exams].sort((a, b) => b.year - a.year || b.month - a.month || (b.semester ?? 0) - (a.semester ?? 0));
          const analyzedSorted = sorted.filter((e) => e.analyzed);
          // If lecture analyzed 2023/5/1, that will be first; don't fallback to 2022 if 2023 is analyzed
          const pick = analyzedSorted.length > 0 ? analyzedSorted[0] : sorted[0];
          // If the most recent is not analyzed but an older one is, still pick the analyzed one? No — show wait for the most recent
          // The spec: check analyzedExams, if lecturer didn't analyze say wait. So if top is not analyzed, don't auto-fallback to older analyzed
          const mostRecent = sorted[0];
          if (mostRecent && mostRecent.analyzed === false) {
            // Still select it so the 423 wait message is shown, rather than silently showing 2022
            setSelectedExam(mostRecent);
          } else {
            setSelectedExam(pick);
          }
        }
      })
      .catch(async () => {
        // fallback: try exams directly
        try {
          const list = await fetchStudentExams(studentId);
          if (cancelled) return;
          setExams(list);
          if (list.length > 0) {
            const sorted = [...list].sort((a, b) => b.year - a.year || b.month - a.month || (b.semester ?? 0) - (a.semester ?? 0));
            const analyzedSorted = sorted.filter((e) => e.analyzed);
            const pick = analyzedSorted.length > 0 ? analyzedSorted[0] : sorted[0];
            const mostRecent = sorted[0];
            setSelectedExam(mostRecent && mostRecent.analyzed === false ? mostRecent : pick);
          }
          setProfile({ email: `${studentId.toLowerCase()}@my.sliit.lk`, examCount: list.length });
        } catch (e) {
          if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load profile");
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingExams(false);
      });
    return () => {
      cancelled = true;
    };
  }, [studentId]);

  // Fetch analytics when exam selected — this triggers background generation on first access (ensure_student_analytics)
  useEffect(() => {
    if (!selectedExam) return;
    // If backend says not yet analyzed, show wait message immediately without hitting dashboard (which would 423)
    if (selectedExam.analyzed === false) {
      setAnalytics(null);
      setError("Wait for lecture to analyze your data — this exam has not been analyzed yet");
      setLoadingAnalytics(false);
      return;
    }
    let cancelled = false;
    setLoadingAnalytics(true);
    setAnalytics(null);
    setError(null);
    setCurrentStep(1);
    // simulate staged progress
    const t1 = setTimeout(() => !cancelled && setCurrentStep(2), 800);
    fetchStudentDashboard(studentId, selectedExam.subject_code, selectedExam.session_name, selectedExam.year, selectedExam.month, selectedExam.semester)
      .then((data) => {
        if (cancelled) return;
        // Double-check year: backend should return matching year; if we got 2022 when requesting 2023, it's a bug — surface it
        if (data.year !== selectedExam.year || data.session_name !== selectedExam.session_name) {
          console.warn(`Dashboard year mismatch: requested ${selectedExam.year} got ${data.year}`);
        }
        setAnalytics(data);
        setCurrentStep(3);
      })
      .catch((e) => {
        if (!cancelled) {
          const msg = e instanceof Error ? e.message : "Failed to load dashboard";
          // Surface 423 as wait message
          if (msg.includes("Wait for lecture")) setError(msg);
          else setError(msg);
        }
      })
      .finally(() => {
        clearTimeout(t1);
        if (!cancelled) setLoadingAnalytics(false);
      });
    return () => {
      cancelled = true;
      clearTimeout(t1);
    };
  }, [studentId, selectedExam]);

  const overall = analytics?.overall_performance;
  const initials = initialsFor(studentId);

  return (
    <div className="p-6 md:p-8 space-y-6">
      {/* Profile header — real data, not dummy */}
      <Card className="p-6 md:p-8 border-border relative overflow-hidden">
        <div className="absolute -right-12 -top-12 size-56 rounded-full bg-primary/[0.04] blur-2xl" />
        <div className="relative flex items-center gap-5 flex-wrap">
          <div className="size-16 rounded-2xl bg-primary text-primary-foreground flex items-center justify-center text-xl tracking-tight font-medium shrink-0">
            {initials}
          </div>
          <div className="flex-1 min-w-[220px]">
            <div className="text-muted-foreground text-sm">Welcome back,</div>
            <h2 className="text-2xl tracking-tight mt-0.5">{studentId}</h2>
            <div className="text-sm text-muted-foreground mt-1 truncate">{profile?.email ?? `${studentId.toLowerCase()}@my.sliit.lk`}</div>
            {selectedExam && (
              <div className="text-xs text-muted-foreground mt-1">
                {selectedExam.subject_name} · {selectedExam.session_name} · {selectedExam.year}
              </div>
            )}
          </div>
          <div className="flex items-center gap-3">
            <div className="px-4 py-3 rounded-xl border border-border bg-card/60 text-center min-w-[90px]">
              <div className="text-lg tracking-tight tabular-nums font-medium">
                {loadingExams ? "—" : (profile?.examCount ?? exams.length)}
              </div>
              <div className="text-xs text-muted-foreground">Exams taken</div>
            </div>
            {overall && (
              <div className={`px-4 py-3 rounded-xl border text-center min-w-[110px] ${statusTone[overall.status] ?? "bg-muted"}`}>
                <div className="text-lg tracking-tight tabular-nums font-medium">{overall.percentage.toFixed(1)}%</div>
                <div className="text-xs opacity-80">{overall.status}</div>
              </div>
            )}
          </div>
        </div>
        {/* Data processing status bar — clearly shows background analysis */}
        {(loadingExams || loadingAnalytics) && (
          <div className="relative mt-6 rounded-xl border border-primary/20 bg-primary/5 p-4 flex items-center gap-3">
            <Clock className="size-5 text-primary animate-pulse shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-foreground">Your data is being processed in background</div>
              <div className="text-xs text-muted-foreground mt-0.5 truncate">
                {loadingExams ? "Fetching your exam list..." : `Analyzing ${selectedExam?.subject_code} ${selectedExam?.session_name} — generating Bloom, topic & teaching insights`}
              </div>
              <div className="h-1.5 bg-muted rounded-full overflow-hidden mt-2">
                <motion.div
                  className="h-full bg-primary rounded-full"
                  initial={{ width: 0 }}
                  animate={{ width: `${((currentStep + 1) / loadSteps.length) * 100}%` }}
                  transition={{ duration: 0.6 }}
                />
              </div>
            </div>
            <Badge variant="outline" className="shrink-0 bg-background">
              {Math.round(((currentStep + 1) / loadSteps.length) * 100)}%
            </Badge>
          </div>
        )}
      </Card>

      {/* Exam selector — shows analyzed vs pending, fixes 2022 vs 2023 */}
      {exams.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm text-muted-foreground">Exams:</span>
          {exams.map((ex) => {
            const key = `${ex.subject_code}@${ex.session_name}@${ex.year}-${ex.month}-${ex.semester}`;
            const active =
              selectedExam &&
              ex.subject_code === selectedExam.subject_code &&
              ex.session_name === selectedExam.session_name &&
              ex.year === selectedExam.year &&
              ex.month === selectedExam.month &&
              ex.semester === selectedExam.semester;
            return (
              <Button
                key={key}
                variant={active ? "default" : "outline"}
                size="sm"
                onClick={() => {
                  setSelectedExam(ex);
                  setError(null);
                }}
                className="text-xs relative"
                title={ex.analyzed ? `Analyzed ${ex.analyzed_at?.slice(0, 10) ?? ""}` : "Not yet analyzed by lecturer"}
              >
                {ex.subject_code} · {ex.session_name} ({ex.year})
                {ex.analyzed === false && <span className="ml-1.5 size-2 rounded-full bg-amber-500 inline-block" title="Pending lecture analysis" />}
                {ex.analyzed && <span className="ml-1.5 size-2 rounded-full bg-emerald-500 inline-block" title="Analyzed" />}
              </Button>
            );
          })}
        </div>
      )}

      {/* Error / Wait for lecture */}
      {error && !loadingAnalytics && !loadingExams && (
        <Card className={`p-6 border ${error.includes("Wait for lecture") ? "border-amber-200 bg-amber-50 dark:bg-amber-950/20" : "border-red-200 bg-red-50 dark:bg-red-950/20"}`}>
          <div className="flex gap-3">
            {error.includes("Wait for lecture") ? (
              <Clock className="size-5 text-amber-600 shrink-0 mt-0.5" />
            ) : (
              <AlertCircle className="size-5 text-red-600 shrink-0 mt-0.5" />
            )}
            <div>
              <div className={`text-sm font-medium ${error.includes("Wait for lecture") ? "text-amber-800 dark:text-amber-300" : "text-red-800 dark:text-red-300"}`}>
                {error.includes("Wait for lecture") ? "Waiting for lecturer analysis" : "Could not load your dashboard"}
              </div>
              <div className={`text-sm mt-1 ${error.includes("Wait for lecture") ? "text-amber-700 dark:text-amber-400" : "text-red-700 dark:text-red-400"}`}>{error}</div>
              <div className="text-xs text-muted-foreground mt-2">
                {error.includes("Wait for lecture")
                  ? `Your submission for ${selectedExam?.subject_code} ${selectedExam?.session_name} ${selectedExam?.year} is saved. Once your lecturer clicks Analyze for this exam, your personalized analytics will be generated in background and appear here.`
                  : `If you just completed an exam, ask your lecturer to analyze it — your account (${studentId.toLowerCase()}@my.sliit.lk / Student@123) is provisioned then and analytics is generated in background.`}
              </div>
            </div>
          </div>
        </Card>
      )}

      {!error && !loadingExams && exams.length === 0 && (
        <Card className="p-12 text-center">
          <BookOpen className="size-10 mx-auto text-muted-foreground/40" />
          <div className="mt-4 font-medium">No graded exams yet</div>
          <div className="text-sm text-muted-foreground mt-1 max-w-md mx-auto">
            Your submissions will appear here once your lecturer analyzes the exam. Your student account is created automatically as <span className="font-mono text-foreground">{studentId.toLowerCase()}@my.sliit.lk</span>.
          </div>
        </Card>
      )}

      {/* Loading analytics */}
      {loadingAnalytics && (
        <ProgressLoader steps={loadSteps} currentStep={currentStep} />
      )}

      {/* Real analytics content — replaces all dummy trend/grades/upcoming */}
      {!loadingAnalytics && analytics && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
          {/* Overall + model */}
          <div className="grid md:grid-cols-3 gap-4">
            <Card className="p-5">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Award className="size-4 text-primary" /> Overall
              </div>
              <div className="mt-3">
                <div className="text-3xl font-semibold tabular-nums">
                  {overall?.score.toFixed(1)} <span className="text-lg text-muted-foreground">/ {overall?.maximum.toFixed(1)}</span>
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <Badge className={`${statusTone[overall?.status ?? ""] ?? "bg-muted"} border`}>{overall?.status}</Badge>
                  <span className="text-sm tabular-nums text-muted-foreground">{overall?.percentage.toFixed(1)}%</span>
                </div>
                <div className="h-2 bg-muted rounded-full overflow-hidden mt-3">
                  <div className="h-full bg-primary rounded-full" style={{ width: `${overall?.percentage ?? 0}%` }} />
                </div>
                <div className="text-xs text-muted-foreground mt-2">
                  {analytics.subject_name} · {analytics.session_name} · {analytics.year}
                </div>
              </div>
            </Card>
            <Card className="p-5">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Target className="size-4 text-primary" /> Learning gaps
              </div>
              <div className="mt-3 space-y-2">
                {analytics.learning_analysis.learning_gaps.length === 0 ? (
                  <div className="text-sm text-muted-foreground flex items-center gap-1.5">
                    <CheckCircle2 className="size-4 text-emerald-600" /> No critical gaps
                  </div>
                ) : (
                  analytics.learning_analysis.learning_gaps.slice(0, 4).map((g, i) => (
                    <div key={i} className="flex items-center justify-between text-sm">
                      <span className="truncate">
                        {g.topic} — {g.subtopic}
                      </span>
                      <Badge className={`${priorityTone[g.priority] ?? "bg-muted"} border-0 text-xs ml-2 shrink-0`}>{g.priority}</Badge>
                    </div>
                  ))
                )}
                <div className="text-xs text-muted-foreground mt-2">
                  Strong: {analytics.learning_analysis.strong_topics.join(", ") || "—"} · Weak: {analytics.learning_analysis.weak_topics.join(", ") || "—"}
                </div>
              </div>
            </Card>
            <Card className="p-5">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Brain className="size-4 text-primary" /> Next steps
              </div>
              <div className="mt-3 space-y-1.5 text-sm">
                <div>
                  <span className="text-muted-foreground">Difficulty:</span> {analytics.next_question_strategy.recommended_difficulty}
                </div>
                <div>
                  <span className="text-muted-foreground">Bloom:</span> {analytics.next_question_strategy.recommended_bloom_levels.join(", ") || "—"}
                </div>
                <div>
                  <span className="text-muted-foreground">Topics:</span> {analytics.next_question_strategy.recommended_topics.join(", ") || "—"}
                </div>
                <div className="text-xs text-muted-foreground mt-2">
                  Model: {analytics.model_metadata.bloom_model} ({analytics.model_metadata.bloom_model_type}) · {analytics.generated_at.slice(0, 10)}
                </div>
              </div>
            </Card>
          </div>

          {/* Topic & Bloom */}
          <div className="grid lg:grid-cols-2 gap-6">
            <Card className="p-5">
              <div className="font-medium flex items-center gap-2">
                <TrendingUp className="size-4 text-primary" /> Topic performance
              </div>
              <div className="mt-4 space-y-3">
                {analytics.topic_performance.map((t) => (
                  <div key={t.topic} className="flex items-center gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="text-sm truncate">{t.topic}</div>
                      <div className="h-1.5 bg-muted rounded-full overflow-hidden mt-1">
                        <div className="h-full bg-primary rounded-full" style={{ width: `${t.percentage}%` }} />
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className="text-sm tabular-nums font-medium">{t.percentage.toFixed(1)}%</div>
                      <Badge className={`${statusTone[t.status] ?? "bg-muted"} border text-[10px] mt-1`}>{t.status}</Badge>
                    </div>
                  </div>
                ))}
                {analytics.topic_performance.length === 0 && <div className="text-sm text-muted-foreground">No topic data yet</div>}
              </div>
            </Card>
            <Card className="p-5">
              <div className="font-medium flex items-center gap-2">
                <Brain className="size-4 text-primary" /> Bloom performance
              </div>
              <div className="mt-4 space-y-3">
                {analytics.bloom_performance.map((b) => (
                  <div key={b.level} className="flex items-center gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="text-sm">{b.level}</div>
                      <div className="h-1.5 bg-muted rounded-full overflow-hidden mt-1">
                        <div className="h-full bg-primary rounded-full" style={{ width: `${b.average_score}%` }} />
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className="text-sm tabular-nums font-medium">{b.average_score.toFixed(1)}%</div>
                      <Badge className={`${statusTone[b.status] ?? "bg-muted"} border text-[10px] mt-1`}>{b.status}</Badge>
                    </div>
                  </div>
                ))}
                {analytics.bloom_performance.length === 0 && <div className="text-sm text-muted-foreground">No Bloom data yet</div>}
              </div>
            </Card>
          </div>

          {/* Question performance — grade and stuff */}
          <Card className="overflow-hidden">
            <div className="px-6 py-4 border-b border-border flex items-center justify-between">
              <div className="font-medium">Your grades by question</div>
              <Badge variant="outline">{analytics.question_performance.length} questions</Badge>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted/50 text-muted-foreground text-xs uppercase tracking-wide">
                  <tr>
                    <th className="text-left px-4 py-3 font-medium">Q</th>
                    <th className="text-left px-4 py-3 font-medium">Topic</th>
                    <th className="text-left px-4 py-3 font-medium">Bloom</th>
                    <th className="text-left px-4 py-3 font-medium">Score</th>
                    <th className="text-left px-4 py-3 font-medium">%</th>
                  </tr>
                </thead>
                <tbody>
                  {analytics.question_performance.map((q) => (
                    <tr key={q.question_id} className="border-t border-border hover:bg-muted/40">
                      <td className="px-4 py-3 font-medium">{q.question_no}</td>
                      <td className="px-4 py-3">
                        <div className="truncate max-w-[220px]">{q.topic}</div>
                        <div className="text-xs text-muted-foreground truncate max-w-[220px]">{q.subtopic}</div>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="outline" className="text-xs">
                          {q.bloom_analysis.level}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 tabular-nums">
                        {q.performance.score.toFixed(1)} / {q.performance.max_score.toFixed(1)}
                      </td>
                      <td className="px-4 py-3">
                        <Badge className={`${statusTone[q.performance.percentage >= 80 ? "Strong" : q.performance.percentage >= 60 ? "Developing" : q.performance.percentage >= 40 ? "Needs Improvement" : "Critical"] ?? "bg-muted"} border-0`}>
                          {q.performance.percentage.toFixed(1)}%
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Recommendations */}
          {analytics.recommendations.length > 0 && (
            <Card className="p-5">
              <div className="font-medium flex items-center gap-2">
                <BookOpen className="size-4 text-primary" /> Recommendations for you
              </div>
              <div className="mt-4 space-y-3">
                {analytics.recommendations.map((r, i) => (
                  <div key={i} className="p-3 rounded-lg border bg-muted/20 flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-medium">{r.topic}</div>
                      <div className="text-sm text-muted-foreground mt-0.5">{r.action}</div>
                    </div>
                    <Badge className={`${priorityTone[r.priority] ?? "bg-muted"} border-0 shrink-0`}>{r.priority}</Badge>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Footer hint */}
          <div className="text-xs text-muted-foreground text-center">
            Data is analyzed in background after your lecturer clicks <span className="font-medium">Analyze</span> — if you see &quot;Model unavailable&quot; on the lecturer side, analytics falls back to rule-based scoring. Your login: <span className="font-mono">{studentId.toLowerCase()}@my.sliit.lk</span> / Student@123
          </div>
        </motion.div>
      )}
    </div>
  );
}
