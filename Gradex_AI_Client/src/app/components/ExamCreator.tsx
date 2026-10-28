import { useState, useEffect, useCallback, useRef, type Dispatch, type SetStateAction } from "react";
import { BrandOrb } from "./BrandOrb";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft, BookOpen, ChevronRight, CloudUpload, Eye, FileDown, FileText, Layers,
  Plus, Sparkles, Target, Undo2, X,
} from "lucide-react";
import { useHideSidebar } from "../App";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Input } from "./ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { type LoadStep } from "./ProgressLoader";
import { PremiumExamLoader } from "./PremiumExamLoader";
import pulseSomnolentSvg from "./animations/bloub-galet-somnolent-turquoise-anime.svg";
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

function questionMarks(question: PaperQuestion): number {
  return question.parts.reduce((sum, part) => sum + (Number(part.max_marks) || 0), 0);
}

function formatAverage(value: number | null | undefined): string {
  return value == null ? "N/A" : `${value.toFixed(1)}%`;
}

function formatPassRate(value: number | null | undefined): string {
  return value == null ? "N/A" : `${value.toFixed(0)}%`;
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
  const partCount = paper.questions.flatMap(q => q.parts).length;
  const marksComplete = total === targetMarks;
  const marksOver = total > targetMarks;
  const marksTone = marksComplete ? "text-emerald-600 dark:text-emerald-400" : marksOver ? "text-destructive" : "text-amber-600 dark:text-amber-400";
  const progressTone = marksComplete ? "bg-emerald-500" : marksOver ? "bg-destructive" : "bg-amber-500";

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
      <div className="mx-auto w-full max-w-[1400px] px-5 py-8 md:px-8 lg:py-10">
        <div className="mb-8 space-y-6">
          <div className="flex flex-wrap items-start justify-between gap-5">
            <div className="max-w-2xl">
              <h2 className="text-2xl font-semibold tracking-tight text-foreground md:text-3xl">Create your next exam</h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Choose a course exam, then build a balanced paper with recommendations drawn from student analytics,
                curriculum coverage and previous assessments.
              </p>
            </div>
            <img
              src={pulseSomnolentSvg}
              alt="PULSE·AI"
              className="size-12 shrink-0 object-contain"
            />
          </div>

          <div className="grid gap-5 rounded-2xl border border-border bg-card p-5 sm:grid-cols-3">
            {[
              { title: "Choose an exam", detail: "Start from a course and session" },
              { title: "Build the paper", detail: "Add recommended or custom questions" },
              { title: "Review and export", detail: "Check marks, then download a PDF" },
            ].map((step, index) => (
              <div key={step.title} className="flex items-start gap-3">
                <span className="flex size-7 shrink-0 items-center justify-center rounded-full border border-border bg-background text-xs font-semibold tabular-nums">
                  {index + 1}
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-foreground">{step.title}</p>
                  <p className="mt-0.5 text-xs leading-5 text-muted-foreground">{step.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <section className="space-y-4">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h3 className="text-base font-semibold tracking-tight">Available exams</h3>
              <p className="mt-1 text-xs text-muted-foreground">
                {loadingExams ? "Loading your course exams…" : `${exams.length} exam${exams.length === 1 ? "" : "s"} ready to build from`}
              </p>
            </div>
            <Badge variant="outline" className="rounded-full font-normal">Step 1 of 3</Badge>
          </div>

          {loadingExams ? (
            <PremiumExamLoader steps={loadSteps} currentStep={currentStep} />
          ) : exams.length === 0 ? (
            <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }}>
              <Card className="items-center rounded-2xl border-dashed p-12 text-center">
                <span className="mx-auto mb-4 flex size-12 items-center justify-center rounded-2xl bg-muted">
                  <BookOpen className="size-6 text-muted-foreground/60" aria-hidden="true" />
                </span>
                <p className="text-sm font-medium">No exams found</p>
                <p className="mt-1 text-sm text-muted-foreground">Ingest student submissions first, then return here to build a paper.</p>
              </Card>
            </motion.div>
          ) : (
            <motion.div layout className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
              <AnimatePresence>
                {exams.map((exam, idx) => (
                  <motion.div
                    key={examKey(exam)}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.3, delay: idx * 0.035, ease: "easeOut" }}
                  >
                    <Card
                      className="group h-full cursor-pointer gap-0 overflow-hidden rounded-2xl border-border/80 bg-card p-0 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/25 hover:shadow-md"
                      onClick={() => handleSelectExam(exam)}
                    >
                      <div className="flex items-start justify-between gap-3 p-5 pb-4">
                        <span className="flex size-11 items-center justify-center rounded-xl bg-secondary text-secondary-foreground transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
                          <BookOpen className="size-5" aria-hidden="true" />
                        </span>
                        <span className="flex size-8 items-center justify-center rounded-full border border-border bg-background text-muted-foreground opacity-0 transition-all duration-200 group-hover:opacity-100">
                          <ChevronRight className="size-4" aria-hidden="true" />
                        </span>
                      </div>

                      <div className="px-5">
                        <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">{exam.subject_name}</p>
                        <h4 className="mt-1 text-base font-semibold leading-snug">{exam.course_code} — {exam.session_name}</h4>
                        <p className="mt-1 text-sm text-muted-foreground">{exam.year} · Semester {exam.semester}</p>
                      </div>

                      <div className="mt-5 grid grid-cols-3 divide-x divide-border/70 border-y border-border/70 bg-muted/20 text-center">
                        <div className="px-2 py-3">
                          <p className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">Students</p>
                          <p className="mt-1 text-sm font-medium tabular-nums">{exam.student_count ?? "—"}</p>
                        </div>
                        <div className="px-2 py-3">
                          <p className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">Highest</p>
                          <p className="mt-1 text-sm font-medium tabular-nums">{exam.highest_score ?? "—"}</p>
                        </div>
                        <div className="px-2 py-3">
                          <p className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">Lowest</p>
                          <p className="mt-1 text-sm font-medium tabular-nums">{exam.lowest_score ?? "—"}</p>
                        </div>
                      </div>

                      <div className="p-5 pt-4">
                        <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${Math.min(exam.average_percentage ?? 0, 100)}%` }}
                            transition={{ duration: 0.7, delay: 0.2 + idx * 0.04, ease: "easeOut" }}
                            className="h-full rounded-full bg-primary/70"
                          />
                        </div>
                        <div className="mt-3 flex items-center justify-between gap-3">
                          <span className="text-xs text-muted-foreground">
                            Avg {formatAverage(exam.average_percentage)} · Pass {formatPassRate(exam.pass_rate)}
                          </span>
                          <span className="inline-flex items-center gap-1 text-xs font-medium text-foreground/70 transition-colors group-hover:text-foreground">
                            Start paper
                            <ChevronRight className="size-3.5" aria-hidden="true" />
                          </span>
                        </div>
                      </div>
                    </Card>
                  </motion.div>
                ))}
              </AnimatePresence>
            </motion.div>
          )}
        </section>

        <section className="mt-10 space-y-4">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h3 className="flex items-center gap-2 text-base font-semibold tracking-tight">
                <CloudUpload className="size-4 text-muted-foreground" aria-hidden="true" />
                Continue drafting
              </h3>
              <p className="mt-1 text-xs text-muted-foreground">
                {loadingDrafts ? "Loading saved papers…" : "Papers saved to the cloud, ready to pick up where you left off."}
              </p>
            </div>
            <Badge variant="outline" className="rounded-full font-normal">Cloud saved</Badge>
          </div>

          {drafts.length === 0 && !loadingDrafts ? (
            <Card className="items-center rounded-2xl border-dashed bg-card/50 p-8 text-center">
              <span className="mx-auto mb-3 flex size-11 items-center justify-center rounded-xl bg-muted">
                <FileText className="size-5 text-muted-foreground/60" aria-hidden="true" />
              </span>
              <p className="text-sm font-medium">No saved drafts yet</p>
              <p className="mt-1 text-sm text-muted-foreground">Build a paper in the editor and choose “Upload to Cloud” to keep it here.</p>
            </Card>
          ) : (
            <Card className="divide-y divide-border/70 overflow-hidden rounded-2xl p-0 shadow-sm">
              {drafts.map((draft) => (
                <button
                  key={draft.draft_id}
                  type="button"
                  className="flex w-full items-center gap-4 px-5 py-4 text-left transition-colors hover:bg-muted/40 focus-visible:bg-muted/40 focus-visible:outline-none"
                  onClick={() => handleLoadDraft(draft)}
                >
                  <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-secondary">
                    <FileText className="size-4" aria-hidden="true" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="truncate text-sm font-medium">{draft.paper.exam}</span>
                      <Badge variant="outline" className="rounded-full text-[10px] font-normal">{draft.subject_code}</Badge>
                    </span>
                    <span className="mt-1 block truncate text-xs text-muted-foreground">
                      {draft.paper.year} · {draft.question_count} question{draft.question_count === 1 ? "" : "s"} · {draft.total_marks} marks · updated {new Date(draft.updated_at).toLocaleDateString()}
                    </span>
                  </span>
                  <ChevronRight className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                </button>
              ))}
            </Card>
          )}
        </section>
      </div>
    );
  }

  // Split layout: paper canvas (left) + recommendations (right)
  return (
    <div className="flex min-h-[calc(100dvh-5.25rem)] flex-col bg-background lg:h-[calc(100dvh-5.25rem)] lg:overflow-hidden">
      {/* Editor header */}
      <header className="shrink-0 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="flex flex-wrap items-center gap-3 px-4 py-3 sm:px-6">
          <Button
            variant="ghost"
            size="icon"
            className="-ml-1 rounded-full"
            aria-label="Back to exam selection"
            onClick={handleBackToSelector}
            disabled={uploading}
          >
            <ArrowLeft className="size-4" aria-hidden="true" />
          </Button>

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h2 className="truncate text-sm font-semibold sm:text-base">{paper.exam}</h2>
              <Badge variant="secondary" className="hidden rounded-full font-normal sm:inline-flex">Draft</Badge>
            </div>
            <p className="truncate text-xs text-muted-foreground">
              {selectedExam.course_code} · {selectedExam.session_name} · {paper.year} · {paper.blueprint?.duration_minutes ?? 180} min
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              aria-label="Undo move / add"
              title="Undo the latest move or insertion before making another edit"
              disabled={!undoPaper}
              onClick={() => {
                if (undoPaper) setPaper(undoPaper);
                setSelectedQuestion(null);
                setPlacementMessage("Last structural change undone.");
              }}
            >
              <Undo2 className="size-4" aria-hidden="true" />
              <span className="hidden sm:inline">Undo</span>
            </Button>
            <Button variant="outline" size="sm" onClick={handlePreview} aria-label="Preview paper">
              <Eye className="size-4" aria-hidden="true" />
              <span className="hidden sm:inline">Preview</span>
            </Button>
            <Button variant="outline" size="sm" onClick={handleUpload} disabled={uploading} aria-label="Upload paper to cloud">
              <CloudUpload className="size-4" aria-hidden="true" />
              <span className="hidden md:inline">{uploading ? "Uploading…" : currentDraftId ? "Update Cloud" : "Upload to Cloud"}</span>
            </Button>
            <Button variant="outline" size="sm" onClick={() => handleDownload(true)} aria-label="Download marking scheme">
              <FileText className="size-4" aria-hidden="true" />
              <span className="hidden lg:inline">Marking scheme</span>
            </Button>
            <Button size="sm" onClick={() => handleDownload()} aria-label="Download PDF">
              <FileDown className="size-4" aria-hidden="true" />
              <span className="hidden sm:inline">Download PDF</span>
            </Button>
          </div>
        </div>

        <div className="flex items-center gap-3 border-t border-border/70 px-4 py-2 sm:px-6">
          <span className="hidden text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground sm:inline">Paper progress</span>
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
            <motion.div
              animate={{ width: `${Math.min((total / targetMarks) * 100, 100)}%` }}
              transition={{ duration: 0.5, ease: "easeOut" }}
              className={`h-full rounded-full ${progressTone}`}
            />
          </div>
          <motion.span
            key={total}
            initial={{ scale: 0.94, opacity: 0.6 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.2 }}
            className={`text-xs font-medium tabular-nums ${marksTone}`}
          >
            Total: {total}/{targetMarks}
          </motion.span>
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row lg:overflow-hidden">
        {/* Paper canvas */}
        <div className="w-full bg-muted/20 lg:w-[60%] lg:overflow-y-auto">
          <div className="mx-auto max-w-3xl space-y-4 px-4 py-6 sm:px-6 lg:px-8">
            <motion.div
              key={`${paper.exam}-${paper.year}`}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className="rounded-2xl border border-border/80 bg-card p-5 shadow-sm"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">Paper outline</p>
                  <h3 className="mt-1.5 text-lg font-semibold leading-snug">{paper.exam} · {paper.year}</h3>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {paper.questions.length} question{paper.questions.length === 1 ? "" : "s"} · {partCount} part{partCount === 1 ? "" : "s"} · {paper.blueprint?.duration_minutes ?? 180} minutes
                  </p>
                </div>
                <div className="shrink-0 text-right">
                  <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">Total marks</p>
                  <p className={`mt-1.5 text-2xl font-semibold tabular-nums leading-none ${marksTone}`}>
                    {total}
                    <span className="ml-1 text-sm font-normal text-muted-foreground">/ {targetMarks}</span>
                  </p>
                </div>
              </div>

              <div className="mt-4 flex items-center gap-3">
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                  <motion.div
                    animate={{ width: `${Math.min((total / targetMarks) * 100, 100)}%` }}
                    transition={{ duration: 0.5, ease: "easeOut" }}
                    className={`h-full rounded-full ${progressTone}`}
                  />
                </div>
                <span className="text-xs text-muted-foreground tabular-nums">
                  {marksComplete ? "Target met" : marksOver ? `${total - targetMarks} over target` : `${targetMarks - total} marks to go`}
                </span>
              </div>

              <div className="mt-4 flex items-start gap-2 rounded-xl bg-muted/50 px-3 py-2.5">
                <Target className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                <p className="text-xs leading-5 text-muted-foreground">
                  Drag questions from the assistant, or write your own. Select a question to add matching subparts.
                </p>
              </div>
              <p role="status" className="mt-2 text-xs text-primary">{placementMessage}</p>
            </motion.div>

            {!paper.questions.length && (
              <div className="rounded-2xl border border-dashed border-border bg-card/50 px-6 py-12 text-center">
                <span className="mx-auto mb-3 flex size-11 items-center justify-center rounded-xl bg-muted">
                  <Layers className="size-5 text-muted-foreground/60" aria-hidden="true" />
                </span>
                <p className="text-sm font-medium">Your paper is empty</p>
                <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">
                  Add a suggested question from the assistant, or start from scratch with a custom question below.
                </p>
              </div>
            )}

            <AnimatePresence>
              {paper.questions.map((q, idx) => (
                <motion.div key={q.question_number} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.25, delay: idx * 0.02 }}>
                  <DropZone active={!!dragged} label={`Insert as Question ${q.question_number}`} onDrop={() => dropAt({ question: idx })} />
                  <Card
                    id={`question-${q.question_number}`}
                    className="gap-0 overflow-hidden rounded-2xl border-border/80 bg-card p-0 shadow-sm transition-shadow hover:shadow-md"
                  >
                    <div className="flex flex-wrap items-center gap-1.5 border-b border-border/70 bg-muted/30 px-2.5 py-2">
                      <MoveControls
                        label={`question ${q.question_number}`}
                        source={{ kind: "question", question: idx }}
                        actions={structureActions}
                        up={idx > 0 ? { question: idx - 1 } : undefined}
                        down={idx < paper.questions.length - 1 ? { question: idx + 2 } : undefined}
                      />
                      <Button
                        variant={selectedQuestion === q.question_number ? "secondary" : "ghost"}
                        size="sm"
                        aria-pressed={selectedQuestion === q.question_number}
                        title="Select this question to add matching subparts"
                        className="h-8 gap-1.5 px-2"
                        onClick={() => setSelectedQuestion(selectedQuestion === q.question_number ? null : q.question_number)}
                      >
                        <span className={`flex size-5 items-center justify-center rounded-md text-[10px] font-semibold ${selectedQuestion === q.question_number ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}>
                          {q.question_number}
                        </span>
                        <span className="hidden text-xs lg:inline">Question {q.question_number}</span>
                        {selectedQuestion === q.question_number && <span className="hidden text-[10px] font-normal text-muted-foreground lg:inline">Selected</span>}
                      </Button>
                      <Input
                        aria-label={`Question ${q.question_number} topic`}
                        value={q.topic}
                        placeholder="Topic"
                        onChange={e => setPaper(prev => ({ ...prev, questions: prev.questions.map(x => x.question_number === q.question_number ? { ...x, topic: e.target.value, parts: x.parts.map(p => ({ ...p, review_status: "needs_review" })) } : x) }))}
                        className="h-8 min-w-[120px] flex-1 border-transparent bg-transparent px-2 text-sm font-medium shadow-none hover:border-input focus-visible:bg-background"
                      />
                      <span className="hidden shrink-0 rounded-full bg-card px-2 py-0.5 text-[11px] font-medium tabular-nums text-muted-foreground lg:inline">
                        {questionMarks(q)} marks
                      </span>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-8 shrink-0"
                        aria-label={`Remove question ${q.question_number}`}
                        onClick={() => { setSelectedQuestion(null); setPaper((prev) => ({ ...prev, questions: renumberQuestions(prev.questions.filter((x) => x.question_number !== q.question_number)) })); }}
                      >
                        <X className="size-4" aria-hidden="true" />
                      </Button>
                    </div>

                    <div className="space-y-2.5 p-3 sm:p-4">
                      {q.parts.map((p, partIndex) => (
                        <div key={p.part} className="space-y-2">
                          <DropZone active={!!dragged && dragged.kind !== "question" && draggedTopic === q.topic} label={`Insert part before ${p.part})`} onDrop={() => dropAt({ question: idx, part: partIndex })} />
                          <div className="rounded-xl border border-border/70 bg-background p-3">
                            <div className="mb-2 flex flex-wrap items-center gap-1.5">
                              <MoveControls
                                label={`Q${q.question_number} part ${p.part}`}
                                source={{ kind: "part", question: idx, part: partIndex }}
                                actions={structureActions}
                                up={partIndex > 0 ? { question: idx, part: partIndex - 1 } : undefined}
                                down={partIndex < q.parts.length - 1 ? { question: idx, part: partIndex + 2 } : undefined}
                              />
                              <span className="flex size-6 items-center justify-center rounded-md bg-muted text-[11px] font-semibold uppercase">{p.part}</span>
                              <span className="text-xs text-muted-foreground">Part {p.part}</span>
                              {q.parts.length > 1 && (
                                <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => insert({ kind: "part", question: idx, part: partIndex })}>
                                  Make separate question
                                </Button>
                              )}
                              <div className="ml-auto flex items-center gap-1.5">
                                <Input
                                  type="number"
                                  aria-label={`Q${q.question_number} part ${p.part} marks`}
                                  value={p.max_marks}
                                  onChange={(e) => setPaper((prev) => ({ ...prev, questions: prev.questions.map((x) => (x.question_number === q.question_number ? { ...x, parts: x.parts.map((y) => (y.part === p.part ? { ...y, max_marks: Number(e.target.value) || 0, review_status: "needs_review" } : y)) } : x)) }))}
                                  className="h-8 w-16 px-2 text-right text-sm tabular-nums"
                                  min={1}
                                  max={40}
                                />
                                <span className="text-[11px] text-muted-foreground">marks</span>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="size-8"
                                  aria-label={`Remove Q${q.question_number} part ${p.part}`}
                                  onClick={() => { setSelectedQuestion(null); setPaper((prev) => ({ ...prev, questions: renumberQuestions(prev.questions.map((x) => (x.question_number === q.question_number ? { ...x, parts: x.parts.filter((y) => y.part !== p.part) } : x)).filter((x) => x.parts.length > 0)) })); }}
                                >
                                  <X className="size-4" aria-hidden="true" />
                                </Button>
                              </div>
                            </div>

                            <div className="relative">
                              <QuestionTextInput
                                aria-label={`Q${q.question_number} part ${p.part} text`}
                                questionId={p.question_id}
                                value={p.question}
                                onChange={(e) => setPaper((prev) => ({ ...prev, questions: prev.questions.map((x) => (x.question_number === q.question_number ? { ...x, parts: x.parts.map((y) => (y.part === p.part ? { ...y, question: e.target.value, review_status: "needs_review" } : y)) } : x)) }))}
                                className="min-h-[100px] resize-y bg-card pr-14 text-sm leading-relaxed"
                                placeholder="Write the question text…"
                              />
                              <CustomQuestionGenerator courseCode={selectedExam.course_code} paper={paper} question={q} part={p}
                                onGenerated={candidate => setPaper(prev => ({ ...prev, questions: prev.questions.map(x => x === q
                                  ? { ...x, topic: candidate.topic, parts: x.parts.map(y => y === p
                                    ? { ...candidate, part: y.part, question: candidate.text, max_marks: candidate.marks, review_status: "needs_review" }
                                    : y) } : x) }))} />
                            </div>

                            {paper.questions.some(other => other !== q && other.topic === q.topic) && (
                              <label className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                                Move part to
                                <select
                                  aria-label={`Move Q${q.question_number} part ${p.part} to question`}
                                  className="h-8 rounded-md border border-input bg-background px-2 text-xs"
                                  value=""
                                  onChange={e => {
                                    const target = paper.questions[Number(e.target.value)];
                                    insert({ kind: "part", question: idx, part: partIndex }, { question: Number(e.target.value), part: target.parts.length });
                                  }}
                                >
                                  <option value="" disabled>Choose question</option>
                                  {paper.questions.map((other, i) => other !== q && other.topic === q.topic ? <option key={i} value={i}>Question {other.question_number}</option> : null)}
                                </select>
                              </label>
                            )}
                          </div>
                        </div>
                      ))}

                      <DropZone active={!!dragged && dragged.kind !== "question" && draggedTopic === q.topic} label={`Add part to Question ${q.question_number} (${q.topic})`} onDrop={() => dropAt({ question: idx, part: q.parts.length })} />

                      <div className="space-y-2">
                        {q.parts.map(p => (
                          <PartReviewEditor key={`review-${p.part}`} part={p} onChange={changes => setPaper(prev => ({ ...prev,
                            questions: prev.questions.map(x => x.question_number === q.question_number ? { ...x, parts: x.parts.map(y => y.part === p.part ? { ...y, ...changes } : y) } : x),
                          }))} />
                        ))}
                      </div>

                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 w-full border border-dashed border-border/80 text-xs text-muted-foreground hover:border-primary/30 hover:text-foreground"
                        onClick={() => setPaper((prev) => ({ ...prev, questions: prev.questions.map((x) => (x.question_number === q.question_number ? { ...x, parts: [...x.parts, { part: String.fromCharCode(97 + x.parts.length), question: "", max_marks: 10 }] } : x)) }))}
                      >
                        <Plus className="size-3.5" aria-hidden="true" />
                        Add part
                      </Button>
                    </div>
                  </Card>
                </motion.div>
              ))}
            </AnimatePresence>

            <DropZone active={!!dragged} label="Add new question at end" onDrop={() => dropAt({ question: paper.questions.length })} />

            <motion.div whileHover={{ scale: 1.005 }} whileTap={{ scale: 0.995 }}>
              <Button
                onClick={() => setPaper((prev) => ({ ...prev, questions: renumberQuestions([...prev.questions, { question_number: prev.questions.length + 1, topic: "", parts: [{ part: "a", question: "", max_marks: 10 }] }]) }))}
                className="h-11 w-full rounded-xl border-dashed"
                variant="outline"
              >
                <Plus className="size-4" aria-hidden="true" />
                Add Custom Question
              </Button>
            </motion.div>
          </div>
        </div>

        {/* Assistant panel */}
        <aside className="w-full border-t border-border bg-background lg:w-[40%] lg:border-l lg:border-t-0 lg:overflow-hidden">
          <Tabs value={rightTab} onValueChange={(v) => setRightTab(v as "recommended" | "browse")} className="flex h-full min-h-0 flex-col gap-0">
            <div className="shrink-0 border-b border-border px-4 pt-4 sm:px-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">Paper assistant</p>
                  <p className="mt-0.5 text-sm font-medium">Recommendations and checks</p>
                </div>
                <span className="flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-[10px] font-medium text-muted-foreground">
                  <span className="size-1.5 rounded-full bg-emerald-500" />
                  Live
                </span>
              </div>
              <TabsList className="mt-3 mb-3 grid w-full grid-cols-2">
                <TabsTrigger value="recommended" className="text-xs">Recommended</TabsTrigger>
                <TabsTrigger value="browse" className="text-xs">Browse Bank</TabsTrigger>
              </TabsList>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 sm:px-5">
              <TabsContent value="recommended" forceMount hidden={rightTab !== "recommended"} className="mt-0 space-y-4">
                <ExamCreatorAssistant key={`${selectedExam.course_code}-${currentDraftId ?? "new"}`} courseCode={selectedExam.course_code} paper={paper} setPaper={setPaper} structureActions={structureActions} />
              </TabsContent>

              <TabsContent value="browse" className="mt-0 space-y-3">
                <div className="flex gap-2">
                  <Select value={bankFilters.source_type || "all"} onValueChange={(v) => setBankFilters((s) => ({ ...s, source_type: v === "all" ? undefined : v }))}>
                    <SelectTrigger className="h-9 flex-1 text-xs"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All sources</SelectItem>
                      <SelectItem value="tutorial">Tutorial</SelectItem>
                      <SelectItem value="exam">Exam</SelectItem>
                      <SelectItem value="generated">Generated candidate</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select value={bankFilters.year ? String(bankFilters.year) : "all"} onValueChange={(v) => setBankFilters((s) => ({ ...s, year: v === "all" ? undefined : Number(v) }))}>
                    <SelectTrigger className="h-9 w-[120px] text-xs"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All years</SelectItem>
                      {Array.from(new Set(exams.filter(e => e.course_code === selectedExam.course_code).map(e => e.year))).sort((a, b) => b - a).map(year => <SelectItem key={year} value={String(year)}>{year}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>

                {loadingBank ? (
                  <p role="status" className="flex items-center gap-2 rounded-xl border border-border bg-card px-3 py-4 text-xs text-muted-foreground">
                    <BrandOrb state="searching" size={20} aria-hidden="true" />
                    Loading question bank...
                  </p>
                ) : bankItems.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-border bg-card/50 px-4 py-8 text-center">
                    <p className="text-sm font-medium">No questions found</p>
                    <p className="mt-1 text-xs text-muted-foreground">Adjust the filters or switch to Recommended.</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {bankItems.map((item) => (
                      <Card key={item.question_id} className="gap-0 space-y-2.5 rounded-xl border-border/80 bg-card p-3.5 shadow-none">
                        <div className="flex flex-wrap gap-1.5">
                          <Badge variant="outline" className="rounded-full text-[10px] font-normal">{item.canonical_topic.slice(0, 28)}</Badge>
                          <Badge variant="secondary" className="rounded-full text-[10px] font-normal">{item.bloom_level}</Badge>
                          <Badge variant="outline" className="rounded-full text-[10px] font-normal">{item.source_type} {item.year}</Badge>
                          {item.marks > 0 && <Badge variant="outline" className="rounded-full text-[10px] font-normal">{item.marks} marks</Badge>}
                        </div>
                        <p className="max-h-64 overflow-y-auto whitespace-pre-wrap break-words rounded-lg border border-border/70 bg-muted/30 p-2.5 text-xs leading-5">{item.text}</p>
                        <p className="whitespace-pre-wrap break-words text-[11px] text-muted-foreground">{item.subtopic}</p>
                        <CandidateActions topic={item.canonical_topic} part={{ part: "a", question: item.text, max_marks: item.marks > 0 ? item.marks : 10,
                          question_id: item.question_id, bloom_level: item.bloom_level, review_status: "needs_review" }} actions={structureActions} />
                      </Card>
                    ))}
                  </div>
                )}
              </TabsContent>
            </div>
          </Tabs>
        </aside>
      </div>
    </div>
  );
}
