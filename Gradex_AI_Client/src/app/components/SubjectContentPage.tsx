"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  Upload,
  Loader2,
  Save,
  Plus,
  Trash2,
  FileText,
  AlertCircle,
  ArrowLeft,
  BookOpen,
} from "lucide-react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
import { Slider } from "./ui/slider";
import { AIPageBanner } from "./AIBrand";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import {
  CONCEPT_WEIGHT_MAX,
  CONCEPT_WEIGHT_MIN,
  SubjectConcept,
  SubjectRubric,
  SubjectRubricSummary,
  fetchSubjectContent,
  listSubjectContent,
  saveSubjectContent,
  uploadSubjectContent,
} from "./viva/subjectContentApi";

/**
 * Lecturer-facing page for the technical viva flow's *first* step: turning
 * subject material into a concept rubric.
 *
 * A technical viva's AI-suggested technical-accuracy score is produced by
 * checking the student's transcript against the concepts stored here, keyed by
 * subject code. Without a rubric for that code the suggestion comes back
 * "skipped" and the examiner scores technical accuracy unaided — so this page
 * is what makes the "Subject code" field on Viva Assessment do anything.
 *
 * The AI-drafted concepts are a draft, not a rubric: the edit list below maps
 * to PUT /api/subject-content/{code} so a lecturer curates them before any
 * viva is graded against them.
 */

function makeConceptId(name: string): string {
  const slug = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug || `concept-${Date.now()}`;
}

function formatDate(value?: string): string {
  if (!value) return "";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "" : parsed.toLocaleString();
}

export function SubjectContentPage() {
  const [subjectCode, setSubjectCode] = useState("");
  const [subjectName, setSubjectName] = useState("");
  const [rubric, setRubric] = useState<SubjectRubric | null>(null);
  const [concepts, setConcepts] = useState<SubjectConcept[]>([]);
  const [dirty, setDirty] = useState(false);

  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  const [subjects, setSubjects] = useState<SubjectRubricSummary[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const trimmedCode = subjectCode.trim();

  const refreshList = useCallback(async () => {
    setListLoading(true);
    try {
      setSubjects(await listSubjectContent());
      setListError(null);
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Could not load subjects");
    } finally {
      setListLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshList();
  }, [refreshList]);

  /** Adopt a server response as the current editing state. */
  function applyRubric(next: SubjectRubric) {
    setRubric(next);
    setConcepts(next.concepts ?? []);
    setSubjectCode(next.subject_code ?? "");
    setSubjectName(next.subject_name ?? "");
    setDirty(false);
  }

  /** Open a subject from the browser list. */
  async function openSubject(code: string) {
    setLoading(true);
    try {
      const found = await fetchSubjectContent(code);
      if (!found) {
        toast.error("Subject no longer exists", { description: code });
        await refreshList();
        return;
      }
      applyRubric(found);
    } catch (err) {
      toast.error("Could not open subject", {
        description: err instanceof Error ? err.message : "Request failed",
      });
    } finally {
      setLoading(false);
    }
  }

  /** Return to the browser without discarding unsaved edits silently. */
  function closeSubject() {
    if (dirty && !window.confirm("Discard unsaved changes to this rubric?")) return;
    setRubric(null);
    setConcepts([]);
    setSubjectCode("");
    setSubjectName("");
    setDirty(false);
  }

  async function handleUpload(file: File) {
    if (!trimmedCode) {
      toast.error("Enter a subject code first", {
        description: "The rubric is stored against the subject code.",
      });
      return;
    }
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      toast.error("Only PDF files are supported", {
        description:
          "Text is extracted directly — a scanned PDF with no text layer will not work.",
      });
      return;
    }

    setUploading(true);
    try {
      const next = await uploadSubjectContent(
        file,
        trimmedCode,
        subjectName.trim() || trimmedCode,
      );
      applyRubric(next);
      void refreshList();
      toast.success("Concepts generated", {
        description: `${next.concepts?.length ?? 0} concepts now stored for ${next.subject_code}. Review them before grading.`,
      });
    } catch (err) {
      toast.error("Upload failed", {
        description: err instanceof Error ? err.message : "Request failed",
      });
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleSave() {
    if (!trimmedCode) return;
    const named = concepts.filter((concept) => concept.name.trim());
    if (named.length !== concepts.length) {
      toast.error("Every concept needs a name");
      return;
    }
    setSaving(true);
    try {
      const next = await saveSubjectContent(
        trimmedCode,
        subjectName.trim() || trimmedCode,
        named,
      );
      applyRubric(next);
      void refreshList();
      toast.success("Rubric saved", {
        description: "Vivas using this subject code will be checked against these concepts.",
      });
    } catch (err) {
      toast.error("Save failed", {
        description: err instanceof Error ? err.message : "Request failed",
      });
    } finally {
      setSaving(false);
    }
  }

  function updateConcept(index: number, patch: Partial<SubjectConcept>) {
    setConcepts((prev) =>
      prev.map((concept, i) => (i === index ? { ...concept, ...patch } : concept)),
    );
    setDirty(true);
  }

  function removeConcept(index: number) {
    setConcepts((prev) => prev.filter((_, i) => i !== index));
    setDirty(true);
  }

  function addConcept() {
    setConcepts((prev) => [
      ...prev,
      { id: `concept-${Date.now()}`, name: "", description: "", weight: 3 },
    ]);
    setDirty(true);
  }

  return (
    <div className="space-y-6">
      <AIPageBanner model="voca" />

      {rubric ? (
        <Button variant="ghost" className="-ml-2" onClick={closeSubject}>
          <ArrowLeft className="size-4 mr-1.5" />
          All subjects
        </Button>
      ) : (
        <Card className="p-6">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-foreground">Subjects</h2>
              <p className="text-sm text-muted-foreground mt-1">
                Every subject with a stored concept rubric. Open one to review its concepts and
                the text read from its uploaded material.
              </p>
            </div>
            <Badge variant="outline">{subjects.length}</Badge>
          </div>

          <div className="mt-4">
            {listLoading || loading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" />
                {loading ? "Opening subject…" : "Loading subjects…"}
              </div>
            ) : listError ? (
              <div className="flex items-start gap-2 text-sm text-amber-700 dark:text-amber-400">
                <AlertCircle className="size-4 mt-0.5 shrink-0" />
                <span>{listError}</span>
              </div>
            ) : subjects.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No subjects yet. Upload lecture material below to create the first one.
              </p>
            ) : (
              <div className="grid gap-2 sm:grid-cols-2">
                {subjects.map((subject) => (
                  <button
                    key={subject.subject_code}
                    type="button"
                    onClick={() => openSubject(subject.subject_code)}
                    className="rounded-lg border border-border p-3 text-left transition-colors hover:border-primary/40 hover:bg-muted/50"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <BookOpen className="size-4 text-primary shrink-0" />
                        <span className="text-sm font-medium text-foreground truncate">
                          {subject.subject_code}
                        </span>
                      </div>
                      <Badge variant="outline" className="text-xs shrink-0">
                        {subject.concept_count} concepts
                      </Badge>
                    </div>
                    <div className="text-xs text-muted-foreground mt-1 truncate">
                      {subject.subject_name}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1.5 truncate">
                      {(subject.source_files ?? []).length} file
                      {(subject.source_files ?? []).length === 1 ? "" : "s"}
                      {formatDate(subject.updated_at) && ` · updated ${formatDate(subject.updated_at)}`}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </Card>
      )}

      <Card className="p-6">
        <h2 className="text-foreground">
          {rubric ? `${rubric.subject_code} — add more material` : "Subject content"}
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Upload lecture material for a subject, and the AI drafts the list of concepts a student
          is expected to cover. Technical vivas entered with this subject code are checked against
          these concepts to suggest a technical-accuracy score.
        </p>

        <div className="mt-5 grid gap-4 sm:grid-cols-2 max-w-2xl">
          <div>
            <label className="text-xs text-muted-foreground" htmlFor="subject-code">
              Subject code
            </label>
            <Input
              id="subject-code"
              className="mt-1"
              value={subjectCode}
              onChange={(e) => setSubjectCode(e.target.value)}
              placeholder="e.g. CS3021"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Must match the code entered on the Viva Assessment page. Uploading to an existing
              code adds to that subject.
            </p>
          </div>

          <div>
            <label className="text-xs text-muted-foreground" htmlFor="subject-name">
              Subject name
            </label>
            <Input
              id="subject-name"
              className="mt-1"
              value={subjectName}
              onChange={(e) => {
                setSubjectName(e.target.value);
                setDirty(true);
              }}
              placeholder="e.g. Database Systems"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Gives the AI context when drafting concepts.
            </p>
          </div>
        </div>

        <div
          className={`mt-5 rounded-xl border-2 border-dashed p-10 text-center transition-colors ${
            uploading
              ? "border-border bg-muted/30 cursor-wait"
              : isDragging
                ? "border-primary bg-primary/5 cursor-pointer"
                : "border-border bg-muted/30 hover:border-primary/40 hover:bg-muted/50 cursor-pointer"
          }`}
          onDragEnter={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={(e) => {
            e.preventDefault();
            setIsDragging(false);
          }}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            setIsDragging(false);
            if (uploading) return;
            const file = e.dataTransfer.files?.[0];
            if (file) handleUpload(file);
          }}
          onClick={() => {
            if (!uploading) fileInputRef.current?.click();
          }}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if ((e.key === "Enter" || e.key === " ") && !uploading) {
              fileInputRef.current?.click();
            }
          }}
          aria-label="Upload subject material PDF"
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf,.pdf"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleUpload(file);
            }}
          />
          <div className="size-14 rounded-full bg-primary/10 mx-auto flex items-center justify-center text-primary">
            {uploading ? (
              <Loader2 className="size-6 animate-spin" />
            ) : (
              <Upload className="size-6" />
            )}
          </div>
          <div className="text-sm text-foreground mt-4">
            {uploading
              ? "Extracting text and drafting concepts…"
              : "Drag & drop lecture material, or click to browse"}
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            PDF only · text is read directly, so scanned/image-only PDFs will not work
          </div>
        </div>

      </Card>

      {rubric && (
        <Card className="p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-foreground">Concept rubric</h2>
              <p className="text-sm text-muted-foreground mt-1">
                AI-drafted from the uploaded material. Review and edit before it is used for
                grading — weight controls how much a concept counts toward the suggested score.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="outline">{concepts.length} concepts</Badge>
              {dirty && <Badge variant="outline">Unsaved changes</Badge>}
              <Button variant="outline" onClick={addConcept}>
                <Plus className="size-4 mr-1.5" />
                Add
              </Button>
              <Button onClick={handleSave} disabled={saving || !dirty}>
                {saving ? (
                  <Loader2 className="size-4 mr-1.5 animate-spin" />
                ) : (
                  <Save className="size-4 mr-1.5" />
                )}
                {saving ? "Saving…" : "Save rubric"}
              </Button>
            </div>
          </div>

          <Tabs defaultValue="concepts" className="mt-4">
            <TabsList>
              <TabsTrigger value="concepts">Concepts</TabsTrigger>
              <TabsTrigger value="source">
                Source text
                {rubric.source_files?.length ? ` (${rubric.source_files.length})` : ""}
              </TabsTrigger>
            </TabsList>

            <TabsContent value="source" className="mt-4 space-y-4">
              {!rubric.source_files?.length ? (
                <p className="text-sm text-muted-foreground">
                  No uploaded files recorded for this subject.
                </p>
              ) : (
                rubric.source_files.map((source) => (
                  <div key={source.filename} className="rounded-lg border border-border">
                    <div className="flex flex-wrap items-center gap-2 border-b border-border px-3 py-2">
                      <FileText className="size-4 text-muted-foreground shrink-0" />
                      <span className="text-sm text-foreground truncate">{source.filename}</span>
                      {formatDate(source.uploaded_at) && (
                        <span className="text-xs text-muted-foreground">
                          {formatDate(source.uploaded_at)}
                        </span>
                      )}
                      {source.extracted_chars != null && (
                        <Badge variant="outline" className="text-xs font-normal ml-auto">
                          {source.extracted_chars.toLocaleString()} chars
                        </Badge>
                      )}
                    </div>
                    {source.extracted_text ? (
                      <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words px-3 py-3 text-xs leading-relaxed text-muted-foreground">
                        {source.extracted_text}
                      </pre>
                    ) : (
                      <p className="px-3 py-3 text-xs text-muted-foreground">
                        No stored text for this file — it was uploaded before source text was
                        retained. Re-upload it to capture the text.
                      </p>
                    )}
                  </div>
                ))
              )}
            </TabsContent>

            <TabsContent value="concepts" className="mt-4 space-y-3">
            {concepts.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No concepts yet. Upload a PDF above or add one by hand.
              </p>
            )}
            {concepts.map((concept, index) => (
              <div key={concept.id || index} className="rounded-lg border border-border p-4">
                <div className="flex items-start gap-3">
                  <div className="flex-1 space-y-3">
                    <Input
                      value={concept.name}
                      onChange={(e) => {
                        const name = e.target.value;
                        // Concepts the server already stamped with a source_file keep
                        // their id, so re-uploading that file still matches them up.
                        updateConcept(index, {
                          name,
                          id: concept.source_file ? concept.id : makeConceptId(name),
                        });
                      }}
                      placeholder="Concept name"
                      aria-label={`Concept ${index + 1} name`}
                    />
                    <Textarea
                      value={concept.description ?? ""}
                      onChange={(e) => updateConcept(index, { description: e.target.value })}
                      placeholder="What should the student say about this? (guides the AI check)"
                      rows={2}
                      aria-label={`Concept ${index + 1} description`}
                    />
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-muted-foreground w-14">Weight</span>
                      <Slider
                        className="max-w-xs"
                        value={[concept.weight ?? 3]}
                        min={CONCEPT_WEIGHT_MIN}
                        max={CONCEPT_WEIGHT_MAX}
                        step={0.5}
                        onValueChange={([value]) => updateConcept(index, { weight: value })}
                        aria-label={`Concept ${index + 1} weight`}
                      />
                      <span className="text-xs text-foreground tabular-nums">
                        {(concept.weight ?? 3).toFixed(1)}
                      </span>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => removeConcept(index)}
                    aria-label={`Remove concept ${index + 1}`}
                  >
                    <Trash2 className="size-4 text-muted-foreground" />
                  </Button>
                </div>
              </div>
            ))}
            </TabsContent>
          </Tabs>
        </Card>
      )}
    </div>
  );
}
