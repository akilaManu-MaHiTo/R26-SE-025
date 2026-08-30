"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  Upload,
  Loader2,
  FileText,
  AlertCircle,
  ArrowLeft,
  ClipboardList,
} from "lucide-react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Input } from "./ui/input";
import { AIPageBanner } from "./AIBrand";
import {
  DiagramGuideline,
  GuidelineExpected,
  listDiagramGuidelines,
  uploadDiagramGuideline,
} from "./viva/diagramGuidelineApi";

/**
 * Lecturer-facing page for the diagram grading flow's *first* step: turning a
 * marking-guideline PDF into the structured criteria the grader scores against.
 *
 * The uploaded PDF's text is distilled by the AI into
 * {examCode, guideLines[], totalMarks} and stored in the same `diagram_marking`
 * collection /api/diagram-evaluate loads by guideline id — so a guideline
 * created here is what makes a diagram submission gradable for that exam code.
 */

function formatDate(value?: string): string {
  if (!value) return "";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "" : parsed.toLocaleString();
}

/** Render an `expected` object as compact "key: value" chips. Its keys differ
 * per criterion type, so this formats generically rather than per-shape. */
function describeExpected(expected?: GuidelineExpected): string[] {
  if (!expected) return [];
  return Object.entries(expected).map(([key, value]) => {
    const rendered = Array.isArray(value) ? value.join(", ") : String(value);
    return `${key}: ${rendered}`;
  });
}

export function DiagramGuidelinePage() {
  const [examCode, setExamCode] = useState("");
  const [guideline, setGuideline] = useState<DiagramGuideline | null>(null);

  const [uploading, setUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  const [guidelines, setGuidelines] = useState<DiagramGuideline[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const trimmedCode = examCode.trim();

  const refreshList = useCallback(async () => {
    setListLoading(true);
    try {
      setGuidelines(await listDiagramGuidelines());
      setListError(null);
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Could not load guidelines");
    } finally {
      setListLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshList();
  }, [refreshList]);

  function openGuideline(next: DiagramGuideline) {
    setGuideline(next);
    setExamCode(next.examCode ?? "");
  }

  function closeGuideline() {
    setGuideline(null);
    setExamCode("");
  }

  async function handleUpload(file: File) {
    if (!trimmedCode) {
      toast.error("Enter an exam code first", {
        description: "The guideline is stored against the exam code.",
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
      const next = await uploadDiagramGuideline(file, trimmedCode);
      openGuideline(next);
      void refreshList();
      toast.success(
        next.status === "updated" ? "Guideline updated" : "Guideline created",
        {
          description: `${next.guideLines?.length ?? 0} criteria totalling ${next.totalMarks ?? 0} marks stored for ${next.examCode}.`,
        },
      );
    } catch (err) {
      toast.error("Upload failed", {
        description: err instanceof Error ? err.message : "Request failed",
      });
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  const criteria = guideline?.guideLines ?? [];

  return (
    <div className="space-y-6">
      <AIPageBanner model="structr" />

      {guideline ? (
        <Button variant="ghost" className="-ml-2" onClick={closeGuideline}>
          <ArrowLeft className="size-4 mr-1.5" />
          All guidelines
        </Button>
      ) : (
        <Card className="p-6">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-foreground">Marking guidelines</h2>
              <p className="text-sm text-muted-foreground mt-1">
                Every exam with a stored marking guideline. Open one to review the criteria the
                grader scores diagram submissions against.
              </p>
            </div>
            <Badge variant="outline">{guidelines.length}</Badge>
          </div>

          <div className="mt-4">
            {listLoading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" />
                Loading guidelines…
              </div>
            ) : listError ? (
              <div className="flex items-start gap-2 text-sm text-amber-700 dark:text-amber-400">
                <AlertCircle className="size-4 mt-0.5 shrink-0" />
                <span>{listError}</span>
              </div>
            ) : guidelines.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No guidelines yet. Upload a marking scheme below to create the first one.
              </p>
            ) : (
              <div className="grid gap-2 sm:grid-cols-2">
                {guidelines.map((item) => (
                  <button
                    key={item._id ?? item.examCode}
                    type="button"
                    onClick={() => openGuideline(item)}
                    className="rounded-lg border border-border p-3 text-left transition-colors hover:border-primary/40 hover:bg-muted/50"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <ClipboardList className="size-4 text-primary shrink-0" />
                        <span className="text-sm font-medium text-foreground truncate">
                          {item.examCode}
                        </span>
                      </div>
                      <Badge variant="outline" className="text-xs shrink-0">
                        {item.totalMarks ?? 0} marks
                      </Badge>
                    </div>
                    <div className="text-xs text-muted-foreground mt-1 truncate">
                      {(item.guideLines ?? []).length} criteria
                    </div>
                    <div className="text-xs text-muted-foreground mt-1.5 truncate">
                      {item.source_file?.filename || "—"}
                      {formatDate(item.updated_at) && ` · updated ${formatDate(item.updated_at)}`}
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
          {guideline ? `${guideline.examCode} — replace guideline` : "Diagram guideline"}
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Upload the marking scheme for an exam, and the AI turns it into the structured criteria
          used to grade ER diagram submissions. Each criterion keeps its own mark allocation.
        </p>

        <div className="mt-5 max-w-md">
          <label className="text-xs text-muted-foreground" htmlFor="exam-code">
            Exam code
          </label>
          <Input
            id="exam-code"
            className="mt-1"
            value={examCode}
            onChange={(e) => setExamCode(e.target.value)}
            placeholder="e.g. ERD-003"
          />
          <p className="text-xs text-muted-foreground mt-1">
            Uploading to an existing exam code replaces that guideline's criteria.
          </p>
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
            if (file) void handleUpload(file);
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
          aria-label="Upload marking guideline PDF"
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf,.pdf"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void handleUpload(file);
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
              ? "Extracting text and structuring criteria…"
              : "Drag & drop the marking guideline, or click to browse"}
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            PDF only · text is read directly, so scanned/image-only PDFs will not work
          </div>
        </div>
      </Card>

      {guideline && (
        <Card className="p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-foreground">Criteria</h2>
              <p className="text-sm text-muted-foreground mt-1">
                Extracted from the uploaded marking scheme. These are what the grader scores each
                submission against for exam code {guideline.examCode}.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="outline">{criteria.length} criteria</Badge>
              <Badge variant="outline">{guideline.totalMarks ?? 0} marks</Badge>
            </div>
          </div>

          <div className="mt-4 space-y-3">
            {criteria.map((item) => (
              <div key={item.id} className="rounded-lg border border-border p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-foreground">
                      {item.id}. {item.criterion}
                    </div>
                    {item.description && (
                      <p className="text-sm text-muted-foreground mt-1">{item.description}</p>
                    )}
                  </div>
                  <Badge variant="outline" className="shrink-0">
                    {item.marks} {item.marks === 1 ? "mark" : "marks"}
                  </Badge>
                </div>

                {describeExpected(item.expected).length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-3">
                    {describeExpected(item.expected).map((chip) => (
                      <span
                        key={chip}
                        className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground"
                      >
                        {chip}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          {guideline.source_file?.extracted_text && (
            <div className="mt-5">
              <div className="flex items-center gap-2 text-sm text-foreground">
                <FileText className="size-4 text-primary" />
                Text read from {guideline.source_file.filename || "the PDF"}
              </div>
              <pre className="mt-2 max-h-64 overflow-auto rounded-lg bg-muted/50 p-3 text-xs text-muted-foreground whitespace-pre-wrap">
                {guideline.source_file.extracted_text}
              </pre>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
