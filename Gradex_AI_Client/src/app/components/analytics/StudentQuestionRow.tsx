import React, { useEffect, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { fetchStudentAnswerEvidence, type LecturerStudentDetail, type StudentAnswerEvidence } from "../../api/lecturerApi";
import { Button } from "../ui/button";
import { Badge } from "../ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../ui/table";

interface Props {
  question: LecturerStudentDetail["question_performance"][number];
  exam: { course_code: string; session_name: string; year: number; month: number; semester: number };
  studentId: string;
}

export function StudentQuestionRow({ question: q, exam, studentId }: Props) {
  const [open, setOpen] = useState(false);
  const [evidence, setEvidence] = useState<StudentAnswerEvidence | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const { course_code, session_name, year, month, semester } = exam;

  useEffect(() => {
    if (!open) return;
    let ignore = false;
    setEvidence(null);
    setError(null);
    fetchStudentAnswerEvidence({ course_code, session_name, year, month, semester }, studentId, q.question_no)
      .then(value => { if (!ignore) setEvidence(value); })
      .catch(err => { if (!ignore) setError(err instanceof Error ? err.message : "Could not load answer evidence"); });
    return () => { ignore = true; };
  }, [open, course_code, session_name, year, month, semester, studentId, q.question_no, retry]);

  const panelId = `answer-${encodeURIComponent(studentId)}-${encodeURIComponent(q.question_id)}`;
  return <>
    <TableRow>
      <TableCell className="font-medium text-xs">
        <Button variant="ghost" size="sm" aria-expanded={open} aria-controls={panelId}
          aria-label={`${open ? "Hide" : "Review"} answer for question ${q.question_no}`} onClick={() => setOpen(value => !value)}>
          {open ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />} {q.question_no}
        </Button>
      </TableCell>
      <TableCell className="text-xs max-w-[160px] truncate" title={q.topic}>{q.topic}<span className="text-muted-foreground"> · {q.subtopic}</span></TableCell>
      <TableCell><Badge variant="outline" className="text-xs">{q.bloom_analysis.level}</Badge></TableCell>
      <TableCell className="text-xs text-right tabular-nums">{q.performance.score.toFixed(1)} / {q.performance.max_score.toFixed(1)}</TableCell>
      <TableCell className="text-xs text-right tabular-nums">{q.performance.percentage.toFixed(1)}%</TableCell>
    </TableRow>
    {open && <TableRow className="bg-muted/20 hover:bg-muted/20">
      <TableCell colSpan={5} className="p-4 whitespace-normal">
        <div id={panelId} className="space-y-4" role="region" aria-label={`Question ${q.question_no} answer review`}>
          <section className="space-y-1">
            <h5 className="text-sm font-semibold">Question</h5>
            <p className="text-sm whitespace-pre-wrap break-words">{q.question_text}</p>
          </section>
          {!evidence && !error && <p role="status" className="text-sm text-muted-foreground">Loading saved answer evidence...</p>}
          {error && <div role="alert" className="space-y-2">
            <p className="text-sm text-destructive">{error}</p>
            <Button variant="outline" size="sm" onClick={() => setRetry(value => value + 1)}>Retry</Button>
          </div>}
          {evidence && <>
            {evidence.grading_error && <p role="alert" className="text-sm text-amber-700 dark:text-amber-300">Grading needs manual review: {evidence.grading_error}</p>}
            <div className="grid gap-4 lg:grid-cols-2">
              <section className="space-y-2 min-w-0">
                <h5 className="text-sm font-semibold">Student's written answer</h5>
                <p className="text-xs text-muted-foreground">{evidence.slice_source === "ocr"
                  ? "Recovered OCR excerpt; the text used for grading was not saved."
                  : evidence.slice_source === "full" ? "Full-paper excerpt: OCR did not separate this question's answer."
                  : "Saved answer excerpt used for grading."} Excerpts may be incomplete (up to 1,200 characters); OCR may misread handwriting.</p>
                {evidence.answer_excerpt
                  ? <p className="rounded-md border bg-background p-3 text-sm whitespace-pre-wrap break-words">{evidence.answer_excerpt}</p>
                  : <p className="text-sm text-muted-foreground">{evidence.slice_source === "empty"
                    ? "No answer text was extracted for grading. Check the original script before treating this as unanswered."
                    : "No saved answer text is available. This does not establish whether the student answered."}</p>}
              </section>
              <section className="space-y-2 min-w-0">
                <h5 className="text-sm font-semibold">Grading feedback</h5>
                <p className="text-sm whitespace-pre-wrap break-words">{evidence.feedback || "No saved grading feedback available."}</p>
                {evidence.justification && <><h6 className="text-xs font-medium">Mark justification</h6><p className="text-sm whitespace-pre-wrap break-words">{evidence.justification}</p></>}
                {evidence.grading_source && <p className="text-xs text-muted-foreground">Grading source: {evidence.grading_source}</p>}
              </section>
            </div>
          </>}
          <section className="space-y-2">
            <h5 className="text-sm font-semibold">Marking criteria</h5>
            {q.criteria_performance.length ? <Table>
              <TableHeader><TableRow><TableHead>Criterion</TableHead><TableHead className="text-right">Marks</TableHead><TableHead>Outcome</TableHead></TableRow></TableHeader>
              <TableBody>{q.criteria_performance.map((criterion, index) => <TableRow key={index}>
                <TableCell className="whitespace-normal text-xs">{criterion.criterion}</TableCell>
                <TableCell className="text-right text-xs tabular-nums">{criterion.awarded_marks} / {criterion.max_marks}</TableCell>
                <TableCell className="text-xs">{criterion.awarded_marks >= criterion.max_marks ? "Full marks" : criterion.awarded_marks > 0 ? "Partial credit" : "No marks"}</TableCell>
              </TableRow>)}</TableBody>
            </Table> : <p className="text-sm text-muted-foreground">No saved criterion breakdown available.</p>}
            {evidence?.criteria_breakdown.filter(item => item.reason).map((item, index) => <p key={index} className="text-xs whitespace-pre-wrap break-words">
              <span className="font-medium">{item.point || "Grading criterion"}:</span> {item.reason}
            </p>)}
          </section>
        </div>
      </TableCell>
    </TableRow>}
  </>;
}
