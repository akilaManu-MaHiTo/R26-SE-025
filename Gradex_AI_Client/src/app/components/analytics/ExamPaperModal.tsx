import React, { useEffect, useState } from "react";
import { Button } from "../ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "../ui/dialog";
import { fetchExamPaperDefinition, type ExamListItem, type ExamPaperDefinition } from "../../api/lecturerApi";

const text = (value: unknown) => typeof value === "string" ? value : value == null ? "Not available" : JSON.stringify(value);
const marks = (value: number | null) => typeof value === "number" && Number.isFinite(value) ? `${value} marks` : "Marks unavailable";

export function ExamPaperModal({ exam, open, onClose }: { exam: ExamListItem | null; open: boolean; onClose: () => void }) {
  const [paper, setPaper] = useState<ExamPaperDefinition | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const course = exam?.course_code, session = exam?.session_name, year = exam?.year, month = exam?.month, semester = exam?.semester;
  useEffect(() => {
    setPaper(null);
    setError(null);
    if (!open || course === undefined || session === undefined || year === undefined || month === undefined || semester === undefined) return;
    let ignore = false;
    fetchExamPaperDefinition({ course_code: course, session_name: session, year, month, semester })
      .then(value => { if (!ignore) setPaper(value); })
      .catch(reason => { if (!ignore) setError(reason instanceof Error ? reason.message : "Failed to load question paper"); });
    return () => { ignore = true; };
  }, [open, course, session, year, month, semester, retry]);

  if (!open || !exam) return null;
  return <Dialog open={open} onOpenChange={value => { if (!value) onClose(); }}>
    <DialogContent className="sm:max-w-4xl max-h-[85vh] overflow-y-auto">
      <DialogHeader>
        <DialogTitle>Question paper & marking rubrics</DialogTitle>
        <DialogDescription>{course} · {session} · {year}, month {month}, semester {semester}. Saved extracted wording and marking criteria; compare with the original paper to confirm full wording.</DialogDescription>
      </DialogHeader>
      {!paper && !error && <p role="status">Loading question paper...</p>}
      {error && <div role="alert"><p>{error}</p><Button variant="outline" onClick={() => setRetry(value => value + 1)}>Retry</Button></div>}
      {paper && <div className="space-y-6">
        <div className="space-y-1 text-sm">
          <p>Expected structure: {paper.expected_structure.join(" · ")}</p>
          <p className="font-medium">{paper.maximum_marks == null ? "Maximum unavailable" : `Verified maximum: ${paper.maximum_marks} marks`}</p>
        </div>
        {paper.validation.messages.length > 0 && <div role="status" className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">
          <p className="font-medium">Source paper incomplete</p>
          <ul className="list-disc pl-5">{paper.validation.messages.map(message => <li key={message}>{message}</li>)}</ul>
        </div>}
        <section aria-label="Essay questions" className="space-y-4">
          <h3 className="font-semibold">Essay questions</h3>
          {paper.essay_questions.length === 0 && <p>No essay question definitions available.</p>}
          {paper.essay_questions.map((question, index) => <article key={index} className="rounded-md border p-4 space-y-3">
            <h4 className="font-medium">Question {question.question_no ?? "number unavailable"} · {marks(question.max_marks)}</h4>
            <p className="whitespace-pre-wrap">{text(question.question_text)}</p>
            <ul className="list-disc pl-5 space-y-2 text-sm">{question.criteria.map((criterion, i) => <li key={i}>{text(criterion.point)} — {marks(criterion.marks)}</li>)}</ul>
          </article>)}
        </section>
        <section aria-label="Diagram marking rubrics" className="space-y-4">
          <h3 className="font-semibold">Diagram marking rubrics</h3>
          {paper.diagram_rubrics.length === 0 && <p>No confidently linked diagram rubric available.</p>}
          {paper.diagram_rubrics.map(rubric => <article key={rubric.rubric_id} className="rounded-md border p-4 space-y-3">
            <h4 className="font-medium">{rubric.exam_code ?? "Diagram rubric"} · {marks(rubric.total_marks)}</h4>
            {rubric.criteria.map((criterion, index) => <div key={index} className="border-t pt-3 text-sm space-y-1">
              <p className="font-medium">{text(criterion.criterion)} — {marks(criterion.marks)}</p>
              <p className="whitespace-pre-wrap">{text(criterion.description)}</p>
              {criterion.expected != null && <details><summary className="cursor-pointer">Expected diagram criteria</summary><pre className="whitespace-pre-wrap break-words mt-2">{JSON.stringify(criterion.expected, null, 2)}</pre></details>}
            </div>)}
          </article>)}
        </section>
      </div>}
    </DialogContent>
  </Dialog>;
}
