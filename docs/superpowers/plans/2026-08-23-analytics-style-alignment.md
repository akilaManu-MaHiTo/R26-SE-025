# Analytics Page Style Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align analytics page styling with LecturerDashboard site patterns

**Architecture:** Replace custom teal/emerald styling with site-standard shadcn/ui patterns

**Tech Stack:** React, TypeScript, Tailwind CSS, shadcn/ui, Lucide icons

## Global Constraints

- Node.js >= 18
- React 18+
- Tailwind CSS 3+
- shadcn/ui components
- Site-standard colors: bg-muted, text-muted-foreground, bg-primary

---

## Task 1: Update KpiCards

**Files:**
- Modify: `Gradex_AI_Client/src/app/components/analytics/KpiCards.tsx`

**Interfaces:**
- Consumes: statistics object (unchanged)
- Produces: KPI cards with site-standard styling

- [ ] **Step 1: Read existing file**

Read `Gradex_AI_Client/src/app/components/analytics/KpiCards.tsx`

- [ ] **Step 2: Replace icon container styling**

Change:
```tsx
// Before
<div className="size-10 rounded-lg bg-teal-50 dark:bg-teal-500/10 flex items-center justify-center">
  <Icon className="h-5 w-5 text-teal-600 dark:text-teal-400" />
</div>
```

To:
```tsx
// After
<div className="size-10 rounded-lg bg-muted flex items-center justify-center text-muted-foreground">
  <Icon className="size-5" />
</div>
```

- [ ] **Step 3: Remove Card gradient background**

Change:
```tsx
// Before
<Card key={key} className="p-5 relative overflow-hidden">
  <div className="absolute inset-0 bg-gradient-to-br from-teal-50/50 to-transparent dark:from-teal-500/5 dark:to-transparent" />
  <div className="relative">
```

To:
```tsx
// After
<Card key={key} className="p-5">
```

- [ ] **Step 4: Add Card-based header**

Replace the section header with inline Card header:
```tsx
<div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
  <Card className="col-span-full p-5">
    <div className="font-medium">Performance Overview</div>
  </Card>
  {kpis.map(({ key, label, icon: Icon, suffix }) => (
    // ... card content
  ))}
</div>
```

- [ ] **Step 5: Commit**

```bash
git add Gradex_AI_Client/src/app/components/analytics/KpiCards.tsx
git commit -m "style: align KpiCards with site-standard styling"
```

---

## Task 2: Update CanonicalTopicTable

**Files:**
- Modify: `Gradex_AI_Client/src/app/components/analytics/CanonicalTopicTable.tsx`

**Interfaces:**
- Consumes: topics array (unchanged)
- Produces: Topic table with site-standard styling

- [ ] **Step 1: Read existing file**

Read `Gradex_AI_Client/src/app/components/analytics/CanonicalTopicTable.tsx`

- [ ] **Step 2: Remove SectionHeader import and usage**

Remove:
```tsx
import { SectionHeader } from "./SectionHeader";
```

Replace SectionHeader with inline Card header:
```tsx
<Card className="p-5">
  <div className="flex items-center justify-between mb-4">
    <div className="font-medium">Topic Mastery</div>
  </div>
  {/* content */}
</Card>
```

- [ ] **Step 3: Update progress bar color**

Change:
```tsx
// Before
className={`h-full rounded-full transition-all ${progressColor[t.status] || "bg-gray-400"}`}
```

To:
```tsx
// After
className="h-full rounded-full transition-all bg-primary"
```

- [ ] **Step 4: Commit**

```bash
git add Gradex_AI_Client/src/app/components/analytics/CanonicalTopicTable.tsx
git commit -m "style: align CanonicalTopicTable with site-standard styling"
```

---

## Task 3: Update AttentionAreasPanel

**Files:**
- Modify: `Gradex_AI_Client/src/app/components/analytics/AttentionAreasPanel.tsx`

**Interfaces:**
- Consumes: areas array (unchanged)
- Produces: Attention areas with Badge-based priority indicators

- [ ] **Step 1: Read existing file**

Read `Gradex_AI_Client/src/app/components/analytics/AttentionAreasPanel.tsx`

- [ ] **Step 2: Remove SectionHeader import and usage**

Remove:
```tsx
import { SectionHeader } from "./SectionHeader";
```

Replace with inline Card header:
```tsx
<Card className="p-5">
  <div className="flex items-center justify-between mb-4">
    <div className="font-medium">Needs Attention</div>
  </div>
  {/* content */}
</Card>
```

- [ ] **Step 3: Replace colored left borders with Badges**

Replace:
```tsx
// Before
const priorityConfig = [
  { priority: "Critical", color: "border-l-red-500", bg: "bg-red-50 dark:bg-red-500/5", icon: "🔴" },
  // ...
];
<div key={priority} className={`border-l-4 ${color} rounded-r-lg ${bg} p-3`}>
```

With:
```tsx
// After
const priorityConfig = [
  { priority: "Critical", badge: "destructive" },
  { priority: "High", badge: "bg-orange-100 text-orange-800..." },
  { priority: "Medium", badge: "bg-amber-100 text-amber-800..." },
];

<div key={priority} className="p-3">
  <div className="flex items-center justify-between mb-2">
    <Badge variant={config.badge}>{priority} Priority</Badge>
  </div>
```

- [ ] **Step 4: Commit**

```bash
git add Gradex_AI_Client/src/app/components/analytics/AttentionAreasPanel.tsx
git commit -m "style: align AttentionAreasPanel with site-standard styling"
```

---

## Task 4: Update BloomChart

**Files:**
- Modify: `Gradex_AI_Client/src/app/components/analytics/BloomChart.tsx`

**Interfaces:**
- Consumes: bloomPerformance array (unchanged)
- Produces: Bloom chart with site-standard colors

- [ ] **Step 1: Read existing file**

Read `Gradex_AI_Client/src/app/components/analytics/BloomChart.tsx`

- [ ] **Step 2: Remove SectionHeader import and usage**

Remove:
```tsx
import { SectionHeader } from "./SectionHeader";
```

Replace with inline Card header:
```tsx
<Card className="p-5">
  <div className="flex items-center justify-between mb-4">
    <div className="font-medium">Cognitive Analysis</div>
  </div>
  {/* content */}
</Card>
```

- [ ] **Step 3: Update chart colors**

Change:
```tsx
// Before
const COLORS = ["#0f766e", "#059669", "#14b8a6", "#2dd4bf", "#5eead4", "#99f6e4"];
```

To:
```tsx
// After (using CSS variables or site-standard colors)
const COLORS = ["hsl(var(--primary))", "hsl(var(--primary)/0.8)", "hsl(var(--primary)/0.6)", "hsl(var(--primary)/0.4)", "hsl(var(--primary)/0.3)", "hsl(var(--primary)/0.2)"];
```

- [ ] **Step 4: Commit**

```bash
git add Gradex_AI_Client/src/app/components/analytics/BloomChart.tsx
git commit -m "style: align BloomChart with site-standard styling"
```

---

## Task 5: Update QuestionPerformanceTable

**Files:**
- Modify: `Gradex_AI_Client/src/app/components/analytics/QuestionPerformanceTable.tsx`

**Interfaces:**
- Consumes: questions array (unchanged)
- Produces: Question table with site-standard styling

- [ ] **Step 1: Read existing file**

Read `Gradex_AI_Client/src/app/components/analytics/QuestionPerformanceTable.tsx`

- [ ] **Step 2: Remove SectionHeader import and usage**

Remove:
```tsx
import { SectionHeader } from "./SectionHeader";
```

Replace with inline Card header:
```tsx
<Card className="p-5">
  <div className="flex items-center justify-between mb-4">
    <div className="font-medium">Question Performance</div>
  </div>
  {/* content */}
</Card>
```

- [ ] **Step 3: Update progress bar color**

Change:
```tsx
// Before
className={`h-full rounded-full transition-all ${
  isLowest ? "bg-amber-500" : status === "Strong" ? "bg-emerald-500" : status === "Developing" ? "bg-amber-500" : "bg-orange-500"
}`}
```

To:
```tsx
// After
className="h-full rounded-full transition-all bg-primary"
```

- [ ] **Step 4: Commit**

```bash
git add Gradex_AI_Client/src/app/components/analytics/QuestionPerformanceTable.tsx
git commit -m "style: align QuestionPerformanceTable with site-standard styling"
```

---

## Task 6: Update InsightsPanel

**Files:**
- Modify: `Gradex_AI_Client/src/app/components/analytics/InsightsPanel.tsx`

**Interfaces:**
- Consumes: insights string array (unchanged)
- Produces: Insights with site-standard styling

- [ ] **Step 1: Read existing file**

Read `Gradex_AI_Client/src/app/components/analytics/InsightsPanel.tsx`

- [ ] **Step 2: Remove SectionHeader import and usage**

Remove:
```tsx
import { SectionHeader } from "./SectionHeader";
```

Replace with inline Card header:
```tsx
<Card className="p-5">
  <div className="flex items-center justify-between mb-4">
    <div className="font-medium">Key Insights</div>
  </div>
  {/* content */}
</Card>
```

- [ ] **Step 3: Update card styling**

Replace custom colored backgrounds with site-standard:
```tsx
// Before
bg: "bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/20",

// After (use Badge or site-standard patterns)
// Keep the icon colors but use Card-based styling
```

- [ ] **Step 4: Commit**

```bash
git add Gradex_AI_Client/src/app/components/analytics/InsightsPanel.tsx
git commit -m "style: align InsightsPanel with site-standard styling"
```

---

## Task 7: Update TeachingActions

**Files:**
- Modify: `Gradex_AI_Client/src/app/components/analytics/TeachingActions.tsx`

**Interfaces:**
- Consumes: actions array, loading boolean (unchanged)
- Produces: Teaching actions with site-standard styling

- [ ] **Step 1: Read existing file**

Read `Gradex_AI_Client/src/app/components/analytics/TeachingActions.tsx`

- [ ] **Step 2: Remove SectionHeader import and usage**

Remove:
```tsx
import { SectionHeader } from "./SectionHeader";
```

Replace with inline Card header:
```tsx
<Card className="p-5">
  <div className="flex items-center justify-between mb-4">
    <div className="font-medium">Recommended Teaching Actions</div>
    <Badge variant="secondary" className="bg-emerald-100 text-emerald-800...">AI Generated</Badge>
  </div>
  {/* content */}
</Card>
```

- [ ] **Step 3: Update loading skeleton**

Change:
```tsx
// Before
<div key={i} className="h-32 bg-muted animate-pulse rounded-xl" />
```

To:
```tsx
// After
<Skeleton className="h-32" />
```

- [ ] **Step 4: Commit**

```bash
git add Gradex_AI_Client/src/app/components/analytics/TeachingActions.tsx
git commit -m "style: align TeachingActions with site-standard styling"
```

---

## Task 8: Delete SectionHeader Component

**Files:**
- Delete: `Gradex_AI_Client/src/app/components/analytics/SectionHeader.tsx`

- [ ] **Step 1: Delete the file**

```bash
rm Gradex_AI_Client/src/app/components/analytics/SectionHeader.tsx
```

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "chore: remove unused SectionHeader component"
```

---

## Task 9: Build and Verify

- [ ] **Step 1: Run build**

```bash
cd Gradex_AI_Client
npm run build
```

Expected: Build succeeds with no errors.

- [ ] **Step 2: Final commit**

```bash
git add -A
git commit -m "style: complete analytics page style alignment"
```
