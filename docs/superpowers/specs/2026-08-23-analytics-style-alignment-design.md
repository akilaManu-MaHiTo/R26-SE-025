# Analytics Page Style Alignment — Design Spec

**Date:** 2026-08-23
**Status:** Approved
**Scope:** Align analytics page styling with LecturerDashboard site patterns

## Goal

Replace custom teal/emerald styling with site-standard shadcn/ui patterns to match LecturerDashboard's polished look.

---

## Section 1: KpiCards

### Current
- Teal-50 icon backgrounds
- Custom gradient Card backgrounds
- Custom SectionHeader with teal icon

### New
- `bg-muted` icon backgrounds (like LecturerDashboard stats)
- Standard Card styling (no gradient)
- Card-based header inside KpiCards

### Code Changes
```tsx
// Icon container
// Before: bg-teal-50 dark:bg-teal-500/10 text-teal-600 dark:text-teal-400
// After:  bg-muted text-muted-foreground

// Card
// Before: <Card className="p-5 relative overflow-hidden">
// After:  <Card className="p-5">
```

---

## Section 2: Section Headers

### Current
- Custom `SectionHeader` component with teal icon background

### New
- Remove `SectionHeader` component entirely
- Use Card-based headers like LecturerDashboard

### Pattern (from LecturerDashboard)
```tsx
<Card className="p-5">
  <div className="flex items-center justify-between">
    <div className="font-medium">Section Title</div>
    <Badge variant="secondary">Status</Badge>
  </div>
  {/* content */}
</Card>
```

### Apply to All Analytics Cards
- KpiCards: "Performance Overview"
- CanonicalTopicTable: "Topic Mastery"
- AttentionAreasPanel: "Needs Attention"
- BloomChart: "Cognitive Analysis"
- QuestionPerformanceTable: "Question Performance"
- InsightsPanel: "Key Insights"
- TeachingActions: "Recommended Teaching Actions"

---

## Section 3: Progress Bars and Colors

### Progress Bars
```tsx
// Before: bg-gradient-to-r from-teal-500 to-emerald-500
// After:  bg-primary
```

### Attention Areas
```tsx
// Before: Colored left borders (border-l-red-500, etc.)
// After:  Badge-based priority indicators

<Badge variant="destructive">Critical</Badge>
<Badge className="bg-orange-100 text-orange-800...">High</Badge>
<Badge className="bg-amber-100 text-amber-800...">Medium</Badge>
```

### Bloom Chart Colors
```tsx
// Before: ["#0f766e", "#059669", "#14b8a6", ...] (teal palette)
// After:  Use CSS variables or site-standard chart colors
```

---

## Files to Modify

1. `Gradex_AI_Client/src/app/components/analytics/KpiCards.tsx`
2. `Gradex_AI_Client/src/app/components/analytics/CanonicalTopicTable.tsx`
3. `Gradex_AI_Client/src/app/components/analytics/AttentionAreasPanel.tsx`
4. `Gradex_AI_Client/src/app/components/analytics/BloomChart.tsx`
5. `Gradex_AI_Client/src/app/components/analytics/QuestionPerformanceTable.tsx`
6. `Gradex_AI_Client/src/app/components/analytics/InsightsPanel.tsx`
7. `Gradex_AI_Client/src/app/components/analytics/TeachingActions.tsx`
8. `Gradex_AI_Client/src/app/components/AnalyticsPage.tsx`

## Files to Delete

1. `Gradex_AI_Client/src/app/components/analytics/SectionHeader.tsx`

---

## Success Criteria

1. All icon containers use `bg-muted text-muted-foreground`
2. All cards use standard Card styling (no gradients)
3. All sections have Card-based headers (no SectionHeader component)
4. Progress bars use `bg-primary`
5. Attention areas use Badge-based priority indicators
6. Build passes with no errors
7. Visual consistency with LecturerDashboard
