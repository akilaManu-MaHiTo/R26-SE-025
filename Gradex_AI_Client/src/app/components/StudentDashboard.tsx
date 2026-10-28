import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { ArrowUpRight, Award, BookOpen, Brain, CheckCircle2, ChevronRight, Clock, FileText, GraduationCap, Search, Sparkles, Target, User } from "lucide-react";
import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { BrandOrb } from "./BrandOrb";
import practiceAnimation from "./animations/bloub-cercle-surpris-turquoise-anime.svg";
import { fetchStudentDashboard, fetchStudentExams, fetchStudentProfile, fetchStudentMaterials, fetchStudentPractice, studentMaterialPdfUrl,
  type StudentAnalytics, type StudentExam, type StudentProfile, type StudentPractice } from "../api/studentApi";
import type { MaterialInventory } from "../api/courseMaterialsApi";

type View = "dashboard" | "profile" | "materials" | "practice";
const views = [{ view: "dashboard", path: "/student-dashboard", label: "Overview", icon: GraduationCap },
  { view: "profile", path: "/student-profile", label: "My profile", icon: User },
  { view: "materials", path: "/student-materials", label: "Study materials", icon: BookOpen },
  { view: "practice", path: "/student-practice", label: "Practice", icon: Brain }] as const;
const statusTone: Record<string, string> = {
  Strong: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
  Developing: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  "Needs Improvement": "bg-orange-100 text-orange-800 dark:bg-orange-500/15 dark:text-orange-300",
  Critical: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
};
const priorityTone: Record<string, string> = { Critical: statusTone.Critical, High: statusTone["Needs Improvement"], Medium: statusTone.Developing, Low: statusTone.Strong };
const bloomMeaning: Record<string, string> = { Remember: "Recall facts and definitions", Understand: "Explain ideas in your own words", Apply: "Use knowledge to solve problems", Analyze: "Break down and connect ideas", Evaluate: "Justify a decision with evidence", Create: "Develop an original solution" };
const examKey = (exam: StudentExam) => `${exam.subject_code}@${exam.session_name}@${exam.year}-${exam.month}-${exam.semester}`;
const dateLabel = (value: string) => { const date = new Date(value); return Number.isNaN(date.getTime()) ? "Date unavailable" : date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }); };

function Meter({ label, value }: { label: string; value: number }) {
  return <div role="progressbar" aria-label={label} aria-valuenow={Math.round(value)} aria-valuemin={0} aria-valuemax={100} className="h-2 overflow-hidden rounded-full bg-muted">
    <div className="h-full rounded-full bg-primary/80" style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
  </div>;
}

export function StudentDashboard({ studentId, view = "dashboard" }: { studentId: string; view?: View }) {
  const [params, setParams] = useSearchParams();
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [selectedExam, setSelectedExam] = useState<StudentExam | null>(null);
  const [analytics, setAnalytics] = useState<StudentAnalytics | null>(null);
  const [materials, setMaterials] = useState<MaterialInventory | null>(null);
  const [practice, setPractice] = useState<StudentPractice | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingAnalytics, setLoadingAnalytics] = useState(false);
  const [loadingPractice, setLoadingPractice] = useState(false);
  const [error, setError] = useState("");
  const [analysisError, setAnalysisError] = useState("");
  const [materialError, setMaterialError] = useState("");
  const [practiceError, setPracticeError] = useState("");
  const [search, setSearch] = useState("");
  const [materialType, setMaterialType] = useState("all");
  const [reload, setReload] = useState(0);
  const practiceRequest = useRef(0);
  const requestedExam = params.get("exam");

  useEffect(() => {
    let active = true;
    setLoading(true); setError(""); setProfile(null); setSelectedExam(null); setAnalytics(null);
    async function loadProfile() {
      let result: StudentProfile;
      try { result = await fetchStudentProfile(studentId); }
      catch { const exams = await fetchStudentExams(studentId); result = { student_id: studentId, email: "", exam_count: exams.length, exams }; }
      if (active) setProfile(result);
    }
    loadProfile().catch(e => { if (active) setError(e instanceof Error ? e.message : "Could not load your profile."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [studentId, reload]);

  useEffect(() => {
    const exams = [...(profile?.exams ?? [])].sort((a, b) => b.year - a.year || b.month - a.month || b.semester - a.semester);
    setSelectedExam(exams.find(exam => examKey(exam) === requestedExam) ?? exams[0] ?? null);
  }, [profile, requestedExam]);

  useEffect(() => {
    let active = true;
    setAnalytics(null); setAnalysisError(""); setPractice(null); setPracticeError(""); setLoadingPractice(false);
    practiceRequest.current++;
    if (!selectedExam || selectedExam.analyzed === false) { setLoadingAnalytics(false); return; }
    setLoadingAnalytics(true);
    fetchStudentDashboard(studentId, selectedExam.subject_code, selectedExam.session_name, selectedExam.year, selectedExam.month, selectedExam.semester)
      .then(result => {
        if (!active) return;
        if (result.student_id !== studentId || result.subject_code !== selectedExam.subject_code || result.session_name !== selectedExam.session_name ||
          result.year !== selectedExam.year || result.month !== selectedExam.month || result.semester !== selectedExam.semester) throw new Error("The returned results do not match this exam. Please retry.");
        setAnalytics(result);
      })
      .catch(e => { if (active) setAnalysisError(e instanceof Error ? e.message : "Could not load your results."); })
      .finally(() => { if (active) setLoadingAnalytics(false); });
    return () => { active = false; practiceRequest.current++; };
  }, [studentId, selectedExam, reload]);

  useEffect(() => {
    let active = true;
    setMaterials(null); setMaterialError("");
    fetchStudentMaterials(studentId).then(result => { if (active) setMaterials(result); })
      .catch(e => { if (active) setMaterialError(e instanceof Error ? e.message : "Could not load study materials."); });
    return () => { active = false; };
  }, [studentId, reload]);

  const exams = profile?.exams ?? [];
  const overall = analytics?.overall_performance;
  const learning = analytics?.learning_analysis;
  const gaps = [...(learning?.learning_gaps ?? [])].sort((a, b) => ["Critical", "High", "Medium", "Low"].indexOf(a.priority) - ["Critical", "High", "Medium", "Low"].indexOf(b.priority));
  const topics = [...(analytics?.topic_performance ?? [])].sort((a, b) => a.percentage - b.percentage);
  const courseMaterials = (materials?.items ?? []).filter(item => !selectedExam || item.course_code === selectedExam.subject_code);
  const filteredMaterials = courseMaterials.filter(item => (materialType === "all" || item.document_type === materialType) && `${item.filename} ${item.course_code}`.toLowerCase().includes(search.toLowerCase()));
  const href = (path: string) => selectedExam ? `${path}?${new URLSearchParams({ exam: examKey(selectedExam) })}` : path;
  const pending = selectedExam?.analyzed === false || analysisError.includes("Wait for lecture");
  const selectExam = (exam: StudentExam) => { setParams({ exam: examKey(exam) }); };

  async function generatePractice() {
    if (!selectedExam || !analytics || loadingPractice) return;
    const request = ++practiceRequest.current;
    setLoadingPractice(true); setPracticeError("");
    try { const result = await fetchStudentPractice(studentId, selectedExam); if (request === practiceRequest.current) setPractice(result); }
    catch (e) { if (request === practiceRequest.current) setPracticeError(e instanceof Error ? e.message : "Could not generate practice."); }
    finally { if (request === practiceRequest.current) setLoadingPractice(false); }
  }

  const materialsLink = <Button asChild variant="outline" className="min-h-11"><Link to={href("/student-materials")}>Browse study materials <ArrowUpRight className="size-4" /></Link></Button>;
  const recommendations = analytics?.recommendations ?? [];

  return <div className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8">
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div><p className="mb-1 text-xs font-medium uppercase tracking-widest text-muted-foreground">Your learning space</p>
        <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">{view === "dashboard" ? "Make your next attempt count." : view === "profile" ? "Your learning profile" : view === "materials" ? "Build understanding, one topic at a time." : "Turn your gaps into strengths."}</h2>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">{view === "dashboard" ? "Understand your results. Focus your revision. Know what to do next." : view === "profile" ? "Your strengths, learning needs, and the evidence behind them." : view === "materials" ? "Lectures and tutorials for your courses, ready for focused revision." : "Targeted questions shaped by your selected exam results."}</p>
      </div>
      <Badge variant="outline" className="gap-2 px-3 py-2"><User className="size-4" />{studentId}</Badge>
    </div>

    <nav aria-label="Student pages" className="grid grid-cols-2 gap-1 rounded-xl border bg-muted/40 p-1 sm:flex sm:flex-wrap">
      {views.map(item => <Link key={item.view} to={href(item.path)} aria-current={view === item.view ? "page" : undefined}
        className={`flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${view === item.view ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:bg-card/60 hover:text-foreground"}`}>
        <item.icon className="size-4" />{item.label}</Link>)}
    </nav>

    {loading && <Card className="p-6" role="status">Loading your learning profile…</Card>}
    {error && <Card className="gap-3 p-6"><p role="alert">{error}</p><Button className="self-start" onClick={() => setReload(value => value + 1)}>Retry</Button></Card>}
    {!loading && !error && <>
      {exams.length > 0 && <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card px-4 py-3">
        <label className="flex min-w-0 flex-1 basis-full flex-wrap items-center gap-3 text-sm font-medium sm:basis-auto"><GraduationCap className="size-5 text-muted-foreground" />Exam context
          <select aria-label="Selected exam" value={selectedExam ? examKey(selectedExam) : ""} onChange={e => setParams({ exam: e.target.value })}
            className="min-h-11 w-full min-w-0 rounded-lg border bg-background px-3 text-sm sm:w-auto sm:max-w-lg">
            {[...exams].sort((a, b) => b.year - a.year || b.month - a.month).map(exam => <option key={examKey(exam)} value={examKey(exam)}>{exam.subject_name} · {exam.session_name} · {exam.year}/{exam.month} · Semester {exam.semester}{exam.analyzed === false ? " · Pending" : ""}</option>)}
          </select>
        </label>
        <span className="flex items-center gap-2 text-xs text-muted-foreground"><Clock className="size-3.5" />{analytics ? `Updated ${dateLabel(analytics.generated_at)}` : pending ? "Analysis pending" : "Results for selected exam"}</span>
      </div>}

      {view !== "materials" && <>
        {exams.length === 0 && <Card className="items-start gap-4 p-6 sm:p-8"><BookOpen className="size-8 text-muted-foreground" /><h3 className="text-lg font-semibold">Your learning journey starts here</h3><p className="max-w-xl text-sm text-muted-foreground">No exam submissions are linked to your account yet. When your lecturer grades and analyzes an exam, your strengths, revision priorities, and personalized practice will appear here. Ask your lecturer if you expected to see results.</p>{materialsLink}</Card>}
        {pending && <Card className="gap-3 border-amber-300/60 bg-amber-50/50 p-6 dark:bg-amber-950/20"><div className="flex items-center gap-2 font-medium"><Clock className="size-5" />Waiting for lecturer analysis</div><p className="text-sm text-muted-foreground">Your submission is listed. Your lecturer needs to complete analysis before personalized findings are available. You can review course materials now or select an earlier analyzed exam.</p><div className="self-start">{materialsLink}</div></Card>}
        {analysisError && !pending && <Card className="gap-3 p-6"><p role="alert">{analysisError}</p><Button variant="outline" className="self-start" onClick={() => setReload(value => value + 1)}>Retry results</Button></Card>}
        {loadingAnalytics && <Card className="gap-2 p-6" role="status"><div className="flex items-center gap-2 font-medium"><Sparkles className="size-5" />Preparing your learning insights…</div><p className="text-sm text-muted-foreground">We’re checking your question marks, topic performance, and revision priorities.</p></Card>}
      </>}

      {view === "dashboard" && analytics && !loadingAnalytics && <>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[{ label: "Selected exam score", value: `${overall!.percentage.toFixed(1)}%`, detail: `${overall!.score} / ${overall!.maximum} marks · ${overall!.status}`, icon: Award },
            { label: "Strong topics", value: learning!.strong_topics.length, detail: "Keep these skills active", icon: CheckCircle2 },
            { label: "Revision priorities", value: gaps.length, detail: "Learning gaps identified in this exam", icon: Target },
            { label: "Course resources", value: materials ? courseMaterials.length : "—", detail: "Lectures and tutorials to explore", icon: BookOpen }].map(stat => <Card key={stat.label} className="gap-3 p-5"><div className="flex items-center justify-between text-sm text-muted-foreground">{stat.label}<stat.icon className="size-4" /></div><div className="text-3xl font-semibold tracking-tight tabular-nums">{stat.value}</div><p className="text-xs text-muted-foreground">{stat.detail}</p></Card>)}
        </div>
        <div className="grid items-start gap-6 lg:grid-cols-3">
          <Card className="gap-5 overflow-hidden lg:col-span-2">
            <div className="border-b bg-secondary/40 p-6"><div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-widest text-muted-foreground"><Sparkles className="size-4" />Your next chapter</div><h3 className="text-xl font-semibold">Study next</h3><p className="mt-1 text-sm text-muted-foreground">Start with the gaps that need the most attention.</p></div>
            <div className="space-y-5 px-6 pb-6">{gaps.length ? gaps.slice(0, 3).map((gap, i) => <div key={`${gap.topic}-${gap.subtopic}`} className="flex gap-4"><span className="flex size-8 shrink-0 items-center justify-center rounded-full border bg-muted/50 text-sm font-medium">{i + 1}</span><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><h4 className="font-medium">{gap.topic}</h4><Badge className={priorityTone[gap.priority]}>{gap.priority}</Badge></div><p className="mt-1 text-sm text-muted-foreground">{gap.subtopic}</p></div></div>) : <p className="text-sm text-muted-foreground">No specific learning gaps were identified. Review your lowest-scoring topics and keep practicing your strengths.</p>}
              {recommendations.length > 0 && <div className="space-y-3 border-t pt-4">{recommendations.slice(0, 3).map((item, i) => <div key={i}><p className="text-sm font-medium">{item.topic}</p><p className="mt-1 text-sm leading-relaxed text-muted-foreground">{item.action}</p></div>)}</div>}
              <div className="flex flex-wrap gap-3">{materialsLink}<Button asChild className="min-h-11"><Link to={href("/student-practice")}>Practice these skills <ChevronRight className="size-4" /></Link></Button></div>
            </div>
          </Card>
          <Card className="gap-4 p-6"><div className="flex items-center gap-2"><CheckCircle2 className="size-5 text-emerald-700 dark:text-emerald-400" /><h3 className="font-semibold">Build on what works</h3></div><p className="text-sm text-muted-foreground">Your strong topics in this exam. Revisit them between revision sessions.</p>{learning!.strong_topics.length ? <div className="flex flex-wrap gap-2">{learning!.strong_topics.map(topic => <Badge key={topic} className={statusTone.Strong}>{topic}</Badge>)}</div> : <p className="text-sm text-muted-foreground">No topic has reached the strong band yet. Each focused revision session is a step forward.</p>}<div className="border-t pt-4"><p className="text-sm font-medium">How to use this space</p><ol className="mt-3 list-decimal space-y-2 pl-4 text-sm text-muted-foreground"><li>Review a priority topic.</li><li>Work through the related tutorial.</li><li>Try practice questions without notes.</li><li>Check missed criteria on your profile.</li></ol></div></Card>
        </div>
      </>}

      {view === "profile" && <Card className="gap-4 p-6"><div className="flex flex-wrap items-center gap-4"><div className="flex size-14 items-center justify-center rounded-2xl bg-secondary"><User className="size-7" /></div><div className="min-w-0"><h3 className="text-lg font-semibold">{studentId}</h3><p className="break-all text-sm text-muted-foreground">{profile?.email || "Email unavailable"}</p></div><Badge variant="outline" className="sm:ml-auto">{exams.length} linked exams</Badge></div><p className="border-t pt-4 text-sm text-muted-foreground">Findings below describe the selected exam. Choose another exam to explore its results; these are not an overall academic grade.</p></Card>}

      {(view === "dashboard" || view === "profile") && analytics && !loadingAnalytics && <div className="grid items-start gap-6 lg:grid-cols-2">
        <Card className="gap-5 p-6"><div><h3 className="text-lg font-semibold">Topic performance</h3><p className="mt-1 text-sm text-muted-foreground">Lowest scores first, so you know where to focus.</p></div>{topics.map(topic => <div key={topic.topic} className="space-y-2"><div className="flex justify-between gap-3 text-sm"><span className="font-medium">{topic.topic}</span><span className="shrink-0 tabular-nums">{topic.percentage.toFixed(1)}%</span></div><Meter label={topic.topic} value={topic.percentage} /><div className="flex items-center justify-between gap-2"><span className="text-xs text-muted-foreground">{topic.score}/{topic.max_score} marks · {topic.questions_attempted} questions</span><Badge className={statusTone[topic.status]}>{topic.status}</Badge></div></div>)}{!topics.length && <p className="text-sm text-muted-foreground">Topic-level results are not available for this exam.</p>}</Card>
        <Card className="gap-5 p-6"><div><h3 className="text-lg font-semibold">How you use your knowledge</h3><p className="mt-1 text-sm text-muted-foreground">Thinking skills measured using Bloom’s taxonomy.</p></div>{analytics.bloom_performance.map(skill => <div key={skill.level} className="space-y-2"><div className="flex justify-between gap-3 text-sm"><span className="font-medium">{skill.level}</span><span className="shrink-0 tabular-nums">{skill.average_score.toFixed(1)}%</span></div><p className="text-xs text-muted-foreground">{bloomMeaning[skill.level]}</p><Meter label={skill.level} value={skill.average_score} /><Badge className={statusTone[skill.status]}>{skill.status}</Badge></div>)}{!analytics.bloom_performance.length && <p className="text-sm text-muted-foreground">Thinking-skill results are not available for this exam.</p>}</Card>
      </div>}

      {view === "profile" && analytics && !loadingAnalytics && <>
        <Card className="gap-5 p-6"><h3 className="text-lg font-semibold">Your strengths and development areas</h3><div className="grid gap-5 sm:grid-cols-2">{[{ title: "Strong", values: learning!.strong_topics }, { title: "Developing", values: learning!.developing_topics }, { title: "Needs Improvement", values: learning!.weak_topics }, { title: "Critical", values: learning!.critical_topics }].map(group => <div key={group.title}><Badge className={statusTone[group.title]}>{group.title}</Badge><p className="mt-2 text-sm">{group.values.join(", ") || "No topics in this band"}</p></div>)}</div>{gaps.length > 0 && <div className="space-y-3 border-t pt-4"><h4 className="font-medium">Specific learning gaps</h4>{gaps.map((gap, i) => <div key={i} className="flex flex-wrap items-center justify-between gap-2 text-sm"><span>{gap.topic} · {gap.subtopic}</span><Badge className={priorityTone[gap.priority]}>{gap.priority}</Badge></div>)}</div>}</Card>
        <Card className="gap-0 overflow-hidden"><div className="border-b p-6"><h3 className="text-lg font-semibold">The evidence behind your results</h3><p className="mt-1 text-sm text-muted-foreground">Open a question to see its marks and the criteria to revisit.</p></div>{analytics.question_performance.map(q => <details key={q.question_id} className="group border-b last:border-b-0"><summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-4 p-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"><div className="min-w-0"><p className="text-sm font-medium">Question {q.question_no} · {q.topic}</p><p className="mt-1 text-xs text-muted-foreground">{q.subtopic} · {q.bloom_analysis.level}</p></div><div className="flex shrink-0 items-center gap-3"><span className="text-sm tabular-nums">{q.performance.score}/{q.performance.max_score}</span><ChevronRight className="size-4 transition-transform group-open:rotate-90" /></div></summary><div className="space-y-4 border-t bg-muted/20 p-5"><p className="whitespace-pre-wrap text-sm leading-relaxed">{q.question_text}</p><h4 className="text-sm font-medium">Marking criteria</h4>{q.criteria_performance.length ? q.criteria_performance.map((criterion, i) => <div key={i} className="flex flex-wrap items-start justify-between gap-2 rounded-lg border bg-card p-3 text-sm"><div className="flex-1"><p>{criterion.criterion}</p><p className="mt-1 text-xs text-muted-foreground">{criterion.awarded_marks >= criterion.max_marks ? "Full marks achieved" : "Revisit this criterion to recover missed marks"}</p></div><Badge variant="outline">{criterion.awarded_marks}/{criterion.max_marks}</Badge></div>) : <p className="text-sm text-muted-foreground">Detailed criteria were not included in this result.</p>}</div></details>)}{!analytics.question_performance.length && <p className="p-6 text-sm text-muted-foreground">Question-level evidence is not available for this exam.</p>}</Card>
      </>}

      {view === "profile" && <Card className="gap-4 p-6"><h3 className="text-lg font-semibold">Exam history</h3><p className="text-sm text-muted-foreground">Select an exam to inspect its learning profile.</p>{exams.map(exam => <button key={examKey(exam)} onClick={() => selectExam(exam)} aria-pressed={selectedExam && examKey(exam) === examKey(selectedExam)} className="flex min-h-14 items-center justify-between gap-3 rounded-xl border p-4 text-left hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><div><p className="text-sm font-medium">{exam.subject_name}</p><p className="mt-1 text-xs text-muted-foreground">{exam.session_name} · {exam.year}/{exam.month} · Semester {exam.semester}</p></div><Badge variant="outline">{exam.analyzed === false ? "Pending" : exam.analyzed ? "Analyzed" : "Check results"}</Badge></button>)}{!exams.length && <p className="text-sm text-muted-foreground">No exams linked yet.</p>}</Card>}

      {view === "materials" && <>
        {gaps.length > 0 && <Card className="gap-3 bg-secondary/30 p-5"><div className="flex items-center gap-2 text-sm font-medium"><Target className="size-4" />Your revision focus</div><p className="text-sm text-muted-foreground">Look for these topics in your lectures and tutorials. Resources below are grouped by course; topic matches are not guaranteed.</p><div className="flex flex-wrap gap-2">{gaps.map((gap, i) => <Badge key={i} variant="outline">{gap.topic} · {gap.subtopic}</Badge>)}</div></Card>}
        <div className="flex flex-wrap items-center gap-3"><label className="relative min-w-0 flex-1"><Search className="pointer-events-none absolute left-3 top-3 size-4 text-muted-foreground" /><Input type="search" aria-label="Search study materials" placeholder="Search lecture or tutorial names…" className="min-h-11 pl-9" value={search} onChange={e => setSearch(e.target.value)} /></label><label className="flex items-center gap-2 text-sm">Type<select className="min-h-11 rounded-lg border bg-card px-3" value={materialType} onChange={e => setMaterialType(e.target.value)}><option value="all">All resources</option><option value="lecture">Lectures</option><option value="tutorial">Tutorials</option></select></label></div>
        {materialError ? <Card className="gap-3 p-6"><p role="alert">{materialError}</p><Button variant="outline" className="self-start" onClick={() => setReload(value => value + 1)}>Retry materials</Button></Card> : !materials ? <p role="status" className="text-sm text-muted-foreground">Loading study materials…</p> : materials.status === "unavailable" ? <Card className="p-6"><p className="text-sm text-muted-foreground">Study resources are not available right now. Ask your lecturer to check the course material library.</p></Card> : <>
          <p className="text-sm text-muted-foreground">{filteredMaterials.length} resources{selectedExam ? ` for ${selectedExam.subject_name}` : " for your linked courses"}</p>
          <div className="grid items-stretch gap-4 sm:grid-cols-2 xl:grid-cols-3">{filteredMaterials.map(item => <Card key={item.document_id} className="gap-4 p-5"><div className="flex items-center justify-between"><div className="rounded-xl bg-secondary p-3"><FileText className="size-5" /></div><Badge variant="outline">{item.document_type === "lecture" ? "Lecture" : "Tutorial"}</Badge></div><div><h3 className="break-words font-medium">{item.filename}</h3><p className="mt-2 text-xs text-muted-foreground">{item.course_code} · {item.pages} pages{item.year ? ` · ${item.year}` : ""}</p></div>{item.empty_pages.length > 0 && <p className="text-xs text-muted-foreground">Some pages contain scanned text or diagrams. Review the original PDF.</p>}<div className="mt-auto">{item.pdf_available ? <Button asChild variant="outline" className="min-h-11 w-full"><a href={studentMaterialPdfUrl(studentId, item.document_id)} target="_blank" rel="noreferrer" aria-label={`Open ${item.filename}`}>Open PDF <ArrowUpRight className="size-4" /></a></Button> : <p className="text-xs text-muted-foreground">Original PDF unavailable. Ask your lecturer to reattach this resource.</p>}</div></Card>)}</div>
          {!filteredMaterials.length && <Card className="items-start gap-3 p-8"><BookOpen className="size-7 text-muted-foreground" /><h3 className="font-semibold">{search || materialType !== "all" ? "No matching resources" : "Your course library is waiting to grow"}</h3><p className="text-sm text-muted-foreground">{search || materialType !== "all" ? "Try another search or choose all resource types." : "Ask your lecturer to add lectures and tutorials for this course. Your question feedback is still available on your profile."}</p><Button asChild variant="outline"><Link to={href("/student-profile")}>Review my feedback</Link></Button></Card>}
        </>}
      </>}

      {view === "practice" && analytics && !loadingAnalytics && <>
        <Card className="gap-5 p-6 sm:p-8"><div className="flex items-center gap-3"><div className="rounded-xl bg-secondary p-3"><Brain className="size-6" /></div><div><h3 className="text-xl font-semibold">A focused practice session</h3><p className="mt-1 text-sm text-muted-foreground">Based on your selected exam, tailored to the skills you need next.</p></div></div><div className="grid gap-4 sm:grid-cols-3"><div><p className="text-xs uppercase tracking-wide text-muted-foreground">Focus topics</p><p className="mt-2 text-sm font-medium">{analytics.next_question_strategy.recommended_topics.join(", ") || "No target topics available"}</p></div><div><p className="text-xs uppercase tracking-wide text-muted-foreground">Thinking skills</p><p className="mt-2 text-sm font-medium">{analytics.next_question_strategy.recommended_bloom_levels.join(", ") || "Not specified"}</p></div><div><p className="text-xs uppercase tracking-wide text-muted-foreground">Session</p><p className="mt-2 text-sm font-medium">{analytics.next_question_strategy.number_of_questions} questions · {analytics.next_question_strategy.recommended_difficulty}</p></div></div><p className="text-sm text-muted-foreground">Work through each question on paper before opening its hints. This is self-study practice and does not change your exam grade.</p><Button className="min-h-11 h-auto self-start" aria-busy={loadingPractice} disabled={loadingPractice || !analytics.next_question_strategy.recommended_topics.length} onClick={() => void generatePractice()}>{loadingPractice ? <BrandOrb state="solving" size={32} aria-hidden="true" /> : <img src={practiceAnimation} alt="" aria-hidden="true" className="size-8 motion-reduce:hidden" />}{loadingPractice ? "Preparing questions…" : practice ? "Reload practice questions" : "Generate practice questions"}</Button>{loadingPractice && <p role="status" className="text-sm text-muted-foreground">Question generation can take a little time. Your practice will appear here when ready.</p>}{practiceError && <p role="alert" className="text-sm text-destructive">{practiceError}</p>}</Card>
        {practice && <div className="space-y-4"><p className="text-xs text-muted-foreground">Practice prepared {dateLabel(practice.generated_at)}</p>{practice.questions.map((q, i) => <Card key={i} className="gap-4 p-6"><div className="flex flex-wrap items-center gap-2"><span className="mr-auto text-sm font-medium">Practice {i + 1}</span><Badge variant="outline">{q.topic}</Badge><Badge variant="outline">{q.bloom_level}</Badge><Badge variant="outline">{q.difficulty}</Badge></div><p className="whitespace-pre-wrap leading-relaxed">{q.prompt}</p>{q.hints.length > 0 && <details className="rounded-lg border bg-muted/20 p-3"><summary className="min-h-8 cursor-pointer text-sm font-medium">Show hints</summary><ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-muted-foreground">{q.hints.map((hint, index) => <li key={index}>{hint}</li>)}</ul></details>}<label className="text-sm font-medium">Your working notes<textarea className="mt-2 min-h-28 w-full rounded-lg border bg-background p-3 text-sm font-normal focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" placeholder="Outline your answer here…" /></label><p className="text-xs text-muted-foreground">Notes stay on this page only. Copy them before leaving or switching exams.</p></Card>)}{!practice.questions.length && <p className="text-sm text-muted-foreground">No practice questions were returned. Please try again later.</p>}</div>}
        <div>{materialsLink}</div>
      </>}
      <p className="text-center text-xs leading-relaxed text-muted-foreground">Your insights come from recorded exam results. Review your question feedback and discuss any concerns with your lecturer.</p>
    </>}
  </div>;
}
