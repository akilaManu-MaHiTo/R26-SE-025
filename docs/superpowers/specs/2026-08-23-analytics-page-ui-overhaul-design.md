# Analytics Page UI Overhaul — Design Spec

**Date:** 2026-08-23
**Status:** Approved
**Scope:** Full visual overhaul of AnalyticsPage (exam list + analytics view)

## Goal

Redesign the AnalyticsPage to match the polished card-based style of LecturerDashboard while integrating PULSE AI branding (teal/emerald colors, ambient effects).

## Design Approach

**Sectioned Dashboard** — Group analytics into distinct visual sections with headers, progress bars, and priority indicators.

---

## Section 1: Exam List View

### Current
- Plain button list with minimal info

### New
- Card-based grid with visual indicators
- Each card shows: course code, subject, session, year
- Student count and average as stats on the right
- Progress bar showing average percentage
- Hover effect with subtle elevation
- Empty state with illustration if no exams

### Layout
```
┌─────────────────────────────────────────────────────────────┐
│  [PULSE AI Banner with ambient teal glow]                   │
├─────────────────────────────────────────────────────────────┤
│  📊 Lecturer Analytics                                      │
│  Select an exam to view detailed performance insights       │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐   │
│  │ CS303 — Database Systems                            │   │
│  │ Final Exam · 2024          │ 45 students │ Avg: 72% │   │
│  │ [████████████████░░░░] 72%                            │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Section 2: Analytics View Header + KPI Cards

### Current
- Plain back button + 6 simple cards

### New
- Header: Back button with course info, Export/Report on right
- Section header with icon: "📊 Performance Overview"
- KPI cards: larger with prominent icons, value, label, and subtext
- Cards have subtle background colors (teal/emerald tint for PULSE theme)
- Sample size warning badge if n < 10

### Layout
```
┌─────────────────────────────────────────────────────────────┐
│  ← Back    CS303 — Database Systems                         │
│             Final Exam · 2024                               │
│                            [Export] [Report]                │
├─────────────────────────────────────────────────────────────┤
│  📊 Performance Overview                                    │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ │
│  │ 👥      │ │ 📈      │ │ 📊      │ │ 🎯      │ │ 🏆      │ │ ⚠️      │ │
│  │ 45      │ │ 72.4    │ │ 72.4%   │ │ 68.9%   │ │ 95      │ │ 42      │ │
│  │ Total   │ │ Average │ │ Score   │ │ Pass    │ │ Highest │ │ Lowest  │ │
│  │ Students│ │ Score   │ │         │ │ Rate    │ │         │ │         │ │
│  │ 42 tried│ │         │ │         │ │         │ │         │ │         │ │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## Section 3: Topic Performance + Attention Areas

### Current
- Plain table + simple grouped list

### New
- Topic table: horizontal progress bars with color coding (green/amber/red)
- Status badges inline with topic name
- Question and student counts below
- Clickable rows open TopicDetailModal
- Attention areas: grouped by priority with colored left borders
- Priority headers with icons (🔴🟠🟡)
- Empty state for unused priority bands

### Layout
```
┌─────────────────────────────────────────────────────────────┐
│  📈 Topic Mastery               │  ⚠️ Needs Attention       │
├─────────────────────────────────┼───────────────────────────┤
│  ┌───────────────────────────┐  │  🔴 Critical Priority     │
│  │ SQL Queries          82%  │  │  ┌─────────────────────┐  │
│  │ [████████████████░░░] Strong│  │  │ Normalization  45% │  │
│  │ 4 questions, 9 students   │  │  │ Joins           52% │  │
│  └───────────────────────────┘  │  └─────────────────────┘  │
│  ┌───────────────────────────┘  │  🟠 High Priority         │
│  │ Normalization       58%  │  │  ┌─────────────────────┐  │
│  │ [███████████░░░░░░░] Dev  │  │  │ Indexing        61% │  │
│  │ 3 questions, 9 students   │  │  │ Transactions    58% │  │
│  └───────────────────────────┘  │  └─────────────────────┘  │
└─────────────────────────────────┴───────────────────────────┘
```

---

## Section 4: Bloom Chart + Question Performance

### Current
- Basic bar chart + simple table

### New
- Bloom chart: larger horizontal bars with percentage labels
- Caption noting which levels were assessed
- Question table: progress bars with color coding
- Auto-flag lowest question with "⚠️ Lowest" badge
- Topic and Bloom level shown below question ID
- Clickable rows open QuestionDetailModal

### Layout
```
┌─────────────────────────────────────────────────────────────┐
│  🧠 Cognitive Analysis           │  📝 Question Performance  │
├─────────────────────────────────┼───────────────────────────┤
│  Bloom's Taxonomy               │                           │
│  Only Apply, Analyze assessed   │  Q1.1  SQL Queries    85% │
│                                 │  [████████████████░░]     │
│  Apply    ████████████░░ 72%    │  Strong · ⚠️ Lowest       │
│  Analyze  ██████████░░░░ 65%    │                           │
│                                 │  Q1.2  Normalization  58% │
│  [Horizontal Bar Chart]         │  [███████████░░░░░░]     │
│                                 │  Developing               │
└─────────────────────────────────┴───────────────────────────┘
```

---

## Section 5: Insights + Teaching Actions

### Current
- Simple grid + basic cards

### New
- Insights: 3-column grid with colored cards (red for weakest, green for strongest, amber for gaps)
- Each insight has an icon and descriptive text
- Teaching Actions: "🤖 Recommended Teaching Actions" header with "AI ✨" badge
- Each action is a card with topic, priority badge, percentage
- Bullet list of recommended actions
- "Generate Practice Questions" button (disabled for now)
- Loading skeleton while fetching from LLM

### Layout
```
┌─────────────────────────────────────────────────────────────┐
│  💡 Key Insights                                            │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ │
│  │ 📉 Weakest      │ │ 📈 Strongest    │ │ ⚠️ Gap          │ │
│  │ topic is        │ │ topic is        │ │ detected in     │ │
│  │ Normalization   │ │ SQL Queries     │ │ cognitive       │ │
│  │ at 58%          │ │ at 82%          │ │ levels          │ │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  🤖 Recommended Teaching Actions                    [AI ✨] │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────┐ │
│  │ 💡 Normalization                               🔴 Crit │ │
│  │    58%                                               │ │
│  │    • Review 1NF, 2NF, 3NF decomposition rules       │ │
│  │    • Practice with real-world schema examples        │ │
│  │    • Create normalization decision tree              │ │
│  │    [Generate Practice Questions]                     │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Changes

### Files to Modify
1. `Gradex_AI_Client/src/app/components/AnalyticsPage.tsx` — Main layout
2. `Gradex_AI_Client/src/app/components/analytics/KpiCards.tsx` — Enhanced KPI cards
3. `Gradex_AI_Client/src/app/components/analytics/CanonicalTopicTable.tsx` — Progress bars
4. `Gradex_AI_Client/src/app/components/analytics/AttentionAreasPanel.tsx` — Priority groups
5. `Gradex_AI_Client/src/app/components/analytics/BloomChart.tsx` — Larger chart
6. `Gradex_AI_Client/src/app/components/analytics/QuestionPerformanceTable.tsx` — Progress bars
7. `Gradex_AI_Client/src/app/components/analytics/InsightsPanel.tsx` — Colored cards
8. `Gradex_AI_Client/src/app/components/analytics/TeachingActions.tsx` — AI branding

### New Components
- `Gradex_AI_Client/src/app/components/analytics/SectionHeader.tsx` — Reusable section header with icon

### Design Tokens (PULSE Theme)
- Primary: `#0f766e` (teal)
- Secondary: `#059669` (emerald)
- Accent: `#14b8a6` (teal-400)
- Background tint: `bg-teal-50 dark:bg-teal-500/5`

---

## Success Criteria

1. Exam list view matches LecturerDashboard card style
2. KPI cards are larger with icons and subtext
3. Topic table has horizontal progress bars
4. Attention areas grouped by priority with colored borders
5. Bloom chart is larger with better labeling
6. Question table has progress bars and auto-flags lowest
7. Insights use colored cards with icons
8. Teaching actions have AI branding and priority badges
9. All sections have clear visual hierarchy with headers
10. Build passes with no errors
