import React, { useEffect, useState } from "react";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { TableCell } from "../ui/table";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "../ui/collapsible";
import { ChevronDown, FileText, Network, Info } from "lucide-react";
import type { StudentRow, ExamListItem } from "../../api/lecturerApi";
import goodAnimation from "../animations/validation/bloub-galet-effraye-vert-anime-good.svg";
import warningAnimation from "../animations/validation/bloub-triangle-effraye-ambre-anime-warning.svg";
import dangerAnimation from "../animations/validation/bloub-capsule-effraye-rouge-anime-danger.svg";

function GradingAnimation({ src }: { src: string }) {
  const [revealed, setRevealed] = useState(false);
  useEffect(() => {
    if (src === goodAnimation) return;
    const timer = window.setTimeout(() => setRevealed(true), 800);
    return () => window.clearTimeout(timer);
  }, [src]);
  const fade = "block size-12 object-contain object-center transition-opacity duration-200 ease-[cubic-bezier(0.23,1,0.32,1)] motion-reduce:transition-none";
  return <span className="relative flex size-12 shrink-0 self-center items-center justify-center" aria-hidden="true">
    <img src={src} alt="" width={48} height={48} className={fade} style={{ opacity: revealed || src === goodAnimation ? 1 : 0 }} />
    {src !== goodAnimation && <img src={goodAnimation} alt="" width={48} height={48}
      className={`absolute inset-0 ${fade}`} style={{ opacity: revealed ? 0 : 1 }} />}
  </span>;
}

export function ExamInventoryScore({ exam }: { exam: ExamListItem }) {
  if (exam.grading_warning) return <span role="status" className="text-xs text-amber-700 dark:text-amber-300">Grades unavailable: {exam.grading_warning}</span>;
  if (exam.average_percentage == null) return <span className="text-xs text-muted-foreground">No valid grades</span>;
  return <div className="text-center text-sm tabular-nums">
    <strong>{exam.average_percentage.toFixed(1)}%</strong>
    <div className="text-xs text-muted-foreground">{exam.score_basis ?? "Essay"}{exam.graded_student_count != null ? ` · ${exam.graded_student_count} graded` : ""}</div>
  </div>;
}

const labels: Record<string, string> = {
  graded: "Graded", processing: "Processing", not_started: "Not started",
  failed: "Grading failed", missing_submission: "No submission", needs_review: "Review needed",
  not_required: "Not required",
};

export function canViewStudent(student: StudentRow) {
  return !student.components || student.analysis_status === "generated" ||
    student.components.essay.status === "graded" || student.components.diagram.status === "graded";
}

export function GradingOverview({ students }: { students: StudentRow[] }) {
  if (students.some(s => !s.components || !s.grading_status)) {
    return <Card className="flex-row items-center gap-3 p-4 text-sm" role="status">
      <GradingAnimation key={warningAnimation} src={warningAnimation} />
      <span>Grading progress is unavailable for legacy records. Overall grades are not verified.</span>
    </Card>;
  }
  const complete = students.filter(s => s.grading_status === "complete" && typeof s.score.percentage === "number" && Number.isFinite(s.score.percentage));
  const review = students.filter(s => s.grading_status === "needs_review").length;
  const pending = students.length - complete.length - review;
  const essay = students.filter(s => s.components?.essay.status === "graded").length;
  const diagram = students.filter(s => s.components?.diagram.status === "graded").length;
  const essayRequired = students.filter(s => s.components?.essay.status !== "not_required").length;
  const diagramRequired = students.filter(s => s.components?.diagram.status !== "not_required").length;
  const average = complete.length ? complete.reduce((sum, s) => sum + s.score.percentage!, 0) / complete.length : null;
  const failed = students.some(s => s.components?.essay.status === "failed" || s.components?.diagram.status === "failed");
  const animation = failed ? dangerAnimation
    : students.length > 0 && complete.length === students.length ? goodAnimation : warningAnimation;
  return <Collapsible asChild>
    <Card className="gap-0 overflow-hidden" aria-label="Exam grading progress">
      <h3>
        <CollapsibleTrigger className="group flex w-full items-center gap-3 p-4 text-left transition-colors hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring sm:gap-5 sm:p-5">
          <GradingAnimation key={animation} src={animation} />
          <span className="min-w-0 flex-1 space-y-2">
            <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="text-sm font-semibold">Grading progress</span>
              <span className="text-xs font-normal text-muted-foreground">{students.length} {students.length === 1 ? "student" : "students"}</span>
            </span>
            <span className="flex flex-wrap gap-x-3 gap-y-1 text-xs font-normal tabular-nums">
              <span className="text-emerald-700 dark:text-emerald-400">{complete.length} complete</span>
              <span className={pending ? "text-amber-700 dark:text-amber-400" : "text-muted-foreground"}>{pending} pending</span>
              <span className={review ? "text-amber-700 dark:text-amber-400" : "text-muted-foreground"}>{review} needs review</span>
            </span>
          </span>
          <span className="shrink-0 text-right">
            <span className="block text-[11px] font-normal text-muted-foreground">Overall average</span>
            <strong className="block text-xl font-semibold tracking-tight tabular-nums sm:text-2xl">{average === null ? "—" : `${average.toFixed(2)}%`}</strong>
          </span>
          <ChevronDown className="size-4 shrink-0 text-muted-foreground transition-transform duration-200 motion-reduce:transition-none group-data-[state=open]:rotate-180" aria-hidden="true" />
        </CollapsibleTrigger>
      </h3>
      {average === null && <p className="px-4 pb-4 text-xs text-muted-foreground sm:px-5">No complete overall grades yet</p>}
      <CollapsibleContent className="overflow-hidden data-[state=open]:animate-collapsible-down data-[state=closed]:animate-collapsible-up duration-200 ease-[cubic-bezier(0.23,1,0.32,1)] motion-reduce:animate-none">
        <div className="space-y-4 border-t bg-muted/15 p-4 sm:p-5">
          <div className="grid gap-3 sm:grid-cols-2">
            {([
              { label: "Essay", count: essay, required: essayRequired, Icon: FileText },
              { label: "Diagram", count: diagram, required: diagramRequired, Icon: Network },
            ]).map(({ label, count, required, Icon }) => (
              <div key={label} className="space-y-3 rounded-lg border bg-card p-4">
                <div className="flex items-center justify-between gap-3">
                  <span className="flex items-center gap-2 text-sm font-medium"><Icon className="size-4 text-muted-foreground" aria-hidden="true" />{label}</span>
                  <span className="text-xs tabular-nums text-muted-foreground">{required ? <><strong className="font-semibold text-foreground">{count}</strong> / {required} graded</> : "Not required"}</span>
                </div>
                {required > 0 && <div role="progressbar" aria-label={`${label} grading`} aria-valuemin={0} aria-valuemax={100}
                  aria-valuenow={Math.round(count / required * 100)} aria-valuetext={`${count} of ${required} graded`}
                  className="h-1.5 overflow-hidden rounded-full bg-muted">
                  <div className={`h-full w-full origin-left rounded-full ${count === required ? "bg-emerald-500" : "bg-primary"}`} style={{ transform: `scaleX(${count / required})` }} />
                </div>}
              </div>
            ))}
          </div>
          <div className="flex items-start gap-2.5 text-xs leading-relaxed text-muted-foreground">
            <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <div className="space-y-1">
              <p className="font-medium text-foreground">Based on {complete.length} complete {complete.length === 1 ? "grade" : "grades"}</p>
              <p>Overall statistics exclude incomplete and review-needed results. Essay and diagram analytics use their own graded-student counts.</p>
            </div>
          </div>
          {(essayRequired > essay || diagramRequired > diagram || review > 0) && <div role="status" className="space-y-1 rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2.5 text-xs leading-relaxed text-amber-800 dark:text-amber-300">
            {essayRequired > essay && <p>{essayRequired - essay} {essayRequired - essay === 1 ? "student is" : "students are"} awaiting essay grades.</p>}
            {diagramRequired > diagram && <p>{diagramRequired - diagram} {diagramRequired - diagram === 1 ? "student is" : "students are"} awaiting diagram grades.</p>}
            {review > 0 && <p>{review} {review === 1 ? "grade needs" : "grades need"} review before inclusion in overall statistics.</p>}
          </div>}
        </div>
      </CollapsibleContent>
    </Card>
  </Collapsible>;
}

export function StudentGradingCells({ student }: { student: StudentRow }) {
  const { components, grading_status: status, score } = student;
  const pendingLabel = components?.essay.status !== "graded" && components?.essay.status !== "not_required"
    ? "Pending essay grading" : "Pending diagram grading";
  return <>
    {(["essay", "diagram"] as const).map(kind => {
      const component = components?.[kind];
      return <TableCell key={kind} className="py-2 text-center text-sm tabular-nums">
        {component?.obtained != null && component.maximum != null
          ? <><div>{component.obtained.toFixed(1)} / {component.maximum.toFixed(1)}</div><span className="text-xs text-muted-foreground">{labels[component.status] || "Not available"}</span></>
          : labels[component?.status || ""] || "Not available"}
      </TableCell>;
    })}
    <TableCell className="py-2 text-center text-sm tabular-nums">
      {status && score.obtained != null && score.maximum != null ? <>
        <div>{score.obtained.toFixed(1)} / {score.maximum.toFixed(1)}</div>
        {score.percentage != null && <div className="text-xs text-muted-foreground">{status === "needs_review" ? "Provisional · " : ""}{score.percentage.toFixed(2)}%</div>}
      </> : "—"}
    </TableCell>
    <TableCell className="py-2" title={student.review_reasons?.join(" ")}>
      <Badge variant="outline" className={status !== "complete" ? "text-amber-700 dark:text-amber-300" : "text-emerald-700 dark:text-emerald-300"}>
        {status === "complete" ? "Complete" : status === "needs_review" ? "Review needed" : status === "pending" ? pendingLabel : "Not verified"}
      </Badge>
      {status === "needs_review" && student.review_reasons?.[0] && <p className="mt-1 max-w-64 text-xs text-muted-foreground">{student.review_reasons[0]}</p>}
    </TableCell>
  </>;
}
