import { useEffect, useState, type FormEvent } from "react";
import { toast } from "sonner";
import { createExamKey, fetchExamKeys, type ExamKeyInput, type ExamKeyRecord } from "../api/examKeysApi";
import { formatCourseLabel, type CourseItem } from "../utils/courseOptions";
import { fetchTaxonomyCourses } from "../api/taxonomyApi";
import { MONTH_OPTIONS } from "../utils/dateOptions";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Input } from "./ui/input";

const selectClass = "border rounded-md p-2 bg-background text-sm";

export function ExamKeysPage() {
  const [courses, setCourses] = useState<CourseItem[]>([]);
  const [exams, setExams] = useState<ExamKeyRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [courseError, setCourseError] = useState("");
  const [examError, setExamError] = useState("");
  const [saveError, setSaveError] = useState("");
  const [saving, setSaving] = useState(false);
  const [reload, setReload] = useState(0);
  const loadError = [courseError, examError].filter(Boolean).join(" ");
  const [draft, setDraft] = useState<ExamKeyInput>({
    subjectCode: "", subjectName: "",
    examYear: new Date().getFullYear(), examSemester: 1,
    examMonth: MONTH_OPTIONS[new Date().getMonth()].label,
    session: "Final", examStructure: ["Essay"],
  });
  const generatedKey = draft.subjectCode
    ? `EXAM-${draft.subjectCode}-${draft.examYear}-S${draft.examSemester}-${draft.examMonth.slice(0, 3)}-${draft.session.replaceAll(" ", "").toUpperCase()}`
    : "";

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setCourseError("");
    setExamError("");
    Promise.allSettled([fetchTaxonomyCourses(), fetchExamKeys()]).then(([courseResult, examResult]) => {
      if (cancelled) return;
      if (courseResult.status === "fulfilled") setCourses(courseResult.value);
      else setCourseError(courseResult.reason instanceof Error ? courseResult.reason.message : "Could not load courses.");
      if (examResult.status === "fulfilled") setExams(examResult.value);
      else setExamError(examResult.reason instanceof Error ? examResult.reason.message : "Could not load exam keys.");
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [reload]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving) return;
    setSaving(true);
    setSaveError("");
    try {
      const exam = await createExamKey(draft);
      setExams((current) => [exam, ...current]);
      toast.success(`Exam key ${exam.examKey} created.`);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Could not save exam key.");
    } finally { setSaving(false); }
  }

  return (
    <div className="p-8 space-y-6 max-w-6xl mx-auto">
      <div>
        <h2 className="text-2xl font-semibold">Exam Keys</h2>
        <p className="text-sm text-muted-foreground mt-1">Register an exam before grading. Its subject, date, semester and session identify the saved key.</p>
      </div>
      {loadError && <div role="alert" className="text-sm text-destructive flex items-center gap-3">
        {loadError}<Button variant="outline" onClick={() => setReload((value) => value + 1)}>Retry</Button>
      </div>}
      <Card className="p-6">
        <form onSubmit={save} className="space-y-5">
          <h3 className="font-medium">Create exam key</h3>
          <fieldset disabled={loading || saving || !!courseError} className="space-y-5">
            <div className="grid sm:grid-cols-2 gap-4">
              <label className="grid gap-1 text-sm">Subject
                <select required className={selectClass} value={draft.subjectCode} onChange={(event) => {
                  const course = courses.find((item) => item.code === event.target.value);
                  setDraft({ ...draft, subjectCode: course?.code ?? "", subjectName: course?.name ?? "" });
                }}>
                  <option value="">{loading ? "Loading subjects…" : "Select subject"}</option>
                  {courses.map((course) => <option key={course._id} value={course.code}>{formatCourseLabel(course)}</option>)}
                </select>
              </label>
              <label className="grid gap-1 text-sm">Subject name
                <Input required maxLength={200} value={draft.subjectName} onChange={(event) => setDraft({ ...draft, subjectName: event.target.value })} />
              </label>
              <div className="grid gap-1 text-sm">
                <label htmlFor="exam-key">Exam key</label>
                <Input id="exam-key" aria-describedby="exam-key-help" readOnly placeholder="Select a subject to generate the key" value={generatedKey} />
                <span id="exam-key-help" className="text-xs text-muted-foreground">Generated automatically from the exam details. This key cannot be edited.</span>
              </div>
              <label className="grid gap-1 text-sm">Year
                <Input required type="number" min={1900} max={9999} value={draft.examYear || ""} onChange={(event) => setDraft({ ...draft, examYear: Number(event.target.value) })} />
              </label>
              <label className="grid gap-1 text-sm">Semester
                <select className={selectClass} value={draft.examSemester} onChange={(event) => setDraft({ ...draft, examSemester: Number(event.target.value) })}>
                  <option value={1}>First Semester</option><option value={2}>Second Semester</option>
                </select>
              </label>
              <label className="grid gap-1 text-sm">Month
                <select className={selectClass} value={draft.examMonth} onChange={(event) => setDraft({ ...draft, examMonth: event.target.value })}>
                  {MONTH_OPTIONS.map((month) => <option key={month.value} value={month.label}>{month.label}</option>)}
                </select>
              </label>
              <label className="grid gap-1 text-sm">Session
                <select className={selectClass} value={draft.session} onChange={(event) => setDraft({ ...draft, session: event.target.value })}>
                  <option>Final</option><option>Mid Term</option>
                </select>
              </label>
            </div>
            <div className="space-y-3">
              <div><h4 className="text-sm font-medium">Exam structure</h4><p className="text-xs text-muted-foreground">Add one type for each question, in exam order.</p></div>
              {draft.examStructure.map((type, index) => <div key={index} className="flex items-end gap-3">
                <label className="grid gap-1 text-sm flex-1">Question {index + 1} type
                  <select className={selectClass} value={type} onChange={(event) => setDraft({ ...draft, examStructure: draft.examStructure.map((item, i) => i === index ? event.target.value : item) })}>
                    <option>Essay</option><option>Diagram</option><option>MCQ</option><option>Viva</option>
                  </select>
                </label>
                <Button type="button" variant="outline" disabled={draft.examStructure.length === 1} aria-label={`Remove question ${index + 1}`} onClick={() => setDraft({ ...draft, examStructure: draft.examStructure.filter((_, i) => i !== index) })}>Remove</Button>
              </div>)}
              <Button type="button" variant="outline" disabled={draft.examStructure.length >= 100} onClick={() => setDraft({ ...draft, examStructure: [...draft.examStructure, "Essay"] })}>Add question</Button>
            </div>
            {saveError && <p role="alert" className="text-sm text-destructive">{saveError}</p>}
            {!loading && !courses.length && <p className="text-sm text-muted-foreground">Create a course before registering an exam key.</p>}
            <Button type="submit" disabled={!courses.length}>{saving ? "Creating…" : "Create exam key"}</Button>
          </fieldset>
        </form>
      </Card>
      <Card className="p-6 space-y-4">
        <h3 className="font-medium">Saved exam keys</h3>
        {loading ? <p role="status" className="text-sm text-muted-foreground">Loading exam keys…</p> : !examError && !exams.length ? <p className="text-sm text-muted-foreground">No exam keys yet.</p> : <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead><tr className="border-b"><th scope="col" className="p-2">Exam key</th><th scope="col" className="p-2">Subject</th><th scope="col" className="p-2">Exam details</th><th scope="col" className="p-2">Structure</th></tr></thead>
            <tbody>{exams.map((exam) => <tr key={exam.examKey} className="border-b">
              <td className="p-2 font-medium">{exam.examKey}</td>
              <td className="p-2">{exam.subjectCode}<div className="text-muted-foreground">{exam.subjectName}</div></td>
              <td className="p-2">{exam.examMonth} {exam.examYear} · S{exam.examSemester} · {exam.session}</td>
              <td className="p-2">{exam.examStructure?.map((type, index) => `Q${index + 1}: ${type}`).join(" · ")}</td>
            </tr>)}</tbody>
          </table>
        </div>}
      </Card>
    </div>
  );
}
