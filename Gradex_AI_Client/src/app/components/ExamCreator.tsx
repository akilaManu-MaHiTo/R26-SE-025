import { useState, useEffect, useCallback } from "react";
import { Sparkles, Plus, Pencil, X, AlertTriangle, BookOpen, BarChart3, ChevronRight, Layers, FileDown, Eye, CloudUpload } from "lucide-react";
import { useHideSidebar } from "../App";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { ProgressLoader, type LoadStep } from "./ProgressLoader";
import { AIPageBanner } from "./AIBrand";
import {
  fetchExams,
  fetchRecommendations,
  fetchQuestionBank,
  createExamDraft,
  listExamDrafts,
  getExamDraft,
  type ExamListItem,
  type RecommendationsResponse,
  type Recommendation,
  type QuestionBankItem,
  type ExamDraft,
} from "../api/lecturerApi";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./ui/tabs";
import { toast } from "sonner";

// ─── Paper Model (Task 2) ───
export type Part = { part: string; question: string; max_marks: number };
export type PaperQuestion = { question_number: number; topic: string; parts: Part[] };
export type Paper = { exam: string; year: number; questions: PaperQuestion[] };

export const seedPaper: Paper = {
  exam: "IT2040 – Database Management Systems",
  year: 2023,
  questions: [
    {
      question_number: 1,
      topic: "Schema refinement",
      parts: [
        { part: "a", question: "Explain schema refinement and its importance in database design.", max_marks: 8 },
        { part: "b", question: "What is functional dependency? Explain full, partial, and transitive dependency with examples.", max_marks: 12 },
      ],
    },
    {
      question_number: 2,
      topic: "Schema refinement",
      parts: [
        { part: "a", question: "Given a relation and set of functional dependencies, explain the step-by-step process of normalization up to BCNF.", max_marks: 10 },
        { part: "b", question: "Define lossless join decomposition and dependency preservation.", max_marks: 10 },
      ],
    },
    {
      question_number: 3,
      topic: "Java Database Connectivity (JDBC)",
      parts: [
        { part: "a", question: "Explain the steps involved in connecting to a database using JDBC. Include necessary exception handling.", max_marks: 10 },
        { part: "b", question: "What is SQL injection? How can it be prevented using JDBC?", max_marks: 8 },
        { part: "c", question: "Differentiate between ResultSet TYPE_SCROLL_INSENSITIVE and TYPE_FORWARD_ONLY.", max_marks: 7 },
      ],
    },
    {
      question_number: 4,
      topic: "SQL",
      parts: [
        { part: "a", question: "Write SQL queries to:\n(i) Find the top 5 members with the highest number of loans.\n(ii) Update fine amounts by adding 10% penalty for overdue payments.", max_marks: 12 },
        { part: "b", question: "Create a trigger that automatically updates availableCopies in the Book table when a book is returned.", max_marks: 12 },
        { part: "c", question: "Explain how to implement role-based access control in SQL Server with examples.", max_marks: 11 },
      ],
    },
  ],
};

function renumberQuestions(qs: PaperQuestion[]): PaperQuestion[] {
  return qs.map((q, i) => ({
    ...q,
    question_number: i + 1,
    parts: q.parts.map((p, j) => ({ ...p, part: String.fromCharCode(97 + j) })),
  }));
}

function totalMarks(paper: Paper): number {
  return paper.questions.flatMap((q) => q.parts).reduce((s, p) => s + (Number(p.max_marks) || 0), 0);
}

const CANONICAL_TOPICS = [
  "Introduction to DBMS & Conceptual Database Design",
  "Logical Database Design",
  "Schema Refinement",
  "Structured Query Language (SQL)",
  "Database Programming",
  "Java Database Connectivity (JDBC)",
  "Database Indexes and Storage Structures",
  "Database Transaction Management and Concurrency Control",
  "Database Recovery and Log Management",
  "Database Utilities",
  "Database Security",
];

// ─── Helpers ───
function PriorityBadge({ priority }: { priority: string }) {
  const color =
    priority === "High" ? "bg-red-500 text-white" : priority === "Medium" ? "bg-amber-500 text-white" : "bg-muted text-muted-foreground";
  return <Badge className={color}>{priority}</Badge>;
}

export function ExamCreator() {
  const hideCtx = useHideSidebar();
  const [exams, setExams] = useState<ExamListItem[]>([]);
  const [selectedExam, setSelectedExam] = useState<ExamListItem | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendationsResponse | null>(null);
  const [rejectedIds, setRejectedIds] = useState<Set<string>>(new Set());
  const [paper, setPaper] = useState<Paper>(seedPaper);
  const [insertTargets, setInsertTargets] = useState<Record<string, string>>({});
  const [loadingExams, setLoadingExams] = useState(true);
  const [loadingRecs, setLoadingRecs] = useState(false);
  const [loadSteps, setLoadSteps] = useState<LoadStep[]>([]);
  const [currentStep, setCurrentStep] = useState(0);
  const [rightTab, setRightTab] = useState<"recommended" | "browse">("recommended");
  const [bankFilters, setBankFilters] = useState<{ source_type?: string; year?: number }>({});
  const [bankItems, setBankItems] = useState<QuestionBankItem[]>([]);
  const [loadingBank, setLoadingBank] = useState(false);
  const [drafts, setDrafts] = useState<ExamDraft[]>([]);
  const [loadingDrafts, setLoadingDrafts] = useState(false);
  const [currentDraftId, setCurrentDraftId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const total = totalMarks(paper);

  useEffect(() => {
    setLoadSteps([{ label: "Fetching exams..." }]);
    fetchExams()
      .then(setExams)
      .catch(console.error)
      .finally(() => setLoadingExams(false));
    setLoadingDrafts(true);
    listExamDrafts()
      .then(setDrafts)
      .catch(() => {})
      .finally(() => setLoadingDrafts(false));
  }, []);

  const handleSelectExam = useCallback(async (exam: ExamListItem) => {
    setSelectedExam(exam);
    hideCtx?.setHide(true);
    setLoadingRecs(true);
    setRecommendations(null);
    setRejectedIds(new Set());
    const steps: LoadStep[] = [
      { label: "Loading student weakness..." },
      { label: "Scoring against curriculum..." },
      { label: "Ranking recommendations..." },
    ];
    setLoadSteps(steps);
    setCurrentStep(0);
    try {
      setCurrentStep(0);
      const data = await fetchRecommendations(exam.course_code, exam.session_name, exam.year, exam.month, exam.semester, 12);
      setCurrentStep(2);
      setRecommendations(data);
      setPaper((prev) => ({ ...prev, exam: `${exam.course_code} – ${exam.subject_name}`, year: exam.year }));
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingRecs(false);
    }
  }, [hideCtx]);

  const handleBackToSelector = useCallback(() => {
    hideCtx?.setHide(false);
    setSelectedExam(null);
  }, [hideCtx]);

  useEffect(() => {
    return () => hideCtx?.setHide(false);
  }, [hideCtx]);

  const handleFetchBank = useCallback(async (filters: { source_type?: string; year?: number }) => {
    setLoadingBank(true);
    try {
      const items = await fetchQuestionBank({ ...filters, limit: 50 });
      setBankItems(items);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingBank(false);
    }
  }, []);

  useEffect(() => {
    if (rightTab === "browse") handleFetchBank(bankFilters);
  }, [rightTab, bankFilters, handleFetchBank]);

  const handleInsertFromBank = (item: QuestionBankItem) => {
    const fakeRec: Recommendation = {
      question_id: item.question_id,
      source_type: item.source_type,
      source_id: item.source_id,
      canonical_topic: item.canonical_topic,
      subtopic: item.subtopic,
      bloom_level: item.bloom_level,
      difficulty: item.difficulty,
      marks: item.marks,
      text: item.text,
      weakness: 0,
      lecture_coverage: 1,
      tutorial_evidence: 1,
      exam_relevance: 1,
      bloom_gap: 0,
      recommendation_score: 0,
      priority: "Medium",
      reason: { weakness_pct: 0, lecture: true, tutorial_count: 0, exam_recent_count: 0, bloom_gap: 0 },
    };
    handleInsert(fakeRec);
  };

  const handleUpload = async () => {
    if (total === 0) {
      toast.error("Paper is empty");
      return;
    }
    setUploading(true);
    try {
      const subject = selectedExam?.course_code || paper.exam.split(" ")[0] || "IT2040";
      const draft = await createExamDraft(subject, paper, currentDraftId || undefined);
      setCurrentDraftId(draft.draft_id);
      setDrafts((prev) => {
        const filtered = prev.filter((d) => d.draft_id !== draft.draft_id);
        return [draft, ...filtered];
      });
      toast.success(`Uploaded to cloud — ${draft.draft_id}`);
    } catch (e) {
      toast.error("Upload failed");
      console.error(e);
    } finally {
      setUploading(false);
    }
  };

  const handleLoadDraft = async (draft: ExamDraft) => {
    setPaper(draft.paper as Paper);
    setCurrentDraftId(draft.draft_id);
    hideCtx?.setHide(true);
    // create a synthetic selectedExam for header
    setSelectedExam({
      course_code: draft.subject_code,
      subject_name: draft.subject_name,
      session_name: "Draft",
      year: draft.paper.year,
      month: 1,
      semester: 1,
      total_marks: draft.total_marks,
      question_count: draft.question_count,
      student_count: 0,
      average_score: 0,
      average_percentage: 0,
      highest_score: 0,
      lowest_score: 0,
      pass_rate: 0,
      analyzed: false,
      analyzed_at: null,
    } as ExamListItem);
    toast.success(`Loaded draft ${draft.draft_id}`);
    // fetch recommendations for this draft's subject
    try {
      const rec = await fetchRecommendations(draft.subject_code, "Final Examination", draft.paper.year, 1, 1, 12);
      setRecommendations(rec);
    } catch {}
  };

  const handleInsert = (rec: Recommendation) => {
    const target = insertTargets[rec.question_id] || "end";
    setPaper((prev) => {
      let qs = [...prev.questions];
      const newPart: Part = { part: "a", question: rec.text, max_marks: rec.marks > 0 ? rec.marks : 10 };
      if (target === "end") {
        qs.push({ question_number: qs.length + 1, topic: rec.canonical_topic, parts: [newPart] });
      } else if (target.includes("-part")) {
        const qn = Number(target.split("Q")[1].split("-")[0]);
        qs = qs.map((q) => (q.question_number === qn ? { ...q, parts: [...q.parts, { ...newPart, part: String.fromCharCode(97 + q.parts.length) }] } : q));
      } else if (target.startsWith("Q")) {
        const qn = Number(target.slice(1));
        qs.splice(qn - 1, 0, { question_number: qn, topic: rec.canonical_topic, parts: [newPart] });
      }
      const renumbered = renumberQuestions(qs);
      setTimeout(() => {
        const el = document.getElementById(`question-${renumbered.find((q) => q.parts.some((p) => p.question === rec.text))?.question_number}`);
        el?.scrollIntoView({ behavior: "smooth", block: "center" });
        el?.classList.add("ring-2", "ring-primary");
        setTimeout(() => el?.classList.remove("ring-2", "ring-primary"), 1000);
      }, 100);
      return { ...prev, questions: renumbered };
    });
  };

  const handleDownload = async () => {
    const { default: jsPDF } = await import("jspdf");
    const doc = new jsPDF();
    doc.setFontSize(14);
    doc.text(`${paper.exam} ${paper.year}`, 10, 15);
    doc.setFontSize(10);
    doc.text(`Total Marks: ${total}`, 10, 22);
    let y = 30;
    paper.questions.forEach((q) => {
      if (y > 270) {
        doc.addPage();
        y = 15;
      }
      doc.setFontSize(11);
      doc.text(`Question ${q.question_number} (${q.topic})`, 10, y);
      y += 7;
      q.parts.forEach((p) => {
        const lines = doc.splitTextToSize(`${p.part}) ${p.question} [${p.max_marks} marks]`, 190);
        if (y + lines.length * 5 > 280) {
          doc.addPage();
          y = 15;
        }
        doc.setFontSize(10);
        doc.text(lines, 12, y);
        y += lines.length * 5 + 3;
      });
      y += 4;
    });
    doc.save(`${paper.exam.replace(/\s/g, "_")}_${paper.year}.pdf`);
  };

  const handlePreview = async () => {
    const { default: jsPDF } = await import("jspdf");
    const doc = new jsPDF();
    doc.setFontSize(14);
    doc.text(`${paper.exam} ${paper.year}`, 10, 15);
    let y = 30;
    paper.questions.forEach((q) => {
      doc.setFontSize(11);
      doc.text(`Question ${q.question_number} (${q.topic})`, 10, y);
      y += 7;
      q.parts.forEach((p) => {
        const lines = doc.splitTextToSize(`${p.part}) ${p.question} [${p.max_marks}]`, 190);
        if (y + lines.length * 5 > 280) {
          doc.addPage();
          y = 15;
        }
        doc.text(lines, 12, y);
        y += lines.length * 5 + 3;
      });
      y += 4;
    });
    window.open(doc.output("bloburl"), "_blank");
  };

  const visibleRecs = recommendations?.recommendations.filter((r) => !rejectedIds.has(r.question_id)) ?? [];
  const high = visibleRecs.filter((r) => r.priority === "High");
  const medium = visibleRecs.filter((r) => r.priority === "Medium");
  const low = visibleRecs.filter((r) => r.priority === "Low");

  // Exam selector (no exam chosen)
  if (!selectedExam) {
    return (
      <div className="p-6 md:p-8 space-y-6">
        <AIPageBanner model="pulse" />
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Layers className="size-4" /> Exam Creator <ChevronRight className="size-4" /> Select Exam
          </div>
          <h2 className="tracking-tight text-foreground">Adaptive Exam Question Recommendation Engine</h2>
          <p className="text-sm text-muted-foreground max-w-2xl">
            Based on student analytics + curriculum + previous assessments. Select an exam to get weak-area-driven recommendations and compose your draft.
          </p>
        </div>
        {loadingExams ? (
          <ProgressLoader steps={loadSteps} currentStep={currentStep} className="min-h-[300px]" />
        ) : exams.length === 0 ? (
          <Card className="p-12 text-center border-border">
            <BookOpen className="h-12 w-12 mx-auto mb-4 text-muted-foreground/50" />
            <p className="text-muted-foreground">No exams found. Ingest submissions first.</p>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {exams.map((exam) => (
              <Card
                key={`${exam.course_code}-${exam.year}-${exam.session_name}`}
                className="group p-5 border-border hover:border-primary/40 cursor-pointer transition-colors"
                onClick={() => handleSelectExam(exam)}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="size-10 rounded-lg bg-primary text-primary-foreground flex items-center justify-center">
                    <Sparkles className="size-5" />
                  </div>
                  <Badge variant="secondary">{exam.student_count} students</Badge>
                </div>
                <div className="font-semibold">{exam.course_code} — {exam.session_name}</div>
                <div className="text-sm text-muted-foreground">{exam.subject_name} · {exam.year}</div>
                <div className="text-xs text-muted-foreground mt-2">Avg {exam.average_percentage.toFixed(1)}% · Pass {exam.pass_rate.toFixed(0)}%</div>
              </Card>
            ))}
          </div>
        )}
        {/* My Drafts — cloud saved papers, accessible again */}
        <div className="space-y-3">
          <h3 className="font-semibold flex items-center gap-2">
            <CloudUpload className="size-5 text-primary" /> My Drafts — Cloud Saved
            {loadingDrafts && <span className="text-xs font-normal text-muted-foreground">loading...</span>}
          </h3>
          {drafts.length === 0 && !loadingDrafts ? (
            <Card className="p-6 text-center border-dashed">
              <p className="text-sm text-muted-foreground">No drafts yet. Create a paper in the editor and click “Upload to Cloud”.</p>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {drafts.map((d) => (
                <Card key={d.draft_id} className="p-4 border-border hover:border-primary/30 cursor-pointer" onClick={() => handleLoadDraft(d)}>
                  <div className="flex items-center justify-between mb-2">
                    <Badge variant="outline" className="text-xs">{d.subject_code}</Badge>
                    <span className="text-xs text-muted-foreground">{new Date(d.updated_at).toLocaleDateString()}</span>
                  </div>
                  <div className="font-medium text-sm truncate">{d.paper.exam}</div>
                  <div className="text-xs text-muted-foreground">{d.paper.year} · {d.question_count} Q · {d.total_marks} marks</div>
                  <div className="text-xs text-muted-foreground mt-1 truncate">ID: {d.draft_id}</div>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  // Split layout: left editor (65%) + right recommendations (35%)
  return (
    <div className="flex flex-col h-[calc(100vh-64px)]">
      {/* Top bar: exam switcher + total + exit */}
      <div className="flex items-center gap-3 px-6 py-3 border-b bg-background shrink-0">
        <Layers className="size-4 text-muted-foreground" />
        <Select
          value={`${selectedExam.course_code}-${selectedExam.year}`}
          onValueChange={(v) => {
            const ex = exams.find((e) => `${e.course_code}-${e.year}` === v);
            if (ex) handleSelectExam(ex);
          }}
        >
          <SelectTrigger className="w-[280px]"><SelectValue /></SelectTrigger>
          <SelectContent>{exams.map((e) => <SelectItem key={`${e.course_code}-${e.year}`} value={`${e.course_code}-${e.year}`}>{e.course_code} {e.year} — {e.session_name}</SelectItem>)}</SelectContent>
        </Select>
        <Button variant="ghost" size="sm" onClick={handleBackToSelector} className="ml-2">Change exam</Button>
        <div className="ml-auto flex items-center gap-3">
          <span className={`text-sm font-medium tabular-nums ${total === 100 ? "text-green-600" : total < 100 ? "text-amber-600" : "text-red-600"}`}>
            Total: {total}/100 {total !== 100 && "⚠️"}
          </span>
          <Button variant="outline" size="sm" onClick={handlePreview}><Eye className="size-4 mr-1" />Preview</Button>
          <Button variant="outline" size="sm" onClick={handleUpload} disabled={uploading}><CloudUpload className="size-4 mr-1" />{uploading ? "Uploading..." : currentDraftId ? "Update Cloud" : "Upload to Cloud"}</Button>
          <Button size="sm" onClick={handleDownload}><FileDown className="size-4 mr-1" />Download PDF</Button>
        </div>
      </div>

      <div className="flex flex-1 min-h-0">
        {/* Left 65%: Full paper editor */}
        <div className="w-[65%] overflow-y-auto p-6 space-y-4 border-r bg-muted/20">
          <div>
            <h2 className="font-semibold">{paper.exam} {paper.year}</h2>
            <p className="text-xs text-muted-foreground">Draft paper — editable. Total {total}/100</p>
          </div>
          {paper.questions.map((q) => (
            <Card key={q.question_number} id={`question-${q.question_number}`} className="p-4 space-y-3">
              <div className="flex items-center gap-2">
                <span className="font-semibold shrink-0">Question {q.question_number}</span>
                <Select
                  value={q.topic}
                  onValueChange={(v) => setPaper((prev) => ({ ...prev, questions: prev.questions.map((x) => (x.question_number === q.question_number ? { ...x, topic: v } : x)) }))}
                >
                  <SelectTrigger className="flex-1"><SelectValue /></SelectTrigger>
                  <SelectContent>{CANONICAL_TOPICS.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
                </Select>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setPaper((prev) => ({ ...prev, questions: renumberQuestions(prev.questions.filter((x) => x.question_number !== q.question_number)) }))}
                >
                  <X className="size-4" />
                </Button>
              </div>
              {q.parts.map((p) => (
                <div key={p.part} className="flex gap-2">
                  <span className="mt-2 text-sm font-medium shrink-0">{p.part})</span>
                  <Textarea
                    value={p.question}
                    onChange={(e) => setPaper((prev) => ({ ...prev, questions: prev.questions.map((x) => (x.question_number === q.question_number ? { ...x, parts: x.parts.map((y) => (y.part === p.part ? { ...y, question: e.target.value } : y)) } : x)) }))}
                    className="flex-1 min-h-[60px]"
                    placeholder="Question text..."
                  />
                  <Input
                    type="number"
                    value={p.max_marks}
                    onChange={(e) => setPaper((prev) => ({ ...prev, questions: prev.questions.map((x) => (x.question_number === q.question_number ? { ...x, parts: x.parts.map((y) => (y.part === p.part ? { ...y, max_marks: Number(e.target.value) || 0 } : y)) } : x)) }))}
                    className="w-20 shrink-0"
                    min={1}
                    max={40}
                  />
                  <Button
                    variant="ghost"
                    size="icon"
                    className="shrink-0"
                    onClick={() => setPaper((prev) => ({ ...prev, questions: renumberQuestions(prev.questions.map((x) => (x.question_number === q.question_number ? { ...x, parts: x.parts.filter((y) => y.part !== p.part) } : x)).filter((x) => x.parts.length > 0)) }))}
                  >
                    <X className="size-4" />
                  </Button>
                </div>
              ))}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPaper((prev) => ({ ...prev, questions: prev.questions.map((x) => (x.question_number === q.question_number ? { ...x, parts: [...x.parts, { part: String.fromCharCode(97 + x.parts.length), question: "", max_marks: 10 }] } : x)) }))}
              >
                <Plus className="size-4 mr-1" /> Add part
              </Button>
            </Card>
          ))}
          <Button
            onClick={() => setPaper((prev) => ({ ...prev, questions: renumberQuestions([...prev.questions, { question_number: prev.questions.length + 1, topic: "Structured Query Language (SQL)", parts: [{ part: "a", question: "", max_marks: 10 }] }]) }))}
            className="w-full"
            variant="outline"
          >
            <Plus className="size-4 mr-1" /> Add Custom Question
          </Button>
        </div>

        {/* Right 35%: Recommendations + Browse Bank */}
        <div className="w-[35%] overflow-y-auto p-4 space-y-4 bg-background">
          <Tabs value={rightTab} onValueChange={(v) => setRightTab(v as "recommended" | "browse")} className="w-full">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="recommended" className="text-xs">Recommended</TabsTrigger>
              <TabsTrigger value="browse" className="text-xs">Browse Bank</TabsTrigger>
            </TabsList>
            <TabsContent value="recommended" className="space-y-4 mt-4">
              {loadingRecs ? (
                <ProgressLoader steps={loadSteps} currentStep={currentStep} />
              ) : recommendations ? (
                <>
                  <Card className="p-3 border-border">
                    <div className="font-medium flex items-center gap-2 text-sm">
                      <AlertTriangle className="size-4 text-amber-500" /> Weak Areas to Assess
                    </div>
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {recommendations.ranked_weak_topics.map(([topic, weakness]) => (
                        <Badge
                          key={topic}
                          variant="outline"
                          className={weakness >= 0.4 ? "border-red-300 text-red-600 bg-red-50" : weakness >= 0.3 ? "border-amber-300 text-amber-600 bg-amber-50" : "border-border"}
                        >
                          {topic.split(" ").slice(0, 3).join(" ")} {(weakness * 100).toFixed(0)}%
                        </Badge>
                      ))}
                    </div>
                  </Card>

              {[
                { label: "High Priority", color: "bg-red-500", items: high },
                { label: "Medium Priority", color: "bg-amber-500", items: medium },
              ].map(({ label, color, items }) => (
                <div key={label} className="space-y-2">
                  <h3 className="font-semibold text-sm flex items-center gap-2">
                    <span className={`size-2 rounded-full ${color}`} /> {label} <span className="font-normal text-muted-foreground">({items.length})</span>
                  </h3>
                  {items.length === 0 ? (
                    <p className="text-xs text-muted-foreground">No {label.toLowerCase()} recommendations.</p>
                  ) : (
                    items.map((rec) => (
                      <Card key={rec.question_id} className="p-3 space-y-2 border-border">
                        <div className="flex flex-wrap gap-1">
                          <Badge variant="outline" className="text-[10px]">{rec.canonical_topic.slice(0, 30)}</Badge>
                          <Badge variant="secondary" className="text-[10px]">{rec.bloom_level}</Badge>
                          <Badge variant="outline" className="text-[10px]">{rec.marks || 10} m</Badge>
                          <PriorityBadge priority={rec.priority} />
                        </div>
                        <p className="text-xs line-clamp-3 leading-relaxed">{rec.text}</p>
                        <div className="text-[11px] text-muted-foreground bg-muted/50 rounded p-1.5">
                          Weak {rec.reason.weakness_pct}% · Tut {rec.reason.tutorial_count} · Exam {rec.reason.exam_recent_count} · Bloom {(rec.bloom_gap * 100).toFixed(0)}%
                        </div>
                        <div className="flex gap-1">
                          <Select value={insertTargets[rec.question_id] || "end"} onValueChange={(v) => setInsertTargets((s) => ({ ...s, [rec.question_id]: v }))}>
                            <SelectTrigger className="flex-1 h-7 text-xs"><SelectValue /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="end">Add as Q{paper.questions.length + 1}</SelectItem>
                              {paper.questions.map((q) => (
                                <SelectItem key={`q${q.question_number}`} value={`Q${q.question_number}`}>Insert as Q{q.question_number}</SelectItem>
                              ))}
                              {paper.questions.map((q) => (
                                <SelectItem key={`qp${q.question_number}`} value={`Q${q.question_number}-part`}>Add part to Q{q.question_number}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <Button size="sm" className="h-7" onClick={() => handleInsert(rec)}><Plus className="size-3 mr-1" />Add</Button>
                        </div>
                        <div className="flex gap-1">
                          <Button size="sm" variant="ghost" className="h-6 text-xs flex-1" onClick={() => setRejectedIds((s) => new Set(s).add(rec.question_id))}><X className="size-3 mr-1" />Reject</Button>
                        </div>
                      </Card>
                    ))
                  )}
                </div>
              ))}

               {low.length > 0 && (
                <details>
                  <summary className="font-semibold text-sm cursor-pointer">Low Priority ({low.length}) — expand</summary>
                  <div className="space-y-2 mt-2">
                    {low.map((rec) => (
                      <Card key={rec.question_id} className="p-2 text-xs border-border">
                        <p className="line-clamp-2">{rec.text}</p>
                        <Button size="sm" variant="ghost" className="h-6 mt-1" onClick={() => handleInsert(rec)}><Plus className="size-3 mr-1" />Add</Button>
                      </Card>
                    ))}
                  </div>
                </details>
              )}
            </>
          ) : null}
            </TabsContent>
            <TabsContent value="browse" className="space-y-3 mt-4">
              <div className="flex gap-2">
                <Select value={bankFilters.source_type || "all"} onValueChange={(v) => setBankFilters((s) => ({ ...s, source_type: v === "all" ? undefined : v }))}>
                  <SelectTrigger className="flex-1 h-8 text-xs"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All sources</SelectItem>
                    <SelectItem value="tutorial">Tutorial</SelectItem>
                    <SelectItem value="exam">Exam</SelectItem>
                    <SelectItem value="lecture">Lecture objective</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={bankFilters.year ? String(bankFilters.year) : "all"} onValueChange={(v) => setBankFilters((s) => ({ ...s, year: v === "all" ? undefined : Number(v) }))}>
                  <SelectTrigger className="w-[120px] h-8 text-xs"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All years</SelectItem>
                    <SelectItem value="2024">2024</SelectItem>
                    <SelectItem value="2023">2023</SelectItem>
                    <SelectItem value="2022">2022</SelectItem>
                    <SelectItem value="2019">2019</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {loadingBank ? (
                <p className="text-xs text-muted-foreground">Loading question bank...</p>
              ) : bankItems.length === 0 ? (
                <p className="text-xs text-muted-foreground">No questions. Adjust filters or switch to Recommended tab.</p>
              ) : (
                <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
                  {bankItems.map((item) => (
                    <Card key={item.question_id} className="p-3 space-y-2 border-border">
                      <div className="flex flex-wrap gap-1">
                        <Badge variant="outline" className="text-[10px]">{item.canonical_topic.slice(0, 28)}</Badge>
                        <Badge variant="secondary" className="text-[10px]">{item.bloom_level}</Badge>
                        <Badge variant="outline" className="text-[10px]">{item.source_type} {item.year}</Badge>
                        {item.marks > 0 && <Badge variant="outline" className="text-[10px]">{item.marks} m</Badge>}
                      </div>
                      <p className="text-xs line-clamp-3 leading-relaxed">{item.text}</p>
                      <p className="text-[11px] text-muted-foreground truncate">{item.subtopic}</p>
                      <div className="flex gap-1">
                        <Select value={insertTargets[item.question_id] || "end"} onValueChange={(v) => setInsertTargets((s) => ({ ...s, [item.question_id]: v }))}>
                          <SelectTrigger className="flex-1 h-7 text-xs"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="end">Add as Q{paper.questions.length + 1}</SelectItem>
                            {paper.questions.map((q) => <SelectItem key={`bq${q.question_number}`} value={`Q${q.question_number}`}>Insert as Q{q.question_number}</SelectItem>)}
                            {paper.questions.map((q) => <SelectItem key={`bqp${q.question_number}`} value={`Q${q.question_number}-part`}>Add part to Q{q.question_number}</SelectItem>)}
                          </SelectContent>
                        </Select>
                        <Button size="sm" className="h-7" onClick={() => handleInsertFromBank(item)}><Plus className="size-3 mr-1" />Add</Button>
                      </div>
                    </Card>
                  ))}
                </div>
              )}
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}
