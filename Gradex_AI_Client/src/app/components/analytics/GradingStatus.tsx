import React from "react";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { TableCell } from "../ui/table";
import type { StudentRow, ExamListItem } from "../../api/lecturerApi";

export function ExamInventoryScore({ exam }: { exam: ExamListItem }) {
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
    return <Card className="p-4 text-sm" role="status">Grading progress is unavailable for legacy records. Overall grades are not verified.</Card>;
  }
  const complete = students.filter(s => s.grading_status === "complete" && typeof s.score.percentage === "number" && Number.isFinite(s.score.percentage));
  const review = students.filter(s => s.grading_status === "needs_review").length;
  const pending = students.length - complete.length - review;
  const essay = students.filter(s => s.components?.essay.status === "graded").length;
  const diagram = students.filter(s => s.components?.diagram.status === "graded").length;
  const essayRequired = students.filter(s => s.components?.essay.status !== "not_required").length;
  const diagramRequired = students.filter(s => s.components?.diagram.status !== "not_required").length;
  const average = complete.length ? complete.reduce((sum, s) => sum + s.score.percentage!, 0) / complete.length : null;
  return <Card className="p-4 space-y-3" aria-label="Exam grading progress">
    <h3 className="font-semibold">Grading progress · {students.length} students</h3>
    <div className="flex flex-wrap gap-2 text-sm">
      <Badge variant="secondary">Essay: {essay}/{essayRequired} graded</Badge>
      <Badge variant="secondary">Diagram: {diagram}/{diagramRequired} graded</Badge>
      <span>Overall: {pending} pending · {review} needs review · {complete.length} complete</span>
    </div>
    <div className="text-sm">Overall average: <strong>{average === null ? "No complete overall grades yet" : `${average.toFixed(2)}%`}</strong>
      <span className="text-muted-foreground"> · Based on {complete.length} complete {complete.length === 1 ? "grade" : "grades"}</span>
    </div>
    <div role="status" className="rounded-md bg-amber-500/10 p-3 text-sm">
      {essayRequired > essay && `${essayRequired - essay} ${essayRequired - essay === 1 ? "student is" : "students are"} awaiting essay grades. `}
      {diagramRequired > diagram && `${diagramRequired - diagram} ${diagramRequired - diagram === 1 ? "student is" : "students are"} awaiting diagram grades. `}
      Overall statistics exclude incomplete and review-needed results. Essay and diagram analytics use their own graded-student counts.
    </div>
  </Card>;
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
