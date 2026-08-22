import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  BookOpen,
  FileText,
  Plus,
  Presentation,
  RefreshCw,
  Trash2,
  Upload,
} from "lucide-react";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "./ui/alert-dialog";

const DEFAULT_API_BASE_URL =
  (import.meta as { env?: Record<string, string> }).env?.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export type CourseItem = {
  _id: string;
  code: string;
  name?: string;
  description?: string;
};

export type LectureMaterialItem = {
  course_name: string;
  filename: string;
  type: string;
  indexed_items: number;
};

type LectureMaterialsPanelProps = {
  apiBaseUrl?: string;
};

function parseApiError(data: unknown, fallback: string): string {
  if (data == null || typeof data !== "object") return fallback;
  const detail = (data as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const parts = detail.map((item) => {
      if (item && typeof item === "object" && "msg" in item) return String((item as { msg: string }).msg);
      return String(item);
    });
    return parts.length ? parts.join("; ") : fallback;
  }
  return fallback;
}

async function readJsonResponse(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text.trim()) return {};
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text.slice(0, 200) };
  }
}

export async function fetchCourses(apiBaseUrl: string): Promise<CourseItem[]> {
  const response = await fetch(`${apiBaseUrl}/courses`);
  const data = (await readJsonResponse(response)) as { items?: CourseItem[] };
  if (!response.ok) {
    throw new Error(parseApiError(data, "Failed to load courses."));
  }
  return data.items ?? [];
}

export function formatCourseLabel(course: CourseItem): string {
  const name = (course.name || "").trim();
  if (!name || name === course.code) return course.code;
  return `${course.code} - ${name}`;
}

export function LectureMaterialsPanel({
  apiBaseUrl = DEFAULT_API_BASE_URL,
}: LectureMaterialsPanelProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [courses, setCourses] = useState<CourseItem[]>([]);
  const [coursesLoading, setCoursesLoading] = useState(false);
  const [selectedCourse, setSelectedCourse] = useState("");
  const [newCode, setNewCode] = useState("");
  const [newName, setNewName] = useState("");
  const [addingCourse, setAddingCourse] = useState(false);
  const [showAllCourses, setShowAllCourses] = useState(true);
  const [items, setItems] = useState<LectureMaterialItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [deletingKey, setDeletingKey] = useState<string | null>(null);
  const [deletingCourseCode, setDeletingCourseCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<LectureMaterialItem | null>(null);
  const [pendingCourseDelete, setPendingCourseDelete] = useState<CourseItem | null>(null);
  const [pendingUploadFile, setPendingUploadFile] = useState<File | null>(null);

  const loadCourses = useCallback(async () => {
    setCoursesLoading(true);
    try {
      const list = await fetchCourses(apiBaseUrl);
      setCourses(list);
      setSelectedCourse((prev) => {
        if (prev && list.some((c) => c.code === prev)) return prev;
        return list[0]?.code ?? "";
      });
    } catch (err) {
      setCourses([]);
      setError(err instanceof Error ? err.message : "Failed to load courses.");
    } finally {
      setCoursesLoading(false);
    }
  }, [apiBaseUrl]);

  const loadMaterials = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (!showAllCourses && selectedCourse.trim()) {
        params.set("course_name", selectedCourse.trim());
      }
      const query = params.toString();
      const response = await fetch(
        `${apiBaseUrl}/lecture-notes${query ? `?${query}` : ""}`
      );
      const data = (await readJsonResponse(response)) as {
        items?: LectureMaterialItem[];
      };
      if (!response.ok) {
        throw new Error(parseApiError(data, "Failed to load lecture materials."));
      }
      setItems(data.items ?? []);
    } catch (err) {
      setItems([]);
      setError(err instanceof Error ? err.message : "Failed to load lecture materials.");
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl, showAllCourses, selectedCourse]);

  useEffect(() => {
    void loadCourses();
  }, [loadCourses]);

  useEffect(() => {
    void loadMaterials();
  }, [loadMaterials]);

  const addCourse = async () => {
    const code = newCode.trim();
    if (!code) {
      setError("Enter a course code (e.g. SE3040).");
      return;
    }
    setAddingCourse(true);
    setError(null);
    setSuccess(null);
    try {
      const response = await fetch(`${apiBaseUrl}/courses`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code,
          name: newName.trim() || code,
        }),
      });
      const data = (await readJsonResponse(response)) as { item?: CourseItem };
      if (!response.ok) {
        throw new Error(parseApiError(data, "Failed to create course."));
      }
      setNewCode("");
      setNewName("");
      setSuccess(`Course ${data.item?.code ?? code} added.`);
      await loadCourses();
      if (data.item?.code) setSelectedCourse(data.item.code);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create course.");
    } finally {
      setAddingCourse(false);
    }
  };

  const confirmDeleteCourse = async () => {
    if (!pendingCourseDelete) return;
    setDeletingCourseCode(pendingCourseDelete.code);
    setError(null);
    setSuccess(null);
    try {
      const response = await fetch(
        `${apiBaseUrl}/courses/${encodeURIComponent(pendingCourseDelete.code)}?purge_materials=true`,
        { method: "DELETE" }
      );
      const data = await readJsonResponse(response);
      if (!response.ok) {
        throw new Error(parseApiError(data, "Failed to delete course."));
      }
      setSuccess(`Removed course ${pendingCourseDelete.code} and its indexed materials.`);
      setPendingCourseDelete(null);
      await loadCourses();
      await loadMaterials();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete course.");
    } finally {
      setDeletingCourseCode(null);
    }
  };

  const uploadFile = async (file: File) => {
    const trimmedCourse = selectedCourse.trim();
    if (!trimmedCourse) {
      setError("Add and select a course before uploading lecture materials.");
      return;
    }

    const lower = file.name.toLowerCase();
    if (!lower.endsWith(".pdf") && !lower.endsWith(".pptx")) {
      setError("Only PDF and PPTX files are supported.");
      return;
    }

    setUploading(true);
    setError(null);
    setSuccess(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("course_name", trimmedCourse);

      const response = await fetch(`${apiBaseUrl}/upload-lecture-notes`, {
        method: "POST",
        body: formData,
      });
      const data = (await readJsonResponse(response)) as {
        indexed_items?: number;
        indexed_pages?: number;
        filename?: string;
      };
      if (!response.ok) {
        throw new Error(parseApiError(data, "Failed to upload lecture material."));
      }

      const indexed = data.indexed_items ?? data.indexed_pages ?? 0;
      setSuccess(
        `Indexed ${indexed} page(s)/slide(s) from ${data.filename ?? file.name} under ${trimmedCourse}.`,
      );
      await loadMaterials();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload lecture material.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleFileInput = (fileList: FileList | null) => {
    const file = fileList?.[0];
    if (file) setPendingUploadFile(file);
  };

  const confirmUpload = async () => {
    const file = pendingUploadFile;
    setPendingUploadFile(null);
    if (file) await uploadFile(file);
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;

    const deleteKey = `${pendingDelete.course_name}::${pendingDelete.filename}`;
    setDeletingKey(deleteKey);
    setError(null);
    setSuccess(null);
    try {
      const params = new URLSearchParams({
        course_name: pendingDelete.course_name,
        filename: pendingDelete.filename,
      });
      const response = await fetch(`${apiBaseUrl}/lecture-notes?${params.toString()}`, {
        method: "DELETE",
      });
      const data = await readJsonResponse(response);
      if (!response.ok) {
        throw new Error(parseApiError(data, "Failed to delete lecture material."));
      }
      setSuccess(`Removed ${pendingDelete.filename} from the knowledge base.`);
      setPendingDelete(null);
      await loadMaterials();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete lecture material.");
    } finally {
      setDeletingKey(null);
    }
  };

  const typeIcon = (docType: string) => {
    if (docType.toUpperCase() === "PPTX") {
      return <Presentation className="size-4 text-orange-600 shrink-0" />;
    }
    return <FileText className="size-4 text-primary shrink-0" />;
  };

  return (
    <div className="space-y-6">
      {/* Manage courses */}
      <div className="space-y-3 rounded-xl border border-border bg-muted/40 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-sm text-foreground">Manage subjects / courses</div>
            <p className="text-xs text-muted-foreground mt-1">
              Add course codes once. Use the same codes when grading so RAG stays filtered correctly.
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => void loadCourses()}
            disabled={coursesLoading}
          >
            <RefreshCw className={`size-3.5 mr-1.5 ${coursesLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>

        <div className="grid sm:grid-cols-[1fr_1.2fr_auto] gap-2">
          <Input
            value={newCode}
            onChange={(e) => setNewCode(e.target.value)}
            placeholder="Code (e.g. SE3040)"
          />
          <Input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Name (optional)"
          />
          <Button
            type="button"
           
            onClick={() => void addCourse()}
            disabled={addingCourse}
          >
            {addingCourse ? (
              <RefreshCw className="size-4 animate-spin" />
            ) : (
              <>
                <Plus className="size-4 mr-1" /> Add
              </>
            )}
          </Button>
        </div>

        {coursesLoading ? (
          <div className="text-sm text-muted-foreground flex items-center gap-2 py-2">
            <RefreshCw className="size-4 animate-spin" /> Loading courses...
          </div>
        ) : courses.length === 0 ? (
          <div className="text-sm text-muted-foreground py-2">
            No courses yet. Add one above before uploading materials.
          </div>
        ) : (
          <div className="space-y-2">
            {courses.map((course) => (
              <div
                key={course._id}
                className="flex items-center gap-3 rounded-lg border border-border bg-card px-3 py-2"
              >
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-foreground font-medium">{formatCourseLabel(course)}</div>
                  {course.description ? (
                    <div className="text-xs text-muted-foreground truncate">{course.description}</div>
                  ) : null}
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="text-destructive hover:text-destructive hover:bg-destructive/10 shrink-0"
                  disabled={deletingCourseCode === course.code}
                  onClick={() => setPendingCourseDelete(course)}
                >
                  {deletingCourseCode === course.code ? (
                    <RefreshCw className="size-4 animate-spin" />
                  ) : (
                    <Trash2 className="size-4" />
                  )}
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Upload materials */}
      <div className="space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-sm text-foreground">
              <BookOpen className="size-4 text-primary" />
              <span>Lecture materials (RAG)</span>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Upload PDFs or PowerPoints under a managed course. Multiple files per course are supported.
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => void loadMaterials()}
            disabled={loading}
          >
            <RefreshCw className={`size-3.5 mr-1.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>

        <div>
          <label className="text-sm text-foreground mb-2 block">Course for upload / filter</label>
          <Select
            value={selectedCourse || undefined}
            onValueChange={setSelectedCourse}
            disabled={courses.length === 0}
          >
            <SelectTrigger className="w-full bg-card">
              <SelectValue placeholder={courses.length ? "Select a course" : "Add a course first"} />
            </SelectTrigger>
            <SelectContent>
              {courses.map((course) => (
                <SelectItem key={course._id} value={course.code}>
                  {formatCourseLabel(course)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground mt-1">
            Must match the subject used in grading sessions for RAG filtering.
          </p>
        </div>

        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            handleFileInput(e.dataTransfer.files);
          }}
          onClick={() => !uploading && courses.length > 0 && fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-5 transition-colors ${
            courses.length === 0
              ? "border-border bg-muted/40 cursor-not-allowed opacity-70"
              : uploading
                ? "border-border bg-muted/40 cursor-wait"
                : dragOver
                  ? "border-primary bg-accent/40 cursor-pointer"
                  : "border-border bg-muted/40 hover:bg-accent/30 hover:border-primary/40 cursor-pointer"
          }`}
        >
          <div className="flex items-center gap-3">
            <div className="size-10 rounded-full bg-card border border-border flex items-center justify-center shrink-0">
              {uploading ? (
                <RefreshCw className="size-5 text-primary animate-spin" />
              ) : (
                <Upload className="size-5 text-muted-foreground" />
              )}
            </div>
            <div>
              <div className="text-sm text-foreground">
                {uploading
                  ? "Indexing lecture material..."
                  : courses.length === 0
                    ? "Add a course before uploading"
                    : "Upload PDF or PPTX"}
              </div>
              <div className="text-xs text-muted-foreground mt-0.5">
                Drop a file here or click to browse
              </div>
            </div>
          </div>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.pptx,application/pdf,application/vnd.openxmlformats-officedocument.presentationml.presentation"
          className="hidden"
          onChange={(e) => handleFileInput(e.target.files)}
        />

        <div className="flex items-center justify-between gap-3">
          <div className="text-sm text-foreground">Indexed materials</div>
          <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
            <input
              type="checkbox"
              checked={showAllCourses}
              onChange={(e) => setShowAllCourses(e.target.checked)}
              className="rounded border-border"
            />
            Show all courses
          </label>
        </div>

        {loading ? (
          <div className="text-sm text-muted-foreground flex items-center gap-2 py-4">
            <RefreshCw className="size-4 animate-spin" />
            Loading lecture materials...
          </div>
        ) : items.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border bg-muted/40 px-4 py-5 text-sm text-muted-foreground">
            {showAllCourses
              ? "No lecture materials indexed yet. Upload a PDF or PPTX to enable RAG."
              : `No lecture materials for ${selectedCourse || "this course"} yet. Upload slides or notes above.`}
          </div>
        ) : (
          <div className="space-y-2">
            {items.map((item) => {
              const rowKey = `${item.course_name}::${item.filename}`;
              const isDeleting = deletingKey === rowKey;
              return (
                <div
                  key={rowKey}
                  className="flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-3"
                >
                  {typeIcon(item.type)}
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-foreground truncate">{item.filename}</div>
                    <div className="flex flex-wrap items-center gap-2 mt-1">
                      <Badge variant="outline" className="text-[10px]">
                        {item.type}
                      </Badge>
                      <span className="text-xs text-muted-foreground">{item.course_name}</span>
                      <span className="text-xs text-muted-foreground">
                        {item.indexed_items} page{item.indexed_items === 1 ? "" : "s"}/slide
                        {item.indexed_items === 1 ? "" : "s"}
                      </span>
                    </div>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="text-destructive hover:text-destructive hover:bg-destructive/10 shrink-0"
                    disabled={isDeleting}
                    onClick={() => setPendingDelete(item)}
                  >
                    {isDeleting ? (
                      <RefreshCw className="size-4 animate-spin" />
                    ) : (
                      <Trash2 className="size-4" />
                    )}
                  </Button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {error && (
        <div className="flex items-start gap-2 text-sm text-destructive">
          <AlertCircle className="size-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}
      {success && <div className="text-sm text-emerald-700 dark:text-emerald-400">{success}</div>}

      <AlertDialog
        open={pendingUploadFile != null}
        onOpenChange={(open) => {
          if (!open && !uploading) setPendingUploadFile(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Upload lecture material?</AlertDialogTitle>
            <AlertDialogDescription>
              Upload{" "}
              <span className="font-medium text-foreground">{pendingUploadFile?.name}</span> to course{" "}
              <span className="font-medium text-foreground">{selectedCourse || "—"}</span> and index it
              for RAG?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={uploading}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              
              disabled={uploading}
              onClick={(e) => {
                e.preventDefault();
                void confirmUpload();
              }}
            >
              {uploading ? "Uploading…" : "Upload"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={pendingDelete != null} onOpenChange={(open) => !open && setPendingDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove lecture material?</AlertDialogTitle>
            <AlertDialogDescription>
              This deletes all indexed pages/slides for{" "}
              <span className="font-medium text-foreground">{pendingDelete?.filename}</span> from{" "}
              <span className="font-medium text-foreground">{pendingDelete?.course_name}</span>. Grading will no
              longer retrieve this content via RAG.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700"
              onClick={(e) => {
                e.preventDefault();
                void confirmDelete();
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog
        open={pendingCourseDelete != null}
        onOpenChange={(open) => !open && setPendingCourseDelete(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete course?</AlertDialogTitle>
            <AlertDialogDescription>
              This removes{" "}
              <span className="font-medium text-foreground">
                {pendingCourseDelete ? formatCourseLabel(pendingCourseDelete) : ""}
              </span>{" "}
              and purges all indexed lecture materials tagged with that course code.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700"
              onClick={(e) => {
                e.preventDefault();
                void confirmDeleteCourse();
              }}
            >
              Delete course
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
