import { useState, useEffect, useCallback, useRef, type Dispatch, type SetStateAction } from "react";
import { BrandOrb } from "./BrandOrb";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, Plus, X, BookOpen, ChevronRight, Layers, FileDown, Eye, CloudUpload } from "lucide-react";
import { useHideSidebar } from "../App";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Input } from "./ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { type LoadStep } from "./ProgressLoader";
import { AIPageBanner } from "./AIBrand";
import {
  fetchExams,
  fetchQuestionBank,
  createExamDraft,
  listExamDrafts,
  type ExamListItem,
  type QuestionBankItem,
  type ExamDraft,
} from "../api/lecturerApi";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./ui/tabs";
import { toast } from "sonner";

import { CandidateActions, DropZone, MoveControls, type StructureActions } from "./ExamStructureControls";
import { placeQuestion, renumberQuestions, type PlacementSource, type PlacementTarget } from "./examStructure";
import { ExamCreatorAssistant, PartReviewEditor } from "./ExamCreatorAssistant";
import { CustomQuestionGenerator } from "./CustomQuestionGenerator";
import { QuestionTextInput } from "./QuestionTextInput";
import { defaultBlueprint, type Part, type PaperQuestion, type Paper } from "../api/examCreatorApi";
export type { Part, PaperQuestion, Paper } from "../api/examCreatorApi";

function totalMarks(paper: Paper): number {
  return paper.questions.flatMap((q) => q.parts).reduce((s, p) => s + (Number(p.max_marks) || 0), 0);
}

function PremiumExamLoader({ steps, currentStep }: { steps: LoadStep[]; currentStep: number }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 space-y-6">
      <BrandOrb state="searching" size={64} aria-label="Loading exams" />
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
  const [paper, setPaperState] = useState<Paper>({ exam: "New exam", year: new Date().getFullYear(), questions: [], blueprint: defaultBlueprint() });
  const [selectedQuestion, setSelectedQuestion] = useState<number | null>(null);
  const [dragged, setDragged] = useState<PlacementSource | null>(null);
  const [undoPaper, setUndoPaper] = useState<Paper | null>(null);
  const [placementMessage, setPlacementMessage] = useState("");
  const setPaper: Dispatch<SetStateAction<Paper>> = useCallback(value => {
    setUndoPaper(null);
    setDragged(null);
    setPlacementMessage("");
    setPaperState(value);
  }, []);
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
    setSelectedQuestion(null);
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
    setSelectedQuestion(null);
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

  const insert = (source: PlacementSource, target: PlacementTarget = { question: paper.questions.length }) => {
    try {
      const questions = placeQuestion(paper.questions, source, target);
      if (JSON.stringify(questions) === JSON.stringify(paper.questions)) return;
      setUndoPaper(paper);
      setPaperState({ ...paper, questions });
      setSelectedQuestion(null);
      setPlacementMessage(source.kind === "candidate" ? "Question added to paper." : "Paper order updated.");
      const number = Math.min(target.question + 1, questions.length);
      requestAnimationFrame(() => {
        const element = document.getElementById(`question-${number}`);
        element?.scrollIntoView?.({ block: "nearest" });
        element?.classList.add("ring-2", "ring-primary");
        setTimeout(() => element?.classList.remove("ring-2", "ring-primary"), 1200);
      });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to place question");
    } finally {
      setDragged(null);
    }
  };
  const structureActions: StructureActions = {
    insert,
    selected: paper.questions.find(q => q.question_number === selectedQuestion),
    startDrag: (source, event) => {
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", "Exam question");
      setDragged(source);
    },
    endDrag: () => setDragged(null),
  };
  const draggedTopic = dragged?.kind === "candidate" ? dragged.topic : dragged ? paper.questions[dragged.question]?.topic : undefined;
  const dropAt = (target: PlacementTarget) => { if (dragged) insert(dragged, target); };

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
                      <Badge variant="secondary" className="backdrop-blur">{exam.student_count == null ? "Student count unavailable" : `${exam.student_count} students`}</Badge>
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
          <Button variant="outline" size="sm" title="Undo the latest move or insertion before making another edit" disabled={!undoPaper} onClick={() => {
            if (undoPaper) setPaper(undoPaper);
            setSelectedQuestion(null);
            setPlacementMessage("Last structural change undone.");
          }}>Undo move / add</Button>
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
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">Drag questions into your paper, or use Add to paper. Select a question to add matching subparts.</p>
            <p role="status" className="text-sm text-primary">{placementMessage}</p>
            {!paper.questions.length && <div className="rounded-lg border border-dashed p-6 text-center text-muted-foreground">Your paper is empty. Add a suggested question or write a custom question below.</div>}
          </div>
          <AnimatePresence>
            {paper.questions.map((q, idx) => (
              <motion.div key={q.question_number} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.3, delay: idx * 0.03 }}>
                <DropZone active={!!dragged} label={`Insert as Question ${q.question_number}`} onDrop={() => dropAt({ question: idx })} />
                <Card id={`question-${q.question_number}`} className="p-4 space-y-3 bg-card/80 backdrop-blur border-border/60 hover:border-primary/20 hover:shadow-md transition-all">
              <div className="flex flex-wrap items-center gap-2">
                <MoveControls label={`question ${q.question_number}`} source={{ kind: "question", question: idx }} actions={structureActions}
                  up={idx > 0 ? { question: idx - 1 } : undefined} down={idx < paper.questions.length - 1 ? { question: idx + 2 } : undefined} />
                <Button variant={selectedQuestion === q.question_number ? "secondary" : "outline"} size="sm" aria-pressed={selectedQuestion === q.question_number}
                  title="Select this question to add matching subparts" onClick={() => setSelectedQuestion(selectedQuestion === q.question_number ? null : q.question_number)}>Question {q.question_number}{selectedQuestion === q.question_number ? " · Selected" : ""}</Button>
                <Input aria-label={`Question ${q.question_number} topic`} value={q.topic}
                  onChange={e => setPaper(prev => ({ ...prev, questions: prev.questions.map(x => x.question_number === q.question_number ? { ...x, topic: e.target.value, parts: x.parts.map(p => ({ ...p, review_status: "needs_review" })) } : x) }))} />
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Remove question ${q.question_number}`}
                  onClick={() => { setSelectedQuestion(null); setPaper((prev) => ({ ...prev, questions: renumberQuestions(prev.questions.filter((x) => x.question_number !== q.question_number)) })); }}
                >
                  <X className="size-4" />
                </Button>
              </div>
              {q.parts.map((p, partIndex) => (
                <div key={p.part} className="space-y-2">
                <DropZone active={!!dragged && dragged.kind !== "question" && draggedTopic === q.topic} label={`Insert part before ${p.part})`} onDrop={() => dropAt({ question: idx, part: partIndex })} />
                <div className="flex flex-wrap items-center gap-2">
                  <MoveControls label={`Q${q.question_number} part ${p.part}`} source={{ kind: "part", question: idx, part: partIndex }} actions={structureActions}
                    up={partIndex > 0 ? { question: idx, part: partIndex - 1 } : undefined}
                    down={partIndex < q.parts.length - 1 ? { question: idx, part: partIndex + 2 } : undefined} />
                  <span className="text-sm font-medium">Part {p.part}</span>
                  {q.parts.length > 1 && <Button size="sm" variant="ghost" onClick={() => insert({ kind: "part", question: idx, part: partIndex })}>Make separate question</Button>}
                </div>
                <div className="flex flex-wrap items-start gap-2">
                  <div className="relative min-w-0 flex-1">
                  <QuestionTextInput
                    aria-label={`Q${q.question_number} part ${p.part} text`}
                    questionId={p.question_id}
                    value={p.question}
                    onChange={(e) => setPaper((prev) => ({ ...prev, questions: prev.questions.map((x) => (x.question_number === q.question_number ? { ...x, parts: x.parts.map((y) => (y.part === p.part ? { ...y, question: e.target.value, review_status: "needs_review" } : y)) } : x)) }))}
                    className="min-h-[100px] pr-14"
                    placeholder="Question text..."
                  />
                  <CustomQuestionGenerator courseCode={selectedExam.course_code} paper={paper} question={q} part={p}
                    onGenerated={candidate => setPaper(prev => ({ ...prev, questions: prev.questions.map(x => x === q
                      ? { ...x, topic: candidate.topic, parts: x.parts.map(y => y === p
                        ? { ...candidate, part: y.part, question: candidate.text, max_marks: candidate.marks, review_status: "needs_review" }
                        : y) } : x) }))} />
                  </div>
                  <Input
                    type="number"
                    aria-label={`Q${q.question_number} part ${p.part} marks`}
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
                    aria-label={`Remove Q${q.question_number} part ${p.part}`}
                    onClick={() => { setSelectedQuestion(null); setPaper((prev) => ({ ...prev, questions: renumberQuestions(prev.questions.map((x) => (x.question_number === q.question_number ? { ...x, parts: x.parts.filter((y) => y.part !== p.part) } : x)).filter((x) => x.parts.length > 0)) })); }}
                  >
                    <X className="size-4" />
                  </Button>
                </div>
                {paper.questions.some(other => other !== q && other.topic === q.topic) && <label className="flex items-center gap-2 text-xs text-muted-foreground">Move part to
                  <select aria-label={`Move Q${q.question_number} part ${p.part} to question`} className="rounded border bg-background p-2" value="" onChange={e => {
                    const target = paper.questions[Number(e.target.value)];
                    insert({ kind: "part", question: idx, part: partIndex }, { question: Number(e.target.value), part: target.parts.length });
                  }}><option value="" disabled>Choose question</option>{paper.questions.map((other, i) => other !== q && other.topic === q.topic ? <option key={i} value={i}>Question {other.question_number}</option> : null)}</select>
                </label>}
                </div>
              ))}
              <DropZone active={!!dragged && dragged.kind !== "question" && draggedTopic === q.topic} label={`Add part to Question ${q.question_number} (${q.topic})`} onDrop={() => dropAt({ question: idx, part: q.parts.length })} />
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
          <DropZone active={!!dragged} label="Add new question at end" onDrop={() => dropAt({ question: paper.questions.length })} />
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
            <TabsContent value="recommended" forceMount hidden={rightTab !== "recommended"} className="space-y-4 mt-4">
              <ExamCreatorAssistant key={`${selectedExam.course_code}-${currentDraftId ?? "new"}`} courseCode={selectedExam.course_code} paper={paper} setPaper={setPaper} structureActions={structureActions} />
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
                <p role="status" className="flex items-center gap-2 text-xs text-muted-foreground"><BrandOrb state="searching" size={20} aria-hidden="true" />Loading question bank...</p>
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
                      <CandidateActions topic={item.canonical_topic} part={{ part: "a", question: item.text, max_marks: item.marks > 0 ? item.marks : 10,
                        question_id: item.question_id, bloom_level: item.bloom_level, review_status: "needs_review" }} actions={structureActions} />
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

