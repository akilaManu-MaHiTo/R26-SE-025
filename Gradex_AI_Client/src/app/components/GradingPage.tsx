import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import {
  Upload, FileText, Sparkles, Save, Edit3, CheckCircle2,
  FileImage, ZoomIn, ZoomOut, X, RotateCcw,
  ScanLine, ImageIcon, RefreshCw, AlertCircle, ChevronRight,
  Eye, Layers, Type, Cpu, BookOpen, Users, TrendingUp, Filter,
  Download, FileSpreadsheet, Calendar, Clock, FolderOpen,
  Table, BarChart3, ArrowRight, ArrowLeft, PenTool, Settings, Plus, Trash2,
} from "lucide-react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Progress } from "./ui/progress";
import { Separator } from "./ui/separator";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";
import { AIPageBanner, AILoadingOverlay, AIBadgePill, type AIModel } from "./AIBrand";
import { LectureMaterialsPanel, fetchCourses, formatCourseLabel, type CourseItem } from "./LectureMaterialsPanel";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";

import { GRADING_API_BASE_URL } from "../api/gradingApiBase";

const SESSION_NAME_OPTIONS = [
  "Final Examination",
  "Mid Term Examination",
  "Tutorial Examination",
  "Quiz",
] as const;

const SEMESTER_OPTIONS = [
  { value: "1", label: "Semester 1" },
  { value: "2", label: "Semester 2" },
] as const;

const MONTH_OPTIONS = [
  { value: "1", label: "January" },
  { value: "2", label: "February" },
  { value: "3", label: "March" },
  { value: "4", label: "April" },
  { value: "5", label: "May" },
  { value: "6", label: "June" },
  { value: "7", label: "July" },
  { value: "8", label: "August" },
  { value: "9", label: "September" },
  { value: "10", label: "October" },
  { value: "11", label: "November" },
  { value: "12", label: "December" },
] as const;

function buildYearOptions(centerYear = new Date().getFullYear()): string[] {
  const years: string[] = [];
  for (let y = centerYear - 2; y <= centerYear + 2; y += 1) {
    years.push(String(y));
  }
  return years;
}

function formatRubricDetailsLabel(r: {
  session_name?: string | null;
  subject_code?: string | null;
  subject_name?: string | null;
  year?: number | null;
  month?: number | null;
  semester?: number | null;
}): string {
  const session = (r.session_name || "").trim() || null;
  const code = (r.subject_code || "").trim();
  const name = (r.subject_name || "").trim();
  const subject =
    code && name && name !== code ? `${code} - ${name}` : code || name || null;
  const monthLabel =
    r.month != null
      ? MONTH_OPTIONS.find((m) => m.value === String(r.month))?.label ?? `M${r.month}`
      : null;
  const term = [
    r.year != null ? String(r.year) : null,
    monthLabel,
    r.semester != null ? `Sem ${r.semester}` : null,
  ]
    .filter(Boolean)
    .join(" · ");
  return [session, subject, term || null].filter(Boolean).join(" · ");
}

function parseApiError(data: unknown, fallback: string): string {
  if (data == null || typeof data !== "object") return fallback;
  const detail = (data as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && !Array.isArray(detail) && "message" in detail) {
    return String((detail as { message: string }).message || fallback);
  }
  if (Array.isArray(detail)) {
    const parts = detail.map((item) => {
      if (item && typeof item === "object" && "msg" in item) return String((item as { msg: string }).msg);
      return String(item);
    });
    return parts.length ? parts.join("; ") : fallback;
  }
  return fallback;
}

async function readJsonResponse(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text.trim()) return {};
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text.slice(0, 200) };
  }
}

function historyItemSortMs(item: {
  sort_at?: string | null;
  parsed_at?: number | string | null;
  date?: string | null;
}): number {
  const candidates = [item.sort_at, item.parsed_at, item.date];
  for (const raw of candidates) {
    if (raw == null || raw === "") continue;
    const ms =
      typeof raw === "number"
        ? raw < 1e12
          ? raw * 1000
          : raw
        : Date.parse(String(raw));
    if (Number.isFinite(ms)) return ms;
  }
  return 0;
}

function sortGradingHistoryNewestFirst<T extends {
  sort_at?: string | null;
  parsed_at?: number | string | null;
  date?: string | null;
  history_key?: string;
  _id?: string;
}>(items: T[]): T[] {
  return [...items].sort((a, b) => {
    const diff = historyItemSortMs(b) - historyItemSortMs(a);
    if (diff !== 0) return diff;
    const keyA = a.history_key || a._id || "";
    const keyB = b.history_key || b._id || "";
    return keyB.localeCompare(keyA);
  });
}

/* ─── Types ──────────────────────────────────────────────────────────────── */
type OcrLine = { text: string; conf: number; highlight?: boolean };

/* ─── Mock extraction results ────────────────────────────────────────────── */
const MOCK_OCR_LINES: OcrLine[] = [
  { text: "An ER diagram for the university system will include the entity", conf: 0.97 },
  { text: "Student with attributes studentID, name, and email.", conf: 0.95 },
  { text: "Each student enrolls in many courses through the Enrollment", conf: 0.91 },
  { text: "entity which carries grade and semester as attributes.", conf: 0.88 },
  { text: "The relationship 'Enrolls' between Student and Course is M:N.", conf: 0.93 },
  { text: "In normalization, dependency name → email violates 2NF when", conf: 0.72, highlight: true },
  { text: "composite key (studentID, courseID) exists in relation schema.", conf: 0.68, highlight: true },
  { text: "Converting to 3NF requires decomposing the relation into two:", conf: 0.89 },
  { text: "R1(studentID, name, email) and R2(studentID, courseID, grade).", conf: 0.85 },
];

/* ═══════════════════════════════════════════════════════════════════════════
   HANDWRITTEN GRADING: 7-PAGE WORKFLOW
   ═══════════════════════════════════════════════════════════════════════════ */

type CriterionEntry = {
  point: string;
  marks: number;
};

type RubricEntry = {
  questionNo: string;
  questionText: string;
  criteria: CriterionEntry[];
};

function coerceMarks(v: unknown): number {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function sumQuestionMarks(entry: RubricEntry): number {
  return entry.criteria.reduce((s, c) => s + coerceMarks(c.marks), 0);
}

function mapQuestionsFromBackend(questions: unknown): RubricEntry[] {
  const list = Array.isArray(questions) ? questions : [];
  return list.map((q: Record<string, unknown>, index) => {
    const questionText = String(
      q?.question_text ?? q?.question ?? `Question ${index + 1}`
    ).trim();
    const rawNo = q?.question_no ?? index + 1;
    const digits = String(rawNo).match(/\d+/);
    const questionNo = digits ? digits[0].padStart(2, "0") : String(index + 1).padStart(2, "0");
    const maxFromDoc = coerceMarks(q?.max_marks);

    let criteria: CriterionEntry[] = [];
    const rawCrit = q?.criteria;

    if (Array.isArray(rawCrit)) {
      criteria = rawCrit
        .map((item: unknown) => {
          if (item && typeof item === "object") {
            const o = item as Record<string, unknown>;
            return {
              point: String(o.point ?? o.description ?? o.text ?? "").trim(),
              marks: coerceMarks(o.marks),
            };
          }
          const text = String(item ?? "").trim();
          return { point: text, marks: 0 };
        })
        .filter((c) => c.point.length > 0);
    } else if (typeof rawCrit === "string" && rawCrit.trim()) {
      const parts = rawCrit
        .split(";")
        .map((s) => s.trim())
        .filter(Boolean);
      const per =
        parts.length > 0 && maxFromDoc > 0
          ? Math.round((maxFromDoc / parts.length) * 10000) / 10000
          : 0;
      criteria = parts.map((point) => ({ point, marks: per }));
    }

    let sumCrit = criteria.reduce((s, c) => s + coerceMarks(c.marks), 0);
    if (criteria.length > 0 && sumCrit === 0 && maxFromDoc > 0) {
      const per =
        Math.round((maxFromDoc / criteria.length) * 10000) / 10000;
      criteria = criteria.map((c) => ({ ...c, marks: per }));
      sumCrit = criteria.reduce((s, c) => s + coerceMarks(c.marks), 0);
    }

    if (criteria.length === 0 && maxFromDoc > 0) {
      criteria = [{ point: "Marking criterion (edit)", marks: maxFromDoc }];
    }

    return {
      questionNo,
      questionText,
      criteria,
    };
  });
}

type StudentProgress = {
  stage: string;
  pagesDone: number;
  pagesTotal: number;
  questionsDone: number;
  questionsTotal: number;
  currentQuestion?: string | null;
  startedAt?: string | null;
  updatedAt?: string | null;
};

type DashboardStudent = {
  id: string;
  submissionId?: string;
  status: "not_started" | "processing" | "completed" | "warning" | "failed" | "skipped";
  ocrConf?: number;
  quickGrade?: number;
  maxGrade: number;
  rawTranscript?: string;
  cleanedTranscript?: string;
  evaluation?: Record<string, unknown>;
  lecturerNote?: string;
  manualOverride?: boolean;
  maxMarksPerQuestion?: { question_no: string; max_marks: number }[];
  error?: string;
  progress?: StudentProgress;
  processedAt?: string | null;
  gradingEngine?: string;
  sliceSources?: Record<string, string>;
};

function mapProgress(raw: unknown): StudentProgress | undefined {
  if (!raw || typeof raw !== "object") return undefined;
  const p = raw as Record<string, unknown>;
  return {
    stage: String(p.stage ?? "queued"),
    pagesDone: typeof p.pages_done === "number" ? p.pages_done : 0,
    pagesTotal: typeof p.pages_total === "number" ? p.pages_total : 0,
    questionsDone: typeof p.questions_done === "number" ? p.questions_done : 0,
    questionsTotal: typeof p.questions_total === "number" ? p.questions_total : 0,
    currentQuestion:
      p.current_question == null ? null : String(p.current_question),
    startedAt: typeof p.started_at === "string" ? p.started_at : null,
    updatedAt: typeof p.updated_at === "string" ? p.updated_at : null,
  };
}

function formatEtaSeconds(seconds: number | null): string {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) return "—";
  if (seconds < 60) return `~${Math.max(1, Math.round(seconds))}s`;
  const mins = Math.round(seconds / 60);
  if (mins < 60) return `~${mins}m`;
  const hrs = Math.floor(mins / 60);
  const rem = mins % 60;
  return rem ? `~${hrs}h ${rem}m` : `~${hrs}h`;
}

/** User-facing label for grading_source values stored in Mongo. */
function formatGradingEngineLabel(source?: string | null): string {
  const s = String(source || "").trim().toLowerCase();
  if (!s) return "";
  if (s === "colab") return "Local model";
  if (s === "groq") return "Cloud fallback";
  if (s === "empty") return "No answer";
  if (s === "emergency") return "Emergency";
  if (s === "unknown") return "Unknown";
  return String(source).trim();
}

function estimateStudentEta(progress?: StudentProgress): number | null {
  if (!progress?.startedAt) return null;
  const started = Date.parse(progress.startedAt);
  if (!Number.isFinite(started)) return null;
  const elapsedSec = Math.max(1, (Date.now() - started) / 1000);

  if (progress.stage === "ocr") {
    if (progress.pagesDone <= 0 || progress.pagesTotal <= 0) return null;
    const perPage = elapsedSec / progress.pagesDone;
    return perPage * Math.max(0, progress.pagesTotal - progress.pagesDone);
  }

  if (progress.stage === "grading") {
    if (progress.questionsDone <= 0 || progress.questionsTotal <= 0) return null;
    const perQ = elapsedSec / progress.questionsDone;
    return perQ * Math.max(0, progress.questionsTotal - progress.questionsDone);
  }

  return null;
}

function progressSummaryLine(student: DashboardStudent): string {
  const p = student.progress;
  if (!p) {
    if (student.status === "processing") return "Working…";
    if (student.status === "not_started") return "Queued";
    return "—";
  }
  if (p.stage === "ocr") {
    return `OCR ${p.pagesDone}/${p.pagesTotal || "?"} pages`;
  }
  if (p.stage === "grading") {
    const cur = p.currentQuestion ? ` · Q${p.currentQuestion}` : "";
    return `Grading ${p.questionsDone}/${p.questionsTotal || "?"} q${cur}`;
  }
  if (p.stage === "done") {
    return p.questionsTotal
      ? `Done ${p.questionsTotal}/${p.questionsTotal} q`
      : "Done";
  }
  if (p.stage === "queued") return "Queued";
  if (p.stage === "failed") return "Failed";
  return p.stage;
}

/** Drop engine page banners so the review pane does not show image filenames. */
function stripOcrPageBanners(text: string): string {
  return text
    .replace(/\r\n/g, "\n")
    .split("\n")
    .filter((line) => {
      const t = line.trim();
      if (/^-{2,}\s*page\s+\d+\s*:/i.test(t)) return false;
      if (/^\[ocr empty for .+\]$/i.test(t)) return false;
      return true;
    })
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

/** Collect short, actionable issues for the dashboard Errors column. */
function studentIssueLines(student: DashboardStudent): string[] {
  const lines: string[] = [];
  if (student.error?.trim()) {
    lines.push(student.error.trim());
  }

  const transcript = `${student.cleanedTranscript || ""}\n${student.rawTranscript || ""}`;
  if (/\[OCR_EMPTY\]/i.test(transcript) || /OCR empty/i.test(transcript)) {
    lines.push("OCR empty on one or more pages");
  }
  if (/\[OCR_ERROR\]/i.test(transcript) || /OCR Failed:/i.test(transcript)) {
    lines.push("OCR error on one or more pages");
  }

  const results = Array.isArray(student.evaluation?.results)
    ? (student.evaluation!.results as Record<string, unknown>[])
    : [];
  for (const row of results) {
    if (row?.error == null || String(row.error).trim() === "") continue;
    const qNo = String(row.q_no ?? row.question_no ?? "?").trim() || "?";
    lines.push(`Q${qNo}: ${String(row.error).trim()}`);
  }

  const seen = new Set<string>();
  const unique: string[] = [];
  for (const line of lines) {
    const key = line.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(line);
  }
  return unique;
}

const GRADE_BANDS = [
  { label: "0-40", min: 0, maxExclusive: 40 },
  { label: "40-50", min: 40, maxExclusive: 50 },
  { label: "50-60", min: 50, maxExclusive: 60 },
  { label: "60-70", min: 60, maxExclusive: 70 },
  { label: "70-80", min: 70, maxExclusive: 80 },
  { label: "80-100", min: 80, maxExclusive: 100.0001 },
] as const;

function studentPercentScore(student: DashboardStudent): number | null {
  if (student.quickGrade == null || !Number.isFinite(student.quickGrade)) return null;
  if (!(student.maxGrade > 0)) return null;
  return (student.quickGrade / student.maxGrade) * 100;
}

function normalizeQKey(value: unknown, fallback = "?"): string {
  const digits = String(value ?? "").match(/\d+/);
  if (digits) return String(parseInt(digits[0], 10));
  const text = String(value ?? "").trim();
  return text || fallback;
}

function buildGradeDistribution(students: DashboardStudent[]) {
  const graded = students.filter((s) => studentPercentScore(s) != null);
  const bands = GRADE_BANDS.map((band) => {
    const count = graded.filter((s) => {
      const p = studentPercentScore(s)!;
      return p >= band.min && p < band.maxExclusive;
    }).length;
    return { label: band.label, count };
  });
  const percents = graded.map((s) => studentPercentScore(s)!);
  const avgPercent =
    percents.length > 0 ? percents.reduce((a, b) => a + b, 0) / percents.length : null;
  return {
    bands,
    gradedCount: graded.length,
    total: students.length,
    avgPercent,
    maxBandCount: Math.max(1, ...bands.map((b) => b.count)),
  };
}

function buildQuestionMastery(students: DashboardStudent[], rubric: RubricEntry[]) {
  type Acc = { sumScore: number; sumMax: number; n: number; label: string };
  const map = new Map<string, Acc>();

  for (const entry of rubric) {
    const key = normalizeQKey(entry.questionNo);
    map.set(key, {
      sumScore: 0,
      sumMax: 0,
      n: 0,
      label: entry.questionNo || `Q${key}`,
    });
  }

  for (const student of students) {
    const results = Array.isArray(student.evaluation?.results)
      ? (student.evaluation!.results as Record<string, unknown>[])
      : [];
    if (results.length === 0) continue;

    for (let i = 0; i < results.length; i++) {
      const row = results[i];
      const key = normalizeQKey(row.q_no ?? row.question_no, String(i + 1));
      const score = typeof row.score === "number" ? row.score : Number(row.score ?? NaN);
      if (!Number.isFinite(score)) continue;

      let max = 0;
      const fromRoster = student.maxMarksPerQuestion?.find(
        (m) => normalizeQKey(m.question_no) === key,
      );
      if (fromRoster && Number.isFinite(fromRoster.max_marks) && fromRoster.max_marks > 0) {
        max = fromRoster.max_marks;
      } else {
        const rub = rubric.find((r) => normalizeQKey(r.questionNo) === key);
        if (rub) max = sumQuestionMarks(rub);
      }

      const prev = map.get(key) || {
        sumScore: 0,
        sumMax: 0,
        n: 0,
        label: `Q${key}`,
      };
      prev.sumScore += score;
      prev.sumMax += max > 0 ? max : 0;
      prev.n += 1;
      map.set(key, prev);
    }
  }

  return [...map.entries()]
    .map(([key, acc]) => {
      const avgScore = acc.n > 0 ? acc.sumScore / acc.n : null;
      const avgMax = acc.n > 0 && acc.sumMax > 0 ? acc.sumMax / acc.n : null;
      const avgPercent =
        avgScore != null && avgMax != null && avgMax > 0 ? (avgScore / avgMax) * 100 : null;
      return {
        key,
        label: acc.label.startsWith("Q") ? acc.label : `Q${acc.label}`,
        avgScore,
        avgMax,
        avgPercent,
        sampleSize: acc.n,
      };
    })
    .sort((a, b) => Number(a.key) - Number(b.key) || a.label.localeCompare(b.label));
}

function csvEscape(value: unknown): string {
  const text = String(value ?? "");
  if (/[",\n\r]/.test(text)) return `"${text.replace(/"/g, '""')}"`;
  return text;
}

function downloadTextFile(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function mapSubmissionToDashboard(doc: Record<string, unknown>): DashboardStudent {
  const evaluation = doc.evaluation as Record<string, unknown> | undefined;
  const totalScore =
    evaluation && typeof evaluation.total_score === "number" ? evaluation.total_score : undefined;
  const maxPaper =
    typeof doc.max_marks_paper_total === "number" ? doc.max_marks_paper_total : 0;
  const st = String(doc.status ?? "graded");
  let uiStatus: DashboardStudent["status"] = "completed";
  if (st === "not_started") uiStatus = "not_started";
  else if (st === "processing") uiStatus = "processing";
  else if (st === "failed") uiStatus = "failed";
  else if (st === "skipped" || st === "warning") uiStatus = st === "skipped" ? "skipped" : "warning";
  else if (st === "graded" || st === "completed") uiStatus = "completed";

  // OCR.Space confidence is not captured today (text-only OCR calls).
  const ocrConf =
    typeof doc.ocr_confidence === "number"
      ? doc.ocr_confidence
      : typeof doc.ocrConf === "number"
        ? doc.ocrConf
        : undefined;

  const maxMarksPerQuestion = Array.isArray(doc.max_marks_per_question)
    ? (doc.max_marks_per_question as { question_no?: unknown; max_marks?: unknown }[])
        .map((item) => ({
          question_no: String(item?.question_no ?? "").trim(),
          max_marks: Number(item?.max_marks ?? 0),
        }))
        .filter((item) => item.question_no)
    : undefined;

  const manualOverride =
    Boolean(doc.manual_override) ||
    Boolean(evaluation && evaluation.manual_override);

  return {
    id: String(doc.student_id ?? ""),
    submissionId: typeof doc._id === "string" ? doc._id : undefined,
    status: uiStatus,
    ocrConf,
    quickGrade: totalScore,
    maxGrade: maxPaper,
    rawTranscript:
      typeof doc.raw_ocr_transcript === "string" ? doc.raw_ocr_transcript : undefined,
    cleanedTranscript:
      typeof doc.cleaned_ocr_transcript === "string"
        ? stripOcrPageBanners(doc.cleaned_ocr_transcript)
        : undefined,
    evaluation,
    lecturerNote: typeof doc.lecturer_note === "string" ? doc.lecturer_note : "",
    manualOverride,
    maxMarksPerQuestion,
    error: typeof doc.error === "string" ? doc.error : undefined,
    progress: mapProgress(doc.progress),
    processedAt: typeof doc.processed_at === "string" ? doc.processed_at : null,
    gradingEngine: (() => {
      const top =
        evaluation && typeof evaluation.grading_source === "string"
          ? evaluation.grading_source
          : "";
      const fromResults = Array.isArray(evaluation?.results)
        ? evaluation.results.find(
            (r): r is { grading_source: string } =>
              Boolean(r) &&
              typeof r === "object" &&
              typeof (r as { grading_source?: unknown }).grading_source === "string",
          )
        : undefined;
      const raw = top || fromResults?.grading_source || "";
      const label = formatGradingEngineLabel(raw);
      return label || undefined;
    })(),
    sliceSources:
      evaluation &&
      evaluation.answer_split &&
      typeof evaluation.answer_split === "object" &&
      (evaluation.answer_split as { per_question_source?: Record<string, string> }).per_question_source
        ? (evaluation.answer_split as { per_question_source: Record<string, string> }).per_question_source
        : undefined,
  };
}

type RubricListItem = {
  _id: string;
  session_name?: string;
  subject_code?: string;
  subject_name?: string;
  year?: number;
  month?: number;
  semester?: number;
  filename?: string;
  parsed_at?: number;
};

type RosterValidationRow = {
  student_id?: string | null;
  name?: string | null;
  status: string;
  paper_keys?: string[];
  error?: string;
  header_preview?: string;
};

type RosterValidationReport = {
  summary: {
    matched: number;
    missing_paper: number;
    extra_paper: number;
    duplicate_paper: number;
    duplicate_roster: number;
    unreadable_id: number;
    roster_count: number;
    paper_count: number;
  };
  rows: RosterValidationRow[];
  matched_paper_keys: string[];
  can_grade: boolean;
  hard_blockers: number;
  soft_warnings: number;
};

type GradingHistoryItem = {
  _id: string;
  history_key?: string;
  batch_job_id?: string | null;
  archived?: boolean;
  session_name?: string;
  subject_code?: string;
  subject_name?: string;
  year?: number | null;
  month?: number | null;
  semester?: number | null;
  filename?: string;
  parsed_at?: number | string | null;
  date?: string | null;
  sort_at?: string | null;
  avg_score?: number | null;
  status?: string;
  submission_count?: number;
  graded_count?: number;
  counts?: {
    not_started?: number;
    processing?: number;
    graded?: number;
    failed?: number;
    skipped?: number;
  };
};

type OngoingGradingJob = {
  rubric_id: string;
  batch_job_id?: string | null;
  session_name: string;
  subject_code?: string;
  subject_name?: string;
  year?: number | null;
  month?: number | null;
  semester?: number | null;
  current_student_id?: string;
  current_stage?: string;
  updated_at?: string | null;
  progress?: {
    total?: number;
    finished?: number;
    percent?: number;
    running?: boolean;
    counts?: {
      not_started?: number;
      processing?: number;
      graded?: number;
      failed?: number;
      skipped?: number;
    };
  };
};


/* ─── Handwritten grading (Grading Engine agent) ─────────────────────────── */
export function GradingPage(_props?: { mode?: "diagram" | "handwritten" }) {
  return <HandwrittenGradingWorkflow />;
}

function HandwrittenGradingWorkflow() {
  const [page, setPage] = useState<1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9>(1);

  // Page 2: Session Initialization
  const [subject, setSubject] = useState("");
  const [subjectName, setSubjectName] = useState("");
  const [courses, setCourses] = useState<CourseItem[]>([]);
  const [coursesLoading, setCoursesLoading] = useState(false);
  const [examName, setExamName] = useState<string>(SESSION_NAME_OPTIONS[0]);
  const [sessionYear, setSessionYear] = useState(String(new Date().getFullYear()));
  const [sessionMonth, setSessionMonth] = useState(String(new Date().getMonth() + 1));
  const [sessionSemester, setSessionSemester] = useState("1");
  const yearOptions = buildYearOptions();
  const [rubricFile, setRubricFile] = useState<File | null>(null);
  const [rubricId, setRubricId] = useState<string | null>(null);
  const [rubricLoading, setRubricLoading] = useState(false);
  const [rubricSaving, setRubricSaving] = useState(false);
  const [rubricError, setRubricError] = useState<string | null>(null);
  const [rubricSuccess, setRubricSuccess] = useState<string | null>(null);
  const [rubricFetchLoading, setRubricFetchLoading] = useState(false);

  // Page 3: Rubric Verification — populated from POST /upload-rubric or GET /rubric/{id}
  const [rubric, setRubric] = useState<RubricEntry[]>([]);

  // Page 4: Batch Upload → backend staging + grade-batch
  const [gradingRubricId, setGradingRubricId] = useState<string | null>(null);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [batchStudentFolderCount, setBatchStudentFolderCount] = useState<number | null>(null);
  const [uploadedFiles, setUploadedFiles] = useState<string[]>([]);
  const [batchUploadError, setBatchUploadError] = useState<string | null>(null);
  const [batchUploading, setBatchUploading] = useState(false);
  const [gradingRunning, setGradingRunning] = useState(false);
  /** True when page 4 was opened via “Continue to batch grading” without uploading a rubric on page 2 (Back → session setup). */
  const [batchBackFromSessionSkip, setBatchBackFromSessionSkip] = useState(false);
  const [rosterUploading, setRosterUploading] = useState(false);
  const [rosterInfo, setRosterInfo] = useState<{
    row_count: number;
    duplicate_roster_ids: string[];
  } | null>(null);
  const [idScanning, setIdScanning] = useState(false);
  const [validatingRoster, setValidatingRoster] = useState(false);
  const [validationReport, setValidationReport] = useState<RosterValidationReport | null>(null);
  const [allowSoftWarnings, setAllowSoftWarnings] = useState(false);
  const [manualIdDrafts, setManualIdDrafts] = useState<Record<string, string>>({});
  const [savingManualIds, setSavingManualIds] = useState(false);
  const rosterInputRef = useRef<HTMLInputElement>(null);
  const [rubricPickerOpen, setRubricPickerOpen] = useState(false);
  const [rubricsList, setRubricsList] = useState<RubricListItem[]>([]);
  const [rubricsListLoading, setRubricsListLoading] = useState(false);
  const [pendingRubricId, setPendingRubricId] = useState<string | null>(null);
  const [applyingRubric, setApplyingRubric] = useState(false);
  const zipInputRef = useRef<HTMLInputElement>(null);

  // Page 5: Master Evaluation Dashboard (from GET /submissions)
  const [dashboardStudents, setDashboardStudents] = useState<DashboardStudent[]>([]);
  const [submissionsLoading, setSubmissionsLoading] = useState(false);
  const [filterWarnings, setFilterWarnings] = useState(false);
  const [selectedStudent, setSelectedStudent] = useState<DashboardStudent | null>(null);
  const [activeBatchJobId, setActiveBatchJobId] = useState<string | null>(null);
  const [batchProgressRunning, setBatchProgressRunning] = useState(false);
  const submissionsFetchGenRef = useRef(0);
  const [progressModalStudent, setProgressModalStudent] = useState<DashboardStudent | null>(null);
  const [ongoingJobs, setOngoingJobs] = useState<OngoingGradingJob[]>([]);
  const [ongoingJobsLoading, setOngoingJobsLoading] = useState(false);
  const [gradingHistory, setGradingHistory] = useState<GradingHistoryItem[]>([]);
  const [gradingHistoryLoading, setGradingHistoryLoading] = useState(false);
  const [historyEditItem, setHistoryEditItem] = useState<GradingHistoryItem | null>(null);
  const [historyEditSaving, setHistoryEditSaving] = useState(false);
  const [historyEditError, setHistoryEditError] = useState<string | null>(null);
  const [historyDeleteItem, setHistoryDeleteItem] = useState<GradingHistoryItem | null>(null);
  const [historyDeleting, setHistoryDeleting] = useState(false);
  const [historyFilterQuery, setHistoryFilterQuery] = useState("");
  const [historyFilterStatus, setHistoryFilterStatus] = useState<string>("all");
  const [historyFilterSubject, setHistoryFilterSubject] = useState<string>("all");
  const [historyFilterYear, setHistoryFilterYear] = useState<string>("all");
  const [editSessionName, setEditSessionName] = useState("");
  const [editSubjectCode, setEditSubjectCode] = useState("");
  const [editSubjectName, setEditSubjectName] = useState("");
  const [editYear, setEditYear] = useState("");
  const [editMonth, setEditMonth] = useState("");
  const [editSemester, setEditSemester] = useState("");

  // Page 6: AI-Assisted Review
  const [zoom, setZoom] = useState(100);
  const [reviewTab, setReviewTab] = useState<"parsed" | "analysis">("parsed");
  const [openQuestionDiag, setOpenQuestionDiag] = useState<Record<string, boolean>>({});
  const [openQuestionRag, setOpenQuestionRag] = useState<Record<string, boolean>>({});
  const [regradingAll, setRegradingAll] = useState(false);
  const [regradingQuestion, setRegradingQuestion] = useState<string | null>(null);
  const [parsedText, setParsedText] = useState(MOCK_OCR_LINES.map(l => l.text).join("\n"));
  const [lecturerNote, setLecturerNote] = useState("");
  const [overrideScores, setOverrideScores] = useState<Record<number, string>>({});
  const [overrideSaving, setOverrideSaving] = useState(false);
  const [overrideMessage, setOverrideMessage] = useState<string | null>(null);
  const [reviewNotice, setReviewNotice] = useState<{ title: string; message: string } | null>(null);
  const [reviewConfirm, setReviewConfirm] = useState<
    | { kind: "reset_ai" }
    | { kind: "save_override" }
    | { kind: "regrade_student" }
    | { kind: "regrade_question"; questionNo: string }
    | null
  >(null);
  const [pendingUpload, setPendingUpload] = useState<
    | { kind: "zip"; file: File }
    | { kind: "folder"; files: File[] }
    | { kind: "roster"; file: File }
    | null
  >(null);
  const [currentStudentIndex, setCurrentStudentIndex] = useState(0);

  const rubricFileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  const loadCourses = useCallback(async () => {
    setCoursesLoading(true);
    try {
      const list = await fetchCourses(GRADING_API_BASE_URL);
      setCourses(list);
      setSubject((prev) => {
        if (prev && list.some((c) => c.code === prev)) return prev;
        return list[0]?.code ?? "";
      });
    } catch {
      setCourses([]);
    } finally {
      setCoursesLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadCourses();
  }, [loadCourses]);

  useEffect(() => {
    if (page === 2 || page === 8 || page === 9) {
      void loadCourses();
    }
  }, [page, loadCourses]);

  useEffect(() => {
    const match = courses.find((c) => c.code === subject);
    setSubjectName((match?.name || "").trim() || subject);
  }, [subject, courses]);

  const handleSubjectChange = (code: string) => {
    setSubject(code);
    const match = courses.find((c) => c.code === code);
    setSubjectName((match?.name || "").trim() || code);
  };

  const fetchOngoingJobs = useCallback(async (opts?: { quiet?: boolean }) => {
    if (!opts?.quiet) setOngoingJobsLoading(true);
    try {
      const response = await fetch(`${GRADING_API_BASE_URL}/grading-jobs/ongoing`);
      const data = (await readJsonResponse(response)) as { items?: OngoingGradingJob[] };
      if (!response.ok) {
        throw new Error(parseApiError(data, "Failed to load ongoing jobs."));
      }
      setOngoingJobs(data.items ?? []);
    } catch (e) {
      console.error(e);
      if (!opts?.quiet) setOngoingJobs([]);
    } finally {
      if (!opts?.quiet) setOngoingJobsLoading(false);
    }
  }, []);

  const openOngoingJob = (job: OngoingGradingJob) => {
    if (!job.rubric_id) return;
    const jobId = job.batch_job_id?.trim() || null;
    // Drop previous session rows immediately so View never flashes the wrong batch.
    setDashboardStudents([]);
    setSubmissionsLoading(true);
    setGradingRubricId(job.rubric_id);
    setPendingRubricId(job.rubric_id);
    setActiveBatchJobId(jobId);
    setBatchProgressRunning(true);
    setPage(5);
    void fetchSubmissionsForRubric(job.rubric_id, { batchJobId: jobId });
  };

  useEffect(() => {
    if (page !== 1) return;
    void fetchOngoingJobs();
    const timer = window.setInterval(() => {
      void fetchOngoingJobs({ quiet: true });
    }, 2000);
    return () => window.clearInterval(timer);
  }, [page, fetchOngoingJobs]);

  const fetchGradingHistory = useCallback(async (opts?: { quiet?: boolean }) => {
    if (!opts?.quiet) setGradingHistoryLoading(true);
    try {
      const response = await fetch(`${GRADING_API_BASE_URL}/grading-history?limit=200`);
      const data = (await readJsonResponse(response)) as { items?: GradingHistoryItem[] };
      if (!response.ok) {
        throw new Error(parseApiError(data, "Failed to load grading history."));
      }
      setGradingHistory(sortGradingHistoryNewestFirst(data.items ?? []));
    } catch (e) {
      console.error(e);
      if (!opts?.quiet) setGradingHistory([]);
    } finally {
      if (!opts?.quiet) setGradingHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    if (page === 1 || page === 9) {
      void fetchGradingHistory();
    }
  }, [page, fetchGradingHistory]);

  const openHistorySession = (item: GradingHistoryItem) => {
    if (!item._id) return;
    const jobId = item.batch_job_id?.trim() || null;
    // Drop previous session rows immediately so View never flashes the wrong batch.
    setDashboardStudents([]);
    setSubmissionsLoading(true);
    setGradingRubricId(item._id);
    setPendingRubricId(item._id);
    setRubricId(item._id);
    setActiveBatchJobId(jobId);
    setBatchProgressRunning(
      Boolean(
        (item.counts?.processing ?? 0) > 0 || (item.counts?.not_started ?? 0) > 0,
      ),
    );
    setPage(5);
    // Fetch this batch explicitly (don't rely on state timing / prior activeBatchJobId).
    void fetchSubmissionsForRubric(item._id, { batchJobId: jobId });
  };

  const openHistoryEdit = (item: GradingHistoryItem) => {
    setHistoryEditError(null);
    setHistoryEditItem(item);
    setEditSessionName(item.session_name || "");
    setEditSubjectCode(item.subject_code || "");
    setEditSubjectName(item.subject_name || "");
    setEditYear(item.year != null ? String(item.year) : String(new Date().getFullYear()));
    setEditMonth(item.month != null ? String(item.month) : String(new Date().getMonth() + 1));
    setEditSemester(item.semester != null ? String(item.semester) : "1");
  };

  const saveHistoryEdit = async () => {
    if (!historyEditItem?._id) return;
    setHistoryEditSaving(true);
    setHistoryEditError(null);
    try {
      const response = await fetch(`${GRADING_API_BASE_URL}/rubric/${historyEditItem._id}/session`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_name: editSessionName.trim(),
          subject_code: editSubjectCode.trim(),
          subject_name: editSubjectName.trim(),
          year: Number(editYear),
          month: Number(editMonth),
          semester: Number(editSemester),
        }),
      });
      const data = await readJsonResponse(response);
      if (!response.ok) {
        throw new Error(parseApiError(data, "Failed to update session."));
      }
      setHistoryEditItem(null);
      await fetchGradingHistory({ quiet: true });
    } catch (e) {
      setHistoryEditError(e instanceof Error ? e.message : "Failed to update session.");
    } finally {
      setHistoryEditSaving(false);
    }
  };

  const confirmHistoryDelete = async () => {
    if (!historyDeleteItem?._id) return;
    setHistoryDeleting(true);
    try {
      const params = new URLSearchParams({ purge_submissions: "true" });
      if (historyDeleteItem.batch_job_id) {
        params.set("batch_job_id", historyDeleteItem.batch_job_id);
      }
      const response = await fetch(
        `${GRADING_API_BASE_URL}/rubric/${encodeURIComponent(historyDeleteItem._id)}?${params.toString()}`,
        { method: "DELETE" },
      );
      const data = await readJsonResponse(response);
      if (!response.ok) {
        throw new Error(parseApiError(data, "Failed to delete session."));
      }
      if (gradingRubricId === historyDeleteItem._id) {
        const deletedWhole =
          !historyDeleteItem.batch_job_id ||
          Boolean((data as { deleted_rubric?: boolean }).deleted_rubric);
        if (deletedWhole) {
          setGradingRubricId(null);
          setDashboardStudents([]);
          setActiveBatchJobId(null);
        } else if (activeBatchJobId === historyDeleteItem.batch_job_id) {
          setDashboardStudents([]);
          setActiveBatchJobId(null);
        }
      }
      if (rubricId === historyDeleteItem._id && (data as { deleted_rubric?: boolean }).deleted_rubric) {
        setRubricId(null);
      }
      setHistoryDeleteItem(null);
      await fetchGradingHistory({ quiet: true });
    } catch (e) {
      console.error(e);
      setHistoryEditError(e instanceof Error ? e.message : "Failed to delete session.");
      setHistoryDeleteItem(null);
    } finally {
      setHistoryDeleting(false);
    }
  };

  const historyStatusBadge = (status?: string) => {
    const s = status || "Draft";
    if (s === "Completed") return "bg-muted text-primary border-0";
    if (s === "Running") return "bg-accent text-accent-foreground border-0";
    if (s === "Alerts") return "bg-amber-50 text-foreground border-0";
    if (s === "Archived") return "bg-muted text-muted-foreground border-0";
    return "bg-muted text-muted-foreground border-0";
  };

  const historySubjectOptions = useMemo(() => {
    const codes = new Set<string>();
    for (const h of gradingHistory) {
      const code = (h.subject_code || "").trim();
      if (code) codes.add(code);
    }
    return Array.from(codes).sort((a, b) => a.localeCompare(b));
  }, [gradingHistory]);

  const historyYearOptions = useMemo(() => {
    const years = new Set<string>();
    for (const h of gradingHistory) {
      if (h.year != null) years.add(String(h.year));
    }
    return Array.from(years).sort((a, b) => Number(b) - Number(a));
  }, [gradingHistory]);

  const rosterReadyToGrade = useMemo(() => {
    if (!validationReport) return false;
    if (validationReport.can_grade) return true;
    return (
      allowSoftWarnings &&
      validationReport.summary.matched > 0 &&
      validationReport.hard_blockers === 0
    );
  }, [validationReport, allowSoftWarnings]);

  const filteredGradingHistory = useMemo(() => {
    const q = historyFilterQuery.trim().toLowerCase();
    const filtered = gradingHistory.filter((h) => {
      if (historyFilterStatus !== "all" && (h.status || "Draft") !== historyFilterStatus) {
        return false;
      }
      if (
        historyFilterSubject !== "all" &&
        (h.subject_code || "").trim() !== historyFilterSubject
      ) {
        return false;
      }
      if (historyFilterYear !== "all" && String(h.year ?? "") !== historyFilterYear) {
        return false;
      }
      if (!q) return true;
      const hay = [
        h.session_name,
        h.subject_code,
        h.subject_name,
        h.status,
        h.date,
        h.year != null ? String(h.year) : "",
        h.batch_job_id,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
    return sortGradingHistoryNewestFirst(filtered);
  }, [
    gradingHistory,
    historyFilterQuery,
    historyFilterStatus,
    historyFilterSubject,
    historyFilterYear,
  ]);

  const fetchSubmissionsForRubric = async (
    rid: string,
    opts?: { quiet?: boolean; batchJobId?: string | null },
  ) => {
    const fetchGen = ++submissionsFetchGenRef.current;
    if (!opts?.quiet) setSubmissionsLoading(true);
    try {
      const params = new URLSearchParams({ rubric_id: rid });
      // Prefer explicit batchJobId (including null = "no job filter") over stale state.
      const jobId =
        opts && "batchJobId" in opts
          ? (opts.batchJobId || "").trim()
          : (activeBatchJobId || "").trim();
      if (jobId) params.set("batch_job_id", jobId);
      const response = await fetch(`${GRADING_API_BASE_URL}/submissions?${params.toString()}`);
      const data = (await readJsonResponse(response)) as { items?: Record<string, unknown>[] };
      if (!response.ok) {
        throw new Error(parseApiError(data, "Failed to load submissions."));
      }
      // Ignore outdated responses (user switched session while this request was in flight).
      if (fetchGen !== submissionsFetchGenRef.current) return [];
      const rows = (data.items ?? []).map((doc) => mapSubmissionToDashboard(doc));
      setDashboardStudents(rows);
      const stillRunning = rows.some(
        (r) => r.status === "not_started" || r.status === "processing",
      );
      setBatchProgressRunning(stillRunning);
      return rows;
    } catch (e) {
      console.error(e);
      if (fetchGen !== submissionsFetchGenRef.current) return [];
      if (!opts?.quiet) setDashboardStudents([]);
      return [];
    } finally {
      if (fetchGen === submissionsFetchGenRef.current && !opts?.quiet) {
      setSubmissionsLoading(false);
      }
    }
  };

  const loadRubricsForPicker = async () => {
    setRubricsListLoading(true);
    try {
      const response = await fetch(`${GRADING_API_BASE_URL}/rubrics`);
      const data = (await readJsonResponse(response)) as { items?: RubricListItem[] };
      if (!response.ok) {
        throw new Error(parseApiError(data, "Failed to load rubrics."));
      }
      setRubricsList(data.items ?? []);
    } catch {
      setRubricsList([]);
    } finally {
      setRubricsListLoading(false);
    }
  };

  useEffect(() => {
    if (page === 5 && gradingRubricId) {
      void fetchSubmissionsForRubric(gradingRubricId, { batchJobId: activeBatchJobId });
    }
  }, [page, gradingRubricId, activeBatchJobId]);

  useEffect(() => {
    if (page === 7 && gradingRubricId) {
      void fetchSubmissionsForRubric(gradingRubricId, {
        quiet: true,
        batchJobId: activeBatchJobId,
      });
    }
  }, [page, gradingRubricId, activeBatchJobId]);

  useEffect(() => {
    if (page !== 5 || !gradingRubricId || !batchProgressRunning) return;
    const timer = window.setInterval(() => {
      void fetchSubmissionsForRubric(gradingRubricId, {
        quiet: true,
        batchJobId: activeBatchJobId,
      });
    }, 2000);
    return () => window.clearInterval(timer);
  }, [page, gradingRubricId, batchProgressRunning, activeBatchJobId]);

  useEffect(() => {
    setProgressModalStudent((prev) => {
      if (!prev) return null;
      const key = prev.submissionId ?? prev.id;
      return (
        dashboardStudents.find((s) => (s.submissionId ?? s.id) === key) ?? prev
      );
    });
  }, [dashboardStudents]);
  useEffect(() => {
    if (!rubricPickerOpen) return;
    loadRubricsForPicker();
    setPendingRubricId(gradingRubricId);
  }, [rubricPickerOpen]);

  useEffect(() => {
    if (page === 4) void loadRubricsForPicker();
  }, [page]);

  useEffect(() => {
    if (page === 4 && rubricId) {
      setGradingRubricId((prev) => prev ?? rubricId);
      setPendingRubricId((prev) => prev ?? rubricId);
    }
  }, [page, rubricId]);

  const selectedGradingRubric = rubricsList.find((r) => r._id === gradingRubricId);
  const selectedRubricLabel =
    (selectedGradingRubric && formatRubricDetailsLabel(selectedGradingRubric)) ||
    (gradingRubricId && rubricId === gradingRubricId
      ? formatRubricDetailsLabel({
          session_name: examName,
          subject_code: subject,
          subject_name: subjectName,
          year: sessionYear ? Number(sessionYear) : null,
          month: sessionMonth ? Number(sessionMonth) : null,
          semester: sessionSemester ? Number(sessionSemester) : null,
        })
      : "") ||
    "";

  const handleRubricUpload = (file: File) => {
    setRubricFile(file);
    setRubricError(null);
    setRubricSuccess(null);
  };

  useEffect(() => {
    if (page !== 3 || !rubricId) return;
    let cancelled = false;
    (async () => {
      setRubricFetchLoading(true);
      setRubricError(null);
      try {
        const response = await fetch(`${GRADING_API_BASE_URL}/rubric/${rubricId}`);
        const data = (await readJsonResponse(response)) as Record<string, unknown>;
        if (!response.ok) {
          throw new Error(parseApiError(data, "Failed to load rubric."));
        }
        const mapped = mapQuestionsFromBackend(data?.questions);
        if (!cancelled) {
          setRubric(mapped);
        }
        if (!cancelled) {
          if (typeof data.session_name === "string" && data.session_name.trim()) {
            setExamName(data.session_name);
          }
          if (typeof data.subject_code === "string" && data.subject_code.trim()) {
            setSubject(data.subject_code);
          }
          if (typeof data.subject_name === "string" && data.subject_name.trim()) {
            setSubjectName(data.subject_name);
          }
          if (typeof data.year === "number") setSessionYear(String(data.year));
          if (typeof data.month === "number") setSessionMonth(String(data.month));
          if (typeof data.semester === "number") setSessionSemester(String(data.semester));
        }
      } catch (error) {
        if (!cancelled) {
          setRubricError(error instanceof Error ? error.message : "Failed to load rubric.");
        }
      } finally {
        if (!cancelled) setRubricFetchLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [page, rubricId]);

  const uploadRubricToBackend = async () => {
    if (!rubricFile) {
      setRubricError("Please upload a rubric file first.");
      return;
    }
    setRubricLoading(true);
    setRubricError(null);
    setRubricSuccess(null);
    try {
      const formData = new FormData();
      formData.append("file", rubricFile);
      formData.append("session_name", examName);
      formData.append("subject_code", subject);
      formData.append("subject_name", subjectName);
      formData.append("year", sessionYear);
      formData.append("month", sessionMonth);
      formData.append("semester", sessionSemester);

      const response = await fetch(`${GRADING_API_BASE_URL}/upload-rubric`, {
        method: "POST",
        body: formData,
      });
      const data = (await readJsonResponse(response)) as Record<string, unknown>;
      if (!response.ok) {
        throw new Error(parseApiError(data, "Failed to upload rubric."));
      }

      setRubricId((data?.mongodb_id as string) ?? null);
      const mapped = mapQuestionsFromBackend(data?.preview);
      if (mapped.length > 0) {
        setRubric(mapped);
      }
      setRubricSuccess("Rubric extracted successfully.");
      setBatchBackFromSessionSkip(false);
      setPage(3);
    } catch (error) {
      setRubricError(error instanceof Error ? error.message : "Failed to upload rubric.");
    } finally {
      setRubricLoading(false);
    }
  };

  /** Continue from session setup: extract PDF when provided, otherwise jump to batch grading and pick a rubric there. */
  const handleSessionContinue = async () => {
    if (rubricFile) {
      await uploadRubricToBackend();
      return;
    }
    setRubricError(null);
    setRubricSuccess(null);
    setBatchBackFromSessionSkip(true);
    setPage(4);
  };

  const saveRubricEdits = async () => {
    if (!rubricId) {
      setRubricError("Rubric ID missing. Upload the rubric again.");
      return;
    }
    if (rubric.length === 0) {
      setRubricError("Add at least one question before saving.");
      return;
    }
    setRubricSaving(true);
    setRubricError(null);
    setRubricSuccess(null);
    try {
      const payload = {
        session_name: examName,
        subject_code: subject,
        subject_name: subjectName,
        year: Number(sessionYear),
        month: Number(sessionMonth),
        semester: Number(sessionSemester),
        questions: rubric.map((entry) => {
          const criteriaRows = entry.criteria
            .filter((c) => c.point.trim().length > 0)
            .map((c) => ({
              point: c.point.trim(),
              marks: coerceMarks(c.marks),
            }));
          const maxMarks = criteriaRows.reduce((s, c) => s + c.marks, 0);
          return {
            question_no: entry.questionNo,
            question_text: entry.questionText.trim(),
            criteria: criteriaRows,
            max_marks: maxMarks,
          };
        }),
      };

      if (
        payload.questions.some((q) => q.criteria.length === 0 || q.max_marks <= 0)
      ) {
        setRubricError(
          "Each question needs at least one criterion with text, and per-criterion marks must sum to more than zero."
        );
        setRubricSaving(false);
        return;
      }

      const response = await fetch(`${GRADING_API_BASE_URL}/rubric/${rubricId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = (await readJsonResponse(response)) as { item?: { questions?: unknown[] } };
      if (!response.ok) {
        throw new Error(parseApiError(data, "Failed to save rubric changes."));
      }

      const mapped = mapQuestionsFromBackend(data?.item?.questions);
      if (mapped.length > 0) {
        setRubric(mapped);
      }
      setRubricSuccess("Rubric updated successfully.");
      if (rubricId) {
        setGradingRubricId(rubricId);
        setPendingRubricId(rubricId);
      }
      setBatchBackFromSessionSkip(false);
      setPage(4);
    } catch (error) {
      setRubricError(error instanceof Error ? error.message : "Failed to save rubric changes.");
    } finally {
      setRubricSaving(false);
    }
  };

  const uploadBatchZip = async (file: File) => {
    setBatchUploadError(null);
    setBatchUploading(true);
    setBatchId(null);
    setBatchStudentFolderCount(null);
    try {
      const formData = new FormData();
      formData.append("archive", file);
      const response = await fetch(`${GRADING_API_BASE_URL}/upload-student-batch/zip`, {
        method: "POST",
        body: formData,
      });
      const data = (await readJsonResponse(response)) as {
        batch_id?: string;
        student_folder_count?: number;
      };
      if (!response.ok) {
        throw new Error(parseApiError(data, "Upload failed."));
      }
      setBatchId(data.batch_id ?? null);
      setBatchStudentFolderCount(
        typeof data.student_folder_count === "number" ? data.student_folder_count : null
      );
      setUploadedFiles([file.name]);
    } catch (e) {
      setBatchUploadError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      setBatchUploading(false);
    }
  };

  const uploadBatchFolder = async (files: File[]) => {
    setBatchUploadError(null);
    setBatchUploading(true);
    setBatchId(null);
    setBatchStudentFolderCount(null);
    try {
      const formData = new FormData();
      for (const f of files) {
        const rel =
          (f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name;
        formData.append("files", f, rel);
      }
      setUploadedFiles(
        files.map(
          (f) => (f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name,
        ),
      );

      const response = await fetch(`${GRADING_API_BASE_URL}/upload-student-batch/files`, {
        method: "POST",
        body: formData,
      });
      const data = (await readJsonResponse(response)) as {
        batch_id?: string;
        student_folder_count?: number;
      };
      if (!response.ok) {
        throw new Error(parseApiError(data, "Upload failed."));
      }
      setBatchId(data.batch_id ?? null);
      setBatchStudentFolderCount(
        typeof data.student_folder_count === "number" ? data.student_folder_count : null
      );
    } catch (e) {
      setBatchUploadError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      setBatchUploading(false);
    }
  };

  const uploadExamRoster = async (file: File) => {
    if (!gradingRubricId) {
      setBatchUploadError("Select a rubric before uploading the attendance roster.");
      return;
    }
    setRosterUploading(true);
    setBatchUploadError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await fetch(`${GRADING_API_BASE_URL}/rubric/${gradingRubricId}/roster`, {
        method: "POST",
        body: formData,
      });
      const data = (await readJsonResponse(response)) as {
        row_count?: number;
        duplicate_roster_ids?: string[];
        detail?: unknown;
      };
      if (!response.ok) {
        throw new Error(parseApiError(data, "Failed to upload roster."));
      }
      setRosterInfo({
        row_count: data.row_count ?? 0,
        duplicate_roster_ids: data.duplicate_roster_ids ?? [],
      });
      setValidationReport(null);
    } catch (e) {
      setBatchUploadError(e instanceof Error ? e.message : "Roster upload failed.");
    } finally {
      setRosterUploading(false);
    }
  };

  const runPendingUpload = async () => {
    const pending = pendingUpload;
    setPendingUpload(null);
    if (!pending) return;
    if (pending.kind === "zip") {
      await uploadBatchZip(pending.file);
      return;
    }
    if (pending.kind === "folder") {
      await uploadBatchFolder(pending.files);
      return;
    }
    if (pending.kind === "roster") {
      await uploadExamRoster(pending.file);
    }
  };

  const scanPaperIds = async () => {
    if (!batchId) {
      setBatchUploadError("Upload a student batch first.");
      return false;
    }
    setIdScanning(true);
    setBatchUploadError(null);
    try {
      const response = await fetch(`${GRADING_API_BASE_URL}/batches/${batchId}/scan-ids`, {
        method: "POST",
      });
      const data = (await readJsonResponse(response)) as {
        scan?: { papers?: { paper_key: string; ocr_student_id?: string | null }[] };
        detail?: unknown;
      };
      if (!response.ok) {
        throw new Error(parseApiError(data, "Failed to scan paper IDs."));
      }
      const drafts: Record<string, string> = {};
      for (const paper of data.scan?.papers ?? []) {
        drafts[paper.paper_key] = paper.ocr_student_id ?? "";
      }
      setManualIdDrafts(drafts);
      setValidationReport(null);
      return true;
    } catch (e) {
      setBatchUploadError(e instanceof Error ? e.message : "ID scan failed.");
      return false;
    } finally {
      setIdScanning(false);
    }
  };

  const validateRoster = async () => {
    if (!batchId || !gradingRubricId) {
      setBatchUploadError("Need both a rubric (with roster) and a staged batch.");
      return false;
    }
    setValidatingRoster(true);
    setBatchUploadError(null);
    try {
      const response = await fetch(
        `${GRADING_API_BASE_URL}/batches/${batchId}/validate-roster?rubric_id=${encodeURIComponent(gradingRubricId)}`,
        { method: "POST" },
      );
      const data = (await readJsonResponse(response)) as {
        report?: RosterValidationReport;
        detail?: unknown;
      };
      if (!response.ok) {
        throw new Error(parseApiError(data, "Validation failed."));
      }
      setValidationReport(data.report ?? null);
      return true;
    } catch (e) {
      setBatchUploadError(e instanceof Error ? e.message : "Validation failed.");
      return false;
    } finally {
      setValidatingRoster(false);
    }
  };

  const scanAndValidateRoster = async () => {
    if (!batchId) {
      setBatchUploadError("Upload a student batch first.");
      return;
    }
    if (!gradingRubricId) {
      setBatchUploadError("Select a rubric and upload the attendance roster first.");
      return;
    }
    if (!rosterInfo) {
      setBatchUploadError("Upload the attendance roster Excel before scanning and validating.");
      return;
    }
    const scanned = await scanPaperIds();
    if (!scanned) return;
    await validateRoster();
  };

  const saveManualPaperIds = async () => {
    if (!batchId) return;
    setSavingManualIds(true);
    setBatchUploadError(null);
    try {
      const response = await fetch(`${GRADING_API_BASE_URL}/batches/${batchId}/paper-ids`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ overrides: manualIdDrafts }),
      });
      const data = await readJsonResponse(response);
      if (!response.ok) {
        throw new Error(parseApiError(data, "Failed to save ID overrides."));
      }
      await validateRoster();
    } catch (e) {
      setBatchUploadError(e instanceof Error ? e.message : "Failed to save IDs.");
    } finally {
      setSavingManualIds(false);
    }
  };

  const applySessionFieldsToRubric = async (rid: string) => {
    const response = await fetch(`${GRADING_API_BASE_URL}/rubric/${rid}/session`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_name: examName.trim(),
        subject_code: subject.trim(),
        subject_name: subjectName.trim(),
        year: Number(sessionYear),
        month: Number(sessionMonth),
        semester: Number(sessionSemester),
      }),
    });
    const data = await readJsonResponse(response);
    if (!response.ok) {
      throw new Error(parseApiError(data, "Failed to apply session details to rubric."));
    }
  };

  const confirmUseRubric = async () => {
    if (!pendingRubricId) return;
    setApplyingRubric(true);
    setBatchUploadError(null);
    try {
      await applySessionFieldsToRubric(pendingRubricId);
      setGradingRubricId(pendingRubricId);
      setRubricId(pendingRubricId);
      setRubricPickerOpen(false);
    } catch (e) {
      setBatchUploadError(
        e instanceof Error ? e.message : "Failed to apply session details to rubric.",
      );
    } finally {
      setApplyingRubric(false);
    }
  };

  const runBatchGrading = async () => {
    if (!gradingRubricId || !batchId) {
      setBatchUploadError("Select a rubric and upload a batch first.");
      return;
    }
    if (!rosterReadyToGrade) {
      setBatchUploadError(
        validationReport
          ? "Fix roster validation issues (or allow soft warnings) before starting."
          : "Run Scan & validate roster before starting processing.",
      );
      return;
    }
    setBatchUploadError(null);
    setGradingRunning(true);
    try {
      const response = await fetch(`${GRADING_API_BASE_URL}/grade-batch/${gradingRubricId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          batch_id: batchId,
          require_roster_validation: true,
          allow_soft_warnings: allowSoftWarnings,
        }),
      });
      const data = (await readJsonResponse(response)) as {
        detail?: unknown;
        validation?: RosterValidationReport;
        batch_job_id?: string;
        status?: string;
      };
      if (!response.ok) {
        const detail = (data as { detail?: { report?: RosterValidationReport; message?: string } }).detail;
        if (detail && typeof detail === "object" && detail.report) {
          setValidationReport(detail.report);
        }
        throw new Error(parseApiError(data, "Grading failed."));
      }
      if (data.validation) setValidationReport(data.validation);
      if (data.batch_job_id) setActiveBatchJobId(data.batch_job_id);
      setBatchProgressRunning(true);
      setPage(5);
      await fetchSubmissionsForRubric(gradingRubricId);
    } catch (e) {
      setBatchUploadError(e instanceof Error ? e.message : "Grading failed.");
    } finally {
      setGradingRunning(false);
    }
  };

  const rowAiScore = (row: Record<string, unknown>): number => {
    if (row.ai_score != null && row.ai_score !== "") {
      const ai = typeof row.ai_score === "number" ? row.ai_score : Number(row.ai_score);
      if (Number.isFinite(ai)) return ai;
    }
    const score = typeof row.score === "number" ? row.score : Number(row.score ?? 0);
    return Number.isFinite(score) ? score : 0;
  };

  const syncManualOverrideDraft = (student: DashboardStudent | null | undefined) => {
    setLecturerNote(student?.lecturerNote || "");
    setOverrideMessage(null);
    const results = Array.isArray(student?.evaluation?.results)
      ? (student!.evaluation!.results as Record<string, unknown>[])
      : [];
    const next: Record<number, string> = {};
    results.forEach((row, i) => {
      const score = typeof row.score === "number" ? row.score : Number(row.score ?? 0);
      next[i] = Number.isFinite(score) ? String(score) : "0";
    });
    setOverrideScores(next);
  };

  const overrideHasChanges = useMemo(() => {
    if (!selectedStudent) return false;
    const savedNote = (selectedStudent.lecturerNote || "").trim();
    if (lecturerNote.trim() !== savedNote) return true;
    const results = Array.isArray(selectedStudent.evaluation?.results)
      ? (selectedStudent.evaluation!.results as Record<string, unknown>[])
      : [];
    if (results.length === 0) return false;
    return results.some((row, i) => {
      const saved = typeof row.score === "number" ? row.score : Number(row.score ?? 0);
      const draft = Number(overrideScores[i]);
      const savedN = Number.isFinite(saved) ? saved : 0;
      const draftN = Number.isFinite(draft) ? draft : 0;
      return Math.abs(savedN - draftN) > 1e-6;
    });
  }, [selectedStudent, lecturerNote, overrideScores]);

  /** Restore official scores to frozen AI values and clear the Manual tag. */
  const resetManualOverrideToAi = async (student: DashboardStudent | null | undefined) => {
    if (!student?.submissionId) {
      setReviewNotice({
        title: "Cannot reset",
        message: "This student has no saved submission to reset.",
      });
      return;
    }
    const baseEval =
      student.evaluation && typeof student.evaluation === "object"
        ? { ...student.evaluation }
        : null;
    const results = Array.isArray(baseEval?.results)
      ? ([...(baseEval!.results as Record<string, unknown>[])] as Record<string, unknown>[])
      : [];
    if (!baseEval || results.length === 0) {
      setReviewNotice({
        title: "Cannot reset",
        message: "No AI scores available to restore.",
      });
      return;
    }

    const nextResults = results.map((row) => {
      const qNo = String(row.q_no ?? row.question_no ?? "");
      const max = lookupQuestionMax(student, qNo);
      let aiScore = rowAiScore(row);
      if (!Number.isFinite(aiScore) || aiScore < 0) aiScore = 0;
      if (max != null && aiScore > max) aiScore = max;
      return {
        ...row,
        ai_score: aiScore,
        score: Math.round(aiScore * 10000) / 10000,
        manually_overridden: false,
      };
    });

    const nextDraft: Record<number, string> = {};
    nextResults.forEach((row, i) => {
      nextDraft[i] = String(row.score ?? 0);
    });
    setOverrideScores(nextDraft);
    setOverrideSaving(true);
    setOverrideMessage(null);
    try {
      const response = await fetch(`${GRADING_API_BASE_URL}/submissions/${student.submissionId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lecturer_note: lecturerNote,
          evaluation: {
            ...baseEval,
            results: nextResults,
            manual_override: false,
          },
          manual_override: false,
        }),
      });
      const data = (await readJsonResponse(response)) as { item?: Record<string, unknown> };
      if (!response.ok) {
        throw new Error(parseApiError(data, "Failed to reset to AI scores."));
      }
      if (data.item) applyUpdatedSubmission(data.item);
      setOverrideMessage("Restored AI scores.");
    } catch (e) {
      console.error(e);
      setReviewNotice({
        title: "Reset failed",
        message: e instanceof Error ? e.message : "Failed to reset to AI scores.",
      });
    } finally {
      setOverrideSaving(false);
    }
  };

  const lookupQuestionMax = (student: DashboardStudent | null | undefined, qNo: string): number | null => {
    const list = student?.maxMarksPerQuestion;
    if (!list?.length) return null;
    const norm = qNo.replace(/^0+/, "") || qNo;
    const hit = list.find((item) => {
      const key = String(item.question_no || "").trim();
      const keyNorm = key.replace(/^0+/, "") || key;
      return key === qNo || keyNorm === norm || key.padStart(2, "0") === norm.padStart(2, "0");
    });
    if (!hit || !Number.isFinite(hit.max_marks)) return null;
    return hit.max_marks;
  };

  const viewStudentDetail = (student: DashboardStudent) => {
    setSelectedStudent(student);
    setCurrentStudentIndex(dashboardStudents.indexOf(student));
    setParsedText(student.cleanedTranscript || student.rawTranscript || "");
    syncManualOverrideDraft(student);
    setOpenQuestionDiag({});
    setOpenQuestionRag({});
    setPage(6);
  };

  const applyUpdatedSubmission = (doc: Record<string, unknown>) => {
    const mapped = mapSubmissionToDashboard(doc);
    setDashboardStudents((prev) =>
      prev.map((s) =>
        (s.submissionId && s.submissionId === mapped.submissionId) || s.id === mapped.id
          ? mapped
          : s,
      ),
    );
    setSelectedStudent(mapped);
    setParsedText(mapped.cleanedTranscript || mapped.rawTranscript || "");
    syncManualOverrideDraft(mapped);
  };

  const regradeSelectedStudent = async () => {
    if (!selectedStudent?.submissionId) return;
    setRegradingAll(true);
    try {
      const response = await fetch(
        `${GRADING_API_BASE_URL}/submissions/${selectedStudent.submissionId}/regrade`,
        { method: "POST" },
      );
      const data = (await readJsonResponse(response)) as { item?: Record<string, unknown> };
      if (!response.ok) {
        throw new Error(parseApiError(data, "Re-grade failed."));
      }
      if (data.item) applyUpdatedSubmission(data.item);
    } catch (e) {
      console.error(e);
      setReviewNotice({
        title: "Re-grade failed",
        message: e instanceof Error ? e.message : "Re-grade failed.",
      });
    } finally {
      setRegradingAll(false);
    }
  };

  const regradeSelectedQuestion = async (questionNo: string) => {
    if (!selectedStudent?.submissionId) return;
    setRegradingQuestion(questionNo);
    try {
      const response = await fetch(
        `${GRADING_API_BASE_URL}/submissions/${selectedStudent.submissionId}/regrade-question?question_no=${encodeURIComponent(questionNo)}`,
        { method: "POST" },
      );
      const data = (await readJsonResponse(response)) as { item?: Record<string, unknown> };
      if (!response.ok) {
        throw new Error(parseApiError(data, "Question re-grade failed."));
      }
      if (data.item) applyUpdatedSubmission(data.item);
    } catch (e) {
      console.error(e);
      setReviewNotice({
        title: "Question re-grade failed",
        message: e instanceof Error ? e.message : "Question re-grade failed.",
      });
    } finally {
      setRegradingQuestion(null);
    }
  };

  const saveManualOverride = async () => {
    if (!selectedStudent?.submissionId) {
      setReviewNotice({
        title: "Cannot save override",
        message: "This student has no saved submission to override.",
      });
      return;
    }
    const baseEval =
      selectedStudent.evaluation && typeof selectedStudent.evaluation === "object"
        ? { ...selectedStudent.evaluation }
        : null;
    const results = Array.isArray(baseEval?.results)
      ? ([...(baseEval!.results as Record<string, unknown>[])] as Record<string, unknown>[])
      : [];
    if (!baseEval || results.length === 0) {
      setReviewNotice({
        title: "Cannot save override",
        message: "No AI scores available yet. Wait for grading to finish, then override.",
      });
      return;
    }

    const nextResults = results.map((row, i) => {
      const qNo = String(row.q_no ?? row.question_no ?? i + 1);
      const max = lookupQuestionMax(selectedStudent, qNo);
      let score = Number(overrideScores[i]);
      if (!Number.isFinite(score) || score < 0) score = 0;
      if (max != null && score > max) score = max;
      const aiScore = rowAiScore(row);
      return {
        ...row,
        // Keep original AI mark frozen; only `score` is the official/override mark.
        ai_score: aiScore,
        score: Math.round(score * 10000) / 10000,
        manually_overridden: true,
      };
    });

    setOverrideSaving(true);
    setOverrideMessage(null);
    try {
      const response = await fetch(
        `${GRADING_API_BASE_URL}/submissions/${selectedStudent.submissionId}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            lecturer_note: lecturerNote,
            evaluation: { ...baseEval, results: nextResults },
            manual_override: true,
          }),
        },
      );
      const data = (await readJsonResponse(response)) as { item?: Record<string, unknown> };
      if (!response.ok) {
        throw new Error(parseApiError(data, "Failed to save manual override."));
      }
      if (data.item) applyUpdatedSubmission(data.item);
      setOverrideMessage("Override saved. Dashboard score updated.");
    } catch (e) {
      console.error(e);
      setReviewNotice({
        title: "Save failed",
        message: e instanceof Error ? e.message : "Failed to save manual override.",
      });
    } finally {
      setOverrideSaving(false);
    }
  };

  const runReviewConfirm = async () => {
    const action = reviewConfirm;
    setReviewConfirm(null);
    if (!action) return;
    if (action.kind === "reset_ai") {
      await resetManualOverrideToAi(selectedStudent);
      return;
    }
    if (action.kind === "save_override") {
      await saveManualOverride();
      return;
    }
    if (action.kind === "regrade_student") {
      await regradeSelectedStudent();
      return;
    }
    if (action.kind === "regrade_question") {
      await regradeSelectedQuestion(action.questionNo);
    }
  };

  const navigateStudent = (direction: "next" | "prev") => {
    const newIndex =
      direction === "next"
        ? Math.min(currentStudentIndex + 1, dashboardStudents.length - 1)
        : Math.max(currentStudentIndex - 1, 0);
    setCurrentStudentIndex(newIndex);
    const st = dashboardStudents[newIndex];
    setSelectedStudent(st);
    setParsedText(st?.cleanedTranscript || st?.rawTranscript || "");
    syncManualOverrideDraft(st);
  };

  const filteredStudents = filterWarnings
    ? dashboardStudents.filter(
        (s) =>
          s.quickGrade !== undefined &&
          s.maxGrade > 0 &&
          s.quickGrade < s.maxGrade * 0.4
      )
    : dashboardStudents;

  const analyticsDistribution = buildGradeDistribution(dashboardStudents);
  const analyticsQuestionMastery = buildQuestionMastery(dashboardStudents, rubric);
  const exportStem = [
    subject || "session",
    examName,
    sessionYear,
    `s${sessionSemester}`,
  ]
    .map((part) => String(part || "").trim().replace(/[^\w.-]+/g, "_"))
    .filter(Boolean)
    .join("_")
    .slice(0, 80) || "grading_export";

  const exportMarksCsv = () => {
    const graded = dashboardStudents.filter((s) => s.quickGrade != null || s.status === "completed");
    if (dashboardStudents.length === 0) {
      setReviewNotice({
        title: "Nothing to export",
        message: "No submissions loaded for this session yet.",
      });
      return;
    }

    const questionKeys = new Set<string>();
    for (const entry of rubric) questionKeys.add(normalizeQKey(entry.questionNo));
    for (const student of dashboardStudents) {
      const results = Array.isArray(student.evaluation?.results)
        ? (student.evaluation!.results as Record<string, unknown>[])
        : [];
      results.forEach((row, i) => {
        questionKeys.add(normalizeQKey(row.q_no ?? row.question_no, String(i + 1)));
      });
    }
    const qKeys = [...questionKeys].sort((a, b) => Number(a) - Number(b) || a.localeCompare(b));

    const header = [
      "student_id",
      "status",
      "total_score",
      "max_score",
      "percent",
      "manual_override",
      "lecturer_note",
      ...qKeys.map((k) => `Q${k}`),
    ];

    const rows = dashboardStudents.map((student) => {
      const results = Array.isArray(student.evaluation?.results)
        ? (student.evaluation!.results as Record<string, unknown>[])
        : [];
      const byQ = new Map<string, number>();
      results.forEach((row, i) => {
        const key = normalizeQKey(row.q_no ?? row.question_no, String(i + 1));
        const score = typeof row.score === "number" ? row.score : Number(row.score ?? NaN);
        if (Number.isFinite(score)) byQ.set(key, score);
      });
      const pct = studentPercentScore(student);
      return [
        student.id,
        student.status,
        student.quickGrade ?? "",
        student.maxGrade || "",
        pct != null ? pct.toFixed(2) : "",
        student.manualOverride ? "yes" : "no",
        student.lecturerNote || "",
        ...qKeys.map((k) => (byQ.has(k) ? byQ.get(k)! : "")),
      ].map(csvEscape);
    });

    const csv = [header.map(csvEscape).join(","), ...rows.map((r) => r.join(","))].join("\r\n");
    downloadTextFile(`${exportStem}_marks.csv`, csv, "text/csv;charset=utf-8");
    setOverrideMessage(null);
    setReviewNotice({
      title: "CSV downloaded",
      message: `Exported ${dashboardStudents.length} row(s)${graded.length ? ` (${graded.length} with scores)` : ""}.`,
    });
  };

  const exportFeedbackPack = () => {
    if (dashboardStudents.length === 0) {
      setReviewNotice({
        title: "Nothing to export",
        message: "No submissions loaded for this session yet.",
      });
      return;
    }

    const sections = dashboardStudents.map((student) => {
      const results = Array.isArray(student.evaluation?.results)
        ? (student.evaluation!.results as Record<string, unknown>[])
        : [];
      const pct = studentPercentScore(student);
      const qRows = results
        .map((row, i) => {
          const qNo = String(row.q_no ?? row.question_no ?? i + 1);
          const score = typeof row.score === "number" ? row.score : Number(row.score ?? "");
          const justification = String(row.justification ?? "").trim();
          const feedback = String(row.feedback ?? "").trim();
          return `<tr>
            <td>Q${escapeHtml(qNo)}</td>
            <td>${Number.isFinite(score) ? escapeHtml(String(score)) : "—"}</td>
            <td>${escapeHtml(justification || "—")}</td>
            <td>${escapeHtml(feedback || "—")}</td>
          </tr>`;
        })
        .join("\n");

      return `<section class="student">
        <h2>Student ${escapeHtml(student.id)}</h2>
        <p><strong>Status:</strong> ${escapeHtml(student.status)}
          · <strong>Final score:</strong> ${student.quickGrade ?? "—"}/${student.maxGrade || "—"}
          ${pct != null ? ` (${pct.toFixed(1)}%)` : ""}
          ${student.manualOverride ? " · Manual override" : ""}</p>
        ${student.lecturerNote ? `<p><strong>Lecturer note:</strong> ${escapeHtml(student.lecturerNote)}</p>` : ""}
        <table>
          <thead><tr><th>Q</th><th>Final score</th><th>Justification</th><th>Feedback</th></tr></thead>
          <tbody>${qRows || `<tr><td colspan="4">No question results</td></tr>`}</tbody>
        </table>
      </section>`;
    });

    const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>${escapeHtml(exportStem)} feedback pack</title>
  <style>
    body { font-family: Georgia, serif; margin: 24px; color: #111; }
    h1 { font-size: 1.4rem; }
    h2 { font-size: 1.15rem; margin-top: 0; }
    .meta { color: #555; margin-bottom: 1.5rem; }
    .student { border-top: 1px solid #ddd; padding: 1.25rem 0; page-break-inside: avoid; }
    table { width: 100%; border-collapse: collapse; margin-top: 0.75rem; font-size: 0.9rem; }
    th, td { border: 1px solid #ddd; padding: 6px 8px; vertical-align: top; text-align: left; }
    th { background: #f6f6f6; }
    @media print { body { margin: 12mm; } .student { page-break-after: always; } }
  </style>
</head>
<body>
  <h1>Feedback pack</h1>
  <p class="meta">${escapeHtml(subject || "—")} · ${escapeHtml(examName)} · ${escapeHtml(sessionYear)} Sem ${escapeHtml(sessionSemester)}<br/>
  Generated ${escapeHtml(new Date().toLocaleString())} · ${dashboardStudents.length} student(s)</p>
  ${sections.join("\n")}
  <p class="meta">Tip: use Print → Save as PDF for a PDF pack.</p>
</body>
</html>`;

    downloadTextFile(`${exportStem}_feedback.html`, html, "text/html;charset=utf-8");
    setReviewNotice({
      title: "Feedback pack downloaded",
      message: "Open the HTML file and use Print → Save as PDF if you need a PDF pack.",
    });
  };

  const updateQuestionField = (qIdx: number, field: "questionNo" | "questionText", value: string) => {
    setRubric((prev) => {
      const next = [...prev];
      next[qIdx] = { ...next[qIdx], [field]: value };
      return next;
    });
  };

  const updateCriterion = (qIdx: number, cIdx: number, patch: Partial<CriterionEntry>) => {
    setRubric((prev) => {
      const next = [...prev];
      const row = { ...next[qIdx], criteria: [...next[qIdx].criteria] };
      row.criteria[cIdx] = { ...row.criteria[cIdx], ...patch };
      next[qIdx] = row;
      return next;
    });
  };

  const addCriterion = (qIdx: number) => {
    setRubric((prev) => {
      const next = [...prev];
      next[qIdx] = {
        ...next[qIdx],
        criteria: [...next[qIdx].criteria, { point: "", marks: 0 }],
      };
      return next;
    });
  };

  const removeCriterion = (qIdx: number, cIdx: number) => {
    setRubric((prev) => {
      const next = [...prev];
      next[qIdx] = {
        ...next[qIdx],
        criteria: next[qIdx].criteria.filter((_, i) => i !== cIdx),
      };
      return next;
    });
  };

  const paperTotalMarks = rubric.reduce((sum, r) => sum + sumQuestionMarks(r), 0);

  const canFinalizeRubric =
    rubric.length > 0 &&
    !rubricFetchLoading &&
    rubric.every(
      (q) =>
        q.criteria.length > 0 &&
        q.criteria.some((c) => c.point.trim().length > 0) &&
        sumQuestionMarks(q) > 0
    );

  return (
    <div className="p-8 space-y-6">
      <AIPageBanner model="lexo" />

      {/* ═══ PAGE 1: Command Center ═══ */}
      {page === 1 && (
        <div className="space-y-6">
          <div>
            <h2 className="tracking-tight text-foreground">Handwritten Grading</h2>
            <p className="text-sm text-muted-foreground mt-1">Command center for AI-assisted answer grading</p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {/* Card 1: Start AI Answer Grading */}
            <Card
              className="p-6 hover:border-primary/40 transition-colors duration-200 cursor-pointer"
              onClick={() => setPage(2)}
            >
              <div className="flex items-start gap-4">
                <div className="size-14 rounded-2xl bg-primary text-primary-foreground flex items-center justify-center shrink-0">
                  <Sparkles className="size-7" />
                </div>
                <div className="flex-1">
                  <h3 className="text-lg text-foreground mb-1">Start AI Answer Grading</h3>
                  <p className="text-sm text-muted-foreground">
                    Launch the OCR + RAG pipeline to grade handwritten exams with AI assistance.
                  </p>
                  <div className="mt-3 flex items-center gap-2 text-primary">
                    <span className="text-sm">Begin session</span>
                    <ArrowRight className="size-4" />
                  </div>
                </div>
              </div>
            </Card>

            {/* Card 2: Lecture Knowledge Base */}
            <Card
              className="p-6 hover:border-primary/40 transition-colors duration-200 cursor-pointer"
              onClick={() => setPage(8)}
            >
              <div className="flex items-start gap-4">
                <div className="size-14 rounded-2xl bg-primary text-primary-foreground flex items-center justify-center shrink-0">
                  <BookOpen className="size-7" />
                </div>
                <div className="flex-1">
                  <h3 className="text-lg text-foreground mb-1">Lecture Knowledge Base</h3>
                  <p className="text-sm text-muted-foreground">
                    Upload and manage lecture PDFs or PowerPoints indexed for RAG during grading.
                  </p>
                  <div className="mt-3 flex items-center gap-2 text-primary">
                    <span className="text-sm">Manage materials</span>
                    <ArrowRight className="size-4" />
                  </div>
                </div>
              </div>
            </Card>

            {/* Card 3: Ongoing Grading Tasks */}
            <Card className="p-6 border-border">
              <div className="flex items-start gap-4">
                <div className="size-14 rounded-2xl bg-primary text-primary-foreground flex items-center justify-center shrink-0">
                  <RefreshCw
                    className={`size-7 ${ongoingJobs.length > 0 || ongoingJobsLoading ? "animate-spin" : ""}`}
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <h3 className="text-lg text-foreground">Ongoing Grading Tasks</h3>
                    <Badge variant="secondary" className="shrink-0">
                      {ongoingJobs.length} active
                    </Badge>
                  </div>
                  {ongoingJobsLoading && ongoingJobs.length === 0 ? (
                    <p className="text-sm text-muted-foreground">Checking for running sessions…</p>
                  ) : ongoingJobs.length === 0 ? (
                    <>
                  <p className="text-sm text-muted-foreground">No background tasks running</p>
                  <div className="mt-3 text-xs text-muted-foreground">
                        Sessions appear here as soon as a batch is queued or processing.
                  </div>
                    </>
                  ) : (
                    <div className="mt-2 space-y-2">
                      {ongoingJobs.slice(0, 3).map((job) => {
                        const counts = job.progress?.counts;
                        const percent = job.progress?.percent ?? 0;
                        const label =
                          [job.subject_code, job.session_name].filter(Boolean).join(" · ") ||
                          "Grading session";
                        return (
                          <button
                            key={`${job.rubric_id}-${job.batch_job_id ?? "x"}`}
                            type="button"
                            onClick={() => openOngoingJob(job)}
                            className="w-full text-left rounded-lg border border-border bg-card px-3 py-2 hover:border-primary/40 hover:bg-accent/30 transition-colors"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-sm text-foreground truncate">{label}</span>
                              <span className="text-xs tabular-nums text-foreground shrink-0">
                                {Math.round(Number(percent))}%
                              </span>
                            </div>
                            <div className="mt-1 text-[11px] text-muted-foreground truncate">
                              {job.current_stage === "queued"
                                ? "Queued…"
                                : job.current_student_id
                                  ? `Current ${job.current_student_id}`
                                  : "Processing…"}
                              {counts?.not_started != null && counts.not_started > 0 && (
                                <> · {counts.not_started} queued</>
                              )}
                              {counts?.processing != null && counts.processing > 0 && (
                                <> · {counts.processing} processing</>
                              )}
                              {job.progress?.finished != null && job.progress?.total != null && (
                                <> · {job.progress.finished}/{job.progress.total} done</>
                              )}
                            </div>
                            <Progress value={Number(percent) || 0} className="h-1.5 mt-2" />
                          </button>
                        );
                      })}
                      {ongoingJobs.length > 3 && (
                        <div className="text-[11px] text-muted-foreground">
                          +{ongoingJobs.length - 3} more running
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </Card>
          </div>

          {/* Recent Grading History */}
          <Card className="p-6 border-border">
            <div className="flex items-center justify-between mb-4 gap-3">
              <div>
              <h3 className="text-lg text-foreground">Recent Grading History</h3>
                <p className="text-xs text-muted-foreground mt-0.5">Latest exam sessions from your database</p>
            </div>
              <div className="flex items-center gap-2 shrink-0">
                <Badge className="bg-muted text-muted-foreground border-0">
                  {gradingHistory.length} sessions
                </Badge>
                <Button variant="outline" size="sm" onClick={() => setPage(9)}>
                  View all
                </Button>
              </div>
            </div>
            {gradingHistoryLoading && gradingHistory.length === 0 ? (
              <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground justify-center">
                <RefreshCw className="size-4 animate-spin" /> Loading history…
              </div>
            ) : gradingHistory.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">
                No grading sessions yet. Start a session to see history here.
              </p>
            ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="border-b border-border">
                  <tr className="text-left text-xs text-muted-foreground uppercase tracking-wide">
                    <th className="pb-3">Session Name</th>
                    <th className="pb-3">Subject Code</th>
                    <th className="pb-3">Date</th>
                    <th className="pb-3">Avg. Score</th>
                    <th className="pb-3">Status</th>
                  </tr>
                </thead>
                <tbody className="text-sm">
                    {gradingHistory.slice(0, 3).map((h) => (
                      <tr
                        key={h.history_key || `${h._id}-${h.batch_job_id || "draft"}`}
                        className="border-b border-border hover:bg-muted/40 cursor-pointer"
                        onClick={() => openHistorySession(h)}
                      >
                        <td className="py-3 text-foreground">{h.session_name || "—"}</td>
                        <td className="py-3 text-muted-foreground">{h.subject_code || "—"}</td>
                        <td className="py-3 text-muted-foreground">{h.date || "—"}</td>
                        <td className="py-3 text-foreground">
                          {typeof h.avg_score === "number" ? `${h.avg_score}%` : "—"}
                        </td>
                      <td className="py-3">
                          <Badge className={historyStatusBadge(h.status)}>{h.status || "Draft"}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            )}
          </Card>
        </div>
      )}

      {/* ═══ PAGE 2: Session Initialization ═══ */}
      {page === 2 && (
        <div className="space-y-6 max-w-3xl">
          <div>
            <h2 className="tracking-tight text-foreground">Session Initialization</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Set the exam context. These details are stored with the rubric and copied onto graded papers.
            </p>
          </div>

          <Card className="border-border bg-muted/40 shadow-sm">
            <div className="p-6 space-y-6">
              <section className="space-y-4">
                <div>
                  <h3 className="text-sm font-semibold text-foreground">Course</h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    From Knowledge Base — RAG uses this subject code
                  </p>
                </div>
              <div className="grid sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Subject code
                  </label>
                  <Select
                    value={subject || undefined}
                    onValueChange={handleSubjectChange}
                    disabled={coursesLoading || courses.length === 0}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue
                        placeholder={
                          coursesLoading
                            ? "Loading courses…"
                            : courses.length
                              ? "Select a course"
                              : "No courses yet"
                        }
                      />
                    </SelectTrigger>
                    <SelectContent>
                      {courses.map((course) => (
                        <SelectItem key={course._id} value={course.code}>
                          {formatCourseLabel(course)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Subject name
                  </label>
                  <Input
                    value={subjectName}
                    readOnly
                    tabIndex={-1}
                    onFocus={(e) => e.currentTarget.blur()}
                    className="h-10 bg-card border-border text-muted-foreground cursor-default caret-transparent select-none focus-visible:ring-0 focus-visible:border-border"
                    placeholder="Filled from the selected course"
                  />
                </div>
              </div>
              {courses.length === 0 && !coursesLoading && (
                <Button
                  type="button"
                  variant="link"
                  className="px-0 h-auto text-primary"
                  onClick={() => setPage(8)}
                >
                  Add a course in Knowledge Base
                </Button>
              )}
              </section>

              <Separator />

              <section className="space-y-4">
                <div>
                  <h3 className="text-sm font-semibold text-foreground">Exam term</h3>
                  <p className="text-xs text-muted-foreground mt-0.5">Academic period for this sitting</p>
                </div>
              <div className="grid sm:grid-cols-3 gap-4">
                <div className="space-y-1.5 min-w-0">
                  <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Year
                  </label>
                  <Select value={sessionYear} onValueChange={setSessionYear}>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select year" />
                    </SelectTrigger>
                    <SelectContent>
                      {yearOptions.map((y) => (
                        <SelectItem key={y} value={y}>{y}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5 min-w-0">
                  <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Month
                  </label>
                  <Select value={sessionMonth} onValueChange={setSessionMonth}>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select month" />
                    </SelectTrigger>
                    <SelectContent>
                      {MONTH_OPTIONS.map((m) => (
                        <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5 min-w-0">
                  <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Semester
                  </label>
                  <Select value={sessionSemester} onValueChange={setSessionSemester}>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select semester" />
                    </SelectTrigger>
                    <SelectContent>
                      {SEMESTER_OPTIONS.map((s) => (
                        <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
            </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Session name
                  </label>
                  <Select value={examName} onValueChange={setExamName}>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select session type" />
                    </SelectTrigger>
                    <SelectContent>
                      {SESSION_NAME_OPTIONS.map((name) => (
                        <SelectItem key={name} value={name}>{name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </section>

              <Separator />

              <section className="space-y-4">
                <div>
                  <h3 className="text-sm font-semibold text-foreground">Marking scheme</h3>
                  <p className="text-xs text-muted-foreground mt-0.5">Optional — you can pick an existing rubric later</p>
                </div>
                <div
                  onClick={() => rubricFileInputRef.current?.click()}
                  className="border border-dashed border-border rounded-lg p-5 bg-card hover:border-primary/40 hover:bg-accent/40 cursor-pointer transition-colors"
                >
                {rubricFile ? (
                  <div className="flex items-center gap-3">
                    <div className="size-10 rounded-md bg-muted border border-border flex items-center justify-center shrink-0">
                      <FileText className="size-5 text-primary" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm text-foreground truncate">{rubricFile.name}</div>
                      <div className="text-xs text-muted-foreground mt-0.5">PDF ready to extract</div>
                    </div>
                  </div>
                ) : (
                  <div className="text-center">
                    <Upload className="size-5 text-muted-foreground mx-auto mb-2" />
                    <div className="text-sm text-foreground">Click to upload a rubric PDF</div>
                    <div className="text-xs text-muted-foreground mt-1">
                      Skip this if you already have a rubric on the server
                    </div>
                  </div>
                )}
                </div>
              <input
                ref={rubricFileInputRef}
                type="file"
                accept=".pdf,application/pdf"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleRubricUpload(file);
                }}
              />
              </section>
            </div>
          </Card>

          <div className="flex flex-wrap items-center gap-3">
            <Button variant="outline" onClick={() => setPage(1)}>
              <ArrowLeft className="size-4 mr-2" /> Back
            </Button>
            <Button
              onClick={handleSessionContinue}
              disabled={!subject || !examName || rubricLoading || courses.length === 0}
            >
              {rubricLoading ? (
                <><RefreshCw className="size-4 mr-2 animate-spin" /> Extracting rubric...</>
              ) : rubricFile ? (
                <>Extract rubric and verify <ArrowRight className="size-4 ml-2" /></>
              ) : (
                <>Continue to batch grading <ArrowRight className="size-4 ml-2" /></>
              )}
            </Button>
            {rubricError && <div className="text-sm text-destructive w-full">{rubricError}</div>}
            {rubricSuccess && <div className="text-sm text-emerald-700 dark:text-emerald-400 w-full">{rubricSuccess}</div>}
          </div>
        </div>
      )}

      {/* ═══ PAGE 3: Rubric Verification ═══ */}
      {page === 3 && (
        <div className="space-y-6">
          <div>
            <h2 className="tracking-tight text-foreground">Rubric Verification</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Verify and edit the extracted marking scheme before grading, or skip to batch grading and select a rubric there.
            </p>
            {rubricId && (
              <div className="mt-2 text-sm text-muted-foreground">
                {formatRubricDetailsLabel({
                  session_name: examName,
                  subject_code: subject,
                  subject_name: subjectName,
                  year: sessionYear ? Number(sessionYear) : null,
                  month: sessionMonth ? Number(sessionMonth) : null,
                  semester: sessionSemester ? Number(sessionSemester) : null,
                }) || "Rubric loaded"}
                {rubricFetchLoading && (
                  <span className="ml-2 text-primary inline-flex items-center gap-1 text-xs">
                    <RefreshCw className="size-3 animate-spin" /> Syncing from server…
                  </span>
                )}
              </div>
            )}
          </div>

          <Card className="p-6 border-border">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-foreground">Extracted Rubric</h3>
              <Badge className="bg-muted text-muted-foreground border-0">
                Paper total: {paperTotalMarks} marks
              </Badge>
            </div>

            {rubricFetchLoading ? (
              <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground border border-border rounded-lg">
                <RefreshCw className="size-5 animate-spin" />
                Loading rubric from the API…
              </div>
            ) : rubric.length === 0 ? (
              <div className="py-12 px-4 text-center text-sm text-muted-foreground border border-border rounded-lg space-y-3">
                <p>
                  No questions were returned. Upload a PDF on session setup, go back to try again, or use{" "}
                  <span className="font-medium text-foreground">Skip to batch grading</span> below and pick an existing rubric on the next screen.
                </p>
                <p className="text-xs">
                  Backend: <span className="font-mono text-foreground">{GRADING_API_BASE_URL}</span>
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {rubric.map((entry, qi) => (
                  <Card key={`${entry.questionNo}-${qi}`} className="p-4 border-border shadow-sm">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="flex flex-wrap items-end gap-3">
                        <div className="space-y-1">
                          <label className="text-xs text-muted-foreground">Question #</label>
                          <Input
                            value={entry.questionNo}
                            onChange={(e) => updateQuestionField(qi, "questionNo", e.target.value)}
                            className="w-24 font-mono"
                            aria-label="Question number"
                          />
                        </div>
                      </div>
                      <Badge className="bg-muted text-foreground border-border shrink-0">
                        Question total: {sumQuestionMarks(entry)} marks
                      </Badge>
                    </div>
                    <div className="mt-3 space-y-1">
                      <label className="text-xs text-muted-foreground">Question wording</label>
                      <Input
                        value={entry.questionText}
                        onChange={(e) => updateQuestionField(qi, "questionText", e.target.value)}
                      />
                    </div>
                    <div className="mt-4">
                      <div className="text-xs font-medium text-muted-foreground mb-2">Criteria (each row is one marking point with its marks)</div>
                      <div className="rounded-lg border border-border overflow-hidden">
                        <table className="w-full text-sm">
                          <thead className="bg-muted/40 border-b border-border">
                            <tr className="text-left text-xs text-muted-foreground uppercase tracking-wide">
                              <th className="p-2 pl-3">Criterion</th>
                              <th className="p-2 w-28 text-right">Marks</th>
                              <th className="p-2 w-12" />
                            </tr>
                          </thead>
                          <tbody>
                            {entry.criteria.length === 0 ? (
                              <tr>
                                <td colSpan={3} className="p-4 text-xs text-muted-foreground">
                                  No criteria yet - use &quot;Add criterion&quot; below.
                                </td>
                              </tr>
                            ) : (
                              entry.criteria.map((c, ci) => (
                                <tr key={ci} className="border-b border-border last:border-0">
                                  <td className="p-2 pl-3 align-top">
                                    <Textarea
                                      value={c.point}
                                      onChange={(e) => updateCriterion(qi, ci, { point: e.target.value })}
                                      rows={2}
                                      className="text-sm resize-y min-h-[2.75rem]"
                                      placeholder="What is assessed"
                                    />
                                  </td>
                                  <td className="p-2 align-top text-right">
                                    <Input
                                      type="number"
                                      min={0}
                                      step={0.5}
                                      value={c.marks}
                                      onChange={(e) => {
                                        const v = e.target.value;
                                        updateCriterion(qi, ci, {
                                          marks: v === "" ? 0 : Number(v),
                                        });
                                      }}
                                      className="w-full text-right tabular-nums"
                                    />
                                  </td>
                                  <td className="p-2 align-top">
                                    <Button
                                      type="button"
                                      variant="ghost"
                                      size="icon"
                                      className="text-muted-foreground hover:text-destructive"
                                      onClick={() => removeCriterion(qi, ci)}
                                      aria-label="Remove criterion"
                                    >
                                      <Trash2 className="size-4" />
                                    </Button>
                                  </td>
                                </tr>
                              ))
                            )}
                          </tbody>
                        </table>
                      </div>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="mt-2"
                        onClick={() => addCriterion(qi)}
                      >
                        <Plus className="size-4 mr-1" /> Add criterion
                      </Button>
                    </div>
                  </Card>
                ))}
              </div>
            )}

            <div className="mt-4 flex items-center gap-2 text-xs text-muted-foreground">
              <CheckCircle2 className="size-4 text-emerald-500 shrink-0" />
              Edit below, then click Finalize — changes are saved with{" "}
              <span className="font-mono">PUT /rubric/&lt;id&gt;</span>.
            </div>
          </Card>

          <div className="flex flex-wrap gap-3">
            <Button variant="outline" onClick={() => setPage(2)}>
              <ArrowLeft className="size-4 mr-2" /> Back
            </Button>
            <Button
              type="button"
              variant="outline"
              className="border-border"
              onClick={() => {
                setRubricError(null);
                setBatchBackFromSessionSkip(false);
                setPage(4);
              }}
            >
              Skip to batch grading <ChevronRight className="size-4 ml-1" />
            </Button>
            <Button
              className="ml-auto sm:ml-0"
              onClick={saveRubricEdits}
              disabled={rubricSaving || !canFinalizeRubric}
            >
              {rubricSaving ? (
                <><RefreshCw className="size-4 mr-2 animate-spin" /> Saving rubric...</>
              ) : (
                <>Finalize Rubric & Upload Scripts <ArrowRight className="size-4 ml-2" /></>
              )}
            </Button>
          </div>
          {rubricError && <div className="text-sm text-destructive">{rubricError}</div>}
          {rubricSuccess && <div className="text-sm text-emerald-700 dark:text-emerald-400">{rubricSuccess}</div>}
        </div>
      )}

      {/* ═══ PAGE 4: Batch Script Ingestion ═══ */}
      {page === 4 && (
        <div className="space-y-6 max-w-3xl">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="tracking-tight text-foreground">Batch Script Ingestion</h2>
              <p className="text-sm text-muted-foreground mt-1">
                Choose a marking rubric, upload student scripts, then validate IDs against the attendance roster.
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={() => setRubricPickerOpen(true)}>
              <BookOpen className="size-4 mr-2" /> Choose rubric
            </Button>
          </div>

          <Card className="p-5 border-border bg-muted/40 shadow-sm space-y-3">
            <div>
              <h3 className="text-sm font-semibold text-foreground">Selected rubric</h3>
              <p className="text-xs text-muted-foreground mt-0.5">Required before staging papers or starting grading</p>
            </div>
            {gradingRubricId ? (
              <div className="rounded-md border border-border bg-card px-3 py-2.5 min-w-0">
                <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {selectedRubricLabel || "Selected rubric"}
                </div>
                {selectedGradingRubric?.filename ? (
                  <div className="text-xs text-muted-foreground mt-0.5 truncate">
                    {selectedGradingRubric.filename}
                  </div>
                ) : (
                  <div className="text-xs text-muted-foreground mt-0.5">
                    Use Choose rubric to pick another scheme from the server.
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-foreground">No rubric selected - click “Choose rubric”.</p>
            )}
          </Card>

          <Card className="p-6 border-border bg-muted/40 shadow-sm space-y-5">
            <div>
              <h3 className="text-sm font-semibold text-foreground">Student scripts</h3>
              <p className="text-xs text-muted-foreground mt-0.5">ZIP or folder — one student ID folder per paper</p>
            </div>
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Upload ZIP archive</label>
                <div
                  onClick={() => !batchUploading && zipInputRef.current?.click()}
                  className={`border border-dashed rounded-lg p-5 text-center bg-card cursor-pointer transition-colors ${
                    batchUploading
                      ? "opacity-60 pointer-events-none border-border"
                      : "border-border hover:border-primary/40 hover:bg-accent/40"
                  }`}
                >
                  <Upload className="size-5 text-primary mx-auto mb-2" />
                  <div className="text-sm text-foreground">Click to select .zip</div>
                  <div className="text-xs text-muted-foreground mt-1">StudentID / page.jpg</div>
                </div>
                <input
                  ref={zipInputRef}
                  type="file"
                  accept=".zip,application/zip"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) setPendingUpload({ kind: "zip", file: f });
                    e.target.value = "";
                  }}
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Or upload folder</label>
                <div
                  onClick={() => !batchUploading && folderInputRef.current?.click()}
                  className={`border border-dashed rounded-lg p-5 text-center bg-card cursor-pointer transition-colors ${
                    batchUploading
                      ? "opacity-60 pointer-events-none border-border"
                      : "border-border hover:border-primary/40 hover:bg-accent/40"
                  }`}
                >
                  <FolderOpen className="size-5 text-primary mx-auto mb-2" />
                  <div className="text-sm text-foreground">Select folder (Chrome / Edge)</div>
                  <div className="text-xs text-muted-foreground mt-1">Preserves student subfolders</div>
                </div>
                {/* webkitdirectory enables folder picker in Chromium */}
                <input
                  ref={folderInputRef}
                  type="file"
                  multiple
                  accept="image/*,.pdf"
                  className="hidden"
                  {...({ webkitdirectory: "" } as Record<string, string>)}
                  onChange={(e) => {
                    const files = e.target.files;
                    if (files && files.length > 0) {
                      setPendingUpload({ kind: "folder", files: Array.from(files) });
                    }
                    e.target.value = "";
                  }}
                />
              </div>
            </div>

            {batchUploading && (
              <div className="flex items-center gap-2 text-sm text-primary">
                <RefreshCw className="size-4 animate-spin" /> Uploading to server…
              </div>
            )}

            {batchId && (
              <div className="rounded-lg bg-muted border border-border px-3 py-2 text-sm text-emerald-900">
                Batch staged: <span className="font-mono">{batchId}</span>
                {batchStudentFolderCount !== null && (
                  <> · {batchStudentFolderCount} student folder(s)</>
                )}
              </div>
            )}

            {uploadedFiles.length > 0 && (
              <div className="space-y-2">
                <div className="text-sm text-foreground">{uploadedFiles.length} path(s) uploaded</div>
                <div className="max-h-48 overflow-y-auto space-y-1 bg-card border border-border rounded-md p-2 text-xs font-mono">
                  {uploadedFiles.slice(0, 80).map((name, i) => (
                    <div key={i} className="truncate text-muted-foreground">
                      {name}
                    </div>
                  ))}
                  {uploadedFiles.length > 80 && (
                    <div className="text-muted-foreground">… and {uploadedFiles.length - 80} more</div>
                  )}
                </div>
              </div>
            )}
          </Card>

          <Card className="p-6 border-border bg-muted/40 shadow-sm space-y-4">
            <div>
              <h3 className="text-sm font-semibold text-foreground">Attendance roster &amp; ID validation</h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                Upload the exam attendance Excel, then scan &amp; validate paper IDs against the roster
                (folder names preferred; OCR is a fallback). Fix mismatches below if needed.
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                disabled={!gradingRubricId || rosterUploading}
                onClick={() => rosterInputRef.current?.click()}
              >
                {rosterUploading ? (
                  <><RefreshCw className="size-4 mr-2 animate-spin" /> Uploading roster…</>
                ) : (
                  <><Upload className="size-4 mr-2" /> Upload roster Excel</>
                )}
              </Button>
              <input
                ref={rosterInputRef}
                type="file"
                accept=".xlsx,.xlsm,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) setPendingUpload({ kind: "roster", file: f });
                  e.target.value = "";
                }}
              />
              <Button
                type="button"
                variant="outline"
                disabled={
                  !batchId ||
                  !gradingRubricId ||
                  !rosterInfo ||
                  idScanning ||
                  validatingRoster
                }
                onClick={() => void scanAndValidateRoster()}
              >
                {idScanning || validatingRoster ? (
                  <>
                    <RefreshCw className="size-4 mr-2 animate-spin" />
                    {idScanning ? "Scanning IDs…" : "Validating…"}
                  </>
                ) : (
                  <><ScanLine className="size-4 mr-2" /> Scan &amp; validate roster</>
                )}
              </Button>
            </div>

            {rosterInfo && (
              <div className="text-xs text-muted-foreground">
                Roster loaded: <span className="font-medium">{rosterInfo.row_count}</span> student(s)
                {rosterInfo.duplicate_roster_ids.length > 0 && (
                  <span className="text-foreground">
                    {" "}· duplicate IDs in Excel: {rosterInfo.duplicate_roster_ids.join(", ")}
                  </span>
                )}
              </div>
            )}

            <label className="flex items-center gap-2 text-sm text-foreground">
              <input
                type="checkbox"
                checked={allowSoftWarnings}
                onChange={(e) => setAllowSoftWarnings(e.target.checked)}
                className="rounded border-border"
              />
              Allow grading with missing/extra papers (matched only)
            </label>

            {validationReport && (
              <div className="space-y-3">
                <div className="flex flex-wrap gap-2 text-xs">
                  <Badge className="bg-muted text-primary border-0">
                    Matched {validationReport.summary.matched}
                  </Badge>
                  <Badge className="bg-amber-50 text-foreground border-0">
                    Missing {validationReport.summary.missing_paper}
                  </Badge>
                  <Badge className="bg-orange-50 text-orange-800 border-0">
                    Extra {validationReport.summary.extra_paper}
                  </Badge>
                  <Badge className="bg-destructive/10 text-destructive border-0">
                    Dup papers {validationReport.summary.duplicate_paper}
                  </Badge>
                  <Badge className="bg-destructive/10 text-destructive border-0">
                    Dup roster {validationReport.summary.duplicate_roster}
                  </Badge>
                  <Badge className="bg-muted text-foreground border-0">
                    Unreadable {validationReport.summary.unreadable_id}
                  </Badge>
                </div>

                <div className="overflow-x-auto border border-border rounded-lg bg-card">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/40 text-xs text-muted-foreground uppercase">
                      <tr>
                        <th className="text-left p-2">Status</th>
                        <th className="text-left p-2">Student ID</th>
                        <th className="text-left p-2">Name</th>
                        <th className="text-left p-2">Paper folder(s)</th>
                        <th className="text-left p-2">Fix ID</th>
                      </tr>
                    </thead>
                    <tbody>
                      {validationReport.rows.map((row, idx) => {
                        const paperKey = row.paper_keys?.[0];
                        const needsFix =
                          row.status === "unreadable_id" ||
                          row.status === "extra_paper";
                        return (
                          <tr key={`${row.status}-${row.student_id ?? paperKey ?? idx}`} className="border-t border-border">
                            <td className="p-2">
                              <Badge
                                variant="outline"
                                className={
                                  row.status === "matched"
                                    ? "border-emerald-300 text-primary"
                                    : row.status.includes("duplicate") || row.status === "unreadable_id"
                                      ? "border-red-300 text-destructive"
                                      : "border-amber-300 text-foreground"
                                }
                              >
                                {row.status}
                              </Badge>
                            </td>
                            <td className="p-2 font-mono text-xs">{row.student_id ?? "—"}</td>
                            <td className="p-2 text-xs text-muted-foreground">{row.name ?? "—"}</td>
                            <td className="p-2 font-mono text-xs text-muted-foreground">
                              {(row.paper_keys ?? []).join(", ") || "—"}
                            </td>
                            <td className="p-2">
                              {needsFix && paperKey ? (
                                <Input
                                  className="h-8 text-xs font-mono"
                                  placeholder="Enter student ID"
                                  value={manualIdDrafts[paperKey] ?? ""}
                                  onChange={(e) =>
                                    setManualIdDrafts((prev) => ({
                                      ...prev,
                                      [paperKey]: e.target.value,
                                    }))
                                  }
                                />
                              ) : (
                                <span className="text-xs text-muted-foreground">—</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {(validationReport.summary.unreadable_id > 0 ||
                  validationReport.summary.extra_paper > 0) && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={savingManualIds}
                    onClick={() => void saveManualPaperIds()}
                  >
                    {savingManualIds ? (
                      <><RefreshCw className="size-4 mr-2 animate-spin" /> Saving IDs…</>
                    ) : (
                      <>Save ID fixes &amp; re-validate</>
                    )}
                  </Button>
                )}
              </div>
            )}
          </Card>

          <div className="flex flex-wrap gap-3">
            <Button
              variant="outline"
              onClick={() => {
                if (batchBackFromSessionSkip) {
                  setBatchBackFromSessionSkip(false);
                  setPage(2);
                } else {
                  setPage(rubricId ? 3 : 2);
                }
              }}
            >
              <ArrowLeft className="size-4 mr-2" /> Back
            </Button>
            <Button
              onClick={() => void runBatchGrading()}
              disabled={
                !gradingRubricId ||
                !batchId ||
                batchUploading ||
                gradingRunning ||
                !rosterReadyToGrade
              }
            >
              {gradingRunning ? (
                <><RefreshCw className="size-4 mr-2 animate-spin" /> Starting batch…</>
              ) : (
                <>Start processing <Sparkles className="size-4 ml-2" /></>
              )}
            </Button>
          </div>
          {!rosterReadyToGrade && gradingRubricId && batchId && !gradingRunning && (
            <p className="text-sm text-muted-foreground">
              {validationReport
                ? "Resolve roster validation issues (or enable “Allow soft warnings”) before starting."
                : "Upload the attendance roster, then run Scan & validate roster before starting."}
            </p>
          )}
          {batchUploadError && <div className="text-sm text-destructive">{batchUploadError}</div>}
        </div>
      )}

      {/* ═══ PAGE 5: Master Evaluation Dashboard ═══ */}
      {page === 5 && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="tracking-tight text-foreground">Master Evaluation Dashboard</h2>
              <p className="text-sm text-muted-foreground mt-1">
                {batchProgressRunning
                  ? "Live batch processing — statuses update as each student finishes"
                  : "Monitor batch processing progress"}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => setFilterWarnings(!filterWarnings)}>
                <Filter className="size-4 mr-2" />
                {filterWarnings ? "Show all" : "Show warnings only"}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => gradingRubricId && fetchSubmissionsForRubric(gradingRubricId)}
                disabled={!gradingRubricId || submissionsLoading}
              >
                <RefreshCw className={`size-4 mr-2 ${submissionsLoading || batchProgressRunning ? "animate-spin" : ""}`} />
                Refresh
              </Button>
              <Badge className="bg-muted text-muted-foreground border-0">
                {dashboardStudents.filter((s) => s.status === "completed").length}/
                {dashboardStudents.length} graded
              </Badge>
            </div>
          </div>

          {dashboardStudents.length > 0 && (
            <Card className="p-4 border-border space-y-2">
              {(() => {
                const total = dashboardStudents.length;
                const finished = dashboardStudents.filter((s) =>
                  ["completed", "failed", "skipped", "warning"].includes(s.status),
                ).length;
                const processing = dashboardStudents.filter((s) => s.status === "processing").length;
                const pending = dashboardStudents.filter((s) => s.status === "not_started").length;
                const percent = total ? Math.round((finished / total) * 100) : 0;
                const durations = dashboardStudents
                  .filter((s) => s.status === "completed" && s.progress?.startedAt && s.processedAt)
                  .map((s) => {
                    const a = Date.parse(String(s.progress?.startedAt));
                    const b = Date.parse(String(s.processedAt));
                    return Number.isFinite(a) && Number.isFinite(b) ? (b - a) / 1000 : null;
                  })
                  .filter((n): n is number => n != null && n > 0);
                const avgSec =
                  durations.length > 0
                    ? durations.reduce((a, b) => a + b, 0) / durations.length
                    : null;
                const batchEta =
                  avgSec != null && pending + processing > 0
                    ? avgSec * (pending + processing)
                    : null;
                const active = dashboardStudents.find((s) => s.status === "processing");
                return (
                  <>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-foreground">
                        {batchProgressRunning ? "Processing…" : "Batch progress"}
                        {activeBatchJobId ? (
                          <span className="ml-2 font-mono text-[11px] text-muted-foreground">
                            job {activeBatchJobId.slice(0, 8)}
                          </span>
                        ) : null}
                      </span>
                      <span className="tabular-nums text-foreground font-medium">{percent}%</span>
                    </div>
                    <Progress value={percent} className="h-2" />
                    <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                      <span>Done {finished}</span>
                      <span>Processing {processing}</span>
                      <span>Not started {pending}</span>
                      <span>Total {total}</span>
                      {batchEta != null && (
                        <span>Batch ETA {formatEtaSeconds(batchEta)}</span>
                      )}
                    </div>
                    {active && (
                      <div className="text-xs text-muted-foreground">
                        Current: <span className="font-mono">{active.id}</span>
                        {" · "}
                        {progressSummaryLine(active)}
                        {" · "}
                        student ETA {formatEtaSeconds(estimateStudentEta(active.progress))}
                      </div>
                    )}
                  </>
                );
              })()}
            </Card>
          )}

          <Card className="p-6 border-border">
            {submissionsLoading && dashboardStudents.length === 0 ? (
              <div className="flex items-center gap-2 py-8 text-muted-foreground text-sm justify-center">
                <RefreshCw className="size-5 animate-spin" /> Loading submissions…
              </div>
            ) : dashboardStudents.length === 0 ? (
              <p className="text-sm text-muted-foreground py-6 text-center">
                No submissions for this rubric yet. Run batch grading from the previous step.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="border-b border-border">
                    <tr className="text-left text-xs text-muted-foreground uppercase tracking-wide">
                      <th className="pb-3">Student ID</th>
                      <th className="pb-3">Status</th>
                      <th className="pb-3">Detail</th>
                      <th className="pb-3">Engine / source</th>
                      <th className="pb-3">Errors</th>
                      <th className="pb-3">Quick grade</th>
                      <th className="pb-3">Action</th>
                    </tr>
                  </thead>
                  <tbody className="text-sm">
                    {filteredStudents.map((student) => (
                      <tr key={student.submissionId ?? student.id} className="border-b border-border hover:bg-muted/40">
                        <td className="py-3 text-foreground font-mono text-xs">{student.id}</td>
                        <td className="py-3">
                          <Badge
                            className={
                              student.status === "completed"
                                ? "bg-muted text-primary border-0"
                                : student.status === "processing"
                                  ? "bg-accent text-accent-foreground border-0"
                                  : student.status === "not_started"
                                    ? "bg-muted text-muted-foreground border-0"
                                    : student.status === "failed"
                                      ? "bg-destructive/10 text-destructive border-0"
                                  : "bg-amber-50 text-foreground border-0"
                            }
                          >
                            {student.status === "processing" && (
                              <RefreshCw className="size-3 mr-1 animate-spin" />
                            )}
                            {student.status === "not_started" && (
                              <Clock className="size-3 mr-1" />
                            )}
                            {(student.status === "warning" || student.status === "skipped" || student.status === "failed") && (
                              <AlertCircle className="size-3 mr-1" />
                            )}
                            {student.status === "completed" && <CheckCircle2 className="size-3 mr-1" />}
                            {student.status === "not_started"
                              ? "Not started"
                              : student.status.charAt(0).toUpperCase() + student.status.slice(1).replace("_", " ")}
                          </Badge>
                        </td>
                        <td className="py-3 text-xs text-muted-foreground">
                          <button
                            type="button"
                            className="text-left hover:text-primary underline-offset-2 hover:underline"
                            onClick={() => setProgressModalStudent(student)}
                          >
                            {progressSummaryLine(student)}
                          </button>
                          {student.status === "processing" && student.progress && (
                            <div className="text-[11px] text-muted-foreground mt-0.5">
                              ETA {formatEtaSeconds(estimateStudentEta(student.progress))}
                            </div>
                          )}
                        </td>
                        <td className="py-3 text-xs text-muted-foreground">
                          {student.gradingEngine || student.sliceSources ? (
                            <div className="space-y-0.5">
                              <div>
                                {student.gradingEngine ? (
                                  <Badge variant="outline" className="text-[10px] font-normal">
                                    {student.gradingEngine}
                                  </Badge>
                                ) : (
                                  <span className="text-muted-foreground">—</span>
                                )}
                              </div>
                              {student.sliceSources && (
                                <div className="text-[11px] text-muted-foreground max-w-[160px] truncate" title={Object.entries(student.sliceSources).map(([k, v]) => `Q${k}:${v}`).join(" · ")}>
                                  {Object.entries(student.sliceSources)
                                    .map(([k, v]) => `Q${k}:${v}`)
                                    .join(" · ")}
                                </div>
                              )}
                            </div>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </td>
                        <td className="py-3 text-xs max-w-[220px]">
                          {(() => {
                            const issues = studentIssueLines(student);
                            if (issues.length === 0) {
                              return <span className="text-muted-foreground">—</span>;
                            }
                            return (
                              <div className="space-y-0.5" title={issues.join("\n")}>
                                <div className="flex items-start gap-1 text-destructive">
                                  <AlertCircle className="size-3.5 mt-0.5 shrink-0" />
                                  <span className="truncate">{issues[0]}</span>
                                </div>
                                {issues.length > 1 && (
                                  <div className="text-[11px] text-red-500/80 pl-4">
                                    +{issues.length - 1} more
                                  </div>
                                )}
                              </div>
                            );
                          })()}
                        </td>
                        <td className="py-3">
                          {student.quickGrade !== undefined ? (
                            <div className="flex items-center gap-1.5">
                            <span className="text-foreground tabular-nums">
                              {student.quickGrade}/{student.maxGrade || "—"}
                            </span>
                              {student.manualOverride && (
                                <Badge
                                  variant="outline"
                                  className="text-[10px] font-normal text-foreground border-amber-300 bg-amber-50"
                                >
                                  Manual
                                </Badge>
                              )}
                            </div>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </td>
                        <td className="py-3">
                          <div className="flex flex-wrap gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => setProgressModalStudent(student)}
                            >
                              Progress
                            </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => viewStudentDetail(student)}
                              disabled={
                                student.status !== "completed" && student.status !== "warning"
                              }
                          >
                            View full report
                          </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <div className="flex gap-3">
            <Button variant="outline" onClick={() => setPage(1)}>
              <ArrowLeft className="size-4 mr-2" /> Back to Dashboard
            </Button>
            <Button  onClick={() => setPage(7)}>
              View Analytics & Export <ArrowRight className="size-4 ml-2" />
            </Button>
          </div>

          <Dialog
            open={progressModalStudent != null}
            onOpenChange={(open) => {
              if (!open) setProgressModalStudent(null);
            }}
          >
            <DialogContent className="sm:max-w-md">
              <DialogHeader>
                <DialogTitle>Student progress</DialogTitle>
                <DialogDescription>
                  Live details for{" "}
                  <span className="font-mono text-foreground">
                    {progressModalStudent?.id ?? "—"}
                  </span>
                </DialogDescription>
              </DialogHeader>
              {progressModalStudent && (() => {
                const p = progressModalStudent.progress;
                const qTotal = p?.questionsTotal ?? 0;
                const qDone =
                  progressModalStudent.status === "completed"
                    ? qTotal || (Array.isArray(progressModalStudent.evaluation?.results)
                        ? (progressModalStudent.evaluation?.results as unknown[]).length
                        : 0)
                    : p?.questionsDone ?? 0;
                const qRemaining = Math.max(0, qTotal - qDone);
                const eta = estimateStudentEta(p);
                const stageLabel =
                  p?.stage === "ocr"
                    ? "Reading pages (OCR)"
                    : p?.stage === "grading"
                      ? "Grading questions"
                      : p?.stage === "done"
                        ? "Finished"
                        : p?.stage === "failed"
                          ? "Failed"
                          : progressModalStudent.status === "not_started"
                            ? "Queued"
                            : progressModalStudent.status;
                return (
                  <div className="space-y-4 text-sm">
                    <div className="grid grid-cols-2 gap-3">
                      <div className="rounded-lg bg-muted/40 p-3">
                        <div className="text-xs text-muted-foreground">Status</div>
                        <div className="mt-1 font-medium text-foreground capitalize">
                          {progressModalStudent.status.replace("_", " ")}
                        </div>
                      </div>
                      <div className="rounded-lg bg-muted/40 p-3">
                        <div className="text-xs text-muted-foreground">Stage</div>
                        <div className="mt-1 font-medium text-foreground">{stageLabel}</div>
                      </div>
                      <div className="rounded-lg bg-muted/40 p-3">
                        <div className="text-xs text-muted-foreground">Questions</div>
                        <div className="mt-1 font-medium text-foreground tabular-nums">
                          {qTotal || "—"}
                        </div>
                      </div>
                      <div className="rounded-lg bg-muted/40 p-3">
                        <div className="text-xs text-muted-foreground">Graded</div>
                        <div className="mt-1 font-medium text-foreground tabular-nums">
                          {qDone}
                        </div>
                      </div>
                      <div className="rounded-lg bg-muted/40 p-3">
                        <div className="text-xs text-muted-foreground">Remaining</div>
                        <div className="mt-1 font-medium text-foreground tabular-nums">
                          {qRemaining}
                        </div>
                      </div>
                      <div className="rounded-lg bg-muted/40 p-3">
                        <div className="text-xs text-muted-foreground">Est. time left</div>
                        <div className="mt-1 font-medium text-foreground">
                          {progressModalStudent.status === "processing"
                            ? formatEtaSeconds(eta)
                            : "—"}
                        </div>
                      </div>
                    </div>

                    {p && (p.stage === "ocr" || p.pagesTotal > 0) && (
                      <div>
                        <div className="flex justify-between text-xs text-muted-foreground mb-1">
                          <span>OCR pages</span>
                          <span className="tabular-nums">
                            {p.pagesDone}/{p.pagesTotal || "?"}
                          </span>
                        </div>
                        <Progress
                          value={
                            p.pagesTotal
                              ? Math.round((p.pagesDone / p.pagesTotal) * 100)
                              : 0
                          }
                          className="h-2"
                        />
                      </div>
                    )}

                    {qTotal > 0 && (
                      <div>
                        <div className="flex justify-between text-xs text-muted-foreground mb-1">
                          <span>
                            Questions
                            {p?.currentQuestion ? ` · current Q${p.currentQuestion}` : ""}
                          </span>
                          <span className="tabular-nums">
                            {qDone}/{qTotal}
                          </span>
                        </div>
                        <Progress
                          value={Math.round((qDone / qTotal) * 100)}
                          className="h-2"
                        />
                      </div>
                    )}

                    {(() => {
                      const issues = studentIssueLines(progressModalStudent);
                      if (issues.length === 0) {
                        return (
                          <div className="text-xs text-muted-foreground">No errors recorded for this student.</div>
                        );
                      }
                      return (
                        <div className="text-xs text-destructive bg-destructive/10 rounded-lg p-2 space-y-1">
                          <div className="font-medium text-red-800">Errors / issues</div>
                          {issues.map((line, i) => (
                            <div key={`${i}-${line.slice(0, 24)}`}>{line}</div>
                          ))}
                        </div>
                      );
                    })()}
                  </div>
                );
              })()}
              <DialogFooter>
                <Button variant="outline" onClick={() => setProgressModalStudent(null)}>
                  Close
                </Button>
                {progressModalStudent &&
                  (progressModalStudent.status === "completed" ||
                    progressModalStudent.status === "warning") && (
                    <Button
                      
                      onClick={() => {
                        const s = progressModalStudent;
                        setProgressModalStudent(null);
                        viewStudentDetail(s);
                      }}
                    >
                      Open full report
                    </Button>
                  )}
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      )}

      {/* ═══ PAGE 6: AI-Assisted Review ═══ */}
      {page === 6 && selectedStudent && (
        <div className="space-y-6">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="tracking-tight text-foreground">AI-Assisted Review</h2>
              <p className="text-sm text-muted-foreground mt-1">Student ID: {selectedStudent.id}</p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={!selectedStudent.submissionId || regradingAll || regradingQuestion != null}
                onClick={() => setReviewConfirm({ kind: "regrade_student" })}
              >
                {regradingAll ? (
                  <><RefreshCw className="size-4 mr-2 animate-spin" /> Re-grading…</>
                ) : (
                  <><RefreshCw className="size-4 mr-2" /> Re-grade student</>
                )}
              </Button>
            <AIBadgePill model="lexo" />
            </div>
          </div>

          <div className="grid lg:grid-cols-2 gap-6">
            {/* Left: Original Scan */}
            <Card className="border-border overflow-hidden flex flex-col">
              <div className="px-4 py-2.5 border-b border-border flex items-center justify-between bg-muted/40">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <FileImage className="size-4" />
                  Original Scan
                </div>
                <div className="flex items-center gap-1">
                  <Button size="icon" variant="ghost" className="size-7" onClick={() => setZoom(z => Math.max(50, z - 25))}>
                    <ZoomOut className="size-3.5" />
                  </Button>
                  <span className="text-xs text-muted-foreground w-10 text-center">{zoom}%</span>
                  <Button size="icon" variant="ghost" className="size-7" onClick={() => setZoom(z => Math.min(200, z + 25))}>
                    <ZoomIn className="size-3.5" />
                  </Button>
                </div>
              </div>

              <div className="flex-1 bg-muted overflow-auto" style={{ minHeight: "500px" }}>
                <div className="p-6 flex items-start justify-center" style={{ transform: `scale(${zoom / 100})`, transformOrigin: "top center" }}>
                  <div className="bg-card rounded-lg shadow-sm p-6 max-w-lg w-full">
                    <div className="text-xs text-muted-foreground uppercase tracking-wider">OCR transcript preview</div>
                    <div className="mt-2 text-foreground tracking-tight text-sm">Student ID: {selectedStudent.id}</div>
                    <div className="mt-4 text-foreground text-sm leading-relaxed whitespace-pre-wrap max-h-[420px] overflow-y-auto border border-border rounded-md p-3 bg-muted/30">
                      {parsedText || "No OCR text stored for this submission."}
                    </div>
                  </div>
                </div>
              </div>
            </Card>

            {/* Right: Digital Workspace */}
            <div className="space-y-4">
              <Card className="border-border">
                <div className="border-b border-border bg-muted/40">
                  <div className="flex gap-1 p-1">
                    <button
                      onClick={() => setReviewTab("parsed")}
                      className={`flex-1 px-3 py-2 rounded text-sm transition-colors ${reviewTab === "parsed" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
                    >
                      <Type className="size-4 inline mr-2" />
                      Parsed Text
                    </button>
                    <button
                      onClick={() => setReviewTab("analysis")}
                      className={`flex-1 px-3 py-2 rounded text-sm transition-colors ${reviewTab === "analysis" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
                    >
                      <Cpu className="size-4 inline mr-2" />
                      AI Analysis
                    </button>
                  </div>
                </div>

                <div className="p-5">
                  {reviewTab === "parsed" ? (
                    <div>
                      <div className="text-xs text-muted-foreground mb-2">OCR Output (editable)</div>
                      <Textarea
                        value={parsedText}
                        onChange={(e) => setParsedText(e.target.value)}
                        className="font-mono text-xs"
                        rows={18}
                      />
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="flex items-center justify-between gap-2 mb-3">
                        <div className="text-xs text-muted-foreground">Score breakdown (from API)</div>
                        {selectedStudent.evaluation && (
                          <div className="flex flex-wrap items-center gap-1.5 justify-end">
                            {typeof selectedStudent.evaluation.grading_source === "string" && (
                              <Badge variant="outline" className="text-[10px] font-normal">
                                Engine:{" "}
                                {formatGradingEngineLabel(
                                  String(selectedStudent.evaluation.grading_source),
                                )}
                              </Badge>
                            )}
                            {selectedStudent.evaluation.rag_context_used ? (
                              <Badge className="text-[10px] font-normal bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300 border-border hover:bg-emerald-100">
                                RAG: {Number(selectedStudent.evaluation.rag_chunks ?? 0)} chunk
                                {Number(selectedStudent.evaluation.rag_chunks ?? 0) === 1 ? "" : "s"}
                                {selectedStudent.evaluation.rag_course
                                  ? ` (${String(selectedStudent.evaluation.rag_course)})`
                                  : ""}
                              </Badge>
                            ) : (
                              <Badge
                                variant="outline"
                                className="text-[10px] font-normal text-foreground border-amber-300 bg-amber-50"
                              >
                                RAG: none
                                {selectedStudent.evaluation.rag_course
                                  ? ` for ${String(selectedStudent.evaluation.rag_course)}`
                                  : ""}
                              </Badge>
                            )}
                          </div>
                        )}
                      </div>
                      {Array.isArray(selectedStudent.evaluation?.results) &&
                      (selectedStudent.evaluation?.results as unknown[]).length > 0 ? (
                        (selectedStudent.evaluation?.results as Record<string, unknown>[]).map((row, i) => {
                          const score = typeof row.score === "number" ? row.score : Number(row.score ?? 0);
                          const aiScore =
                            row.ai_score != null && row.ai_score !== ""
                              ? typeof row.ai_score === "number"
                                ? row.ai_score
                                : Number(row.ai_score)
                              : score;
                          const qNo = String(row.q_no ?? row.question_no ?? i + 1);
                          const qKey = qNo.padStart(2, "0").replace(/^0+(\d)$/, "0$1");
                          const normKey = qNo.replace(/^0+/, "") || qNo;
                          const justification = String(row.justification ?? "");
                          const feedback = String(row.feedback ?? "");
                          const engine = String(row.grading_source ?? "");
                          const sliceSource = String(
                            row.slice_source ??
                              (selectedStudent.evaluation?.answer_split as { per_question_source?: Record<string, string> } | undefined)
                                ?.per_question_source?.[qKey] ??
                              (selectedStudent.evaluation?.answer_split as { per_question_source?: Record<string, string> } | undefined)
                                ?.per_question_source?.[normKey.padStart(2, "0")] ??
                              "",
                          );
                          const answerExcerpt = String(row.answer_excerpt ?? "");
                          const rowError = row.error != null ? String(row.error) : "";
                          const ragMap = (selectedStudent.evaluation?.rag_per_question || {}) as Record<
                            string,
                            { rag_chunks?: number; rag_context_used?: boolean; rag_snippet?: string }
                          >;
                          const rag =
                            ragMap[qKey] ||
                            ragMap[normKey.padStart(2, "0")] ||
                            ragMap[normKey] ||
                            ragMap[qNo];
                          const diagOpen = Boolean(openQuestionDiag[qKey] || openQuestionDiag[qNo]);
                          const ragOpen = Boolean(openQuestionRag[qKey] || openQuestionRag[qNo]);
                          return (
                            <div key={i} className="pb-3 border-b border-border last:border-0 space-y-2">
                              <div className="flex items-center justify-between gap-2">
                                <span className="text-sm text-foreground">Q{qNo}</span>
                                <span className="text-sm text-foreground tabular-nums">
                                  {Number.isFinite(score) ? score : "—"}
                                  {selectedStudent.manualOverride &&
                                  Number.isFinite(aiScore) &&
                                  aiScore !== score
                                    ? ` (AI ${aiScore})`
                                    : ""}
                                </span>
                              </div>
                              <div className="flex flex-wrap gap-1.5">
                                {engine && (
                                  <Badge variant="outline" className="text-[10px] font-normal">
                                    Engine: {formatGradingEngineLabel(engine)}
                                  </Badge>
                                )}
                                {sliceSource && (
                                  <Badge variant="outline" className="text-[10px] font-normal">
                                    Source: {sliceSource}
                                  </Badge>
                                )}
                                {rag?.rag_context_used ? (
                                  <Badge className="text-[10px] font-normal bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300 border-0">
                                    RAG: {rag.rag_chunks ?? 0} chunk{(rag.rag_chunks ?? 0) === 1 ? "" : "s"}
                                  </Badge>
                                ) : (
                                  <Badge variant="outline" className="text-[10px] font-normal text-muted-foreground">
                                    RAG: none
                                  </Badge>
                                )}
                              </div>
                              {justification && (
                                <p className="text-xs text-muted-foreground leading-relaxed">{justification}</p>
                              )}
                              {feedback && (
                                <p className="text-xs text-muted-foreground mt-1 italic">{feedback}</p>
                              )}
                              {rowError && (
                                <p className="text-xs text-destructive bg-destructive/10 rounded px-2 py-1">{rowError}</p>
                              )}
                              <div className="flex flex-wrap gap-2">
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  className="h-7 text-[11px]"
                                  onClick={() =>
                                    setOpenQuestionDiag((prev) => ({
                                      ...prev,
                                      [qKey]: !diagOpen,
                                    }))
                                  }
                                >
                                  {diagOpen ? "Hide answer sent" : "View answer sent"}
                                </Button>
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  className="h-7 text-[11px]"
                                  onClick={() =>
                                    setOpenQuestionRag((prev) => ({
                                      ...prev,
                                      [qKey]: !ragOpen,
                                    }))
                                  }
                                >
                                  {ragOpen ? "Hide RAG" : "View RAG details"}
                                </Button>
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  className="h-7 text-[11px]"
                                  disabled={
                                    !selectedStudent.submissionId ||
                                    regradingAll ||
                                    regradingQuestion != null
                                  }
                                  onClick={() =>
                                    setReviewConfirm({
                                      kind: "regrade_question",
                                      questionNo: String(qNo),
                                    })
                                  }
                                >
                                  {regradingQuestion === String(qNo) ||
                                  regradingQuestion === qKey ? (
                                    <><RefreshCw className="size-3 mr-1 animate-spin" /> Re-grading…</>
                                  ) : (
                                    "Re-grade Q"
                                  )}
                                </Button>
                              </div>
                              {diagOpen && (
                                <pre className="text-[11px] font-mono whitespace-pre-wrap bg-muted/40 border border-border rounded-lg p-2 text-foreground max-h-40 overflow-y-auto">
                                  {answerExcerpt || "(empty — no slice for this question)"}
                                </pre>
                              )}
                              {ragOpen && (
                                <div className="text-[11px] bg-muted/60 border border-border rounded-lg p-2 space-y-1">
                                  <div className="text-muted-foreground">
                                    Used: {rag?.rag_context_used ? "yes" : "no"}
                                    {typeof rag?.rag_chunks === "number" ? ` · ${rag.rag_chunks} chunk(s)` : ""}
                                  </div>
                                  <pre className="font-mono whitespace-pre-wrap text-foreground max-h-40 overflow-y-auto">
                                    {(rag?.rag_snippet || "").trim() || "No RAG snippet stored for this question."}
                                  </pre>
                                </div>
                              )}
                            </div>
                          );
                        })
                      ) : (
                        <p className="text-sm text-muted-foreground">
                          No structured results on this submission yet.
                        </p>
                      )}
                      {selectedStudent.evaluation &&
                        typeof selectedStudent.evaluation.total_score === "number" && (
                          <div className="pt-2 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                            <span>Total: {selectedStudent.evaluation.total_score as number}</span>
                            {selectedStudent.manualOverride && (
                              <Badge className="text-[10px] font-normal bg-muted text-foreground border-0 hover:bg-accent">
                                Manual override
                              </Badge>
                            )}
                          </div>
                        )}
                    </div>
                  )}
                </div>
              </Card>

              <Card className="p-5 border-border space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm text-foreground">Manual Override</div>
                  {selectedStudent.manualOverride && (
                    <Badge className="text-[10px] font-normal bg-muted text-foreground border-amber-200 hover:bg-accent">
                      Overridden
                    </Badge>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  Adjust question scores and add a lecturer note. AI scores stay frozen for reference.
                  Reset to AI restores official marks to the original AI scores.
                </p>

                {Array.isArray(selectedStudent.evaluation?.results) &&
                (selectedStudent.evaluation?.results as unknown[]).length > 0 ? (
                  <div className="space-y-2">
                    {(selectedStudent.evaluation?.results as Record<string, unknown>[]).map((row, i) => {
                      const qNo = String(row.q_no ?? row.question_no ?? i + 1);
                      const max = lookupQuestionMax(selectedStudent, qNo);
                      const aiScore = rowAiScore(row);
                      const currentScore =
                        typeof row.score === "number" ? row.score : Number(row.score ?? 0);
                      return (
                        <div
                          key={`override-${i}-${qNo}`}
                          className="flex items-center gap-2 text-sm"
                        >
                          <span className="w-10 shrink-0 text-muted-foreground">Q{qNo}</span>
                          <Input
                            type="number"
                            min={0}
                            max={max ?? undefined}
                            step="0.25"
                            className="h-8 w-24 tabular-nums"
                            value={overrideScores[i] ?? ""}
                            onChange={(e) => {
                              setOverrideMessage(null);
                              setOverrideScores((prev) => ({ ...prev, [i]: e.target.value }));
                            }}
                            disabled={overrideSaving || regradingAll || regradingQuestion != null}
                          />
                          <span className="text-xs text-muted-foreground tabular-nums">
                            {max != null ? `/ ${max}` : ""}
                            {Number.isFinite(aiScore) ? ` · AI ${aiScore}` : ""}
                            {selectedStudent.manualOverride &&
                            Number.isFinite(currentScore) &&
                            currentScore !== aiScore
                              ? ` · saved ${currentScore}`
                              : ""}
                          </span>
                        </div>
                      );
                    })}
                    <div className="pt-1 text-xs font-medium uppercase tracking-wide text-muted-foreground tabular-nums">
                      Draft total:{" "}
                      {Object.values(overrideScores)
                        .reduce((sum, raw) => {
                          const n = Number(raw);
                          return sum + (Number.isFinite(n) ? Math.max(0, n) : 0);
                        }, 0)
                        .toLocaleString(undefined, { maximumFractionDigits: 4 })}
                      {selectedStudent.maxGrade ? ` / ${selectedStudent.maxGrade}` : ""}
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-foreground bg-muted/40 border border-border rounded-md px-2 py-1.5">
                    Scores appear here after AI grading finishes for this student.
                  </p>
                )}

                <Textarea
                  value={lecturerNote}
                  onChange={(e) => {
                    setOverrideMessage(null);
                    setLecturerNote(e.target.value);
                  }}
                  placeholder="Lecturer note (why the mark was adjusted)…"
                  rows={3}
                  disabled={overrideSaving}
                />
                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    className="flex-1"
                    disabled={
                      !selectedStudent.submissionId ||
                      overrideSaving ||
                      regradingAll ||
                      regradingQuestion != null ||
                      !Array.isArray(selectedStudent.evaluation?.results) ||
                      (selectedStudent.evaluation?.results as unknown[]).length === 0
                    }
                    onClick={() => setReviewConfirm({ kind: "reset_ai" })}
                  >
                    {overrideSaving ? (
                      <><RefreshCw className="size-4 mr-2 animate-spin" /> Saving…</>
                    ) : (
                      "Reset to AI"
                    )}
                </Button>
                  <Button
                    type="button"
                    className="flex-[2]"
                    disabled={
                      !selectedStudent.submissionId ||
                      overrideSaving ||
                      regradingAll ||
                      regradingQuestion != null ||
                      !overrideHasChanges ||
                      !Array.isArray(selectedStudent.evaluation?.results) ||
                      (selectedStudent.evaluation?.results as unknown[]).length === 0
                    }
                    onClick={() => setReviewConfirm({ kind: "save_override" })}
                  >
                    {overrideSaving ? (
                      <><RefreshCw className="size-4 mr-2 animate-spin" /> Saving…</>
                    ) : (
                      <><Save className="size-4 mr-2" /> Save Override</>
                    )}
                  </Button>
                </div>
                {overrideMessage && (
                  <p className="text-xs text-primary bg-muted border border-border rounded-md px-2 py-1.5">
                    {overrideMessage}
                  </p>
                )}
              </Card>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <Button variant="outline" onClick={() => setPage(5)}>
              <ArrowLeft className="size-4 mr-2" /> Back to Dashboard
            </Button>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => navigateStudent("prev")} disabled={currentStudentIndex === 0}>
                <ArrowLeft className="size-4 mr-2" /> Previous Student
              </Button>
              <Button variant="outline" onClick={() => navigateStudent("next")} disabled={currentStudentIndex >= dashboardStudents.length - 1}>
                Next Student <ArrowRight className="size-4 ml-2" />
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ═══ PAGE 7: Analytics & Export ═══ */}
      {page === 7 && (
        <div className="space-y-6">
          <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="tracking-tight text-foreground">Analytics & Export</h2>
              <p className="text-sm text-muted-foreground mt-1">
                Live insights from this session’s submissions
                {subject ? ` · ${subject}` : ""}
                {examName ? ` · ${examName}` : ""}
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              disabled={!gradingRubricId || submissionsLoading}
              onClick={() => gradingRubricId && void fetchSubmissionsForRubric(gradingRubricId)}
            >
              <RefreshCw className={`size-4 mr-2 ${submissionsLoading ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>

          <div className="grid sm:grid-cols-3 gap-4">
            <Card className="p-4 border-border">
              <div className="text-xs text-muted-foreground uppercase tracking-wide">Papers</div>
              <div className="mt-1 text-2xl tabular-nums text-foreground">
                {analyticsDistribution.gradedCount}
                <span className="text-sm text-muted-foreground font-normal">
                  {" "}/ {analyticsDistribution.total}
                </span>
              </div>
              <div className="text-xs text-muted-foreground mt-1">graded / total</div>
            </Card>
            <Card className="p-4 border-border">
              <div className="text-xs text-muted-foreground uppercase tracking-wide">Average</div>
              <div className="mt-1 text-2xl tabular-nums text-foreground">
                {analyticsDistribution.avgPercent != null
                  ? `${analyticsDistribution.avgPercent.toFixed(1)}%`
                  : "—"}
              </div>
              <div className="text-xs text-muted-foreground mt-1">mean % of paper total</div>
            </Card>
            <Card className="p-4 border-border">
              <div className="text-xs text-muted-foreground uppercase tracking-wide">Manual overrides</div>
              <div className="mt-1 text-2xl tabular-nums text-foreground">
                {dashboardStudents.filter((s) => s.manualOverride).length}
              </div>
              <div className="text-xs text-muted-foreground mt-1">students with lecturer edits</div>
            </Card>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            <Card className="p-6 border-border">
              <h3 className="text-lg text-foreground mb-1">Grade Distribution</h3>
              <p className="text-xs text-muted-foreground mb-4">
                Based on scored papers only ({analyticsDistribution.gradedCount})
              </p>
              {analyticsDistribution.gradedCount === 0 ? (
                <p className="text-sm text-muted-foreground py-6 text-center">
                  No graded scores yet. Finish grading, then refresh.
                </p>
              ) : (
              <div className="space-y-3">
                  {analyticsDistribution.bands.map((band) => (
                    <div key={band.label}>
                    <div className="flex items-center justify-between text-sm mb-1">
                        <span className="text-muted-foreground">{band.label}%</span>
                        <span className="text-foreground tabular-nums">
                          {band.count} student{band.count === 1 ? "" : "s"}
                        </span>
                    </div>
                    <div className="bg-muted rounded-full h-2 overflow-hidden">
                      <div
                        className="h-full bg-primary rounded-full transition-all"
                          style={{
                            width: `${(band.count / analyticsDistribution.maxBandCount) * 100}%`,
                          }}
                      />
                    </div>
                  </div>
                ))}
              </div>
              )}
            </Card>

            <Card className="p-6 border-border">
              <h3 className="text-lg text-foreground mb-1">Question Mastery</h3>
              <p className="text-xs text-muted-foreground mb-4">Average score vs question max marks</p>
              {analyticsQuestionMastery.length === 0 ? (
                <p className="text-sm text-muted-foreground py-6 text-center">
                  No per-question results yet.
                </p>
              ) : (
                <div className="space-y-3 max-h-[320px] overflow-y-auto pr-1">
                  {analyticsQuestionMastery.map((q) => {
                    const pct = q.avgPercent != null ? Math.round(q.avgPercent) : null;
                    return (
                      <div key={q.key}>
                        <div className="flex items-center justify-between text-sm mb-1 gap-2">
                          <span className="text-muted-foreground truncate">{q.label}</span>
                          <span className="text-foreground tabular-nums shrink-0">
                            {pct != null
                              ? `${pct}% avg`
                              : q.avgScore != null
                                ? `${q.avgScore.toFixed(1)} avg`
                                : "—"}
                            <span className="text-muted-foreground text-xs ml-1">n={q.sampleSize}</span>
                          </span>
                    </div>
                    <div className="bg-muted rounded-full h-2 overflow-hidden">
                      <div
                            className={`h-full rounded-full transition-all ${
                              pct == null
                                ? "bg-muted-foreground/30"
                                : pct >= 70
                                  ? "bg-emerald-500"
                                  : pct >= 50
                                    ? "bg-amber-500"
                                    : "bg-destructive"
                            }`}
                            style={{ width: `${pct != null ? Math.min(100, Math.max(0, pct)) : 0}%` }}
                      />
                    </div>
                  </div>
                    );
                  })}
              </div>
              )}
            </Card>
          </div>

          <Card className="p-6 border-border">
            <h3 className="text-lg text-foreground mb-4">Export Actions</h3>
            <div className="grid md:grid-cols-2 gap-4">
              <Button
                type="button"
                variant="outline"
                className="justify-start h-auto py-4"
                disabled={dashboardStudents.length === 0}
                onClick={exportMarksCsv}
              >
                <div className="flex items-start gap-3 w-full">
                  <FileSpreadsheet className="size-5 text-emerald-700 dark:text-emerald-400 shrink-0 mt-0.5" />
                  <div className="text-left flex-1">
                    <div className="text-sm text-foreground">Download CSV</div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      Student ID, totals, % and per-question marks
                    </div>
                  </div>
                  <Download className="size-4 text-muted-foreground shrink-0" />
                </div>
              </Button>

              <Button
                type="button"
                variant="outline"
                className="justify-start h-auto py-4"
                disabled={dashboardStudents.length === 0}
                onClick={exportFeedbackPack}
              >
                <div className="flex items-start gap-3 w-full">
                  <FileText className="size-5 text-primary shrink-0 mt-0.5" />
                  <div className="text-left flex-1">
                    <div className="text-sm text-foreground">Download feedback pack</div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      Printable HTML reports (Print → Save as PDF)
                    </div>
                  </div>
                  <Download className="size-4 text-muted-foreground shrink-0" />
                </div>
              </Button>
            </div>
          </Card>

          <div className="flex gap-3">
            <Button variant="outline" onClick={() => setPage(5)}>
              <ArrowLeft className="size-4 mr-2" /> Back to Dashboard
            </Button>
            <Button  onClick={() => setPage(1)}>
              <CheckCircle2 className="size-4 mr-2" /> Finish Session
            </Button>
          </div>
        </div>
      )}

      {/* ═══ PAGE 8: Lecture Knowledge Base (RAG) ═══ */}
      {page === 8 && (
        <div className="space-y-6 max-w-3xl">
          <div>
            <h2 className="tracking-tight text-foreground">Lecture Knowledge Base</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Manage subjects/courses, then upload lecture PDFs or PowerPoints. Materials are indexed once and filtered by course during grading.
            </p>
          </div>

          <Card className="p-6 border-border">
            <LectureMaterialsPanel apiBaseUrl={GRADING_API_BASE_URL} />
          </Card>

          <Button variant="outline" onClick={() => setPage(1)}>
            <ArrowLeft className="size-4 mr-2" /> Back to command center
          </Button>
        </div>
      )}

      {/* ═══ PAGE 9: All Grading History ═══ */}
      {page === 9 && (
        <div className="space-y-6">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="tracking-tight text-foreground">Grading History</h2>
              <p className="text-sm text-muted-foreground mt-1">
                Loaded live from MongoDB — view results, edit details, or delete
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Badge className="bg-muted text-muted-foreground border-0">
                {filteredGradingHistory.length}
                {filteredGradingHistory.length !== gradingHistory.length
                  ? ` / ${gradingHistory.length}`
                  : ""}{" "}
                sessions
              </Badge>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void fetchGradingHistory()}
                disabled={gradingHistoryLoading}
              >
                <RefreshCw className={`size-4 mr-2 ${gradingHistoryLoading ? "animate-spin" : ""}`} />
                Refresh
              </Button>
            </div>
          </div>

          <Card className="p-4 border-border">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">Search</label>
                <Input
                  value={historyFilterQuery}
                  onChange={(e) => setHistoryFilterQuery(e.target.value)}
                  placeholder="Session, subject, date…"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">Status</label>
                <Select value={historyFilterStatus} onValueChange={setHistoryFilterStatus}>
                  <SelectTrigger>
                    <SelectValue placeholder="All statuses" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All statuses</SelectItem>
                    <SelectItem value="Running">Running</SelectItem>
                    <SelectItem value="Completed">Completed</SelectItem>
                    <SelectItem value="Alerts">Alerts</SelectItem>
                    <SelectItem value="Archived">Archived</SelectItem>
                    <SelectItem value="Draft">Draft</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">Subject</label>
                <Select value={historyFilterSubject} onValueChange={setHistoryFilterSubject}>
                  <SelectTrigger>
                    <SelectValue placeholder="All subjects" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All subjects</SelectItem>
                    {historySubjectOptions.map((code) => (
                      <SelectItem key={code} value={code}>
                        {code}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">Year</label>
                <Select value={historyFilterYear} onValueChange={setHistoryFilterYear}>
                  <SelectTrigger>
                    <SelectValue placeholder="All years" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All years</SelectItem>
                    {historyYearOptions.map((year) => (
                      <SelectItem key={year} value={year}>
                        {year}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            {(historyFilterQuery ||
              historyFilterStatus !== "all" ||
              historyFilterSubject !== "all" ||
              historyFilterYear !== "all") && (
              <div className="mt-3">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="text-muted-foreground"
                  onClick={() => {
                    setHistoryFilterQuery("");
                    setHistoryFilterStatus("all");
                    setHistoryFilterSubject("all");
                    setHistoryFilterYear("all");
                  }}
                >
                  Clear filters
                </Button>
              </div>
            )}
          </Card>

          <Card className="p-6 border-border">
            {gradingHistoryLoading && gradingHistory.length === 0 ? (
              <div className="flex items-center gap-2 py-10 text-sm text-muted-foreground justify-center">
                <RefreshCw className="size-5 animate-spin" /> Loading history…
              </div>
            ) : gradingHistory.length === 0 ? (
              <p className="text-sm text-muted-foreground py-8 text-center">
                No grading sessions found.
              </p>
            ) : filteredGradingHistory.length === 0 ? (
              <p className="text-sm text-muted-foreground py-8 text-center">
                No sessions match these filters.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-b border-border">
                    <tr className="text-left text-xs text-muted-foreground uppercase tracking-wide">
                      <th className="pb-3">Session</th>
                      <th className="pb-3">Subject</th>
                      <th className="pb-3">Term</th>
                      <th className="pb-3">Date</th>
                      <th className="pb-3">Papers</th>
                      <th className="pb-3">Avg.</th>
                      <th className="pb-3">Status</th>
                      <th className="pb-3">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredGradingHistory.map((h) => (
                      <tr
                        key={h.history_key || `${h._id}-${h.batch_job_id || "draft"}`}
                        className="border-b border-border hover:bg-muted/40"
                      >
                        <td className="py-3 text-foreground">{h.session_name || "—"}</td>
                        <td className="py-3">
                          <div className="text-foreground">{h.subject_code || "—"}</div>
                          {h.subject_name ? (
                            <div className="text-xs text-muted-foreground">{h.subject_name}</div>
                          ) : null}
                        </td>
                        <td className="py-3 text-xs text-muted-foreground">
                          {[
                            h.year != null ? String(h.year) : null,
                            h.month != null
                              ? MONTH_OPTIONS.find((m) => m.value === String(h.month))?.label ??
                                `M${h.month}`
                              : null,
                            h.semester != null ? `Sem ${h.semester}` : null,
                          ]
                            .filter(Boolean)
                            .join(" · ") || "—"}
                        </td>
                        <td className="py-3 text-muted-foreground">{h.date || "—"}</td>
                        <td className="py-3 tabular-nums text-foreground">
                          {h.graded_count ?? 0}/{h.submission_count ?? 0}
                        </td>
                        <td className="py-3 tabular-nums text-foreground">
                          {typeof h.avg_score === "number" ? `${h.avg_score}%` : "—"}
                        </td>
                        <td className="py-3">
                          <Badge className={historyStatusBadge(h.status)}>{h.status || "Draft"}</Badge>
                        </td>
                        <td className="py-3">
                          <div className="flex flex-wrap gap-2">
                            <Button size="sm" variant="outline" onClick={() => openHistorySession(h)}>
                              View
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => openHistoryEdit(h)}>
                              Edit
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className="text-destructive border-red-200 hover:bg-destructive/10"
                              onClick={() => setHistoryDeleteItem(h)}
                            >
                              Delete
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Button variant="outline" onClick={() => setPage(1)}>
            <ArrowLeft className="size-4 mr-2" /> Back to command center
          </Button>
        </div>
      )}

      <Dialog
        open={historyEditItem != null}
        onOpenChange={(open) => {
          if (!open) {
            setHistoryEditItem(null);
            setHistoryEditError(null);
          }
        }}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Edit session details</DialogTitle>
            <DialogDescription>
              Update metadata for this exam session. Rubric questions are unchanged.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-1">
            <div>
              <label className="text-sm text-foreground mb-1.5 block">Session name</label>
              <Select value={editSessionName || undefined} onValueChange={setEditSessionName}>
                <SelectTrigger className="w-full bg-card">
                  <SelectValue placeholder="Select session type" />
                </SelectTrigger>
                <SelectContent>
                  {!SESSION_NAME_OPTIONS.includes(editSessionName as (typeof SESSION_NAME_OPTIONS)[number]) &&
                    editSessionName && (
                      <SelectItem value={editSessionName}>{editSessionName}</SelectItem>
                    )}
                  {SESSION_NAME_OPTIONS.map((name) => (
                    <SelectItem key={name} value={name}>
                      {name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm text-foreground mb-1.5 block">Subject code</label>
              <Select
                value={editSubjectCode || undefined}
                onValueChange={(code) => {
                  setEditSubjectCode(code);
                  const match = courses.find((c) => c.code === code);
                  setEditSubjectName((match?.name || "").trim() || code);
                }}
                disabled={coursesLoading || courses.length === 0}
              >
                <SelectTrigger className="w-full bg-card">
                  <SelectValue placeholder="Select course" />
                </SelectTrigger>
                <SelectContent>
                  {courses.map((course) => (
                    <SelectItem key={course.code} value={course.code}>
                      {course.code} - {course.name || course.code}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm text-foreground mb-1.5 block">Subject name</label>
              <Input
                value={editSubjectName}
                onChange={(e) => setEditSubjectName(e.target.value)}
                className="bg-card"
              />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="text-sm text-foreground mb-1.5 block">Year</label>
                <Select value={editYear || undefined} onValueChange={setEditYear}>
                  <SelectTrigger className="w-full bg-card">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {yearOptions.map((y) => (
                      <SelectItem key={y} value={y}>
                        {y}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-sm text-foreground mb-1.5 block">Month</label>
                <Select value={editMonth || undefined} onValueChange={setEditMonth}>
                  <SelectTrigger className="w-full bg-card">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {MONTH_OPTIONS.map((m) => (
                      <SelectItem key={m.value} value={m.value}>
                        {m.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-sm text-foreground mb-1.5 block">Semester</label>
                <Select value={editSemester || undefined} onValueChange={setEditSemester}>
                  <SelectTrigger className="w-full bg-card">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {SEMESTER_OPTIONS.map((s) => (
                      <SelectItem key={s.value} value={s.value}>
                        {s.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            {historyEditError && <p className="text-sm text-destructive">{historyEditError}</p>}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setHistoryEditItem(null)}
              disabled={historyEditSaving}
            >
              Cancel
            </Button>
            <Button
              onClick={() => void saveHistoryEdit()}
              disabled={historyEditSaving || !editSessionName || !editSubjectCode}
            >
              {historyEditSaving ? (
                <><RefreshCw className="size-4 mr-2 animate-spin" /> Saving…</>
              ) : (
                "Save changes"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={historyDeleteItem != null}
        onOpenChange={(open) => {
          if (!open && !historyDeleting) setHistoryDeleteItem(null);
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Delete exam session?</DialogTitle>
            <DialogDescription>
              This permanently deletes{" "}
              <span className="font-medium text-foreground">
                {historyDeleteItem?.session_name || "this session"}
              </span>
              {historyDeleteItem?.subject_code ? ` (${historyDeleteItem.subject_code})` : ""}{" "}
              and all linked submissions.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setHistoryDeleteItem(null)}
              disabled={historyDeleting}
            >
              Cancel
            </Button>
            <Button
              className="bg-red-600 hover:bg-red-700"
              onClick={() => void confirmHistoryDelete()}
              disabled={historyDeleting}
            >
              {historyDeleting ? (
                <><RefreshCw className="size-4 mr-2 animate-spin" /> Deleting…</>
              ) : (
                "Delete"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={pendingUpload != null}
        onOpenChange={(open) => {
          if (!open && !batchUploading && !rosterUploading) setPendingUpload(null);
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {pendingUpload?.kind === "roster"
                ? "Upload roster?"
                : pendingUpload?.kind === "folder"
                  ? "Upload student folder?"
                  : "Upload student batch?"}
            </DialogTitle>
            <DialogDescription>
              {pendingUpload?.kind === "zip"
                ? `Upload "${pendingUpload.file.name}" to the grading server?`
                : pendingUpload?.kind === "folder"
                  ? `Upload ${pendingUpload.files.length} file${pendingUpload.files.length === 1 ? "" : "s"} from the selected folder?`
                  : pendingUpload?.kind === "roster"
                    ? `Upload attendance roster "${pendingUpload.file.name}" for this rubric?`
                    : "Confirm upload."}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setPendingUpload(null)}
              disabled={batchUploading || rosterUploading}
            >
              Cancel
            </Button>
            <Button
              onClick={() => void runPendingUpload()}
              disabled={batchUploading || rosterUploading}
            >
              {batchUploading || rosterUploading ? (
                <><RefreshCw className="size-4 mr-2 animate-spin" /> Uploading…</>
              ) : (
                "Upload"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={reviewConfirm != null}
        onOpenChange={(open) => {
          if (!open && !overrideSaving && !regradingAll && regradingQuestion == null) {
            setReviewConfirm(null);
          }
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {reviewConfirm?.kind === "reset_ai"
                ? "Reset to AI scores?"
                : reviewConfirm?.kind === "save_override"
                  ? "Save manual override?"
                  : reviewConfirm?.kind === "regrade_student"
                    ? "Re-grade this student?"
                    : reviewConfirm?.kind === "regrade_question"
                      ? `Re-grade Q${reviewConfirm.questionNo}?`
                      : "Confirm"}
            </DialogTitle>
            <DialogDescription>
              {reviewConfirm?.kind === "reset_ai"
                ? "Official marks will be restored to the original AI scores."
                : reviewConfirm?.kind === "save_override"
                  ? "The edited scores and lecturer note will become the official grade for this student."
                  : reviewConfirm?.kind === "regrade_student"
                    ? "AI will re-grade all questions for this student. Existing manual overrides on this paper will be replaced."
                    : reviewConfirm?.kind === "regrade_question"
                      ? `AI will re-grade question ${reviewConfirm.questionNo} only. Other question scores stay as they are.`
                      : "Please confirm this action."}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setReviewConfirm(null)}
              disabled={overrideSaving || regradingAll || regradingQuestion != null}
            >
              Cancel
            </Button>
            <Button
              variant={reviewConfirm?.kind === "reset_ai" ? "secondary" : "default"}
              onClick={() => void runReviewConfirm()}
              disabled={overrideSaving || regradingAll || regradingQuestion != null}
            >
              {overrideSaving || regradingAll || regradingQuestion != null ? (
                <><RefreshCw className="size-4 mr-2 animate-spin" /> Working…</>
              ) : reviewConfirm?.kind === "reset_ai" ? (
                "Reset to AI"
              ) : reviewConfirm?.kind === "save_override" ? (
                "Save Override"
              ) : reviewConfirm?.kind === "regrade_question" ? (
                "Re-grade Q"
              ) : (
                "Re-grade"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={reviewNotice != null}
        onOpenChange={(open) => {
          if (!open) setReviewNotice(null);
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{reviewNotice?.title || "Notice"}</DialogTitle>
            <DialogDescription className="whitespace-pre-wrap">
              {reviewNotice?.message || ""}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button onClick={() => setReviewNotice(null)}>OK</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={rubricPickerOpen} onOpenChange={setRubricPickerOpen}>
        <DialogContent className="sm:max-w-lg max-h-[90vh] flex flex-col">
          <DialogHeader>
            <DialogTitle>Select rubric for batch grading</DialogTitle>
            <DialogDescription>
              Pick the marking scheme to use for OCR + AI grading. Confirming applies your current
              session details (subject, exam name, year/month/semester) to that rubric.
            </DialogDescription>
          </DialogHeader>
          <div className="min-h-0 flex-1 overflow-y-auto space-y-2 pr-1">
            {rubricsListLoading ? (
              <div className="flex justify-center py-10 text-muted-foreground">
                <RefreshCw className="size-6 animate-spin" />
              </div>
            ) : rubricsList.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4">
                No rubrics in the database yet. Use Session Initialization to upload a marking PDF, or seed rubrics via the API.
              </p>
            ) : (
              rubricsList.map((r) => (
                <button
                  key={r._id}
                  type="button"
                  onClick={() => setPendingRubricId(r._id)}
                  className={`w-full text-left rounded-lg border p-3 text-sm transition-colors ${
                    pendingRubricId === r._id
                      ? "border-primary bg-accent/40"
                      : "border-border hover:bg-muted/40"
                  }`}
                >
                  <div className="font-medium text-foreground">
                    {formatRubricDetailsLabel(r) || r.session_name || "Untitled rubric"}
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {r.filename || "Marking scheme"}
                  </div>
                </button>
              ))
            )}
          </div>
          <DialogFooter className="gap-2">
            <Button type="button" variant="outline" onClick={() => setRubricPickerOpen(false)}>
              Cancel
            </Button>
            <Button
              type="button"
              disabled={!pendingRubricId || applyingRubric}
              onClick={() => void confirmUseRubric()}
            >
              {applyingRubric ? (
                <><RefreshCw className="size-4 mr-2 animate-spin" /> Applying session…</>
              ) : (
                "Use this rubric"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}