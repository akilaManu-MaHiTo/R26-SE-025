import { useState, useEffect, useCallback, useRef } from "react";
import { ThinkingOrb } from "thinking-orbs";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, Plus, X, BookOpen, ChevronRight, Layers, FileDown, Eye, CloudUpload } from "lucide-react";
import { useHideSidebar } from "../App";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { type LoadStep } from "./ProgressLoader";
import { AIPageBanner } from "./AIBrand";
import {
  fetchExams,
  fetchQuestionBank,
  createExamDraft,
  listExamDrafts,
  type ExamListItem,
  type Recommendation,
  type QuestionBankItem,
  type ExamDraft,
} from "../api/lecturerApi";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./ui/tabs";
import { toast } from "sonner";

import { ExamCreatorAssistant, PartReviewEditor } from "./ExamCreatorAssistant";
import { defaultBlueprint, type Part, type PaperQuestion, type Paper } from "../api/examCreatorApi";
export type { Part, PaperQuestion, Paper } from "../api/examCreatorApi";

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

function PremiumExamLoader({ steps, currentStep }: { steps: LoadStep[]; currentStep: number }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 space-y-6">
      <ThinkingOrb state="searching" size={64} aria-label="Loading exams" />
      <div className="space-y-2 text-center" role="status">
        <motion.p key={currentStep} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="text-sm font-medium">
          {steps[currentStep]?.label || "Loading..."}
        </motion.p>
        <div className="flex gap-1.5 justify-center">
          {steps.map((_, i) => (
            <motion.div key={i} className={`h-1.5 rounded-full ${i === currentStep ? "bg-primary w-6" : i < currentStep ? "bg-primary/60 w-1.5" : "bg-muted w-1.5"}`} animate={{ scale: i === currentStep ? 1.2 : 1 }} transition={{ duration: 0.3 }} />
          ))}
        </div>
      </div>
    </div>
  );
}

export function ExamCreator() {
  const setHideSidebar = useHideSidebar()?.setHide;
  const [exams, setExams] = useState<ExamListItem[]>([]);
  const [selectedExam, setSelectedExam] = useState<ExamListItem | null>(null);
  const [paper, setPaper] = useState<Paper>({ exam: "New exam", year: new Date().getFullYear(), questions: [], blueprint: defaultBlueprint() });
  const [insertTargets, setInsertTargets] = useState<Record<string, string>>({});
  const [loadingExams, setLoadingExams] = useState(true);
  const [loadSteps, setLoadSteps] = useState<LoadStep[]>([]);
  const currentStep = 0;
  const [rightTab, setRightTab] = useState<"recommended" | "browse">("recommended");
  const [bankFilters, setBankFilters] = useState<{ source_type?: string; year?: number }>({});
  const [bankItems, setBankItems] = useState<QuestionBankItem[]>([]);
  const [loadingBank, setLoadingBank] = useState(false);
  const [drafts, setDrafts] = useState<ExamDraft[]>([]);
  const [loadingDrafts, setLoadingDrafts] = useState(false);
  const [currentDraftId, setCurrentDraftId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const savedPaper = useRef(JSON.stringify(paper));
  const total = totalMarks(paper);
  const targetMarks = paper.blueprint?.total_marks || 100;

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

  const handleSelectExam = useCallback((exam: ExamListItem) => {
    if (JSON.stringify(paper) !== savedPaper.current && !window.confirm("Start a new draft? Save your current paper to cloud first if you want to keep it.")) return;
    setSelectedExam(exam);
    setCurrentDraftId(null);
    setBankItems([]);
    setBankFilters({});
    setInsertTargets({});
    setRightTab("recommended");
    const nextPaper: Paper = { exam: `${exam.course_code} – ${exam.subject_name}`, year: new Date().getFullYear(),
      questions: [], blueprint: defaultBlueprint(),
      source_exam: { session_name: exam.session_name, year: exam.year, month: exam.month, semester: exam.semester } };
    savedPaper.current = JSON.stringify(nextPaper);
    setPaper(nextPaper);
    setHideSidebar?.(true);
  }, [setHideSidebar, paper]);

  const handleBackToSelector = useCallback(() => {
    setHideSidebar?.(false);
    setSelectedExam(null);
  }, [setHideSidebar]);

  useEffect(() => {
    return () => setHideSidebar?.(false);
  }, [setHideSidebar]);

  useEffect(() => {
    if (rightTab !== "browse" || !selectedExam) return;
    let ignore = false;
    setLoadingBank(true);
    fetchQuestionBank({ ...bankFilters, course_code: selectedExam.course_code, limit: 200 })
      .then(items => { if (!ignore) setBankItems(items.filter(item => item.source_type !== "lecture")); })
      .catch(() => { if (!ignore) { setBankItems([]); toast.error("Question bank unavailable"); } })
      .finally(() => { if (!ignore) setLoadingBank(false); });
    return () => { ignore = true; };
  }, [rightTab, bankFilters, selectedExam]);

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
    setUploading(true);
    try {
      const subject = selectedExam?.course_code || paper.exam.split(" ")[0] || "IT2040";
      const draft = await createExamDraft(subject, paper, currentDraftId || undefined);
      savedPaper.current = JSON.stringify(paper);
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
    if (JSON.stringify(paper) !== savedPaper.current && !window.confirm("Load this saved draft and replace the current editor contents?")) return;
    const nextPaper = { ...draft.paper, blueprint: draft.paper.blueprint ?? defaultBlueprint() };
    savedPaper.current = JSON.stringify(nextPaper);
    setPaper(nextPaper);
    setBankItems([]);
    setBankFilters({});
    setRightTab("recommended");
    setCurrentDraftId(draft.draft_id);
    setHideSidebar?.(true);
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

  };

  const handleInsert = (rec: Recommendation) => {
    if (paper.questions.some(q => q.parts.some(p => p.question_id === rec.question_id))) {
      toast.error("This question is already in the draft"); return;
    }
    const target = insertTargets[rec.question_id] || "end";
    if (target.includes("-part")) {
      const parent = paper.questions.find(q => q.question_number === Number(target.split("Q")[1].split("-")[0]));
      if (parent && parent.topic !== rec.canonical_topic) {
        toast.error("Add this topic as a separate question so blueprint coverage stays accurate");
        return;
      }
    }
    setPaper((prev) => {
      let qs = [...prev.questions];
      const newPart: Part = { part: "a", question: rec.text, max_marks: rec.marks > 0 ? rec.marks : 10, question_id: rec.question_id, bloom_level: rec.bloom_level, review_status: "needs_review" };
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

  const makePdf = async (markingScheme = false) => {
    const { default: jsPDF } = await import("jspdf");
    const doc = new jsPDF();
    let y = 15;
    const write = (text: string, size = 10) => {
      doc.setFontSize(size);
      for (const line of doc.splitTextToSize(text, 185)) {
        if (y > 277) { doc.addPage(); y = 15; }
        doc.text(line, 12, y);
        y += size === 14 ? 7 : 5;
      }
      y += 3;
    };
    write(`${paper.exam} ${paper.year}`, 14);
    write(markingScheme ? "LECTURER COPY - Answers and marking scheme" : "DRAFT EXAMINATION PAPER");
    write(`Total marks: ${total} | Duration: ${paper.blueprint?.duration_minutes ?? 180} minutes`);
    paper.questions.forEach(q => {
      write(`Question ${q.question_number} (${q.topic})`, 12);
      q.parts.forEach(p => {
        write(`${p.part}) ${p.question} [${p.max_marks} marks]`);
        if (markingScheme) {
          write(`Review: ${p.review_status === "approved" ? "Approved" : "Pending lecturer review"}`);
          write(`Answer: ${p.model_answer || "Not supplied"}`);
          (p.marking_scheme ?? []).forEach(c => write(`${c.criterion} [${c.marks} marks]`));
          if (p.sources?.length) write(`Sources: ${p.sources.map(source => source.source_id).join(", ")}`);
        }
      });
    });
    return doc;
  };
  const handleDownload = async (markingScheme = false) => {
    try {
      const doc = await makePdf(markingScheme);
      doc.save(`${paper.exam.replace(/\s/g, "_")}_${paper.year}${markingScheme ? "_marking_scheme" : ""}.pdf`);
    } catch { toast.error("Could not export PDF"); }
  };
  const handlePreview = async () => {
    const previewWindow = window.open("", "_blank");
    try {
      const doc = await makePdf();
      if (previewWindow) previewWindow.location.href = String(doc.output("bloburl"));
      else toast.error("Allow pop-ups to preview the paper");
    } catch { previewWindow?.close(); toast.error("Could not preview PDF"); }
  };

  // Session, month and semester distinguish exams in the same academic year.
  function examKey(exam: ExamListItem) {
    return `${exam.course_code}-${exam.session_name}-${exam.year}-${exam.month}-${exam.semester}`;
  }

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
          <PremiumExamLoader steps={loadSteps} currentStep={currentStep} />
        ) : exams.length === 0 ? (
          <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }}>
            <Card className="p-12 text-center border-border bg-gradient-to-b from-card to-muted/20">
              <BookOpen className="h-12 w-12 mx-auto mb-4 text-muted-foreground/40" />
              <p className="text-muted-foreground">No exams found. Ingest submissions first.</p>
            </Card>
          </motion.div>
        ) : (
          <motion.div layout className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <AnimatePresence>
              {exams.map((exam, idx) => (
                <motion.div
                  key={examKey(exam)}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.35, delay: idx * 0.04 }}
                  whileHover={{ y: -4, transition: { duration: 0.2 } }}
                >
                  <Card
                    className="group p-5 border-border bg-card/80 backdrop-blur hover:border-primary/30 hover:shadow-lg hover:shadow-primary/5 transition-all duration-300 cursor-pointer h-full"
                    onClick={() => handleSelectExam(exam)}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className="size-10 rounded-xl bg-gradient-to-br from-primary to-primary/70 text-primary-foreground flex items-center justify-center shadow-md group-hover:shadow-primary/20 transition-shadow">
                        <Sparkles className="size-5" />
                      </div>
                      <Badge variant="secondary" className="backdrop-blur">{exam.student_count} students</Badge>
                    </div>
                    <div className="font-semibold">{exam.course_code} — {exam.session_name}</div>
                    <div className="text-sm text-muted-foreground">{exam.subject_name} · {exam.year}</div>
                    <div className="h-1.5 bg-muted rounded-full overflow-hidden mt-3">
                      <motion.div initial={{ width: 0 }} animate={{ width: `${Math.min(exam.average_percentage ?? 0, 100)}%` }} transition={{ duration: 0.8, delay: 0.3 + idx * 0.05, ease: "easeOut" }} className="h-full bg-gradient-to-r from-primary to-primary/80 rounded-full" />
                    </div>
                    <div className="text-xs text-muted-foreground mt-2">Avg {exam.average_percentage == null ? "N/A" : `${exam.average_percentage.toFixed(1)}%`} · Pass {exam.pass_rate == null ? "N/A" : `${exam.pass_rate.toFixed(0)}%`}</div>
                  </Card>
                </motion.div>
              ))}
            </AnimatePresence>
          </motion.div>
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
      {/* Top bar: premium exam switcher + total */}
      <div className="flex flex-wrap items-center gap-3 px-4 py-3 border-b bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60 shrink-0 sticky top-0 z-10">
        <Layers className="size-4 text-muted-foreground" />
        <Select
          disabled={uploading}
          value={examKey(selectedExam)}
          onValueChange={(v) => {
            const ex = exams.find((e) => examKey(e) === v);
            if (ex) handleSelectExam(ex);
          }}
        >
          <SelectTrigger className="w-[240px]"><SelectValue /></SelectTrigger>
          <SelectContent>{exams.map((e) => <SelectItem key={examKey(e)} value={examKey(e)}>{e.course_code} {e.year} — {e.session_name}</SelectItem>)}</SelectContent>
        </Select>
        <Button variant="ghost" size="sm" onClick={handleBackToSelector} disabled={uploading} className="ml-2">Change exam</Button>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <motion.span key={total} initial={{ scale: 0.9 }} animate={{ scale: 1 }} transition={{ duration: 0.2 }} className={`text-sm font-medium tabular-nums ${total === targetMarks ? "text-green-600" : total < targetMarks ? "text-amber-600" : "text-red-600"}`}>
            Total: {total}/{targetMarks} {total !== targetMarks && "⚠️"}
          </motion.span>
          <Button variant="outline" size="sm" onClick={handlePreview}><Eye className="size-4 mr-1" />Preview</Button>
          <Button variant="outline" size="sm" onClick={handleUpload} disabled={uploading}><CloudUpload className="size-4 mr-1" />{uploading ? "Uploading..." : currentDraftId ? "Update Cloud" : "Upload to Cloud"}</Button>
          <Button variant="outline" size="sm" onClick={() => handleDownload(true)}>Marking scheme</Button>
          <Button size="sm" onClick={() => handleDownload()}><FileDown className="size-4 mr-1" />Download PDF</Button>
        </div>
      </div>

      <div className="flex flex-col lg:flex-row flex-1 min-h-0 overflow-y-auto lg:overflow-hidden">
        {/* Left 65%: Full paper editor — premium */}
        <div className="w-full lg:w-[60%] lg:overflow-y-auto p-6 space-y-4 border-r bg-gradient-to-b from-muted/30 via-muted/10 to-background">
          <motion.div key={`${paper.exam}-${paper.year}`} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }} className="rounded-xl border bg-card/60 backdrop-blur p-4">
            <h2 className="font-semibold bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text">{paper.exam} {paper.year}</h2>
            <p className="text-xs text-muted-foreground">Draft paper — editable. Total <span className={total === targetMarks ? "text-green-600 font-medium" : total < targetMarks ? "text-amber-600" : "text-red-600"}>{total}/{targetMarks}</span></p>
            <div className="h-1.5 bg-muted rounded-full overflow-hidden mt-2">
              <motion.div initial={{ width: 0 }} animate={{ width: `${Math.min((total / targetMarks) * 100, 100)}%` }} transition={{ duration: 0.6, ease: "easeOut" }} className={`h-full rounded-full ${total === targetMarks ? "bg-gradient-to-r from-green-500 to-emerald-500" : total < targetMarks ? "bg-gradient-to-r from-amber-500 to-orange-500" : "bg-gradient-to-r from-red-500 to-red-400"}`} />
            </div>
          </motion.div>
          <AnimatePresence>
            {paper.questions.map((q, idx) => (
              <motion.div key={q.question_number} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.3, delay: idx * 0.03 }}>
                <Card id={`question-${q.question_number}`} className="p-4 space-y-3 bg-card/80 backdrop-blur border-border/60 hover:border-primary/20 hover:shadow-md transition-all">
              <div className="flex items-center gap-2">
                <span className="font-semibold shrink-0">Question {q.question_number}</span>
                <Input aria-label={`Question ${q.question_number} topic`} value={q.topic}
                  onChange={e => setPaper(prev => ({ ...prev, questions: prev.questions.map(x => x.question_number === q.question_number ? { ...x, topic: e.target.value, parts: x.parts.map(p => ({ ...p, review_status: "needs_review" })) } : x) }))} />
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
                    onChange={(e) => setPaper((prev) => ({ ...prev, questions: prev.questions.map((x) => (x.question_number === q.question_number ? { ...x, parts: x.parts.map((y) => (y.part === p.part ? { ...y, question: e.target.value, review_status: "needs_review" } : y)) } : x)) }))}
                    className="flex-1 min-h-[60px]"
                    placeholder="Question text..."
                  />
                  <Input
                    type="number"
                    value={p.max_marks}
                    onChange={(e) => setPaper((prev) => ({ ...prev, questions: prev.questions.map((x) => (x.question_number === q.question_number ? { ...x, parts: x.parts.map((y) => (y.part === p.part ? { ...y, max_marks: Number(e.target.value) || 0, review_status: "needs_review" } : y)) } : x)) }))}
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
              {q.parts.map(p => <PartReviewEditor key={`review-${p.part}`} part={p} onChange={changes => setPaper(prev => ({ ...prev,
                questions: prev.questions.map(x => x.question_number === q.question_number ? { ...x, parts: x.parts.map(y => y.part === p.part ? { ...y, ...changes } : y) } : x),
              }))} />)}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPaper((prev) => ({ ...prev, questions: prev.questions.map((x) => (x.question_number === q.question_number ? { ...x, parts: [...x.parts, { part: String.fromCharCode(97 + x.parts.length), question: "", max_marks: 10 }] } : x)) }))}
              >
                <Plus className="size-4 mr-1" /> Add part
              </Button>
                </Card>
              </motion.div>
            ))}
          </AnimatePresence>
          <motion.div whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.99 }}>
            <Button
              onClick={() => setPaper((prev) => ({ ...prev, questions: renumberQuestions([...prev.questions, { question_number: prev.questions.length + 1, topic: "", parts: [{ part: "a", question: "", max_marks: 10 }] }]) }))}
              className="w-full border-dashed"
              variant="outline"
            >
              <Plus className="size-4 mr-1" /> Add Custom Question
            </Button>
          </motion.div>
        </div>

        {/* Right 35%: Recommendations + Browse Bank */}
        <div className="w-full lg:w-[40%] lg:overflow-y-auto p-4 space-y-4 bg-background">
          <Tabs value={rightTab} onValueChange={(v) => setRightTab(v as "recommended" | "browse")} className="w-full">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="recommended" className="text-xs">Recommended</TabsTrigger>
              <TabsTrigger value="browse" className="text-xs">Browse Bank</TabsTrigger>
            </TabsList>
            <TabsContent value="recommended" className="space-y-4 mt-4">
              <ExamCreatorAssistant key={`${selectedExam.course_code}-${currentDraftId ?? "new"}`} courseCode={selectedExam.course_code} paper={paper} setPaper={setPaper} />
            </TabsContent>
            <TabsContent value="browse" className="space-y-3 mt-4">
              <div className="flex gap-2">
                <Select value={bankFilters.source_type || "all"} onValueChange={(v) => setBankFilters((s) => ({ ...s, source_type: v === "all" ? undefined : v }))}>
                  <SelectTrigger className="flex-1 h-8 text-xs"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All sources</SelectItem>
                    <SelectItem value="tutorial">Tutorial</SelectItem>
                    <SelectItem value="exam">Exam</SelectItem>
                    <SelectItem value="generated">Generated candidate</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={bankFilters.year ? String(bankFilters.year) : "all"} onValueChange={(v) => setBankFilters((s) => ({ ...s, year: v === "all" ? undefined : Number(v) }))}>
                  <SelectTrigger className="w-[120px] h-8 text-xs"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All years</SelectItem>
                    {Array.from(new Set(exams.filter(e => e.course_code === selectedExam.course_code).map(e => e.year))).sort((a, b) => b - a).map(year => <SelectItem key={year} value={String(year)}>{year}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              {loadingBank ? (
                <p role="status" className="flex items-center gap-2 text-xs text-muted-foreground"><ThinkingOrb state="searching" size={20} aria-hidden="true" />Loading question bank...</p>
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
                      <p className="text-xs leading-relaxed whitespace-pre-wrap break-words max-h-64 overflow-y-auto pr-1 border rounded bg-muted/20 p-1.5">{item.text}</p>
                      <p className="text-[11px] text-muted-foreground whitespace-pre-wrap break-words">{item.subtopic}</p>
                      <div className="flex gap-1">
                        <Select value={insertTargets[item.question_id] || "end"} onValueChange={(v) => setInsertTargets((s) => ({ ...s, [item.question_id]: v }))}>
                          <SelectTrigger className="flex-1 h-7 text-xs"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="end">Add as Q{paper.questions.length + 1}</SelectItem>
                            {paper.questions.map((q) => <SelectItem key={`bq${q.question_number}`} value={`Q${q.question_number}`}>Insert as Q{q.question_number}</SelectItem>)}
                            {paper.questions.filter(q => q.topic === item.canonical_topic).map((q) => <SelectItem key={`bqp${q.question_number}`} value={`Q${q.question_number}-part`}>Add part to Q{q.question_number}</SelectItem>)}
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

