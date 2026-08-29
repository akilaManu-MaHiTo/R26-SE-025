import { type DragEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  ImageIcon,
  Loader2,
  ScanLine,
  Trash2,
  Upload,
} from "lucide-react";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";
import { Progress } from "./ui/progress";
import { Separator } from "./ui/separator";
import {
  MONTH_OPTIONS,
  SEMESTER_OPTIONS,
  SESSION_OPTIONS,
  getLatestFiveYears,
} from "../utils/dateOptions";
import { fetchCourses, formatCourseLabel, SAMPLE_COURSES, type CourseItem } from "../utils/courseOptions.ts";
import {
  buildDiagramEvaluationSavePayload,
  saveDiagramEvaluation,
} from "../api/diagramEvaluationApi.ts";

const API_BASE_URL =
  (import.meta as { env?: Record<string, string> }).env?.VITE_API_BASE_URL ??
  "http://127.0.0.1:8000";

type DiagramDetection = {
  id: string | number;
  label: string;
  bbox: [number, number, number, number];
  confidence?: number;
  text?: string;
};

type DiagramApiResponse = {
  status?: string;
  annotated_image?: string;
  detections?: DiagramDetection[];
  structure?: {
    entities?: Record<string, { attributes?: string[] }>;
    relationships?: Array<{
      name: string;
      entities?: string[];
      attributes?: string[];
    }>;
  };
  ocr_error?: string;
  guideline_object_id?: string;
  agent_marks?: number;
  agent_grading?: {
    agent_marks: number;
    max_marks: number;
    feedback?: string;
  };
  agent_grading_error?: string;
};

type DiagramProgressState = {
  stage: string;
  message: string;
  progress: number;
  current?: number;
  total?: number;
  label?: string;
};

type DiagramGuideline = {
  _id?: string;
  examCode: string;
  guideLines?: Array<{
    id: number;
    criterion: string;
    description: string;
    marks: number;
  }>;
  totalMarks?: number;
};

const FALLBACK_GUIDELINES: DiagramGuideline[] = [{
  _id: "6a89887f8c33278a18482b47",
  examCode: "ERD-001",
  totalMarks: 20,
}];

function parseApiError(data: unknown, fallback: string): string {
  if (data == null || typeof data !== "object") return fallback;
  const detail = (data as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const parts = detail.map((item) => {
      if (item && typeof item === "object" && "msg" in item)
        return String((item as { msg: string }).msg);
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

function formatConfidence(value?: number): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "--";
  return `${Math.round(value * 100)}%`;
}

function parseSseBlock(block: string): { event: string; data: string } | null {
  let event = "message";
  const dataLines: string[] = [];

  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
      continue;
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }

  if (!dataLines.length) return null;
  return { event, data: dataLines.join("\n") };
}

function clampProgress(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}

type DetectionStyle = {
  borderClass: string;
  backgroundClass: string;
  badgeClass: string;
  dotClass: string;
};

function getDetectionStyle(label?: string): DetectionStyle {
  const normalized = label?.toLowerCase() ?? "";

  if (normalized.includes("attribute")) {
    return {
      borderClass: "border-blue-400",
      backgroundClass: "bg-blue-500/10",
      badgeClass: "bg-blue-600 text-white",
      dotClass: "bg-blue-500",
    };
  }

  if (normalized.includes("relationship")) {
    return {
      borderClass: "border-red-400",
      backgroundClass: "bg-red-500/10",
      badgeClass: "bg-red-600 text-white",
      dotClass: "bg-red-500",
    };
  }

  if (normalized.includes("entity")) {
    return {
      borderClass: "border-green-500",
      backgroundClass: "bg-green-500/10",
      badgeClass: "bg-green-600 text-white",
      dotClass: "bg-green-500",
    };
  }

  return {
    borderClass: "border-slate-400",
    backgroundClass: "bg-slate-500/10",
    badgeClass: "bg-slate-600 text-white",
    dotClass: "bg-slate-500",
  };
}

function getDetectionDisplayLabel(detection: DiagramDetection): string {
  const label = detection.label?.trim();
  const text = detection.text?.trim();

  if (label && text) return `${label} - ${text}`;
  if (label) return label;
  if (text) return text;
  return "Unknown label";
}

export function DiagramGrading({ mode }: { mode?: "diagram" | "handwritten" }) {
  void mode;

  const fileInputRef = useRef<HTMLInputElement>(null);
  const previewUrlRef = useRef<string | null>(null);
  const yearOptions = useMemo(() => getLatestFiveYears(), []);

  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [imageSize, setImageSize] = useState<{
    width: number;
    height: number;
  } | null>(null);
  const [courses, setCourses] = useState<CourseItem[]>([]);
  const [coursesLoading, setCoursesLoading] = useState(false);
  const [selectedCourse, setSelectedCourse] = useState("");
  const [guidelines, setGuidelines] = useState<DiagramGuideline[]>([]);
  const [guidelinesLoading, setGuidelinesLoading] = useState(false);
  const [selectedGuidelineCode, setSelectedGuidelineCode] = useState("");
  const [studentId, setStudentId] = useState("");
  const [selectedYear, setSelectedYear] = useState<string>(() =>
    String(new Date().getFullYear()),
  );
  const [selectedMonth, setSelectedMonth] = useState<string>(() =>
    String(new Date().getMonth() + 1),
  );
  const [selectedSemester, setSelectedSemester] = useState<string>(
    SEMESTER_OPTIONS[0]?.value ?? "first",
  );
  const [selectedSession, setSelectedSession] = useState<string>(
    SESSION_OPTIONS[0]?.value ?? "final",
  );
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DiagramApiResponse | null>(null);
  const [progressState, setProgressState] =
    useState<DiagramProgressState | null>(null);
  const [saveState, setSaveState] = useState<string | null>(null);
  const [extractionCompleted, setExtractionCompleted] = useState(false);
  const [activeDetailTab, setActiveDetailTab] = useState<
    "labels" | "structure"
  >("labels");

  useEffect(() => {
    return () => {
      if (previewUrlRef.current?.startsWith("blob:")) {
        URL.revokeObjectURL(previewUrlRef.current);
      }
    };
  }, []);

  useEffect(() => {
    let isActive = true;

    const loadGuidelines = async () => {
      setGuidelinesLoading(true);
      try {
        const response = await fetch(`${API_BASE_URL}/api/diagram-evaluate-guidelines`);
        const data = (await readJsonResponse(response)) as unknown;
        if (!response.ok || !Array.isArray(data)) throw new Error("Failed to load guidelines.");

        const loadedGuidelines = data.filter(
          (guideline): guideline is DiagramGuideline =>
            Boolean(
              guideline &&
                typeof guideline === "object" &&
                typeof (guideline as DiagramGuideline).examCode === "string" &&
                (guideline as DiagramGuideline).examCode.trim(),
            ),
        );
        if (!isActive) return;
        setGuidelines(loadedGuidelines);
        setSelectedGuidelineCode((previous) =>
          previous && loadedGuidelines.some((guideline) => guideline.examCode === previous)
            ? previous
            : loadedGuidelines[0]?.examCode ?? FALLBACK_GUIDELINES[0].examCode,
        );
      } catch {
        if (!isActive) return;
        setGuidelines([]);
        setSelectedGuidelineCode(FALLBACK_GUIDELINES[0].examCode);
      } finally {
        if (isActive) setGuidelinesLoading(false);
      }
    };

    void loadGuidelines();

    return () => {
      isActive = false;
    };
  }, []);

  useEffect(() => {
    let isActive = true;

    const loadCourses = async () => {
      setCoursesLoading(true);
      try {
        const list = await fetchCourses();
        if (!isActive) return;
        setCourses(list);
        setSelectedCourse((prev) => {
          if (prev && list.some((course: CourseItem) => course.code === prev)) return prev;
          return list[0]?.code ?? "";
        });
      } catch {
        if (!isActive) return;
        setCourses([]);
      } finally {
        if (isActive) {
          setCoursesLoading(false);
        }
      }
    };

    void loadCourses();

    return () => {
      isActive = false;
    };
  }, []);

  const detections = result?.detections ?? [];
  const entityEntries = Object.entries(result?.structure?.entities ?? {});
  const relationshipEntries = result?.structure?.relationships ?? [];
  const selectedCourseItem = useMemo(
    () =>
      (courses.length > 0 ? courses : SAMPLE_COURSES).find(
        (course: CourseItem) => course.code === selectedCourse,
      ) ?? null,
    [courses, selectedCourse],
  );
  const courseList = courses.length > 0 ? courses : SAMPLE_COURSES;
  const guidelineList = guidelines.length > 0 ? guidelines : FALLBACK_GUIDELINES;
  const selectedGuideline = guidelineList.find(
    (guideline) => guideline.examCode === selectedGuidelineCode,
  ) ?? null;

  const summary = useMemo(
    () => ({
      labelCount: detections.length,
      entityCount: entityEntries.length,
      relationshipCount: relationshipEntries.length,
    }),
    [detections.length, entityEntries.length, relationshipEntries.length],
  );

  const setSelectedFile = (nextFile: File) => {
    if (previewUrlRef.current?.startsWith("blob:")) {
      URL.revokeObjectURL(previewUrlRef.current);
    }
    const nextUrl = URL.createObjectURL(nextFile);
    previewUrlRef.current = nextUrl;
    setFile(nextFile);
    setPreviewUrl(nextUrl);
    setImageSize(null);
    setError(null);
    setResult(null);
    setExtractionCompleted(false);
    setProgressState(null);
    setSaveState(null);
  };

  const handleFileChange = (nextFile?: File) => {
    if (!nextFile) return;
    if (!nextFile.type.startsWith("image/")) {
      setError("Please upload an image file.");
      return;
    }
    setSelectedFile(nextFile);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    handleFileChange(event.dataTransfer.files?.[0]);
  };

  const persistEvaluation = async (nextResult: DiagramApiResponse) => {
    const activeCourse =
      courseList.find((course) => course.code === selectedCourse) ??
      courseList[0] ??
      null;

    const payload = buildDiagramEvaluationSavePayload({
      result: nextResult,
      course: activeCourse,
      studentId,
      subjectCode: activeCourse?.code ?? selectedCourse,
      subjectName: activeCourse?.name ?? "",
      year: selectedYear,
      month: selectedMonth,
      semester: selectedSemester,
      sessionName:
        selectedSession === "mid-term" ? "Mid Term" : "Final Examination",
      diagramMarks: nextResult.detections?.length ?? 0,
      remarks: nextResult.ocr_error ?? "",
      guidelineObjectId: nextResult.guideline_object_id ?? selectedGuideline?._id,
      agentMarks: nextResult.agent_marks,
    });

    setSaving(true);
    setSaveState(null);

    try {
      await saveDiagramEvaluation(payload);
      setSaveState("Saved to MongoDB");
    } catch (saveError) {
      setSaveState(
        saveError instanceof Error ? saveError.message : "Save failed.",
      );
    } finally {
      setSaving(false);
    }
  };

  const analyzeDiagram = async () => {
    if (!file) {
      setError("Upload a diagram image first.");
      return;
    }

    setLoading(true);
    setError(null);
    setSaveState(null);
    setExtractionCompleted(false);
    setProgressState({
      stage: "starting",
      message: "Preparing diagram evaluation...",
      progress: 0,
    });
    setResult(null);

    const applyProgress = (payload: Record<string, unknown>) => {
      const message =
        typeof payload.message === "string" ? payload.message : "Processing...";
      const stage =
        typeof payload.stage === "string" ? payload.stage : "working";
      const progressValue =
        typeof payload.progress === "number" ? payload.progress : 0;

      if (stage.includes("extraction_completed")) {
        setExtractionCompleted(true);
      }

      setProgressState({
        stage,
        message,
        progress: clampProgress(progressValue),
        current:
          typeof payload.current === "number" ? payload.current : undefined,
        total: typeof payload.total === "number" ? payload.total : undefined,
        label: typeof payload.label === "string" ? payload.label : undefined,
      });
    };

    try {
      const formData = new FormData();
      formData.append("image", file, file.name);
      if (!selectedGuideline?._id) {
        throw new Error("Select a valid guideline before evaluating.");
      }
      formData.append("guideline_object_id", selectedGuideline._id);

      const response = await fetch(
        `${API_BASE_URL}/api/diagram-evaluate?stream=1`,
        {
          method: "POST",
          body: formData,
        },
      );

      if (!response.ok) {
        const data = (await readJsonResponse(response)) as DiagramApiResponse;
        throw new Error(parseApiError(data, "Diagram evaluation failed."));
      }

      const contentType = response.headers.get("content-type") ?? "";
      if (contentType.includes("text/event-stream") && response.body) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let finalResult: DiagramApiResponse | null = null;

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          let separatorIndex = buffer.indexOf("\n\n");
          while (separatorIndex !== -1) {
            const block = buffer.slice(0, separatorIndex).trim();
            buffer = buffer.slice(separatorIndex + 2);
            separatorIndex = buffer.indexOf("\n\n");

            if (!block) continue;

            const parsed = parseSseBlock(block);
            if (!parsed) continue;

            let payload: Record<string, unknown> = {};
            try {
              payload = JSON.parse(parsed.data) as Record<string, unknown>;
            } catch {
              payload = { detail: parsed.data };
            }

            if (parsed.event === "progress") {
              applyProgress(payload);
              continue;
            }

            if (parsed.event === "result") {
              finalResult = payload as DiagramApiResponse;
              setResult(finalResult);
              applyProgress({
                stage: "extraction_completed",
                message: "Extraction complete. Grading with AI...",
                progress: 85,
              });
              continue;
            }

            if (parsed.event === "grading_result") {
              const gradingPayload = payload as Record<string, unknown>;
              finalResult = {
                ...(finalResult ?? {}),
                agent_marks: gradingPayload.agent_marks as number | undefined,
                agent_grading: gradingPayload.agent_grading as DiagramApiResponse["agent_grading"] | undefined,
              };
              setResult(finalResult);
              applyProgress({
                stage: "grading_completed",
                message: "Grading complete.",
                progress: 100,
              });
              continue;
            }

            if (parsed.event === "grading_error") {
              if (finalResult) {
                finalResult.agent_grading_error = typeof payload.detail === "string" ? payload.detail : "Grading failed.";
              }
              continue;
            }

            if (parsed.event === "error") {
              throw new Error(
                typeof payload.detail === "string"
                  ? payload.detail
                  : "Diagram evaluation failed.",
              );
            }
          }
        }

        if (finalResult) {
          setResult(finalResult);
        } else {
          const fallbackResult = (await readJsonResponse(
            response,
          )) as DiagramApiResponse;
          setResult(fallbackResult);
        }
      } else {
        const data = (await readJsonResponse(response)) as DiagramApiResponse;
        setResult(data);
      }
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Diagram evaluation failed.",
      );
    } finally {
      setLoading(false);
      setProgressState((current) => current ?? null);
    }
  };

  const clearSelection = () => {
    if (previewUrlRef.current?.startsWith("blob:")) {
      URL.revokeObjectURL(previewUrlRef.current);
    }
    previewUrlRef.current = null;
    setFile(null);
    setPreviewUrl(null);
    setImageSize(null);
    setError(null);
    setResult(null);
    setExtractionCompleted(false);
    setSaveState(null);
  };

  return (
    <div className="p-6 md:p-8 space-y-6">
      {/* Parent component: page header and short guidance text. */}
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <ScanLine className="size-4" /> Diagram Evaluation
        </div>
        <h2 className="tracking-tight text-foreground">
          Upload a diagram and inspect its detected labels
        </h2>
        <p className="text-sm text-muted-foreground max-w-2xl">
          Upload an image, run the evaluation, and review the detected labels
          with consistent color-coded boxes.
        </p>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.85fr)]">
        {/* Parent component: upload, preview, and evaluation controls. */}
        <Card className="overflow-hidden border-border">
          <div
            className={`border-b border-border p-4 transition-colors ${dragging ? "bg-accent/60" : "bg-muted/40"}`}
            onDragEnter={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
          >
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="space-y-1">
                <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <ImageIcon className="size-4 text-primary" /> Input image
                </div>
                <p className="text-xs text-muted-foreground">
                  Drop a diagram image here or use the file picker.
                </p>
              </div>
              <div className="flex items-center gap-2">
                {file && (
                  <Button variant="outline" onClick={clearSelection}>
                    <Trash2 className="size-4 mr-2" /> Clear
                  </Button>
                )}
                <Button
                  variant="outline"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <Upload className="size-4 mr-2" /> Choose file
                </Button>
                <Button
                  className="bg-primary hover:bg-primary/90"
                  onClick={analyzeDiagram}
                  disabled={loading || !file}
                >
                  {loading ? (
                    <>
                      <Loader2 className="size-4 mr-2 animate-spin" />{" "}
                      Evaluating...
                    </>
                  ) : (
                    <>Evaluate diagram</>
                  )}
                </Button>
              </div>
            </div>

            <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-6">
              <div className="space-y-1.5">
                <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Student ID
                </label>
                <input
                  value={studentId}
                  onChange={(event) => setStudentId(event.target.value)}
                  placeholder="Enter student ID"
                  className="w-full rounded-md border border-input bg-card px-3 py-2 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-primary"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Subject Code
                </label>
                <Select
                  value={selectedCourse}
                  onValueChange={setSelectedCourse}
                  disabled={coursesLoading && courseList.length === 0}
                >
                  <SelectTrigger className="w-full bg-card">
                    <SelectValue
                      placeholder={
                        coursesLoading
                          ? "Loading courses..."
                          : courseList.length
                            ? "Select subject code"
                            : "No courses available"
                      }
                    />
                  </SelectTrigger>
                  <SelectContent>
                    {courseList.map((course) => (
                      <SelectItem key={course._id} value={course.code}>
                        {formatCourseLabel(course)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Year
                </label>
                <Select value={selectedYear} onValueChange={setSelectedYear}>
                  <SelectTrigger className="w-full bg-card">
                    <SelectValue placeholder="Select year" />
                  </SelectTrigger>
                  <SelectContent>
                    {yearOptions.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Month
                </label>
                <Select value={selectedMonth} onValueChange={setSelectedMonth}>
                  <SelectTrigger className="w-full bg-card">
                    <SelectValue placeholder="Select month" />
                  </SelectTrigger>
                  <SelectContent>
                    {MONTH_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Semester
                </label>
                <Select
                  value={selectedSemester}
                  onValueChange={setSelectedSemester}
                >
                  <SelectTrigger className="w-full bg-card">
                    <SelectValue placeholder="Select semester" />
                  </SelectTrigger>
                  <SelectContent>
                    {SEMESTER_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Session
                </label>
                <Select
                  value={selectedSession}
                  onValueChange={setSelectedSession}
                >
                  <SelectTrigger className="w-full bg-card">
                    <SelectValue placeholder="Select session" />
                  </SelectTrigger>
                  <SelectContent>
                    {SESSION_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Guideline code
                </label>
                <Select
                  value={selectedGuidelineCode}
                  onValueChange={setSelectedGuidelineCode}
                  disabled={guidelinesLoading && guidelineList.length === 0}
                >
                  <SelectTrigger className="w-full bg-card">
                    <SelectValue
                      placeholder={
                        guidelinesLoading
                          ? "Loading guidelines..."
                          : "Select guideline code"
                      }
                    />
                  </SelectTrigger>
                  <SelectContent>
                    {guidelineList.map((guideline) => (
                      <SelectItem
                        key={guideline._id ?? guideline.examCode}
                        value={guideline.examCode}
                      >
                        {guideline.examCode}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {loading && progressState && (
              <div className="mt-4 border-t border-border bg-muted/30 px-4 py-3">
                <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
                  <span className="uppercase tracking-wide">
                    {progressState.stage.replace(/_/g, " ")}
                  </span>
                  <span>{progressState.progress}%</span>
                </div>
                <div className="mt-2 flex items-center gap-2 text-sm text-foreground">
                  <Loader2 className="size-4 animate-spin text-primary" />
                  <span>{progressState.message}</span>
                </div>
                <Progress value={progressState.progress} className="mt-3 h-2" />
                {typeof progressState.current === "number" &&
                  typeof progressState.total === "number" &&
                  progressState.total > 0 && (
                    <div className="mt-1 text-xs text-muted-foreground">
                      {progressState.current}/{progressState.total} Objects
                      Processed
                    </div>
                  )}
              </div>
            )}
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(event) => handleFileChange(event.target.files?.[0])}
          />

          <div className="p-4 md:p-6 space-y-4">
            {previewUrl ? (
              <div className="space-y-4">
                <div className="overflow-auto rounded-2xl border border-border bg-muted/30 p-3">
                  <div className="relative inline-block max-w-full">
                    <img
                      src={previewUrl}
                      alt="Uploaded diagram preview"
                      className="block max-w-full h-auto rounded-xl shadow-sm"
                      onLoad={(event) => {
                        const image = event.currentTarget;
                        setImageSize({
                          width: image.naturalWidth,
                          height: image.naturalHeight,
                        });
                      }}
                    />
                    {imageSize && detections.length > 0 && (
                      <div className="absolute inset-0">
                        {detections.map((detection) => {
                          const [x1, y1, x2, y2] = detection.bbox;
                          const left = (x1 / imageSize.width) * 100;
                          const top = (y1 / imageSize.height) * 100;
                          const width = ((x2 - x1) / imageSize.width) * 100;
                          const height = ((y2 - y1) / imageSize.height) * 100;
                          const style = getDetectionStyle(detection.label);

                          return (
                            <div
                              key={String(detection.id)}
                              className={`absolute rounded-md border-2 ${style.borderClass} ${style.backgroundClass}`}
                              style={{
                                left: `${left}%`,
                                top: `${top}%`,
                                width: `${width}%`,
                                height: `${height}%`,
                              }}
                            >
                              <div
                                className={`absolute -top-3 left-1 max-w-full rounded-full border border-white/70 px-2 py-0.5 text-[10px] font-medium shadow-sm ${style.badgeClass}`}
                              >
                                {getDetectionDisplayLabel(detection)}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>{file?.name ?? "Selected diagram"}</span>
                  <span>
                    {imageSize
                      ? `${imageSize.width} × ${imageSize.height}`
                      : "Loading image size..."}
                  </span>
                </div>
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-border bg-muted/20 px-6 py-16 text-center">
                <div className="mx-auto mb-4 flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                  <Upload className="size-6" />
                </div>
                <h3 className="text-base text-foreground">
                  Drop a diagram here
                </h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  Supported formats: JPG, PNG, WEBP and other browser-supported
                  image files.
                </p>
              </div>
            )}

            {error && (
              <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
                <AlertCircle className="mt-0.5 size-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {result?.ocr_error && (
              <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                <AlertCircle className="mt-0.5 size-4 shrink-0" />
                <span>{result.ocr_error}</span>
              </div>
            )}
          </div>
        </Card>

        {/* Parent component: results sidebar with summary, detections, and structure. */}
        <div className="flex h-full flex-col gap-6">
          {/* Parent component: detected labels and structure details. */}
          <Card className="flex-1 p-5 border-border">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="text-sm font-medium text-foreground">
                  Labels & structure
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Switch between detected labels and the extracted structure.
                </p>
              </div>
              <div className="flex rounded-full bg-muted p-1">
                <Button
                  type="button"
                  variant={activeDetailTab === "labels" ? "default" : "ghost"}
                  size="sm"
                  className="rounded-full px-3"
                  onClick={() => setActiveDetailTab("labels")}
                >
                  Labels
                </Button>
                <Button
                  type="button"
                  variant={
                    activeDetailTab === "structure" ? "default" : "ghost"
                  }
                  size="sm"
                  className="rounded-full px-3"
                  onClick={() => setActiveDetailTab("structure")}
                >
                  Structure
                </Button>
              </div>
            </div>
            <Separator className="my-4" />

            {activeDetailTab === "labels" ? (
              <>
                {detections.length > 0 ? (
                  <div className="space-y-2 max-h-[30rem] overflow-auto pr-1">
                    {detections.map((detection) => {
                      const style = getDetectionStyle(detection.label);

                      return (
                        <div
                          key={String(detection.id)}
                          className={`flex items-start gap-3 rounded-xl border border-border bg-card px-3 py-3 ${style.backgroundClass}`}
                        >
                          <div
                            className={`mt-0.5 size-3 rounded-full ${style.dotClass}`}
                          />
                          <div className="min-w-0 flex-1 space-y-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-medium text-foreground">
                                {getDetectionDisplayLabel(detection)}
                              </span>
                              <Badge
                                variant="outline"
                                className="text-[10px] uppercase tracking-wide"
                              >
                                {formatConfidence(detection.confidence)}
                              </Badge>
                            </div>
                            {detection.text && (
                              <p className="text-xs leading-relaxed text-muted-foreground">
                                {detection.text}
                              </p>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="rounded-xl border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
                    No labels yet. Run evaluation after selecting an image.
                  </div>
                )}
              </>
            ) : (
              <>
                {entityEntries.length === 0 &&
                relationshipEntries.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    The backend structure summary will appear here after
                    evaluation.
                  </p>
                ) : (
                  <div className="space-y-4 text-sm">
                    <div>
                      <div className="mb-2 flex items-center gap-2 text-xs uppercase tracking-wide text-muted-foreground">
                        <span>Entities</span>
                        <span className="rounded-full bg-green-500/10 px-2 py-0.5 text-[10px] font-medium text-green-700">
                          Entity
                        </span>
                      </div>
                      <div className="space-y-2">
                        {entityEntries.map(([name, entry]) => (
                          <div
                            key={name}
                            className="rounded-xl bg-muted/40 px-3 py-2"
                          >
                            <div className="font-medium text-foreground">
                              {name}
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {(() => {
                                const attributes = entry.attributes ?? [];
                                return attributes.length > 0
                                  ? attributes.join(", ")
                                  : "No attributes returned";
                              })()}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div>
                      <div className="mb-2 flex items-center gap-2 text-xs uppercase tracking-wide text-muted-foreground">
                        <span>Relationships</span>
                        <span className="rounded-full bg-red-500/10 px-2 py-0.5 text-[10px] font-medium text-red-700">
                          Relationship
                        </span>
                      </div>
                      <div className="space-y-2">
                        {relationshipEntries.map((entry) => (
                          <div
                            key={entry.name}
                            className="rounded-xl bg-muted/40 px-3 py-2"
                          >
                            <div className="font-medium text-foreground">
                              {entry.name}
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {(() => {
                                const entities = entry.entities ?? [];
                                const attributes = entry.attributes ?? [];
                                return `${entities.length > 0 ? entities.join(", ") : "No entities returned"}${
                                  attributes.length > 0
                                    ? ` • ${attributes.join(", ")}`
                                    : ""
                                }`;
                              })()}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </Card>
        </div>
      </div>
      <div>
        {/* Parent component: evaluation summary card. */}
        <Card className="p-5 border-border">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-sm font-medium text-foreground">
                Evaluation summary
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Badge className="bg-accent text-muted-foreground border-0">
                {summary.labelCount} labels
              </Badge>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  if (!result) return;
                  void persistEvaluation(result);
                }}
                disabled={!result || loading || saving}
              >
                {saving ? (
                  <>
                    <Loader2 className="size-4 mr-2 animate-spin" />
                    Saving to MongoDB...
                  </>
                ) : (
                  <>
                    <Upload className="size-4 mr-2" />
                    Save to MongoDB
                  </>
                )}
              </Button>
            </div>
          </div>

          {saveState && (
            <div className="mt-3 rounded-xl border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
              {saveState}
            </div>
          )}

          <div className="mt-3 grid gap-2 text-xs text-muted-foreground sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl bg-muted/40 px-3 py-2">
              <div className="uppercase tracking-wide">Subject Code</div>
              <div className="mt-1 text-foreground">
                {selectedCourseItem
                  ? formatCourseLabel(selectedCourseItem)
                  : selectedCourse || "No course selected"}
              </div>
            </div>
            <div className="rounded-xl bg-muted/40 px-3 py-2">
              <div className="uppercase tracking-wide">Year</div>
              <div className="mt-1 text-foreground">{selectedYear}</div>
            </div>
            <div className="rounded-xl bg-muted/40 px-3 py-2">
              <div className="uppercase tracking-wide">Month</div>
              <div className="mt-1 text-foreground">
                {MONTH_OPTIONS.find((option) => option.value === selectedMonth)
                  ?.label ?? selectedMonth}
              </div>
            </div>
            <div className="rounded-xl bg-muted/40 px-3 py-2">
              <div className="uppercase tracking-wide">Semester</div>
              <div className="mt-1 text-foreground">
                {SEMESTER_OPTIONS.find(
                  (option) => option.value === selectedSemester,
                )?.label ?? selectedSemester}
              </div>
            </div>
            <div className="rounded-xl bg-muted/40 px-3 py-2">
              <div className="uppercase tracking-wide">Session</div>
              <div className="mt-1 text-foreground">
                {SESSION_OPTIONS.find((option) => option.value === selectedSession)
                  ?.label ?? selectedSession}
              </div>
            </div>

            <div className="mt-2 grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
              <div className="rounded-xl bg-muted/40 px-3 py-2">
                <div className="uppercase tracking-wide">Guideline code</div>
                <div className="mt-1 text-foreground">
                  {selectedGuidelineCode || "No guideline selected"}
                </div>
              </div>
              <div className="rounded-xl bg-muted/40 px-3 py-2">
                <div className="uppercase tracking-wide">Agent marks</div>
                <div className="mt-1 text-foreground">
                  {typeof result?.agent_marks === "number"
                    ? `${result.agent_marks}/${result.agent_grading?.max_marks ?? selectedGuideline?.totalMarks ?? "--"}`
                    : "Pending evaluation"}
                </div>
              </div>
            </div>
          </div>

          <Separator className="my-4" />

          

          {result ? (
            <div className="space-y-4 text-sm">
              

              {/* Extracted Objects Section */}
              

              <div className="flex items-center gap-2 text-emerald-700">
                <CheckCircle2 className="size-4" />
                Evaluation completed successfully.
              </div>
              <div className="rounded-xl bg-muted/40 p-3">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">
                  Status
                </div>
                <div className="mt-1 text-foreground">
                  {result.status ?? "ok"}
                </div>
              </div>
              <div className="rounded-xl bg-muted/40 p-3">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">
                  Detections
                </div>
                <div className="mt-1 text-foreground">
                  {summary.labelCount} objects detected
                </div>
              </div>
              <div className="rounded-xl bg-muted/40 p-3">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">
                  Output image
                </div>
                <div className="mt-1 text-foreground">
                  {result.annotated_image
                    ? "Server annotated image available"
                    : "Using local label overlays"}
                </div>
              </div>
              {result.agent_grading?.feedback && (
                <div className="rounded-xl bg-muted/40 p-3">
                  <div className="text-xs uppercase tracking-wide text-muted-foreground">
                    Agent feedback
                  </div>
                  <div className="mt-1 text-foreground">
                    {result.agent_grading.feedback}
                  </div>
                </div>
              )}
              {result.agent_grading_error && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-amber-900">
                  Agent marking unavailable: {result.agent_grading_error}
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              Upload a diagram and run evaluation to see the labels and bounding
              boxes here.
            </p>
          )}
        </Card>
      </div>
    </div>
  );
}
