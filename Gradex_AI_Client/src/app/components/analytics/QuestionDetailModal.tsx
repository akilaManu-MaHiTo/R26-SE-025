import React, { useEffect, useState } from "react";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "../ui/dialog";
import { BarChart3, FileText, Users } from "lucide-react";
import { fetchQuestionDetail, type ExamListItem, type QuestionDetail, type QuestionPerformance } from "../../api/lecturerApi";

interface Props {
  question: QuestionPerformance | null;
  exam: ExamListItem | null;
  open: boolean;
  onClose: () => void;
}

export function QuestionDetailModal({ question, exam, open, onClose }: Props) {
  const [detail, setDetail] = useState<QuestionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<"distribution" | "text" | "responses" | null>(null);
  const [retry, setRetry] = useState(0);
  const questionNo = question?.question_no;
  const courseCode = exam?.course_code;
  const sessionName = exam?.session_name;
  const year = exam?.year;
  const month = exam?.month;
  const semester = exam?.semester;

  useEffect(() => {
    if (!open || !questionNo || courseCode === undefined || sessionName === undefined || year === undefined || month === undefined || semester === undefined) return;
    let ignore = false;
    setDetail(null);
    setError(null);
    setLoading(true);
    setView(null);
    fetchQuestionDetail({ course_code: courseCode, session_name: sessionName, year, month, semester }, questionNo)
      .then((data) => { if (!ignore) setDetail(data); })
      .catch((err) => { if (!ignore) setError(err instanceof Error ? err.message : "Failed to load question detail"); })
      .finally(() => { if (!ignore) setLoading(false); });
    return () => { ignore = true; };
  }, [open, questionNo, courseCode, sessionName, year, month, semester, retry]);

  if (!open || !question || !exam) return null;
  const status = question.average_percentage >= 75 ? "Strong"
    : question.average_percentage >= 60 ? "Developing"
    : question.average_percentage >= 40 ? "Needs Improvement" : "Critical";
  const largestCount = Math.max(1, ...(detail?.mark_distribution.map((bin) => bin.count) ?? []));

  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) onClose(); }}>
      <DialogContent className="sm:max-w-3xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{question.question_id}</DialogTitle>
          <DialogDescription>{exam.course_code} · {exam.session_name} · {exam.year}, month {exam.month}, semester {exam.semester}</DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="text-sm text-muted-foreground">Class Average</div>
            <div className="text-2xl font-bold">{question.average_percentage.toFixed(2)}%</div>
          </div>
          <div>
            <div className="text-sm text-muted-foreground">Status</div>
            <Badge className="mt-1">{status}</Badge>
          </div>
          <div>
            <div className="text-sm text-muted-foreground">Topic</div>
            <div className="text-sm">{question.topic}</div>
          </div>
          <div>
            <div className="text-sm text-muted-foreground">Bloom Level</div>
            <div className="text-sm">{question.bloom_level}</div>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 border-t pt-4">
          <Button variant={view === "distribution" ? "default" : "outline"} size="sm" disabled={!detail} aria-pressed={view === "distribution"} onClick={() => setView("distribution")}>
            <BarChart3 className="h-4 w-4 mr-2" />View Mark Distribution
          </Button>
          <Button variant={view === "text" ? "default" : "outline"} size="sm" disabled={!detail} aria-pressed={view === "text"} onClick={() => setView("text")}>
            <FileText className="h-4 w-4 mr-2" />View Question Text
          </Button>
          <Button variant={view === "responses" ? "default" : "outline"} size="sm" disabled={!detail} aria-pressed={view === "responses"} onClick={() => setView("responses")}>
            <Users className="h-4 w-4 mr-2" />View Student Responses
          </Button>
        </div>

        {loading && <p role="status" className="text-sm text-muted-foreground">Loading question evidence...</p>}
        {error && <div role="alert" className="space-y-2">
          <p className="text-sm text-destructive">{error}</p>
          <Button variant="outline" size="sm" onClick={() => setRetry((value) => value + 1)}>Retry</Button>
        </div>}
        {detail && <>
          <p className="text-xs text-muted-foreground">Maximum: {detail.max_marks} marks · {detail.responses.length} graded responses. Answers are saved OCR excerpts.</p>
          {detail.excluded_count > 0 && <p role="status" className="text-sm text-muted-foreground">{detail.excluded_count} responses excluded because their saved marks are invalid.</p>}
          {view === "text" && <section aria-label="Question Text" className="space-y-2">
            <h3 className="font-medium">Question Text</h3>
            <p className="whitespace-pre-wrap break-words text-sm">{detail.question_text || "No saved question text available."}</p>
          </section>}
          {view === "distribution" && <section aria-label="Mark Distribution" className="space-y-3">
            <h3 className="font-medium">Mark Distribution</h3>
            {detail.mark_distribution.length === 0 ? <p className="text-sm text-muted-foreground">No graded marks available for this question.</p> : <ul className="space-y-2">
              {detail.mark_distribution.map((bin) => <li key={bin.marks} className="flex items-center gap-3 text-sm">
                <span className="w-24 shrink-0 tabular-nums">{bin.marks} marks</span>
                <div className="flex-1 rounded bg-muted h-5" aria-hidden="true">
                  <div className="rounded bg-primary h-full" style={{ width: `${bin.count / largestCount * 100}%` }} />
                </div>
                <span className="w-24 shrink-0 text-right tabular-nums">{bin.count} {bin.count === 1 ? "response" : "responses"}</span>
              </li>)}
            </ul>}
          </section>}
          {view === "responses" && <section aria-label="Student Responses" className="space-y-3">
            <h3 className="font-medium">Student Responses</h3>
            {detail.responses.length === 0 && <p className="text-sm text-muted-foreground">No graded responses available for this question.</p>}
            {detail.responses.map((response, index) => <article key={`${response.student_id}-${index}`} className="rounded-lg border p-4 space-y-2">
              <div className="flex justify-between gap-2 text-sm font-medium">
                <span>{response.student_id}</span>
                <span>{response.score} / {detail.max_marks} marks</span>
              </div>
              {response.slice_source === "full" && <p className="text-xs text-muted-foreground">Full-paper excerpt: OCR did not separate this question's answer.</p>}
              {response.slice_source === "ocr" && <p className="text-xs text-muted-foreground">Extracted from the saved OCR transcript using question headings.</p>}
              <p className="whitespace-pre-wrap break-words text-sm">{response.answer_excerpt || "No saved answer excerpt available."}</p>
              {response.feedback && <p className="whitespace-pre-wrap break-words text-sm text-muted-foreground">Feedback: {response.feedback}</p>}
            </article>)}
          </section>}
        </>}
      </DialogContent>
    </Dialog>
  );
}
