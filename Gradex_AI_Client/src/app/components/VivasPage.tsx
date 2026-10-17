import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { toast } from "sonner";
import { AlertCircle, BarChart3, BookOpen, ChevronUp, Loader2, Plus, Radio, Upload } from "lucide-react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Input } from "./ui/input";
import { Skeleton } from "./ui/skeleton";
import { createViva, listVivas, type Viva, type VivaCategory } from "./viva/vivasApi";
import { listSubjectContent, type SubjectRubricSummary } from "./viva/subjectContentApi";
import { SubjectContentPage } from "./SubjectContentPage";

const SELECT_CLASS =
  "mt-1 h-9 w-full rounded-md border border-input bg-background px-2 text-sm disabled:opacity-60";

function CreateVivaForm({
  rubrics,
  onCreated,
}: {
  rubrics: SubjectRubricSummary[];
  onCreated: (viva: Viva) => void;
}) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState<VivaCategory>("non_technical");
  const [subjectCode, setSubjectCode] = useState("");
  const [subjectName, setSubjectName] = useState("");
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [semester, setSemester] = useState("1");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const technical = category === "technical";

  const changeCategory = (next: VivaCategory) => {
    setCategory(next);
    setSubjectCode("");
    setSubjectName("");
  };

  // Typing a code that already has subject content fills in its name.
  const changeSubjectCode = (code: string) => {
    setSubjectCode(code);
    const match = rubrics.find((row) => row.subject_code === code.trim());
    if (match) setSubjectName(match.subject_name);
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setSaving(true);
    try {
      const viva = await createViva({
        name: name.trim(),
        subject_code: subjectCode.trim(),
        subject_name: subjectName.trim(),
        category,
        year: Number(year),
        semester: Number(semester),
        notes: notes.trim() || undefined,
      });
      toast.success(`Created ${viva.label}`);
      setName("");
      setNotes("");
      onCreated(viva);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the viva");
    } finally {
      setSaving(false);
    }
  };

  const ready = Boolean(
    name.trim() && subjectCode.trim() && subjectName.trim() && Number(year) >= 2000 && Number(semester) >= 1,
  );

  return (
    <Card className="p-6">
      {/* <h3 className="text-base font-medium text-foreground">Create a viveeea</h3> */}
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <label className="text-xs text-muted-foreground" htmlFor="viva-name">
            Viva name
          </label>
          <Input
            id="viva-name"
            className="mt-1"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. ER Viva, Group A"
            maxLength={120}
            required
          />
        </div>

        <div>
          <label className="text-xs text-muted-foreground" htmlFor="viva-category">
            Category
          </label>
          <select
            id="viva-category"
            className={SELECT_CLASS}
            value={category}
            onChange={(e) => changeCategory(e.target.value as VivaCategory)}
          >
            <option value="non_technical">Non-technical — communication / presentation</option>
            <option value="technical">Technical — scored against a subject rubric</option>
          </select>
        </div>

        <div>
          <label className="text-xs text-muted-foreground" htmlFor="viva-subject-code">
            Subject code
          </label>
          <Input
            id="viva-subject-code"
            className="mt-1"
            value={subjectCode}
            onChange={(e) => changeSubjectCode(e.target.value)}
            placeholder="e.g. SE3040"
            maxLength={32}
            list={technical ? "viva-subject-options" : undefined}
            required
          />
          {technical && (
            <>
              <datalist id="viva-subject-options">
                {rubrics.map((row) => (
                  <option key={row.subject_code} value={row.subject_code}>
                    {row.subject_name}
                  </option>
                ))}
              </datalist>
              <p className="text-xs text-muted-foreground mt-1">
                Technical vivas are scored against the subject content (lecture PDFs). Add it right
                after you create the viva, or pick a subject that already has it.
              </p>
            </>
          )}
        </div>

        <div className="sm:col-span-2">
          <label className="text-xs text-muted-foreground" htmlFor="viva-subject-name">
            Subject name
          </label>
          <Input
            id="viva-subject-name"
            className="mt-1"
            value={subjectName}
            onChange={(e) => setSubjectName(e.target.value)}
            placeholder="e.g. Software Testing"
            maxLength={120}
            required
          />
        </div>

        <div>
          <label className="text-xs text-muted-foreground" htmlFor="viva-year">
            Year
          </label>
          <select
            id="viva-year"
            className={SELECT_CLASS}
            value={year}
            onChange={(e) => setYear(e.target.value)}
            required
          >
            {Array.from({ length: 101 }, (_, index) => {
              const optionYear = 2000 + index;
              return (
                <option key={optionYear} value={optionYear}>
                  {optionYear}
                </option>
              );
            })}
          </select>
        </div>
        <div>
          <label className="text-xs text-muted-foreground" htmlFor="viva-semester">
            Semester
          </label>
          <select
            id="viva-semester"
            className={SELECT_CLASS}
            value={semester}
            onChange={(e) => setSemester(e.target.value)}
          >
            <option value="1">Semester 1</option>
            <option value="2">Semester 2</option>
            <option value="3">Semester 3</option>
            <option value="4">Semester 4</option>
          </select>
        </div>

        <div className="sm:col-span-2">
          <label className="text-xs text-muted-foreground" htmlFor="viva-notes">
            Notes (optional)
          </label>
          <Input
            id="viva-notes"
            className="mt-1"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            maxLength={500}
          />
        </div>

        {error && (
          <div className="sm:col-span-2 flex items-start gap-2 text-sm text-destructive">
            <AlertCircle className="size-4 mt-0.5 shrink-0" />
            {error}
          </div>
        )}

        <div className="sm:col-span-2">
          <Button type="submit" disabled={saving || !ready}>
            {saving ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
            Create viva
          </Button>
        </div>
      </form>
    </Card>
  );
}

function VivaCard({
  viva,
  rubric,
  expanded,
  onToggle,
  onRubricChanged,
}: {
  viva: Viva;
  rubric: SubjectRubricSummary | undefined;
  expanded: boolean;
  onToggle: () => void;
  onRubricChanged: () => void;
}) {
  const query = `?viva=${encodeURIComponent(viva.viva_id)}`;
  const technical = viva.category === "technical";
  // A technical viva cannot be analyzed until its subject content exists.
  const needsContent = technical && !rubric;
  return (
    <div className="rounded-lg border border-border p-4">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="min-w-0">
          <div className="text-sm font-medium text-foreground">{viva.label}</div>
          <div className="text-xs text-muted-foreground mt-1">
            {viva.subject_name} · {viva.examiner_email}
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant={technical ? "default" : "secondary"}>{technical ? "Technical" : "Non-technical"}</Badge>
          {technical && (
            <Badge
              variant="outline"
              className={needsContent ? "border-amber-500 text-amber-700 dark:text-amber-400" : undefined}
            >
              {needsContent ? "Subject content needed" : `${rubric?.concept_count ?? 0} concepts`}
            </Badge>
          )}
          <Badge variant="outline">
            {viva.mark_count ?? 0} analysed · {viva.published_count ?? 0} published
          </Badge>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {technical && (
          <Button size="sm" variant={needsContent ? "default" : "outline"} onClick={onToggle}>
            {expanded ? <ChevronUp className="size-3.5" /> : <BookOpen className="size-3.5" />}
            {expanded ? "Hide subject content" : needsContent ? "Add subject content" : "Subject content"}
          </Button>
        )}
        {needsContent ? (
          <>
            <Button size="sm" disabled title="Add the subject content first">
              <Upload className="size-3.5" /> Upload / record
            </Button>
            <Button size="sm" variant="outline" disabled title="Add the subject content first">
              <Radio className="size-3.5" /> Live viva
            </Button>
          </>
        ) : (
          <>
            <Button asChild size="sm">
              <Link to={`/viva-evaluation/viva-assessment${query}`}>
                <Upload className="size-3.5" /> Upload / record
              </Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link to={`/viva-evaluation/live-copilot${query}`}>
                <Radio className="size-3.5" /> Live viva
              </Link>
            </Button>
          </>
        )}
        <Button asChild size="sm" variant="outline">
          <Link to={`/viva-evaluation/viva-results${query}`}>
            <BarChart3 className="size-3.5" /> Results
          </Link>
        </Button>
      </div>

      {needsContent && !expanded && (
        <p className="mt-2 text-xs text-amber-700 dark:text-amber-400">
          Upload the lecture material for {viva.subject_code} to unlock uploading and live recording.
        </p>
      )}

      {technical && expanded && (
        <div className="mt-4 border-t border-border pt-4">
          <SubjectContentPage
            embedded
            lockedSubject={{ code: viva.subject_code, name: viva.subject_name }}
            onChanged={onRubricChanged}
          />
        </div>
      )}
    </div>
  );
}

export function VivasPage() {
  const [vivas, setVivas] = useState<Viva[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [subjectFilter, setSubjectFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<"" | VivaCategory>("");
  const [rubrics, setRubrics] = useState<SubjectRubricSummary[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // A failed lookup only hides the concept counts; it must not block creating vivas.
  const refreshRubrics = useCallback(async () => {
    try {
      setRubrics(await listSubjectContent());
    } catch {
      setRubrics([]);
    }
  }, []);

  useEffect(() => {
    void refreshRubrics();
  }, [refreshRubrics]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setVivas(await listVivas());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load vivas");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const subjects = useMemo(() => Array.from(new Set(vivas.map((v) => v.subject_code))).sort(), [vivas]);

  const groups = useMemo(() => {
    const filtered = vivas.filter(
      (v) =>
        (!subjectFilter || v.subject_code === subjectFilter) &&
        (!categoryFilter || v.category === categoryFilter),
    );
    const bySubject = new Map<string, Viva[]>();
    for (const viva of filtered) {
      bySubject.set(viva.subject_code, [...(bySubject.get(viva.subject_code) ?? []), viva]);
    }
    return Array.from(bySubject.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [vivas, subjectFilter, categoryFilter]);

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6">
      <CreateVivaForm
        rubrics={rubrics}
        onCreated={(viva) => {
          void load();
          // Straight on to step two: a technical viva opens its subject content panel.
          if (viva.category === "technical") setExpandedId(viva.viva_id);
        }}
      />

      <Card className="p-6">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <h3 className="text-base font-medium text-foreground">Vivas by subject</h3>
          <div className="flex items-center gap-2 flex-wrap">
            <select
              aria-label="Filter by subject"
              className="h-9 rounded-md border border-input bg-background px-2 text-sm"
              value={subjectFilter}
              onChange={(e) => setSubjectFilter(e.target.value)}
            >
              <option value="">All subjects</option>
              {subjects.map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </select>
            <select
              aria-label="Filter by category"
              className="h-9 rounded-md border border-input bg-background px-2 text-sm"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value as "" | VivaCategory)}
            >
              <option value="">All categories</option>
              <option value="technical">Technical</option>
              <option value="non_technical">Non-technical</option>
            </select>
          </div>
        </div>

        <div className="mt-4 space-y-6">
          {error && <div className="text-sm text-destructive">{error}</div>}
          {loading ? (
            <Skeleton className="h-24 w-full" />
          ) : groups.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {vivas.length === 0 ? "No vivas yet — create your first one above." : "No vivas match these filters."}
            </p>
          ) : (
            groups.map(([code, items]) => (
              <section key={code}>
                <div className="text-sm font-medium text-foreground mb-2">
                  {code} · {items[0].subject_name}
                </div>
                <div className="space-y-3">
                  {items.map((viva) => (
                    <VivaCard
                      key={viva.viva_id}
                      viva={viva}
                      rubric={rubrics.find((row) => row.subject_code === viva.subject_code)}
                      expanded={expandedId === viva.viva_id}
                      onToggle={() => setExpandedId((current) => (current === viva.viva_id ? null : viva.viva_id))}
                      onRubricChanged={() => void refreshRubrics()}
                    />
                  ))}
                </div>
              </section>
            ))
          )}
        </div>
      </Card>
    </div>
  );
}
