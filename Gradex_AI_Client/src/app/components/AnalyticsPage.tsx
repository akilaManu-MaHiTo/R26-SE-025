// @ts-ignore: allow implicit any for react module when types are not installed
import React, { useState, useRef, useCallback, useEffect, Fragment } from "react";
import {
  AlertTriangle,
  Users,
  BookOpen,
  Brain,
  ChevronDown,
  ArrowUpDown,
  Upload,
  FileJson,
  X,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  RefreshCw,
  ChevronRight,
  FileText,
  Eye,
  EyeOff,
} from "lucide-react";
import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./ui/tabs";
import { Progress } from "./ui/progress";
import { Separator } from "./ui/separator";
import { AIPageBanner, AILoadingOverlay, AIBadgePill } from "./AIBrand";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  CartesianGrid,
  Tooltip,
  ScatterChart,
  Scatter,
  ZAxis,
  ReferenceLine,
  Cell,
} from "recharts";

/* ─── JSON Schema Types ──────────────────────────────────────────────────── */
interface ExamQuestion {
  id: string;
  text: string;
  marks: number;
  topic: string;
  bloom: string;
}
interface ExamPaper {
  title?: string;
  course?: string;
  semester?: string;
  questions: ExamQuestion[];
}
interface StudentAnswer {
  questionId: string;
  score: number;
}
interface StudentSubmission {
  studentId: string;
  answers: StudentAnswer[];
}
interface StudentAnswers {
  submissions: StudentSubmission[];
}

interface BackendStudentSummary {
  student_id: string;
  average_learning_score: number;
  weak_questions: string[];
  dominant_cognitive_level: string;
  performance_band: string;
}

interface BackendStudentReport {
  student_id: string;
  exam: string;
  year: number;
  question: string;
  part: string;
  performance_score: number;
  concept_score: number;
  cognitive_score: number;
  student_level: string;
  required_level: string;
  topic: string;
  learning_score: number;
}

interface BackendWeakTopic {
  topic: string;
  average_learning_score: number;
  average_performance_score: number;
  average_concept_score: number;
  average_cognitive_score: number;
  score_stddev: number;
  weak_student_count: number;
  students_attempted: number;
  attempts: number;
  weak_student_share: number;
  average_level_gap: number;
  weak_probability: number;
  status: string;
}

interface BackendCognitiveGap {
  question: string;
  required: string;
  average_student_level: string;
  gap: string;
}

interface HistoricalDataCollection {
  years: number[];
  data: Record<string, HistoricalSessionRecord[]>;
}

interface HistoricalSessionRecord {
  year: number;
  exam: string;
  timestamp: string;
  totalStudents: number;
  avgLearningScore: number;
  performanceBandDistribution: Record<string, number>;
  studentSummary: BackendStudentSummary[];
  studentReport: BackendStudentReport[];
  weakTopics: BackendWeakTopic[];
  cognitiveGapAnalysis: BackendCognitiveGap[];
  misunderstoodQuestions: Array<{
    question: string;
    average_score: number;
    students_below_threshold: number;
    status: string;
  }>;
  summary?: {
    total: number;
    atRisk: number;
    avgScore: number;
    cogGaps: number;
    problemCount: number;
  };
}

type AnalyticsDashboard = ReturnType<typeof deriveAnalytics>;

type EnginePaperPart = {
  part?: string;
  question?: string;
  max_marks?: number;
  bloom?: string;
};

type EnginePaperQuestion = {
  id?: string;
  question_number?: number | string;
  topic?: string;
  parts?: EnginePaperPart[];
  text?: string;
  marks?: number;
  bloom?: string;
};

type EnginePaperJson = {
  title?: string;
  course?: string;
  semester?: string;
  exam?: string;
  year?: number;
  questions?: EnginePaperQuestion[];
};

type EngineAnswerPart = {
  part?: string;
  answer?: string;
  score?: number;
  max_marks?: number;
};

type EngineSubmission = {
  studentId?: string;
  student_id?: string;
  answers?: Array<{
    questionId?: string;
    question_number?: number | string;
    parts?: EngineAnswerPart[];
    score?: number;
  }>;
};

type EngineAnswersJson = {
  submissions?: EngineSubmission[];
};

interface BackendExamReport extends AnalyticsDashboard {
  source: string;
  generatedAt: string;
  files: {
    student_report?: BackendStudentReport[];
    student_summary?: BackendStudentSummary[];
    misunderstood_questions?: BackendCognitiveGap[];
    cognitive_gap_analysis?: BackendCognitiveGap[];
    weak_topics?: BackendWeakTopic[];
    results?: Array<Record<string, unknown>>;
    final_report?: Record<string, unknown>;
  };
}

/* ─── Bloom numeric mapping ──────────────────────────────────────────────── */
const bloomLevel: Record<string, number> = {
  remember: 1,
  understand: 2,
  apply: 3,
  analyze: 4,
  evaluate: 5,
  create: 6,
};
const bloomLabel = [
  "",
  "Remember",
  "Understand",
  "Apply",
  "Analyze",
  "Evaluate",
  "Create",
];

/* ─── Derivation helpers ─────────────────────────────────────────────────── */
function deriveAnalytics(paper: ExamPaper, answers: StudentAnswers) {
  const questions = paper.questions;
  const submissions = answers.submissions;
  const totalMax = questions.reduce((s, q) => s + q.marks, 0);
  const topics = [...new Set(questions.map((q) => q.topic))];

  // Leaderboard
  const students = submissions.map((sub) => {
    const scoreMap: Record<string, number> = {};
    sub.answers.forEach((a) => {
      scoreMap[a.questionId] = a.score;
    });
    const totalScore = questions.reduce((s, q) => s + (scoreMap[q.id] ?? 0), 0);
    const avg = totalMax > 0 ? Math.round((totalScore / totalMax) * 100) : 0;
    const weak = questions
      .filter((q) => (scoreMap[q.id] ?? 0) / q.marks < 0.6)
      .map((q) => q.id);
    // determine cognitive band: lowest bloom level with poor score
    const bloomScores = questions.map((q) => ({
      bloom: q.bloom,
      pct: q.marks > 0 ? (scoreMap[q.id] ?? 0) / q.marks : 1,
    }));
    bloomScores.sort(
      (a, b) =>
        (bloomLevel[a.bloom.toLowerCase()] ?? 3) -
        (bloomLevel[b.bloom.toLowerCase()] ?? 3),
    );
    const worstBloom =
      bloomScores.find((b) => b.pct < 0.7)?.bloom ??
      bloomScores[0]?.bloom ??
      "Apply";
    const band = avg >= 70 ? "high" : avg >= 50 ? "mid" : "low";
    return { id: sub.studentId, avg, band, weak, cog: worstBloom, scoreMap };
  });

  // Score distribution buckets
  const buckets = [
    { band: "0-39", min: 0, max: 39, c: 0, fill: "#ef4444" },
    { band: "40-54", min: 40, max: 54, c: 0, fill: "#f59e0b" },
    { band: "55-69", min: 55, max: 69, c: 0, fill: "#3b82f6" },
    { band: "70-84", min: 70, max: 84, c: 0, fill: "#10b981" },
    { band: "85-100", min: 85, max: 100, c: 0, fill: "#059669" },
  ];
  students.forEach((s) => {
    const b = buckets.find((b) => s.avg >= b.min && s.avg <= b.max);
    if (b) b.c++;
  });
  const distribution = buckets.map(({ band, c, fill }) => ({ band, c, fill }));

  // Heatmap: students x questions (score out of 10 scaled)
  const heatStudents = students.map((s) => s.id);
  const heatQs = questions.map((q) => q.id);
  const heatData: number[][] = students.map((s) =>
    questions.map((q) => {
      const raw = s.scoreMap[q.id] ?? 0;
      return Math.round((raw / q.marks) * 10);
    }),
  );

  // Cognitive scatter: per-question expected vs actual bloom level
  const cognitiveScatter = questions.map((q) => {
    const expected = bloomLevel[q.bloom.toLowerCase()] ?? 3;
    const avgScore =
      submissions.reduce((sum, sub) => {
        const a = sub.answers.find((a) => a.questionId === q.id);
        return sum + (a ? a.score / q.marks : 0);
      }, 0) / (submissions.length || 1);
    // map avgScore (0-1) to bloom level (1-6)
    const actual = Math.max(1, Math.round(avgScore * 6));
    return { expected, actual, label: q.id };
  });

  // Problem questions
  const problemQs = questions
    .map((q) => {
      const scores = submissions.map((sub) => {
        const a = sub.answers.find((a) => a.questionId === q.id);
        return a ? a.score / q.marks : 0;
      });
      const avgPct = scores.reduce((s, v) => s + v, 0) / (scores.length || 1);
      const belowPct =
        scores.filter((v) => v < 0.6).length / (scores.length || 1);
      const actualBloomNum = Math.max(1, Math.round(avgPct * 6));
      return {
        q: `${q.id} — ${q.text.slice(0, 40)}${q.text.length > 40 ? "…" : ""}`,
        below: `${Math.round(belowPct * 100)}%`,
        avg: Math.round(avgPct * q.marks * 10) / 10,
        req: q.bloom,
        act: bloomLabel[actualBloomNum] ?? "Apply",
        belowPct,
      };
    })
    .filter((p) => parseFloat(p.below) >= 30)
    .slice(0, 5);

  // Bloom ladder
  const bloomLadder = Object.entries(bloomLevel)
    .sort((a, b) => a[1] - b[1])
    .map(([key, level]) => {
      const qs = questions.filter((q) => q.bloom.toLowerCase() === key);
      if (qs.length === 0) return null;
      const avgPct =
        qs.reduce((sum, q) => {
          const qAvg =
            submissions.reduce((s, sub) => {
              const a = sub.answers.find((a) => a.questionId === q.id);
              return s + (a ? a.score / q.marks : 0);
            }, 0) / (submissions.length || 1);
          return sum + qAvg;
        }, 0) / qs.length;
      const colors = [
        "bg-emerald-300",
        "bg-emerald-400",
        "bg-emerald-500",
        "bg-blue-500",
        "bg-indigo-500",
        "bg-violet-500",
      ];
      return {
        l: bloomLabel[level],
        v: Math.round(avgPct * 100),
        c: colors[level - 1] ?? "bg-blue-500",
      };
    })
    .filter(Boolean) as { l: string; v: number; c: string }[];

  // Topic mastery matrix
  const topicMastery: number[][] = students.map((s) =>
    topics.map((topic) => {
      const qs = questions.filter((q) => q.topic === topic);
      if (qs.length === 0) return 0;
      const pct =
        qs.reduce((sum, q) => sum + (s.scoreMap[q.id] ?? 0) / q.marks, 0) /
        qs.length;
      return Math.round(pct * 100);
    }),
  );

  // Summary
  const atRisk = students.filter((s) => s.avg < 40).length;
  const avgScore =
    students.reduce((s, v) => s + v.avg, 0) / (students.length || 1);
  const cogGaps = students.filter(
    (s) => s.cog && bloomLevel[s.cog.toLowerCase()] < 3,
  ).length;

  return {
    students,
    distribution,
    heatStudents,
    heatQs,
    heatData,
    cognitiveScatter,
    bloomLadder,
    topicMastery,
    topics,
    problemQs,
    summary: {
      total: students.length,
      atRisk,
      avgScore: Math.round(avgScore * 10) / 10,
      cogGaps,
      problemCount: problemQs.length,
    },
  };
}

function normalizePaperJson(value: unknown): ExamPaper | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }

  const raw = value as EnginePaperJson;
  if (!Array.isArray(raw.questions) || raw.questions.length === 0) {
    return null;
  }

  const questions = raw.questions.flatMap((question) => {
    if (typeof question.id === "string") {
      return [
        {
          id: question.id,
          text: question.text ?? "",
          marks: Number(question.marks ?? 0),
          topic: question.topic ?? "Unknown",
          bloom: question.bloom ?? "Apply",
        },
      ];
    }

    const questionNumber = question.question_number;
    if (questionNumber === undefined || !Array.isArray(question.parts)) {
      return [];
    }

    return question.parts.map((part) => ({
      id: `Q${questionNumber}${part.part ?? ""}`,
      text: part.question ?? question.text ?? "",
      marks: Number(part.max_marks ?? question.marks ?? 0),
      topic: question.topic ?? raw.course ?? raw.exam ?? "Unknown",
      bloom: part.bloom ?? question.bloom ?? "Apply",
    }));
  });

  if (questions.length === 0) {
    return null;
  }

  return {
    title: raw.title ?? raw.exam,
    course: raw.course ?? raw.exam,
    semester: raw.semester ?? raw.year?.toString(),
    questions,
  };
}

function normalizeAnswersJson(value: unknown): StudentAnswers | null {
  const submissionsSource: unknown[] = Array.isArray(value)
    ? value
    : typeof value === "object" && value !== null && Array.isArray((value as EngineAnswersJson).submissions)
      ? (value as EngineAnswersJson).submissions ?? []
      : [];

  const submissions = submissionsSource.flatMap((submission: unknown) => {
    if (typeof submission !== "object" || submission === null) {
      return [];
    }

    const rawSubmission = submission as EngineSubmission;
    const studentId = rawSubmission.studentId ?? rawSubmission.student_id;
    if (!studentId || !Array.isArray(rawSubmission.answers)) {
      return [];
    }

    const answers = rawSubmission.answers.flatMap((answer: unknown) => {
      if (typeof answer !== "object" || answer === null) {
        return [];
      }

      const rawAnswer = answer as {
        questionId?: string;
        question_number?: number | string;
        parts?: EngineAnswerPart[];
        score?: number;
      };

      if (typeof rawAnswer.questionId === "string") {
        return [
          {
            questionId: rawAnswer.questionId,
            score: Number(rawAnswer.score ?? 0),
          },
        ];
      }

      const questionNumber = rawAnswer.question_number;
      if (questionNumber === undefined || !Array.isArray(rawAnswer.parts)) {
        return [];
      }

      return rawAnswer.parts.map((part) => ({
        questionId: `Q${questionNumber}${part.part ?? ""}`,
        score: Number(part.score ?? 0),
      }));
    });

    return answers.length > 0 ? [{ studentId, answers }] : [];
  });

  return submissions.length > 0 ? { submissions } : null;
}

/* ─── Historical data helpers ───────────────────────────────────────────── */
const titleCase = (value?: string) =>
  value ? value.replace(/_/g, " ").trim().replace(/\b\w/g, (char) => char.toUpperCase()) : "";

const normalizeBand = (value?: string) => {
  const band = value?.trim().toLowerCase();
  if (band === "high") return "high";
  if (band === "low") return "low";
  return "mid";
};

function deriveHistoricalAnalytics(session: HistoricalSessionRecord) {
  const students = [...session.studentSummary]
    .sort((a, b) => b.average_learning_score - a.average_learning_score)
    .map((entry) => ({
      id: entry.student_id,
      avg: Math.round(entry.average_learning_score * 100),
      band: normalizeBand(entry.performance_band),
      weak: entry.weak_questions ?? [],
      cog: titleCase(entry.dominant_cognitive_level) || "Apply",
      scoreMap: {},
    }));

  const distribution = [
    { band: "Low", c: session.performanceBandDistribution.Low ?? 0, fill: "#ef4444" },
    { band: "Medium", c: session.performanceBandDistribution.Medium ?? 0, fill: "#f59e0b" },
    { band: "High", c: session.performanceBandDistribution.High ?? 0, fill: "#10b981" },
  ];

  const studentOrder = students.map((student) => student.id);
  const heatQuestionOrder: string[] = [];
  const heatLookup = new Map<string, number>();

  session.studentReport.forEach((row) => {
    const studentId = row.student_id;
    const questionId = `Q${row.question}${row.part}`;
    if (!heatQuestionOrder.includes(questionId)) {
      heatQuestionOrder.push(questionId);
    }
    heatLookup.set(`${studentId}::${questionId}`, Math.max(0, Math.min(10, Math.round(row.learning_score * 10))));
  });

  const heatData = studentOrder.map((studentId) =>
    heatQuestionOrder.map((questionId) => heatLookup.get(`${studentId}::${questionId}`) ?? 0),
  );

  const cognitiveScatter = session.cognitiveGapAnalysis.map((row) => ({
    expected: bloomLevel[row.required?.toLowerCase()] ?? 3,
    actual: bloomLevel[row.average_student_level?.toLowerCase()] ?? 3,
    label: row.question,
  }));

  const cognitiveMap = new Map(session.cognitiveGapAnalysis.map((row) => [row.question, row]));
  const totalStudents = session.totalStudents || students.length || 1;

  const problemQs = session.misunderstoodQuestions
    .map((row) => {
      const cognitive = cognitiveMap.get(row.question);
      const belowPct = row.students_below_threshold / totalStudents;
      return {
        q: row.question,
        below: `${Math.round(belowPct * 100)}%`,
        avg: Number((row.average_score * 10).toFixed(1)),
        req: titleCase(cognitive?.required) || "Apply",
        act: titleCase(cognitive?.average_student_level) || "Apply",
        belowPct,
      };
    })
    .filter((problem) => problem.belowPct >= 0.3)
    .slice(0, 5);

  const bloomGroups: Record<string, number[]> = {};
  session.studentReport.forEach((row) => {
    const key = row.required_level?.toLowerCase() || "apply";
    bloomGroups[key] ??= [];
    bloomGroups[key].push(row.learning_score * 100);
  });

  const bloomLadder = Object.entries(bloomLevel)
    .sort((a, b) => a[1] - b[1])
    .flatMap(([key, level]) => {
      const values = bloomGroups[key] ?? [];
      if (values.length === 0) return [];
      const colors = [
        "bg-emerald-300",
        "bg-emerald-400",
        "bg-emerald-500",
        "bg-blue-500",
        "bg-indigo-500",
        "bg-violet-500",
      ];
      return [
        {
          l: titleCase(key),
          v: Math.round(values.reduce((sum, value) => sum + value, 0) / values.length),
          c: colors[level - 1] ?? "bg-blue-500",
        },
      ];
    });

  const topics: string[] = [];
  const topicByStudent: Record<string, Record<string, number[]>> = {};
  session.studentReport.forEach((row) => {
    if (!topics.includes(row.topic)) {
      topics.push(row.topic);
    }
    topicByStudent[row.student_id] ??= {};
    topicByStudent[row.student_id][row.topic] ??= [];
    topicByStudent[row.student_id][row.topic].push(row.learning_score * 100);
  });

  const topicMastery = students.map((student) =>
    topics.map((topic) => {
      const values = topicByStudent[student.id]?.[topic] ?? [];
      if (values.length === 0) return 0;
      return Math.round(values.reduce((sum, value) => sum + value, 0) / values.length);
    }),
  );

  const summary = session.summary ?? {
    total: students.length,
    atRisk: students.filter((student) => student.band === "low").length,
    avgScore: Math.round(session.avgLearningScore * 100 * 10) / 10,
    cogGaps: session.cognitiveGapAnalysis.filter((row) => String(row.gap || "").toUpperCase() !== "LOW").length,
    problemCount: problemQs.length,
  };

  return {
    students,
    distribution,
    heatStudents: studentOrder,
    heatQs: heatQuestionOrder,
    heatData,
    cognitiveScatter,
    bloomLadder,
    topicMastery,
    topics,
    problemQs,
    summary,
  };
}

/* ─── Sample JSON templates ──────────────────────────────────────────────── */
const SAMPLE_PAPER_JSON: EnginePaperJson = {
  exam: "IT2040 - Database Management Systems",
  year: 2022,
  questions: [
    {
      question_number: 1,
      topic: "Introduction to DBMS & Conceptual Database Design",
      parts: [
        {
          part: "a",
          question: "What are the main components of a Database Management System? Explain the advantages of DBMS over file processing systems.",
          max_marks: 10,
        },
        {
          part: "b",
          question: "Define primary key, candidate key, foreign key, and super key with appropriate examples.",
          max_marks: 10,
        },
      ],
    },
    {
      question_number: 2,
      topic: "Schema refinement",
      parts: [
        {
          part: "a",
          question: "Normalize the given relation up to 3NF.",
          max_marks: 12,
        },
        {
          part: "b",
          question: "Explain the difference between 3NF and BCNF with an example.",
          max_marks: 8,
        },
      ],
    },
  ],
};

const SAMPLE_ANSWERS_JSON: EngineAnswersJson = {
  submissions: [
    {
      student_id: "it22100001",
      answers: [
        {
          question_number: 1,
          parts: [
            { part: "a", answer: "DBMS components: data, hardware, software, users.", score: 4, max_marks: 10 },
            { part: "b", answer: "Primary key unique identifies row.", score: 3, max_marks: 10 },
          ],
        },
        {
          question_number: 2,
          parts: [
            { part: "a", answer: "Normalize to 3NF by splitting tables.", score: 4, max_marks: 12 },
            { part: "b", answer: "BCNF is stricter than 3NF.", score: 2, max_marks: 8 },
          ],
        },
      ],
    },
    {
      student_id: "it22100002",
      answers: [
        {
          question_number: 1,
          parts: [
            { part: "a", answer: "Storage manager, query processor, transaction manager.", score: 6, max_marks: 10 },
            { part: "b", answer: "Primary key, candidate key, foreign key, super key definitions.", score: 6, max_marks: 10 },
          ],
        },
      ],
    },
  ],
};

/* ─── Colour helpers ─────────────────────────────────────────────────────── */
const bandStyle: Record<string, string> = {
  high: "bg-emerald-50 text-emerald-700 border-emerald-200",
  mid: "bg-amber-50 text-amber-700 border-amber-200",
  low: "bg-red-50 text-red-700 border-red-200",
};
const heatColor = (v: number) => {
  if (v >= 8) return "bg-emerald-500";
  if (v >= 6) return "bg-emerald-300";
  if (v >= 4) return "bg-amber-300";
  if (v >= 2) return "bg-orange-400";
  return "bg-red-500";
};
const topicColor = (v: number) => {
  if (v >= 80) return "bg-emerald-500 text-white";
  if (v >= 65) return "bg-emerald-200 text-emerald-900";
  if (v >= 50) return "bg-amber-200 text-amber-900";
  if (v >= 35) return "bg-orange-300 text-orange-900";
  return "bg-red-400 text-white";
};

/* ─── JSON Upload Zone ───────────────────────────────────────────────────── */
function JsonUploadZone({
  label,
  description,
  icon: Icon,
  file,
  error,
  onFile,
  onClear,
  accentColor,
}: {
  label: string;
  description: string;
  icon: React.ElementType;
  file: File | null;
  error: string | null;
  onFile: (f: File) => void;
  onClear: () => void;
  accentColor: "blue" | "violet";
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const accent =
    accentColor === "blue"
      ? {
          border: "border-blue-300",
          bg: "bg-blue-50",
          text: "text-blue-600",
          icon: "bg-blue-100",
        }
      : {
          border: "border-violet-300",
          bg: "bg-violet-50",
          text: "text-violet-600",
          icon: "bg-violet-100",
        };

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <div
          className={`size-6 rounded ${accent.icon} flex items-center justify-center ${accent.text}`}
        >
          <Icon className="size-3.5" />
        </div>
        <span className="text-sm text-slate-800">{label}</span>
        {file && (
          <Badge className="bg-emerald-50 text-emerald-700 border-0 ml-auto text-[10px]">
            <CheckCircle2 className="size-2.5 mr-0.5" />
            Loaded
          </Badge>
        )}
        {error && (
          <Badge className="bg-red-50 text-red-600 border-0 ml-auto text-[10px]">
            <AlertCircle className="size-2.5 mr-0.5" />
            Error
          </Badge>
        )}
      </div>

      {!file ? (
        <div
          onClick={() => inputRef.current?.click()}
          onDragOver={(e: React.DragEvent<HTMLDivElement>) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e: React.DragEvent<HTMLDivElement>) => {
            e.preventDefault();
            setDrag(false);
            const f = e.dataTransfer.files[0];
            if (f) onFile(f);
          }}
          className={`border-2 border-dashed rounded-xl p-5 flex flex-col items-center gap-2 cursor-pointer transition-colors ${
            drag
              ? `${accent.border} ${accent.bg}`
              : "border-slate-200 bg-slate-50/50 hover:border-slate-300 hover:bg-slate-50"
          }`}
        >
          <div
            className={`size-9 rounded-full ${drag ? accent.icon : "bg-slate-100"} flex items-center justify-center ${drag ? accent.text : "text-slate-400"} transition-colors`}
          >
            <Upload className="size-4" />
          </div>
          <div className="text-center">
            <div className="text-sm text-slate-600">
              {drag ? "Drop to upload" : "Drop JSON or click to browse"}
            </div>
            <div className="text-xs text-slate-400 mt-0.5">{description}</div>
          </div>
        </div>
      ) : (
        <div
          className={`flex items-center gap-3 px-3 py-2.5 rounded-xl border ${error ? "border-red-200 bg-red-50/50" : `border-slate-200 ${accent.bg}`}`}
        >
          <FileJson
            className={`size-5 shrink-0 ${error ? "text-red-400" : accent.text}`}
          />
          <div className="flex-1 min-w-0">
            <div className="text-sm text-slate-800 truncate">{file.name}</div>
            <div
              className={`text-xs mt-0.5 ${error ? "text-red-500" : "text-slate-400"}`}
            >
              {error ?? `${(file.size / 1024).toFixed(1)} KB`}
            </div>
          </div>
          <button
            onClick={onClear}
            className="text-slate-300 hover:text-red-400 transition-colors shrink-0"
          >
            <X className="size-4" />
          </button>
        </div>
      )}

      <input
        ref={inputRef}
        type="file"
        accept=".json,application/json"
        className="hidden"
        onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
          e.target.value = "";
        }}
      />
    </div>
  );
}

/* ─── Main AnalyticsPage ─────────────────────────────────────────────────── */
export function AnalyticsPage() {
  const [expanded, setExpanded] = useState<string | null>("CS-2024-104");
  const [uploadOpen, setUploadOpen] = useState(true);
  const backendBaseUrl =
    ((import.meta as ImportMeta & { env?: { VITE_BACKEND_URL?: string } }).env?.VITE_BACKEND_URL) ??
    "http://localhost:8000";

  // Upload state
  const [paperFile, setPaperFile] = useState<File | null>(null);
  const [answersFile, setAnswersFile] = useState<File | null>(null);
  const [paperError, setPaperError] = useState<string | null>(null);
  const [answersError, setAnswersError] = useState<string | null>(null);
  const [parsedPaper, setParsedPaper] = useState<ExamPaper | null>(null);
  const [parsedAnswers, setParsedAnswers] = useState<StudentAnswers | null>(
    null,
  );
  const [analysed, setAnalysed] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [backendLoading, setBackendLoading] = useState(false);
  const [backendError, setBackendError] = useState<string | null>(null);
  const [backendReport, setBackendReport] = useState<BackendExamReport | null>(null);
  const [derived, setDerived] = useState<ReturnType<
    typeof deriveAnalytics
  > | null>(null);
  const [historicalData, setHistoricalData] = useState<HistoricalDataCollection | null>(null);
  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [selectedSessionIndex, setSelectedSessionIndex] = useState(0);
  const [historicalLoading, setHistoricalLoading] = useState(false);
  const [historicalError, setHistoricalError] = useState<string | null>(null);

  const readJson = useCallback(
    <T,>(
      file: File,
      setFile: (f: File) => void,
      setError: (e: string | null) => void,
      setParsed: (v: T | null) => void,
      parse: (v: unknown) => T | null,
      errorMsg: string,
    ) => {
      setFile(file);
      setError(null);
      setParsed(null);
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const json = JSON.parse(e.target?.result as string);
          const parsed = parse(json);
          if (!parsed) {
            setError(errorMsg);
            return;
          }
          setParsed(parsed);
        } catch {
          setError("Invalid JSON — could not parse file.");
        }
      };
      reader.readAsText(file);
    },
    [],
  );

  const handlePaperFile = (f: File) =>
    readJson(
      f,
      setPaperFile,
      setPaperError,
      setParsedPaper,
      normalizePaperJson,
      "Invalid exam JSON. Upload either the engine format with `questions[].parts[]` or the simplified analytics format.",
    );

  const handleAnswersFile = (f: File) =>
    readJson(
      f,
      setAnswersFile,
      setAnswersError,
      setParsedAnswers,
      normalizeAnswersJson,
      "Invalid student JSON. Upload either the engine format or the simplified analytics format.",
    );

  const clearPaper = () => {
    setPaperFile(null);
    setPaperError(null);
    setParsedPaper(null);
    setAnalysed(false);
    setDerived(null);
  };
  const clearAnswers = () => {
    setAnswersFile(null);
    setAnswersError(null);
    setParsedAnswers(null);
    setAnalysed(false);
    setDerived(null);
  };

  const downloadSample = (which: "paper" | "answers") => {
    const data = which === "paper" ? SAMPLE_PAPER_JSON : SAMPLE_ANSWERS_JSON;
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download =
      which === "paper"
        ? "exam_paper_sample.json"
        : "student_answers_sample.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const runAnalysis = async () => {
    if (!parsedPaper || !parsedAnswers) return;
    setProcessing(true);
    const loaded = await loadBackendReport(paperFile, answersFile);
    if (!loaded) {
      setDerived(deriveAnalytics(parsedPaper, parsedAnswers));
      setAnalysed(true);
    }
    setUploadOpen(false);
    setProcessing(false);
  };

  const loadBackendReport = useCallback(async (paper?: File | null, answers?: File | null) => {
    setBackendLoading(true);
    setBackendError(null);
    try {
      const requestInit: RequestInit = { method: "POST" };
      if (paper && answers) {
        const formData = new FormData();
        formData.append("exam_json", paper);
        formData.append("student_json", answers);
        requestInit.body = formData;
      }

      const response = await fetch(`${backendBaseUrl}/api/analytics/run`, requestInit);
      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || "Backend analytics run failed.");
      }
      const payload = (await response.json()) as BackendExamReport;
      setBackendReport(payload);
      setDerived(payload);
      setAnalysed(true);
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Backend analytics run failed.";
      setBackendError(message);
      return false;
    } finally {
      setBackendLoading(false);
    }
  }, [backendBaseUrl]);

  const loadHistoricalData = useCallback(async () => {
    setHistoricalLoading(true);
    setHistoricalError(null);
    try {
      const response = await fetch(`${backendBaseUrl}/api/analytics/historical`);
      if (!response.ok) {
        const errorText = await response.text();
        console.error("Historical data fetch failed:", response.status, errorText);
        setHistoricalError(errorText || "Historical data unavailable.");
        setHistoricalData({ years: [], data: {} });
        return;
      }
      const data = (await response.json()) as HistoricalDataCollection;
      setHistoricalData(data);
      if (data.years.length > 0) {
        const latestYear = data.years[data.years.length - 1];
        setSelectedYear(latestYear);
        setSelectedSessionIndex(0);
      }
    } catch (error) {
      console.error("Failed to load historical data:", error);
      setHistoricalError(error instanceof Error ? error.message : "Historical data unavailable.");
      setHistoricalData({ years: [], data: {} });
    } finally {
      setHistoricalLoading(false);
    }
  }, [backendBaseUrl]);

  useEffect(() => {
    void loadHistoricalData();
  }, [loadHistoricalData]);

  const selectedYearSessions = selectedYear ? historicalData?.data[String(selectedYear)] ?? [] : [];
  const selectedSession = selectedYearSessions[selectedSessionIndex] ?? selectedYearSessions[0] ?? null;
  const historicalDerived = selectedSession ? deriveHistoricalAnalytics(selectedSession) : null;

  // Active data (uploaded analysis takes priority, otherwise historical output data)
  const D = derived ?? historicalDerived ?? null;
  const activeFiles = selectedSession ? {
    student_summary: selectedSession.studentSummary,
    student_report: selectedSession.studentReport,
    misunderstood_questions: selectedSession.misunderstoodQuestions,
    cognitive_gap_analysis: selectedSession.cognitiveGapAnalysis,
    weak_topics: selectedSession.weakTopics,
  } : null;
  const students = D?.students ?? [];
  const distribution = D?.distribution ?? [];
  const heatStudents = D?.heatStudents ?? [];
  const heatQs = D?.heatQs ?? [];
  const heatData = D?.heatData ?? [];
  const cognitiveScatter = D?.cognitiveScatter ?? [];
  const bloomLadder = D?.bloomLadder ?? [];
  const topics = D?.topics ?? [];
  const topicMastery = D?.topicMastery ?? [];
  const problemQs = D?.problemQs ?? [];
  const course = parsedPaper?.course ?? "Database Systems";
  const semester = parsedPaper?.semester ?? "Spring 2026";

  const summary = [
    {
      title: "Class Performance",
      value: `${D ? D.summary.total : 0} students`,
      icon: Users,
      color: "blue",
      note: `Avg ${D ? D.summary.avgScore : 0} / 100`,
    },
    {
      title: "At-Risk Students",
      value: `${D ? D.summary.atRisk : 0}`,
      icon: AlertTriangle,
      color: "red",
      note: "Below 40% threshold",
    },
    {
      title: "Problem Questions",
      value: `${D ? D.summary.problemCount : 0}`,
      icon: BookOpen,
      color: "amber",
      note:
        problemQs.length > 0
          ? `${problemQs.slice(0, 2).map((p: { q: string }) => p.q).join(", ")} underperforming`
          : "No flagged questions",
    },
    {
      title: "Cognitive Gaps",
      value: `${D ? D.summary.cogGaps : 0}`,
      icon: Brain,
      color: "orange",
      note: "Below required Bloom level",
    },
  ];

  const colorMap: Record<string, string> = {
    blue: "text-blue-600 bg-blue-50",
    red: "text-red-600 bg-red-50",
    amber: "text-amber-600 bg-amber-50",
    orange: "text-orange-600 bg-orange-50",
  };

  const fileCount = (value?: unknown[]) => (Array.isArray(value) ? value.length : 0);

  return (
    <div className="p-8 space-y-6">
      {/* AI Page Banner */}
      <AIPageBanner model="pulse" />

      {/* Page header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h2 className="tracking-tight text-slate-900">Student Analytics</h2>
          <p className="text-sm text-slate-500 mt-1">
            {course} · Final Exam · {semester}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <AIBadgePill model="pulse" />
          {historicalError && (
            <Badge className="bg-red-50 text-red-700 border-red-200 border">
              <AlertCircle className="size-3 mr-1" /> Historical data unavailable
            </Badge>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => void loadHistoricalData()}
            disabled={historicalLoading}
            className="gap-1.5"
          >
            {historicalLoading ? (
              <RefreshCw className="size-3.5 animate-spin" />
            ) : (
              <Sparkles className="size-3.5" />
            )}
            {historicalLoading ? "Syncing data" : "Reload historical data"}
          </Button>
          {analysed && (
            <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200 border">
              <Sparkles className="size-3 mr-1" /> Live data from uploaded JSON
            </Badge>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setUploadOpen((o: boolean) => !o)}
            className="gap-1.5"
          >
            {uploadOpen ? (
              <EyeOff className="size-3.5" />
            ) : (
              <Eye className="size-3.5" />
            )}
            {uploadOpen ? "Hide upload" : "Upload JSON"}
          </Button>
        </div>
      </div>

      {/* ── JSON Upload Panel ─────────────────────────────────────────── */}
      {uploadOpen && (
        <Card className="border-slate-200 overflow-hidden">
          <div className="px-5 py-4 bg-gradient-to-r from-slate-50 to-blue-50/40 border-b border-slate-100 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="size-8 rounded-lg bg-blue-600 flex items-center justify-center">
                <FileJson className="size-4 text-white" />
              </div>
              <div>
                <div className="text-slate-900">Import exam data</div>
                <div className="text-xs text-slate-500 mt-0.5">
                  Upload exam paper + student answers to generate live analytics
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                className="text-xs text-slate-500 gap-1.5"
                onClick={() => downloadSample("paper")}
              >
                <FileText className="size-3.5" /> Sample paper JSON
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="text-xs text-slate-500 gap-1.5"
                onClick={() => downloadSample("answers")}
              >
                <FileText className="size-3.5" /> Sample answers JSON
              </Button>
            </div>
          </div>

          <div className="px-5 pt-4 flex items-center gap-2 flex-wrap text-xs">
            {backendLoading && (
              <Badge className="bg-blue-50 text-blue-700 border-0">
                <RefreshCw className="size-3 mr-1 animate-spin" /> Generating upload report
              </Badge>
            )}
            {backendReport && !backendLoading && (
              <Badge className="bg-emerald-50 text-emerald-700 border-0">
                <Sparkles className="size-3 mr-1" /> Upload report ready
              </Badge>
            )}
            {backendError && (
              <Badge className="bg-red-50 text-red-700 border-0">
                <AlertCircle className="size-3 mr-1" /> {backendError}
              </Badge>
            )}
          </div>

          <div className="p-5 grid md:grid-cols-2 gap-5">
            {/* Paper upload */}
            <JsonUploadZone
              label="Exam Paper JSON"
              description="Questions · marks · topics · Bloom levels"
              icon={BookOpen}
              file={paperFile}
              error={paperError}
              onFile={handlePaperFile}
              onClear={clearPaper}
              accentColor="blue"
            />

            {/* Answers upload */}
            <JsonUploadZone
              label="Student Answers JSON"
              description="Submissions · scores per question"
              icon={Users}
              file={answersFile}
              error={answersError}
              onFile={handleAnswersFile}
              onClear={clearAnswers}
              accentColor="violet"
            />
          </div>

          {/* Schema reference */}
          <div className="mx-5 mb-5 grid md:grid-cols-2 gap-3">
            <div className="bg-slate-900 rounded-xl p-4 text-xs font-mono overflow-x-auto">
              <div className="text-slate-400 mb-2">// exam_paper.json</div>
              <pre className="text-emerald-400 whitespace-pre-wrap leading-relaxed">{`{
  "exam": "IT2040 - Database Management Systems",
  "year": 2022,
  "questions": [{
    "question_number": 1,
    "topic": "Introduction to DBMS & Conceptual Database Design",
    "parts": [{
      "part": "a",
      "question": "What are the main components of a DBMS?",
      "max_marks": 10
    }]
  }]
}`}</pre>
            </div>
            <div className="bg-slate-900 rounded-xl p-4 text-xs font-mono overflow-x-auto">
              <div className="text-slate-400 mb-2">// student_answers.json</div>
              <pre className="text-blue-300 whitespace-pre-wrap leading-relaxed">{`{
  "submissions": [{
    "student_id": "it22100001",
    "answers": [{
      "question_number": 1,
      "parts": [{
        "part": "a",
        "answer": "DBMS components: data, hardware, software, users.",
        "score": 4,
        "max_marks": 10
      }]
    }]
  }]
}`}</pre>
            </div>
          </div>

          {/* Validation summary + Analyse button */}
          <div className="px-5 pb-5">
            <Separator className="mb-5" />
            <div className="flex items-center justify-between gap-4 flex-wrap">
              <div className="flex items-center gap-4 text-sm">
                <div
                  className={`flex items-center gap-1.5 ${parsedPaper ? "text-emerald-600" : "text-slate-400"}`}
                >
                  {parsedPaper ? (
                    <>
                      <CheckCircle2 className="size-4" />{" "}
                      {parsedPaper.questions.length} questions parsed
                    </>
                  ) : (
                    <>
                      <AlertCircle className="size-4" /> Exam paper not loaded
                    </>
                  )}
                </div>
                <div
                  className={`flex items-center gap-1.5 ${parsedAnswers ? "text-emerald-600" : "text-slate-400"}`}
                >
                  {parsedAnswers ? (
                    <>
                      <CheckCircle2 className="size-4" />{" "}
                      {parsedAnswers.submissions.length} submissions parsed
                    </>
                  ) : (
                    <>
                      <AlertCircle className="size-4" /> Student answers not
                      loaded
                    </>
                  )}
                </div>
              </div>
              <div className="flex gap-2">
                {analysed && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      clearPaper();
                      clearAnswers();
                      setAnalysed(false);
                      setDerived(null);
                      setUploadOpen(true);
                    }}
                  >
                    <RefreshCw className="size-3.5 mr-1.5" /> Clear uploaded data
                  </Button>
                )}
                <Button
                  className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
                  disabled={
                    !parsedPaper ||
                    !parsedAnswers ||
                    processing ||
                    !!paperError ||
                    !!answersError
                  }
                  onClick={runAnalysis}
                >
                  {processing ? (
                    <>
                      <RefreshCw className="size-4 mr-2 animate-spin" />{" "}
                      Analysing…
                    </>
                  ) : (
                    <>
                      <Sparkles className="size-4 mr-2" /> Analyse & generate
                      report
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* ── Executive summary cards ───────────────────────────────────── */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {summary.map((s, i) => {
          const Icon = s.icon;
          const tone = colorMap[s.color];
          const [text, bg] = tone.split(" ");
          return (
            <Card
              key={s.title}
              className="p-5 border-slate-200 relative overflow-hidden"
            >
              {i === 0 && (
                <div className="absolute right-2 bottom-2 h-12 w-28 opacity-90">
                  <ResponsiveContainer>
                    <BarChart data={distribution}>
                      <Bar dataKey="c" radius={[3, 3, 0, 0]}>
                        {distribution.map((d, idx) => (
                          <Cell key={`dist-cell-${idx}`} fill={d.fill} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
              <div
                className={`size-10 rounded-lg ${bg} flex items-center justify-center ${text}`}
              >
                <Icon className="size-5" />
              </div>
              <div className="mt-4 text-sm text-slate-500">{s.title}</div>
              <div className="tracking-tight text-slate-900 mt-1">
                {s.value}
              </div>
              <div className="text-xs text-slate-500 mt-1">{s.note}</div>
            </Card>
          );
        })}
      </div>

      {selectedSession && (
        <Card className="border-slate-200 overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between gap-3 flex-wrap">
            <div>
              <div className="text-slate-900">Output session snapshot</div>
              <div className="text-xs text-slate-500 mt-0.5">
                Year {selectedSession.year} · {selectedSession.exam} · {selectedSession.timestamp}
              </div>
            </div>
            <Badge className="bg-blue-50 text-blue-700 border-0">
              {fileCount(activeFiles?.student_summary as unknown[])} student summaries · {fileCount(activeFiles?.student_report as unknown[])} report rows · {fileCount(activeFiles?.cognitive_gap_analysis as unknown[])} cognitive gaps
            </Badge>
          </div>

          <div className="grid lg:grid-cols-2 xl:grid-cols-4 gap-4 p-5">
            <Card className="p-4 border-slate-200 bg-white">
              <div className="text-xs uppercase tracking-wide text-slate-500">student_summary.json</div>
              <div className="mt-2 text-slate-900">{fileCount(activeFiles?.student_summary as unknown[])} students</div>
              <div className="mt-3 space-y-2">
                {(activeFiles?.student_summary ?? []).slice(0, 3).map((student) => (
                  <div key={student.student_id} className="flex items-center justify-between text-xs text-slate-600">
                    <span>{student.student_id}</span>
                    <span>{Math.round(student.average_learning_score * 100)}% · {student.performance_band}</span>
                  </div>
                ))}
              </div>
            </Card>

            <Card className="p-4 border-slate-200 bg-white">
              <div className="text-xs uppercase tracking-wide text-slate-500">weak_topics.json</div>
              <div className="mt-2 text-slate-900">{fileCount(activeFiles?.weak_topics as unknown[])} topic entries</div>
              <div className="mt-3 space-y-2">
                {(activeFiles?.weak_topics ?? []).slice(0, 3).map((topic) => (
                  <div key={topic.topic} className="flex items-center justify-between text-xs text-slate-600 gap-2">
                    <span className="truncate">{topic.topic}</span>
                    <span>{Math.round(topic.weak_probability * 100)}% weak</span>
                  </div>
                ))}
              </div>
            </Card>

            <Card className="p-4 border-slate-200 bg-white">
              <div className="text-xs uppercase tracking-wide text-slate-500">cognitive_gap_analysis.json</div>
              <div className="mt-2 text-slate-900">{fileCount(activeFiles?.cognitive_gap_analysis as unknown[])} question gaps</div>
              <div className="mt-3 space-y-2">
                {(activeFiles?.cognitive_gap_analysis ?? []).slice(0, 3).map((gap) => (
                  <div key={gap.question} className="flex items-center justify-between text-xs text-slate-600 gap-2">
                    <span>{gap.question}</span>
                    <span>{gap.required} → {gap.average_student_level}</span>
                  </div>
                ))}
              </div>
            </Card>

            <Card className="p-4 border-slate-200 bg-white">
              <div className="text-xs uppercase tracking-wide text-slate-500">misunderstood_questions.json</div>
              <div className="mt-2 text-slate-900">{fileCount(activeFiles?.misunderstood_questions as unknown[])} questions flagged</div>
              <div className="mt-3 space-y-2">
                {(activeFiles?.misunderstood_questions ?? []).slice(0, 3).map((question) => (
                  <div key={question.q} className="flex items-center justify-between text-xs text-slate-600 gap-2">
                    <span className="truncate">{question.q}</span>
                    <span>{question.below}</span>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </Card>
      )}

      <Tabs defaultValue="students" className="space-y-4">
        <TabsList className="bg-slate-100">
          <TabsTrigger value="students">Student performance</TabsTrigger>
          <TabsTrigger value="questions">Question analysis</TabsTrigger>
          <TabsTrigger value="cognitive">Cognitive gaps</TabsTrigger>
          <TabsTrigger value="topics">Topic mastery</TabsTrigger>
          <TabsTrigger value="historical">Historical trends</TabsTrigger>
        </TabsList>

        {/* ── Leaderboard ──────────────────────────────────────────────── */}
        <TabsContent value="students" className="m-0">
          <Card className="border-slate-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
              <div className="text-slate-900">Leaderboard</div>
              <div className="text-xs text-slate-500">
                Click a row to drill down
              </div>
            </div>
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
                <tr>
                  {[
                    "Student ID",
                    "Avg score",
                    "Band",
                    "Weak questions",
                    "Cognitive level",
                    "",
                  ].map((h, i) => (
                    <th key={`th-${i}`} className="text-left px-5 py-3">
                      <button className="inline-flex items-center gap-1 hover:text-slate-900">
                        {h}
                        {h && <ArrowUpDown className="size-3" />}
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {students.map((s) => {
                  const open = expanded === s.id;
                  return (
                    <React.Fragment key={s.id}>
                      <tr
                        onClick={() => setExpanded(open ? null : s.id)}
                        className="border-t border-slate-100 hover:bg-slate-50 cursor-pointer"
                      >
                        <td className="px-5 py-3 text-slate-900">{s.id}</td>
                        <td className="px-5 py-3">
                          <div className="flex items-center gap-2">
                            <span className="text-slate-900">{s.avg}</span>
                            <Progress value={s.avg} className="w-24 h-1.5" />
                          </div>
                        </td>
                        <td className="px-5 py-3">
                          <Badge
                            variant="outline"
                            className={bandStyle[s.band]}
                          >
                            {s.band === "high"
                              ? "High"
                              : s.band === "mid"
                                ? "Medium"
                                : "Low"}
                          </Badge>
                        </td>
                        <td className="px-5 py-3">
                          <div className="flex flex-wrap gap-1">
                            {s.weak.map((w) => (
                              <span
                                key={w}
                                className="px-1.5 py-0.5 rounded bg-red-50 text-red-700 text-xs"
                              >
                                {w}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td className="px-5 py-3 text-slate-700">{s.cog}</td>
                        <td className="px-5 py-3 text-right">
                          <ChevronDown
                            className={
                              "size-4 text-slate-400 transition-transform " +
                              (open ? "rotate-180" : "")
                            }
                          />
                        </td>
                      </tr>
                      {open && (
                        <tr className="bg-slate-50/60 border-t border-slate-100">
                          <td colSpan={6} className="p-5">
                            <div className="grid md:grid-cols-3 gap-4">
                              <Card className="p-4 border-slate-200 bg-white">
                                <div className="text-xs text-slate-500 uppercase tracking-wide">
                                  Weak questions
                                </div>
                                <div className="mt-2 space-y-2">
                                  {(s.weak.length > 0 ? s.weak : ["—"])
                                    .slice(0, 3)
                                    .map((w, i) => (
                                      <div key={w}>
                                        <div className="flex items-center justify-between text-sm">
                                          <span className="text-slate-700">
                                            {w}
                                          </span>
                                          <span className="text-slate-500">
                                            &lt; 60%
                                          </span>
                                        </div>
                                        <Progress
                                          value={[42, 38, 28][i] ?? 35}
                                          className="h-1.5 mt-1"
                                        />
                                      </div>
                                    ))}
                                </div>
                              </Card>
                              <Card className="p-4 border-slate-200 bg-white">
                                <div className="text-xs text-slate-500 uppercase tracking-wide">
                                  Score breakdown
                                </div>
                                <div className="h-28 mt-2">
                                  <ResponsiveContainer>
                                    <BarChart
                                      data={[
                                        {
                                          k: "Performance",
                                          v: Math.round(s.avg * 0.9),
                                        },
                                        {
                                          k: "Concept",
                                          v: Math.round(s.avg * 1.1),
                                        },
                                        {
                                          k: "Cognitive",
                                          v: Math.round(s.avg * 0.7),
                                        },
                                      ]}
                                    >
                                      <CartesianGrid
                                        strokeDasharray="3 3"
                                        stroke="#f1f5f9"
                                        vertical={false}
                                      />
                                      <XAxis
                                        dataKey="k"
                                        tick={{ fontSize: 10, fill: "#94a3b8" }}
                                        axisLine={false}
                                        tickLine={false}
                                      />
                                      <YAxis hide />
                                      <Bar
                                        dataKey="v"
                                        fill="#3b82f6"
                                        radius={[4, 4, 0, 0]}
                                      />
                                    </BarChart>
                                  </ResponsiveContainer>
                                </div>
                              </Card>
                              <Card className="p-4 border-slate-200 bg-white">
                                <div className="text-xs text-slate-500 uppercase tracking-wide">
                                  Per-question grid
                                </div>
                                <div
                                  className={`grid gap-1.5 mt-2`}
                                  style={{
                                    gridTemplateColumns: `repeat(${Math.min(heatQs.length, 4)}, 1fr)`,
                                  }}
                                >
                                  {heatQs.slice(0, 8).map((q, i) => {
                                    const si = heatStudents.indexOf(s.id);
                                    const v =
                                      si >= 0 && heatData[si]
                                        ? (heatData[si][i] ?? 5)
                                        : 5;
                                    return (
                                      <div
                                        key={`drill-${q}`}
                                        className={`aspect-square rounded text-[10px] flex items-center justify-center ${heatColor(v)} text-white`}
                                      >
                                        {q}
                                      </div>
                                    );
                                  })}
                                </div>
                              </Card>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </Card>
        </TabsContent>

        {/* ─ Question analysis + Heatmap ──────────────────────────────── */}
        <TabsContent value="questions" className="m-0 space-y-4">
          <Card className="p-5 border-slate-200">
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="text-slate-900">Performance heatmap</div>
                <div className="text-xs text-slate-500 mt-0.5">
                  Students × Questions · score out of 10
                </div>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <span>Low</span>
                <div className="flex">
                  {[
                    "bg-red-500",
                    "bg-orange-400",
                    "bg-amber-300",
                    "bg-emerald-300",
                    "bg-emerald-500",
                  ].map((c, i) => (
                    <div key={`legend-${i}`} className={`w-6 h-3 ${c}`} />
                  ))}
                </div>
                <span>High</span>
              </div>
            </div>
            <div className="overflow-auto">
              <div
                className="inline-grid gap-1.5"
                style={{
                  gridTemplateColumns: `auto repeat(${heatQs.length}, minmax(40px, 1fr))`,
                }}
              >
                <div />
                {heatQs.map((q) => (
                  <div
                    key={`hq-${q}`}
                    className="text-xs text-slate-500 text-center"
                  >
                    {q}
                  </div>
                ))}
                {heatStudents.map((s, r) => (
                  <React.Fragment key={`hs-${s}`}>
                    <div className="text-xs text-slate-500 pr-2 flex items-center whitespace-nowrap">
                      {s}
                    </div>
                    {heatData[r]?.map((v, c) => (
                      <div
                        key={`${s}-col-${c}`}
                        className={`aspect-square rounded ${heatColor(v)} text-white text-[10px] flex items-center justify-center`}
                      >
                        {v}
                      </div>
                    ))}
                  </React.Fragment>
                ))}
              </div>
            </div>
          </Card>

          <Card className="border-slate-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 text-slate-900">
              Problem questions
            </div>
            {problemQs.length === 0 ? (
              <div className="px-5 py-8 text-center text-slate-400 text-sm">
                No problem questions detected — great results!
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
                  <tr>
                    <th className="text-left px-5 py-3">Question</th>
                    <th className="text-left px-5 py-3">Below threshold</th>
                    <th className="text-left px-5 py-3">Avg score</th>
                    <th className="text-left px-5 py-3">
                      Required vs actual Bloom
                    </th>
                    <th className="text-right px-5 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {problemQs.map((p) => (
                    <tr key={`pq-${p.q}`} className="border-t border-slate-100">
                      <td className="px-5 py-3 text-slate-900">{p.q}</td>
                      <td className="px-5 py-3">
                        <Badge className="bg-red-50 text-red-700 border-0 hover:bg-red-50">
                          {p.below}
                        </Badge>
                      </td>
                      <td className="px-5 py-3 text-slate-700">{p.avg} / 10</td>
                      <td className="px-5 py-3 text-slate-700">
                        <span className="text-slate-500 line-through mr-2">
                          {p.req}
                        </span>
                        <span className="text-red-600">{p.act}</span>
                      </td>
                      <td className="px-5 py-3 text-right">
                        <Button variant="outline" size="sm">
                          View answer
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        </TabsContent>

        {/* ── Cognitive gaps ───────────────────────────────────────────── */}
        <TabsContent value="cognitive" className="m-0 space-y-4">
          <div className="grid lg:grid-cols-2 gap-4">
            <Card className="p-5 border-slate-200">
              <div className="text-slate-900">Bloom's Taxonomy ladder</div>
              <div className="text-xs text-slate-500 mt-0.5">
                Class average per cognitive level
              </div>
              <div className="mt-4 space-y-2">
                {[...bloomLadder].reverse().map((b) => (
                  <div key={`bloom-${b.l}`} className="flex items-center gap-3">
                    <div className="w-24 text-sm text-slate-600">{b.l}</div>
                    <div className="flex-1 h-7 rounded-md bg-slate-100 overflow-hidden">
                      <div
                        className={`${b.c} h-full flex items-center justify-end pr-2 text-xs text-white`}
                        style={{ width: `${b.v}%` }}
                      >
                        {b.v}%
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>

            <Card className="p-5 border-slate-200">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-slate-900">Expected vs Actual</div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    Points below the diagonal indicate cognitive gaps
                  </div>
                </div>
                <div className="flex gap-2 text-xs">
                  <Badge className="bg-emerald-50 text-emerald-700 border-0">
                    On track
                  </Badge>
                  <Badge className="bg-amber-50 text-amber-700 border-0">
                    Gap
                  </Badge>
                  <Badge className="bg-red-50 text-red-700 border-0">
                    Critical
                  </Badge>
                </div>
              </div>
              <div className="h-72 mt-4">
                <ResponsiveContainer>
                  <ScatterChart
                    margin={{ top: 10, right: 10, bottom: 10, left: 0 }}
                  >
                    <CartesianGrid stroke="#f1f5f9" />
                    <XAxis
                      type="number"
                      dataKey="expected"
                      domain={[0, 7]}
                      tickCount={7}
                      tick={{ fontSize: 11, fill: "#94a3b8" }}
                      label={{
                        value: "Expected level",
                        position: "insideBottom",
                        offset: -5,
                        fill: "#64748b",
                        fontSize: 12,
                      }}
                    />
                    <YAxis
                      type="number"
                      dataKey="actual"
                      domain={[0, 7]}
                      tickCount={7}
                      tick={{ fontSize: 11, fill: "#94a3b8" }}
                      label={{
                        value: "Actual",
                        angle: -90,
                        position: "insideLeft",
                        fill: "#64748b",
                        fontSize: 12,
                      }}
                    />
                    <ZAxis range={[80, 81]} />
                    <Tooltip
                      cursor={{ strokeDasharray: "3 3" }}
                      contentStyle={{ borderRadius: 8, fontSize: 12 }}
                    />
                    <ReferenceLine
                      segment={[
                        { x: 0, y: 0 },
                        { x: 7, y: 7 },
                      ]}
                      stroke="#94a3b8"
                      strokeDasharray="4 4"
                    />
                    <Scatter data={cognitiveScatter}>
                      {cognitiveScatter.map((p, i) => (
                        <Cell
                          key={`scatter-cell-${i}`}
                          fill={
                            p.actual >= p.expected
                              ? "#10b981"
                              : p.expected - p.actual >= 2
                                ? "#ef4444"
                                : "#f59e0b"
                          }
                        />
                      ))}
                    </Scatter>
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>
        </TabsContent>

        {/* ── Topic mastery ────────────────────────────────────────────── */}
        <TabsContent value="topics" className="m-0">
          <Card className="p-5 border-slate-200">
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="text-slate-900">Topic mastery matrix</div>
                <div className="text-xs text-slate-500 mt-0.5">
                  Highlighted columns indicate ≥40% failure rate
                </div>
              </div>
              <div className="flex items-center gap-3 text-xs text-slate-500">
                {[
                  ["bg-emerald-500", "≥80%"],
                  ["bg-amber-200", "50–64%"],
                  ["bg-red-400", "<35%"],
                ].map(([c, l]) => (
                  <div key={l} className="flex items-center gap-1">
                    <div className={`size-3 rounded ${c}`} />
                    {l}
                  </div>
                ))}
              </div>
            </div>
            <div className="overflow-auto">
              <table className="text-sm border-separate border-spacing-1">
                <thead>
                  <tr>
                    <th className="text-left text-xs text-slate-500 px-2">
                      Student
                    </th>
                    {topics.map((t) => {
                      const colAvg =
                        topicMastery
                          .slice(0, students.length)
                          .reduce(
                            (s, r, i) => s + (r[topics.indexOf(t)] ?? 0),
                            0,
                          ) / (students.length || 1);
                      const fail = colAvg < 60;
                      return (
                        <th
                          key={`topic-th-${t}`}
                          className={`text-xs px-2 py-1 rounded whitespace-nowrap ${fail ? "bg-red-50 text-red-700" : "text-slate-500"}`}
                        >
                          {t}
                        </th>
                      );
                    })}
                    <th className="text-xs text-slate-500 px-2">Avg</th>
                  </tr>
                </thead>
                <tbody>
                  {students.slice(0, topicMastery.length).map((s, r) => {
                    const row = topicMastery[r] ?? [];
                    const avg =
                      row.length > 0
                        ? Math.round(
                            row.reduce((a, b) => a + b, 0) / row.length,
                          )
                        : 0;
                    return (
                      <tr key={`mastery-row-${s.id}`}>
                        <td className="text-slate-700 px-2 py-1 whitespace-nowrap">
                          {s.id}
                        </td>
                        {row.map((v, c) => (
                          <td
                            key={`mastery-${r}-${c}`}
                            className={`text-center px-3 py-2 rounded ${topicColor(v)}`}
                          >
                            {v}
                          </td>
                        ))}
                        <td className="text-slate-900 px-2">{avg}</td>
                      </tr>
                    );
                  })}
                  <tr>
                    <td className="text-slate-500 px-2 pt-3 text-xs uppercase tracking-wide">
                      Topic avg
                    </td>
                    {topics.map((t, c) => {
                      const avg = Math.round(
                        topicMastery
                          .slice(0, students.length)
                          .reduce((a, r) => a + (r[c] ?? 0), 0) /
                          (students.length || 1),
                      );
                      return (
                        <td
                          key={`avg-col-${c}`}
                          className="text-center text-slate-700 pt-3"
                        >
                          {avg}
                        </td>
                      );
                    })}
                    <td />
                  </tr>
                </tbody>
              </table>
            </div>
          </Card>
        </TabsContent>

        {/* ── Historical Trends ────────────────────────────────────────── */}
        <TabsContent value="historical" className="m-0 space-y-4">
          <Card className="border-slate-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <div className="text-slate-900">Year-over-Year Performance</div>
                <div className="text-xs text-slate-500 mt-1">
                  Historical exam performance trends across years
                </div>
              </div>
              {historicalLoading && (
                <RefreshCw className="size-4 animate-spin text-slate-400" />
              )}
            </div>

            {historicalData && historicalData.years.length > 0 ? (
              <div className="p-5 space-y-6">
                {/* Year selector */}
                <div className="flex gap-2 overflow-x-auto pb-2">
                  {historicalData.years.map((year) => (
                    <button
                      key={year}
                      onClick={() => {
                        setSelectedYear(year);
                        setSelectedSessionIndex(0);
                      }}
                      className={`px-4 py-2 rounded-lg whitespace-nowrap text-sm font-medium transition-all ${
                        selectedYear === year
                          ? "bg-blue-600 text-white"
                          : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                      }`}
                    >
                      {year}
                    </button>
                  ))}
                </div>

                {/* Session selector */}
                {selectedYearSessions.length > 1 && (
                  <div className="flex gap-2 overflow-x-auto pb-2">
                    {selectedYearSessions.map((session, index) => (
                      <button
                        key={`${session.timestamp}-${index}`}
                        onClick={() => setSelectedSessionIndex(index)}
                        className={`px-4 py-2 rounded-lg whitespace-nowrap text-sm font-medium transition-all ${
                          selectedSessionIndex === index
                            ? "bg-slate-900 text-white"
                            : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                        }`}
                      >
                        {session.exam} · {session.timestamp}
                      </button>
                    ))}
                  </div>
                )}

                {selectedSession ? (
                  <div className="grid lg:grid-cols-[1.4fr_0.8fr] gap-4">
                    <Card className="p-5 border-slate-200 bg-white">
                      <div className="flex items-start justify-between gap-4 flex-wrap">
                        <div>
                          <div className="text-slate-900">{selectedSession.exam}</div>
                          <div className="text-xs text-slate-500 mt-1">
                            Year {selectedSession.year} · {selectedSession.timestamp}
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-2xl font-bold text-blue-600">
                            {Math.round(selectedSession.avgLearningScore * 100)}%
                          </div>
                          <div className="text-xs text-slate-500 mt-1">
                            Average learning score
                          </div>
                        </div>
                      </div>

                      <div className="mt-5 grid sm:grid-cols-3 gap-3">
                        {Object.entries(selectedSession.performanceBandDistribution).map(([band, count]) => {
                          const bandColors: Record<string, string> = {
                            High: "bg-emerald-100 text-emerald-700",
                            Medium: "bg-amber-100 text-amber-700",
                            Low: "bg-red-100 text-red-700",
                          };
                          return (
                            <div key={band} className={`p-3 rounded-lg text-center ${bandColors[band] ?? "bg-slate-100 text-slate-700"}`}>
                              <div className="text-sm font-semibold">{count}</div>
                              <div className="text-xs mt-1">{band}</div>
                            </div>
                          );
                        })}
                      </div>

                      <div className="mt-5 space-y-3">
                        <div className="text-xs font-semibold text-slate-700">Top student summaries</div>
                        {selectedSession.studentSummary.slice(0, 5).map((student) => (
                          <div key={student.student_id} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-600 gap-3">
                            <div>
                              <div className="text-sm text-slate-900">{student.student_id}</div>
                              <div className="mt-1">{titleCase(student.dominant_cognitive_level)} · {student.performance_band}</div>
                            </div>
                            <div className="text-right">
                              <div className="text-sm font-semibold text-slate-900">
                                {Math.round(student.average_learning_score * 100)}%
                              </div>
                              <div className="text-[11px] text-slate-500 mt-1">
                                {student.weak_questions.length} weak questions
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </Card>

                    <div className="space-y-4">
                      <Card className="p-5 border-slate-200 bg-white">
                        <div className="text-slate-900">Output files</div>
                        <div className="text-xs text-slate-500 mt-0.5">Raw JSON snapshot for the selected session</div>
                        <div className="mt-4 space-y-3 text-xs">
                          <div className="flex items-center justify-between"><span className="text-slate-600">student_summary.json</span><span className="text-slate-900">{selectedSession.studentSummary.length} rows</span></div>
                          <div className="flex items-center justify-between"><span className="text-slate-600">student_report.json</span><span className="text-slate-900">{selectedSession.studentReport.length} rows</span></div>
                          <div className="flex items-center justify-between"><span className="text-slate-600">weak_topics.json</span><span className="text-slate-900">{selectedSession.weakTopics.length} rows</span></div>
                          <div className="flex items-center justify-between"><span className="text-slate-600">cognitive_gap_analysis.json</span><span className="text-slate-900">{selectedSession.cognitiveGapAnalysis.length} rows</span></div>
                          <div className="flex items-center justify-between"><span className="text-slate-600">misunderstood_questions.json</span><span className="text-slate-900">{selectedSession.misunderstoodQuestions.length} rows</span></div>
                        </div>
                      </Card>

                      <Card className="p-5 border-slate-200 bg-white">
                        <div className="text-slate-900">Weak topics</div>
                        <div className="text-xs text-slate-500 mt-0.5">Topics with lower learning score</div>
                        <div className="mt-4 space-y-3">
                          {selectedSession.weakTopics.slice(0, 5).map((topic) => (
                            <div key={topic.topic} className="space-y-1">
                              <div className="flex items-center justify-between text-xs text-slate-600 gap-2">
                                <span className="truncate">{topic.topic}</span>
                                <span>{Math.round(topic.average_learning_score * 100)}%</span>
                              </div>
                              <Progress value={topic.average_learning_score * 100} className="h-2" />
                            </div>
                          ))}
                        </div>
                      </Card>
                    </div>
                  </div>
                ) : (
                  <div className="p-8 text-center text-slate-500">
                    <FileText className="size-8 mx-auto mb-2 opacity-50" />
                    <div className="text-sm">Select a year to view session data</div>
                  </div>
                )}
              </div>
            ) : (
              <div className="p-8 text-center text-slate-500">
                <FileText className="size-8 mx-auto mb-2 opacity-50" />
                <div className="text-sm">No historical data available</div>
                <div className="text-xs mt-1">
                  Run exams and generate analytics to see historical trends
                </div>
              </div>
            )}
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
