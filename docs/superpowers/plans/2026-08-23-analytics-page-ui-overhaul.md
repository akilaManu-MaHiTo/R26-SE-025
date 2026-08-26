# Analytics Page UI Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign AnalyticsPage to match LecturerDashboard polish with PULSE AI branding

**Architecture:** Sectioned dashboard layout with enhanced components, progress bars, priority indicators, and AI-themed styling

**Tech Stack:** React, TypeScript, Tailwind CSS, Lucide icons, Recharts

## Global Constraints

- Node.js >= 18
- React 18+
- Tailwind CSS 3+
- shadcn/ui components
- PULSE theme: teal (#0f766e), emerald (#059669), teal-400 (#14b8a6)

---

## Task 1: Create SectionHeader Component

**Files:**
- Create: `Gradex_AI_Client/src/app/components/analytics/SectionHeader.tsx`

**Interfaces:**
- Consumes: icon (LucideIcon), title (string), subtitle (optional string)
- Produces: Rendered section header

- [ ] **Step 1: Create SectionHeader component**

```tsx
import React from "react";
import type { LucideIcon } from "lucide-react";

interface Props {
  icon: LucideIcon;
  title: string;
  subtitle?: string;
}

export function SectionHeader({ icon: Icon, title, subtitle }: Props) {
  return (
    <div className="flex items-center gap-3 mb-4">
      <div className="size-10 rounded-xl bg-teal-50 dark:bg-teal-500/10 flex items-center justify-center">
        <Icon className="h-5 w-5 text-teal-600 dark:text-teal-400" />
      </div>
      <div>
        <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
        {subtitle && (
          <p className="text-sm text-muted-foreground">{subtitle}</p>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add Gradex_AI_Client/src/app/components/analytics/SectionHeader.tsx
git commit -m "feat: add SectionHeader component"
```

---

## Task 2: Enhance KpiCards Component

**Files:**
- Modify: `Gradex_AI_Client/src/app/components/analytics/KpiCards.tsx`

**Interfaces:**
- Consumes: statistics object (unchanged)
- Produces: Enhanced KPI cards with icons, larger layout, PULSE theme

- [ ] **Step 1: Rewrite KpiCards with enhanced styling**

```tsx
import React from "react";
import { Users, TrendingUp, Target, Award, BarChart3, AlertTriangle } from "lucide-react";
import { Card } from "../ui/card";

interface KpiCardsProps {
  statistics: {
    total_students: number;
    attempted_students: number;
    average_score: number;
    average_percentage: number;
    pass_rate: number;
    highest_score: number;
    lowest_score: number;
  };
}

const kpis = [
  { key: "total_students", label: "Total Students", icon: Users, suffix: "", color: "text-teal-600 dark:text-teal-400" },
  { key: "average_score", label: "Average Score", icon: BarChart3, suffix: "", color: "text-emerald-600 dark:text-emerald-400" },
  { key: "average_percentage", label: "Average %", icon: TrendingUp, suffix: "%", color: "text-blue-600 dark:text-blue-400" },
  { key: "pass_rate", label: "Pass Rate", icon: Target, suffix: "%", color: "text-violet-600 dark:text-violet-400" },
  { key: "highest_score", label: "Highest", icon: Award, suffix: "", color: "text-amber-600 dark:text-amber-400" },
  { key: "lowest_score", label: "Lowest", icon: AlertTriangle, suffix: "", color: "text-rose-600 dark:text-rose-400" },
] as const;

export function KpiCards({ statistics }: KpiCardsProps) {
  const showWarning = statistics.total_students < 10;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="size-10 rounded-xl bg-teal-50 dark:bg-teal-500/10 flex items-center justify-center">
          <BarChart3 className="h-5 w-5 text-teal-600 dark:text-teal-400" />
        </div>
        <h2 className="text-lg font-semibold tracking-tight">Performance Overview</h2>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {kpis.map(({ key, label, icon: Icon, suffix, color }) => {
          const value = statistics[key];
          const isRate = key === "pass_rate" || key === "average_percentage";
          return (
            <Card key={key} className="p-5 relative overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-br from-teal-50/50 to-transparent dark:from-teal-500/5 dark:to-transparent" />
              <div className="relative">
                <div className="flex items-center gap-2 mb-3">
                  <div className={`size-8 rounded-lg bg-muted flex items-center justify-center ${color}`}>
                    <Icon className="h-4 w-4" />
                  </div>
                </div>
                <div className="text-3xl font-bold tracking-tight tabular-nums">
                  {typeof value === "number" ? value.toFixed(isRate ? 1 : 0) : value}
                  {suffix}
                </div>
                <div className="text-sm text-muted-foreground mt-1">{label}</div>
                {key === "total_students" && (
                  <div className="text-xs text-muted-foreground mt-2">
                    {statistics.attempted_students} attempted
                  </div>
                )}
              </div>
            </Card>
          );
        })}
      </div>

      {showWarning && (
        <div className="flex items-center gap-2 text-sm text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-500/10 px-4 py-2 rounded-lg">
          <AlertTriangle className="h-4 w-4" />
          <span>Low sample size (n={statistics.total_students}) — interpret with caution</span>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add Gradex_AI_Client/src/app/components/analytics/KpiCards.tsx
git commit -m "feat: enhance KpiCards with PULSE theme and larger layout"
```

---

## Task 3: Enhance CanonicalTopicTable Component

**Files:**
- Modify: `Gradex_AI_Client/src/app/components/analytics/CanonicalTopicTable.tsx`

**Interfaces:**
- Consumes: topics array (unchanged)
- Produces: Topic table with horizontal progress bars

- [ ] **Step 1: Rewrite CanonicalTopicTable with progress bars**

```tsx
import React from "react";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { BookOpen } from "lucide-react";
import type { CanonicalTopic } from "../../api/lecturerApi";
import { SectionHeader } from "./SectionHeader";

interface Props {
  topics: CanonicalTopic[];
  onSelectTopic: (topic: CanonicalTopic) => void;
}

const statusBadge: Record<string, string> = {
  Critical: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
  "Needs Improvement": "bg-orange-100 text-orange-800 dark:bg-orange-500/15 dark:text-orange-300",
  Developing: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  Strong: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
};

const progressColor: Record<string, string> = {
  Critical: "bg-red-500",
  "Needs Improvement": "bg-orange-500",
  Developing: "bg-amber-500",
  Strong: "bg-emerald-500",
};

export function CanonicalTopicTable({ topics, onSelectTopic }: Props) {
  return (
    <Card className="p-5">
      <SectionHeader icon={BookOpen} title="Topic Mastery" subtitle="Canonical topic performance" />
      <div className="space-y-3">
        {topics.map((t) => (
          <button
            key={t.topic}
            onClick={() => onSelectTopic(t)}
            className="w-full text-left p-4 rounded-xl border bg-card hover:bg-accent/50 transition-all hover:shadow-sm"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="font-medium">{t.topic}</span>
              <div className="flex items-center gap-2">
                <span className="text-sm font-mono font-semibold">{t.average_percentage.toFixed(1)}%</span>
                <Badge className={statusBadge[t.status] || ""}>{t.status}</Badge>
              </div>
            </div>
            <div className="h-2 bg-muted rounded-full overflow-hidden mb-2">
              <div
                className={`h-full rounded-full transition-all ${progressColor[t.status] || "bg-gray-400"}`}
                style={{ width: `${Math.min(t.average_percentage, 100)}%` }}
              />
            </div>
            <div className="text-xs text-muted-foreground">
              {t.question_count} questions · {t.student_count} students
            </div>
          </button>
        ))}
      </div>
    </Card>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add Gradex_AI_Client/src/app/components/analytics/CanonicalTopicTable.tsx
git commit -m "feat: enhance CanonicalTopicTable with progress bars"
```

---

## Task 4: Enhance AttentionAreasPanel Component

**Files:**
- Modify: `Gradex_AI_Client/src/app/components/analytics/AttentionAreasPanel.tsx`

**Interfaces:**
- Consumes: areas array (unchanged)
- Produces: Attention areas grouped by priority with colored borders

- [ ] **Step 1: Rewrite AttentionAreasPanel with priority groups**

```tsx
import React, { useState } from "react";
import { Card } from "../ui/card";
import { Button } from "../ui/button";
import { ChevronDown, ChevronRight, AlertTriangle } from "lucide-react";
import type { CanonicalAttentionArea } from "../../api/lecturerApi";
import { SectionHeader } from "./SectionHeader";

interface Props { areas: CanonicalAttentionArea[]; }

const priorityConfig = [
  { priority: "Critical", color: "border-l-red-500", bg: "bg-red-50 dark:bg-red-500/5", icon: "🔴" },
  { priority: "High", color: "border-l-orange-500", bg: "bg-orange-50 dark:bg-orange-500/5", icon: "🟠" },
  { priority: "Medium", color: "border-l-amber-500", bg: "bg-amber-50 dark:bg-amber-500/5", icon: "🟡" },
];

export function AttentionAreasPanel({ areas }: Props) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  return (
    <Card className="p-5">
      <SectionHeader icon={AlertTriangle} title="Needs Attention" subtitle="Topics requiring focus" />
      <div className="space-y-4">
        {priorityConfig.map(({ priority, color, bg, icon }) => {
          const items = areas.filter((a) => a.priority === priority);
          const isExpanded = expanded[priority];

          return (
            <div key={priority} className={`border-l-4 ${color} rounded-r-lg ${bg} p-3`}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium">
                  {icon} {priority} Priority
                </span>
                {items.length > 0 && (
                  <span className="text-xs text-muted-foreground">{items.length} items</span>
                )}
              </div>

              {items.length === 0 ? (
                <div className="text-xs text-muted-foreground italic py-1">
                  No {priority.toLowerCase()} areas
                </div>
              ) : (
                <>
                  <div className="space-y-2">
                    {(isExpanded ? items : items.slice(0, 2)).map((a) => (
                      <div key={a.name} className="flex items-center justify-between text-sm">
                        <span>{a.name}</span>
                        <span className="font-mono font-semibold">{a.average_percentage.toFixed(1)}%</span>
                      </div>
                    ))}
                  </div>
                  {items.length > 2 && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-xs h-6 mt-2"
                      onClick={() => setExpanded((prev) => ({ ...prev, [priority]: !prev[priority] }))}
                    >
                      {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                      {isExpanded ? "Show less" : `View all (${items.length})`}
                    </Button>
                  )}
                </>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add Gradex_AI_Client/src/app/components/analytics/AttentionAreasPanel.tsx
git commit -m "feat: enhance AttentionAreasPanel with priority groups"
```

---

## Task 5: Enhance BloomChart Component

**Files:**
- Modify: `Gradex_AI_Client/src/app/components/analytics/BloomChart.tsx`

**Interfaces:**
- Consumes: bloomPerformance array (unchanged)
- Produces: Larger Bloom chart with better labeling

- [ ] **Step 1: Rewrite BloomChart with enhanced styling**

```tsx
import React from "react";
import { Card } from "../ui/card";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { Brain } from "lucide-react";
import { SectionHeader } from "./SectionHeader";

interface Props {
  bloomPerformance: { level: string; average_percentage: number }[];
}

const COLORS = ["#0f766e", "#059669", "#14b8a6", "#2dd4bf", "#5eead4", "#99f6e4"];

export function BloomChart({ bloomPerformance }: Props) {
  if (!bloomPerformance.length) return null;

  return (
    <Card className="p-5">
      <SectionHeader
        icon={Brain}
        title="Cognitive Analysis"
        subtitle={`Only ${bloomPerformance.map((b) => b.level).join(", ")} levels assessed`}
      />
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={bloomPerformance} layout="vertical" margin={{ left: 30, right: 30 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
            <YAxis type="category" dataKey="level" width={100} />
            <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
            <Bar dataKey="average_percentage" radius={[0, 6, 6, 0]} barSize={32}>
              {bloomPerformance.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add Gradex_AI_Client/src/app/components/analytics/BloomChart.tsx
git commit -m "feat: enhance BloomChart with PULSE theme colors"
```

---

## Task 6: Enhance QuestionPerformanceTable Component

**Files:**
- Modify: `Gradex_AI_Client/src/app/components/analytics/QuestionPerformanceTable.tsx`

**Interfaces:**
- Consumes: questions array (unchanged)
- Produces: Question table with progress bars and lowest flag

- [ ] **Step 1: Rewrite QuestionPerformanceTable with progress bars**

```tsx
import React from "react";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { AlertTriangle, FileQuestion } from "lucide-react";
import { SectionHeader } from "./SectionHeader";

interface Question {
  question_id: string;
  question_no: string;
  topic: string;
  bloom_level: string;
  average_percentage: number;
}

interface Props {
  questions: Question[];
  onSelectQuestion: (q: Question) => void;
}

export function QuestionPerformanceTable({ questions, onSelectQuestion }: Props) {
  if (!questions.length) return null;

  const lowestId = questions.reduce((min, q) =>
    q.average_percentage < min.average_percentage ? q : min
  ).question_id;

  return (
    <Card className="p-5">
      <SectionHeader icon={FileQuestion} title="Question Performance" subtitle="Individual question analysis" />
      <div className="space-y-3">
        {questions.map((q) => {
          const isLowest = q.question_id === lowestId;
          const status = q.average_percentage >= 75 ? "Strong"
            : q.average_percentage >= 60 ? "Developing"
            : q.average_percentage >= 40 ? "Needs Improvement"
            : "Critical";

          return (
            <button
              key={q.question_id}
              onClick={() => onSelectQuestion(q)}
              className="w-full text-left p-4 rounded-xl border bg-card hover:bg-accent/50 transition-all hover:shadow-sm"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{q.question_id}</span>
                  {isLowest && (
                    <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300 border-0 text-xs">
                      <AlertTriangle className="h-3 w-3 mr-1" />
                      Lowest
                    </Badge>
                  )}
                </div>
                <span className="text-sm font-mono font-semibold">{q.average_percentage.toFixed(1)}%</span>
              </div>
              <div className="text-xs text-muted-foreground mb-2">
                {q.topic} · {q.bloom_level}
              </div>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    isLowest ? "bg-amber-500" : status === "Strong" ? "bg-emerald-500" : status === "Developing" ? "bg-amber-500" : "bg-orange-500"
                  }`}
                  style={{ width: `${Math.min(q.average_percentage, 100)}%` }}
                />
              </div>
            </button>
          );
        })}
      </div>
    </Card>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add Gradex_AI_Client/src/app/components/analytics/QuestionPerformanceTable.tsx
git commit -m "feat: enhance QuestionPerformanceTable with progress bars"
```

---

## Task 7: Enhance InsightsPanel Component

**Files:**
- Modify: `Gradex_AI_Client/src/app/components/analytics/InsightsPanel.tsx`

**Interfaces:**
- Consumes: insights string array (unchanged)
- Produces: Colored insight cards with icons

- [ ] **Step 1: Rewrite InsightsPanel with colored cards**

```tsx
import React from "react";
import { Card } from "../ui/card";
import { TrendingDown, TrendingUp, AlertTriangle, Lightbulb } from "lucide-react";
import { SectionHeader } from "./SectionHeader";

interface Props { insights: string[]; }

const insightConfig = [
  {
    keyword: "weakest",
    icon: TrendingDown,
    bg: "bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/20",
    iconColor: "text-red-500",
  },
  {
    keyword: "strongest",
    icon: TrendingUp,
    bg: "bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/20",
    iconColor: "text-emerald-500",
  },
  {
    keyword: "gap",
    icon: AlertTriangle,
    bg: "bg-amber-50 dark:bg-amber-500/10 border-amber-200 dark:border-amber-500/20",
    iconColor: "text-amber-500",
  },
];

const getInsightStyle = (text: string) => {
  const lower = text.toLowerCase();
  return insightConfig.find((c) => lower.includes(c.keyword)) || {
    keyword: "default",
    icon: Lightbulb,
    bg: "bg-blue-50 dark:bg-blue-500/10 border-blue-200 dark:border-blue-500/20",
    iconColor: "text-blue-500",
  };
};

export function InsightsPanel({ insights }: Props) {
  if (!insights.length) return null;

  return (
    <Card className="p-5">
      <SectionHeader icon={Lightbulb} title="Key Insights" subtitle="Performance highlights" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {insights.map((insight, i) => {
          const { icon: Icon, bg, iconColor } = getInsightStyle(insight);
          return (
            <div key={i} className={`flex items-start gap-3 p-4 rounded-xl border ${bg}`}>
              <Icon className={`h-5 w-5 mt-0.5 shrink-0 ${iconColor}`} />
              <p className="text-sm leading-relaxed">{insight}</p>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add Gradex_AI_Client/src/app/components/analytics/InsightsPanel.tsx
git commit -m "feat: enhance InsightsPanel with colored cards"
```

---

## Task 8: Enhance TeachingActions Component

**Files:**
- Modify: `Gradex_AI_Client/src/app/components/analytics/TeachingActions.tsx`

**Interfaces:**
- Consumes: actions array, loading boolean (unchanged)
- Produces: AI-branded teaching actions with priority badges

- [ ] **Step 1: Rewrite TeachingActions with AI branding**

```tsx
import React from "react";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Sparkles, Lightbulb, Bot } from "lucide-react";
import type { TeachingAction } from "../../api/lecturerApi";
import { SectionHeader } from "./SectionHeader";

interface Props {
  actions: TeachingAction[];
  loading: boolean;
}

const priorityColor: Record<string, string> = {
  Critical: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
  High: "bg-orange-100 text-orange-800 dark:bg-orange-500/15 dark:text-orange-300",
  Medium: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
};

export function TeachingActions({ actions, loading }: Props) {
  if (loading) {
    return (
      <Card className="p-5">
        <SectionHeader icon={Bot} title="Recommended Teaching Actions" subtitle="AI-generated suggestions" />
        <div className="space-y-4">
          {[1, 2].map((i) => (
            <div key={i} className="h-32 bg-muted animate-pulse rounded-xl" />
          ))}
        </div>
      </Card>
    );
  }

  if (!actions.length) return null;

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between mb-4">
        <SectionHeader icon={Bot} title="Recommended Teaching Actions" subtitle="AI-generated suggestions" />
        <Badge className="bg-gradient-to-r from-teal-500 to-emerald-500 text-white border-0">
          <Sparkles className="h-3 w-3 mr-1" />
          AI Generated
        </Badge>
      </div>
      <div className="space-y-4">
        {actions.map((action, i) => (
          <div key={i} className="p-4 rounded-xl border bg-card hover:shadow-sm transition-shadow">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className="size-8 rounded-lg bg-teal-50 dark:bg-teal-500/10 flex items-center justify-center">
                  <Lightbulb className="h-4 w-4 text-teal-600 dark:text-teal-400" />
                </div>
                <div>
                  <span className="font-medium">{action.topic}</span>
                  <span className="text-sm text-muted-foreground ml-2">
                    {action.performance_percentage.toFixed(1)}%
                  </span>
                </div>
              </div>
              <Badge className={priorityColor[action.priority] || ""}>{action.priority}</Badge>
            </div>
            <ul className="space-y-2 ml-11">
              {action.actions.map((a, j) => (
                <li key={j} className="text-sm text-muted-foreground flex items-start gap-2">
                  <span className="text-teal-500 mt-1">•</span>
                  {a}
                </li>
              ))}
            </ul>
            <div className="ml-11 mt-3">
              <Button variant="outline" size="sm" className="text-xs" disabled title="Coming soon">
                Generate Practice Questions
              </Button>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add Gradex_AI_Client/src/app/components/analytics/TeachingActions.tsx
git commit -m "feat: enhance TeachingActions with AI branding"
```

---

## Task 9: Rewrite AnalyticsPage Layout

**Files:**
- Modify: `Gradex_AI_Client/src/app/components/AnalyticsPage.tsx`

**Interfaces:**
- Consumes: All components from Tasks 1-8
- Produces: Full sectioned dashboard layout

- [ ] **Step 1: Rewrite AnalyticsPage with sectioned layout**

```tsx
import React, { useState, useEffect, useCallback } from "react";
import { ArrowLeft, Download, FileText, BarChart3 } from "lucide-react";
import { Button } from "./ui/button";
import { Skeleton } from "./ui/skeleton";
import { AIPageBanner } from "./AIBrand";
import {
  fetchExams,
  fetchExamAnalytics,
  fetchTeachingActions,
  type ExamListItem,
  type ExamAnalytics,
  type CanonicalTopic,
  type TeachingAction,
} from "../api/lecturerApi";
import { KpiCards } from "./analytics/KpiCards";
import { CanonicalTopicTable } from "./analytics/CanonicalTopicTable";
import { AttentionAreasPanel } from "./analytics/AttentionAreasPanel";
import { BloomChart } from "./analytics/BloomChart";
import { QuestionPerformanceTable } from "./analytics/QuestionPerformanceTable";
import { InsightsPanel } from "./analytics/InsightsPanel";
import { TeachingActions } from "./analytics/TeachingActions";
import { TopicDetailModal } from "./analytics/TopicDetailModal";
import { QuestionDetailModal } from "./analytics/QuestionDetailModal";

export default function AnalyticsPage() {
  const [exams, setExams] = useState<ExamListItem[]>([]);
  const [selectedExam, setSelectedExam] = useState<ExamListItem | null>(null);
  const [analytics, setAnalytics] = useState<ExamAnalytics | null>(null);
  const [teachingActions, setTeachingActions] = useState<TeachingAction[]>([]);
  const [loadingExams, setLoadingExams] = useState(true);
  const [loadingAnalytics, setLoadingAnalytics] = useState(false);
  const [loadingActions, setLoadingActions] = useState(false);
  const [selectedTopic, setSelectedTopic] = useState<CanonicalTopic | null>(null);
  const [selectedQuestion, setSelectedQuestion] = useState<any>(null);

  useEffect(() => {
    fetchExams().then((data) => { setExams(data); setLoadingExams(false); }).catch(console.error);
  }, []);

  const handleSelectExam = useCallback(async (exam: ExamListItem) => {
    setSelectedExam(exam);
    setLoadingAnalytics(true);
    setAnalytics(null);
    try {
      const data = await fetchExamAnalytics(exam.course_code, exam.session_name);
      setAnalytics(data);
      setLoadingActions(true);
      fetchTeachingActions(exam.course_code, exam.session_name)
        .then(setTeachingActions)
        .catch(() => setTeachingActions([]))
        .finally(() => setLoadingActions(false));
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingAnalytics(false);
    }
  }, []);

  // Exam List View
  if (!selectedExam) {
    return (
      <div className="space-y-6">
        <AIPageBanner model="pulse" />
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Lecturer Analytics</h1>
          <p className="text-muted-foreground mt-1">Select an exam to view detailed performance insights</p>
        </div>
        {loadingExams ? (
          <div className="space-y-4">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-24 w-full" />)}</div>
        ) : exams.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            <BarChart3 className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>No exams found</p>
          </div>
        ) : (
          <div className="space-y-3">
            {exams.map((exam) => (
              <button
                key={`${exam.course_code}-${exam.session_name}`}
                onClick={() => handleSelectExam(exam)}
                className="w-full text-left p-5 rounded-xl border bg-card hover:bg-accent/50 transition-all hover:shadow-md"
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="font-semibold text-lg">{exam.course_code} — {exam.subject_name}</div>
                    <div className="text-sm text-muted-foreground mt-1">
                      {exam.session_name} · {exam.year}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-bold tabular-nums">{exam.average_percentage.toFixed(1)}%</div>
                    <div className="text-sm text-muted-foreground">{exam.student_count} students</div>
                  </div>
                </div>
                <div className="mt-3 h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-teal-500 to-emerald-500 rounded-full"
                    style={{ width: `${Math.min(exam.average_percentage, 100)}%` }}
                  />
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  // Analytics View
  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => { setSelectedExam(null); setAnalytics(null); setTeachingActions([]); }}>
          <ArrowLeft className="h-4 w-4 mr-1" /> Back
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight">{selectedExam.course_code} — {selectedExam.subject_name}</h1>
          <p className="text-sm text-muted-foreground">{selectedExam.session_name} · {selectedExam.year}</p>
        </div>
        <Button variant="outline" size="sm" disabled title="Coming soon">
          <Download className="h-4 w-4 mr-1" /> Export
        </Button>
        <Button variant="outline" size="sm" disabled title="Coming soon">
          <FileText className="h-4 w-4 mr-1" /> Report
        </Button>
      </div>

      {loadingAnalytics ? (
        <div className="space-y-6">
          <div className="grid grid-cols-6 gap-4">{Array(6).fill(0).map((_, i) => <Skeleton key={i} className="h-32" />)}</div>
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
      ) : analytics ? (
        <>
          {/* Section 1: KPI Cards */}
          <KpiCards statistics={analytics.statistics} />

          {/* Section 2: Topics + Attention */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <CanonicalTopicTable
              topics={analytics.canonical_topic_performance}
              onSelectTopic={setSelectedTopic}
            />
            <AttentionAreasPanel areas={analytics.canonical_attention_areas} />
          </div>

          {/* Section 3: Bloom + Questions */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <BloomChart bloomPerformance={analytics.bloom_performance} />
            <QuestionPerformanceTable
              questions={analytics.question_performance}
              onSelectQuestion={setSelectedQuestion}
            />
          </div>

          {/* Section 4: Insights */}
          <InsightsPanel insights={analytics.canonical_insights} />

          {/* Section 5: Teaching Actions */}
          <TeachingActions actions={teachingActions} loading={loadingActions} />
        </>
      ) : null}

      {/* Modals */}
      <TopicDetailModal topic={selectedTopic} open={!!selectedTopic} onClose={() => setSelectedTopic(null)} />
      <QuestionDetailModal question={selectedQuestion} open={!!selectedQuestion} onClose={() => setSelectedQuestion(null)} />
    </div>
  );
}
```

- [ ] **Step 2: Build and verify**

Run: `cd Gradex_AI_Client && npm run build`
Expected: Build succeeds with no errors.

- [ ] **Step 3: Commit**

```bash
git add Gradex_AI_Client/src/app/components/AnalyticsPage.tsx
git commit -m "feat: rewrite AnalyticsPage with sectioned dashboard layout"
```

---

## Task 10: Integration Test

- [ ] **Step 1: Start the client**

```bash
cd Gradex_AI_Client
npm run dev
```

- [ ] **Step 2: Verify the dashboard**

1. Open `http://localhost:5173/question-exam/analytics`
2. Verify: Exam list shows cards with progress bars
3. Click on an exam
4. Verify: Header shows course info with Back button
5. Verify: KPI cards are larger with icons and PULSE theme
6. Verify: Topic table has progress bars with color coding
7. Verify: Attention areas grouped by priority with colored borders
8. Verify: Bloom chart is larger with teal/emerald colors
9. Verify: Question table has progress bars and flags lowest
10. Verify: Insights show colored cards with icons
11. Verify: Teaching actions have AI branding badge
12. Verify: All section headers have icons

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete analytics page UI overhaul with PULSE theme"
```
