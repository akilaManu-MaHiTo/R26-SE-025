import { useState, useRef, useEffect, useCallback } from "react";
import {
  Upload, FileText, Sparkles, Save, Edit3, CheckCircle2,
  FileImage, Workflow, ZoomIn, ZoomOut, Camera, X, RotateCcw,
  ScanLine, ImageIcon, RefreshCw, AlertCircle, ChevronRight,
  Eye, Layers, Type, Cpu
} from "lucide-react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Progress } from "./ui/progress";
import { Separator } from "./ui/separator";
import { AIPageBanner, AILoadingOverlay, AIBadgePill, type AIModel } from "./AIBrand";

/* ─── Types ──────────────────────────────────────────────────────────────── */
type OcrLine = { text: string; conf: number; highlight?: boolean };
type DiagramNode = {
  id: string; label: string; type: "entity" | "relation" | "attribute";
  x: number; y: number; w: number; h: number; detected: boolean; issue?: string;
};
type DiagramDetection = {
  id: number;
  label: string;
  bbox: number[];
  confidence: number;
  text?: string;
  ocr_status?: string;
};
type ErStructure = {
  entities: Record<string, { attributes: string[] }>;
  relationships: Array<{ name: string; entities: string[]; attributes?: string[] }>;
  unmatched_connections?: Array<{ from: string; to: string; line: number[] }>;
};

/* ─── Mock extraction results ────────────────────────────────────────────── */
const MOCK_OCR_LINES: OcrLine[] = [
  { text: "An ER diagram for the university system will include the entity", conf: 0.97 },
  { text: "Student with attributes studentID, name, and email.", conf: 0.95 },
  { text: "Each student enrolls in many courses through the Enrollment", conf: 0.91 },
  { text: "entity which carries grade and semester as attributes.", conf: 0.88 },
  { text: "The relationship 'Enrolls' between Student and Course is M:N.", conf: 0.93 },
  { text: "In normalization, dependency name → email violates 2NF when", conf: 0.72, highlight: true },
  { text: "composite key (studentID, courseID) exists in relation schema.", conf: 0.68, highlight: true },
  { text: "Converting to 3NF requires decomposing the relation into two:", conf: 0.89 },
  { text: "R1(studentID, name, email) and R2(studentID, courseID, grade).", conf: 0.85 },
];

const MOCK_DIAGRAM_NODES: DiagramNode[] = [
  { id: "student", label: "Student", type: "entity", x: 20, y: 40, w: 100, h: 40, detected: true },
  { id: "course", label: "Course", type: "entity", x: 280, y: 40, w: 100, h: 40, detected: true },
  { id: "enrollment", label: "Enrollment", type: "entity", x: 155, y: 130, w: 90, h: 35, detected: true },
  { id: "enrolls", label: "Enrolls", type: "relation", x: 160, y: 40, w: 80, h: 40, detected: true, issue: "missing cardinality" },
  { id: "sid", label: "studentID", type: "attribute", x: 30, y: 130, w: 80, h: 28, detected: true },
  { id: "cid", label: "courseID", type: "attribute", x: 290, y: 130, w: 80, h: 28, detected: true },
  { id: "grade", label: "grade", type: "attribute", x: 160, y: 195, w: 60, h: 24, detected: false },
];

const LABEL_TYPE_MAP: Record<string, DiagramNode["type"]> = {
  "entities": "entity",
  "weak entity": "entity",
  "relationships": "relation",
  "attributes": "attribute",
  "primary key": "attribute",
};

const toNodeType = (label: string): DiagramNode["type"] => {
  const normalized = label.trim().toLowerCase().replace(/_/g, " ");
  return LABEL_TYPE_MAP[normalized] ?? "entity";
};

const mapDetectionsToNodes = (detections: DiagramDetection[]): DiagramNode[] =>
  detections.map((det) => {
    const [x1, y1, x2, y2] = det.bbox;
    const label = det.text?.trim() ? det.text.trim() : det.label;
    return {
      id: String(det.id),
      label,
      type: toNodeType(det.label),
      x: x1,
      y: y1,
      w: Math.max(0, x2 - x1),
      h: Math.max(0, y2 - y1),
      detected: true,
    };
  });

const dataUrlToFile = (dataUrl: string, filename: string): File => {
  const [header, base64] = dataUrl.split(",");
  const match = /data:(.*?);base64/.exec(header || "");
  const mime = match?.[1] ?? "image/jpeg";
  const binary = atob(base64 || "");
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return new File([bytes], filename, { type: mime });
};

/* ─── Camera Modal ────────────────────────────────────────────────────────── */
function CameraModal({
  onCapture,
  onClose,
}: {
  onCapture: (dataUrl: string) => void;
  onClose: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [captured, setCaptured] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const startCamera = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 720 } },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.onloadedmetadata = () => {
          videoRef.current?.play();
          setLoading(false);
        };
      }
    } catch {
      setError("Camera access denied or unavailable. Please allow camera permissions and try again.");
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    startCamera();
    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, [startCamera]);

  const capture = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext("2d");
    ctx?.drawImage(video, 0, 0);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.9);
    setCaptured(dataUrl);
    streamRef.current?.getTracks().forEach((t) => t.stop());
  };

  const retake = () => {
    setCaptured(null);
    startCamera();
  };

  const confirm = () => {
    if (captured) {
      onCapture(captured);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          <div className="flex items-center gap-2 text-slate-800">
            <Camera className="size-5 text-blue-600" />
            <span>Capture student paper</span>
          </div>
          <Button size="icon" variant="ghost" className="size-8" onClick={onClose}>
            <X className="size-4" />
          </Button>
        </div>

        {/* Viewfinder */}
        <div className="bg-black relative" style={{ aspectRatio: "16/9" }}>
          {!captured ? (
            <>
              <video
                ref={videoRef}
                className="w-full h-full object-cover"
                autoPlay
                playsInline
                muted
              />
              {/* guide overlay */}
              <div className="absolute inset-0 pointer-events-none">
                <div className="absolute inset-8 border-2 border-white/40 rounded-lg" />
                <div className="absolute top-8 left-8 w-8 h-8 border-t-2 border-l-2 border-blue-400 rounded-tl-lg" />
                <div className="absolute top-8 right-8 w-8 h-8 border-t-2 border-r-2 border-blue-400 rounded-tr-lg" />
                <div className="absolute bottom-8 left-8 w-8 h-8 border-b-2 border-l-2 border-blue-400 rounded-bl-lg" />
                <div className="absolute bottom-8 right-8 w-8 h-8 border-b-2 border-r-2 border-blue-400 rounded-br-lg" />
                <div className="absolute inset-x-0 top-1/2 h-px bg-blue-400/30" />
              </div>
              {loading && (
                <div className="absolute inset-0 flex flex-col items-center justify-center text-white gap-2">
                  <div className="size-10 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span className="text-sm text-white/70">Starting camera…</span>
                </div>
              )}
              {error && (
                <div className="absolute inset-0 flex flex-col items-center justify-center text-white gap-3 px-8 text-center">
                  <AlertCircle className="size-10 text-red-400" />
                  <p className="text-sm text-white/80">{error}</p>
                  <Button variant="outline" className="text-white border-white/30 bg-white/10 hover:bg-white/20" onClick={startCamera}>
                    <RefreshCw className="size-4 mr-2" /> Retry
                  </Button>
                </div>
              )}
            </>
          ) : (
            <img src={captured} alt="Captured" className="w-full h-full object-contain" />
          )}
          <canvas ref={canvasRef} className="hidden" />
        </div>

        {/* Controls */}
        <div className="flex items-center justify-between px-5 py-4 bg-slate-50">
          <div className="text-xs text-slate-500 flex items-center gap-1.5">
            <ScanLine className="size-3.5" />
            {captured ? "Preview — looks good? Confirm to proceed." : "Align the paper within the guide frame"}
          </div>
          <div className="flex gap-2">
            {captured ? (
              <>
                <Button variant="outline" onClick={retake}>
                  <RotateCcw className="size-4 mr-2" /> Retake
                </Button>
                <Button className="bg-blue-600 hover:bg-blue-700" onClick={confirm}>
                  <CheckCircle2 className="size-4 mr-2" /> Use this photo
                </Button>
              </>
            ) : (
              <Button
                className="bg-blue-600 hover:bg-blue-700"
                onClick={capture}
                disabled={loading || !!error}
              >
                <Camera className="size-4 mr-2" /> Capture
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── OCR Overlay (handwritten) ──────────────────────────────────────────── */
function OcrOverlay({ lines }: { lines: OcrLine[] }) {
  return (
    <div className="space-y-1.5">
      {lines.map((l, i) => (
        <div
          key={i}
          className={`flex items-start gap-2 px-2 py-1 rounded text-xs ${l.highlight ? "bg-amber-50 border border-amber-200" : "bg-white"}`}
        >
          <span
            className={`shrink-0 mt-0.5 text-[10px] px-1 rounded ${
              l.conf >= 0.9 ? "bg-emerald-100 text-emerald-700" :
              l.conf >= 0.75 ? "bg-amber-100 text-amber-700" :
              "bg-red-100 text-red-700"
            }`}
          >
            {Math.round(l.conf * 100)}%
          </span>
          <span className="text-slate-700 leading-tight">{l.text}</span>
          {l.highlight && <AlertCircle className="size-3 shrink-0 mt-0.5 text-amber-500" />}
        </div>
      ))}
    </div>
  );
}

/* ─── Diagram Node overlay ───────────────────────────────────────────────── */
function DiagramOverlay({ nodes }: { nodes: DiagramNode[] }) {
  const typeColor: Record<DiagramNode["type"], string> = {
    entity: "border-blue-500 bg-blue-50/80 text-blue-800",
    relation: "border-amber-500 bg-amber-50/80 text-amber-800",
    attribute: "border-emerald-500 bg-emerald-50/80 text-emerald-800",
  };
  return (
    <div className="space-y-1.5">
      {nodes.map((n) => (
        <div
          key={n.id}
          className={`flex items-center gap-2 px-2 py-1 rounded border text-xs ${typeColor[n.type]} ${!n.detected ? "opacity-50 line-through" : ""}`}
        >
          <span className="capitalize text-[10px] opacity-60 w-14 shrink-0">{n.type}</span>
          <span className="flex-1">{n.label}</span>
          {n.issue ? (
            <Badge className="bg-red-100 text-red-700 border-red-200 border text-[10px] px-1">
              ⚠ {n.issue}
            </Badge>
          ) : n.detected ? (
            <CheckCircle2 className="size-3 text-emerald-500 shrink-0" />
          ) : (
            <AlertCircle className="size-3 text-red-400 shrink-0" />
          )}
        </div>
      ))}
    </div>
  );
}

/* ─── Main GradingPage ───────────────────────────────────────────────────── */
export function GradingPage({ mode }: { mode: "diagram" | "handwritten" }) {
  const [processing, setProcessing] = useState(false);
  const [done, setDone] = useState(false);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [uploadedImage, setUploadedImage] = useState<string | null>(null);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [processedImage, setProcessedImage] = useState<string | null>(null);
  const [apiStructure, setApiStructure] = useState<ErStructure | null>(null);
  const [apiDetections, setApiDetections] = useState<DiagramDetection[]>([]);
  const [apiError, setApiError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(100);
  const [dragOver, setDragOver] = useState(false);
  const [activeTab, setActiveTab] = useState<"preview" | "extracted">("preview");
  const [extractProgress, setExtractProgress] = useState(0);
  const [extractStep, setExtractStep] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const aiModel: AIModel = mode === "diagram" ? "structr" : "lexo";
  const Icon = mode === "diagram" ? Workflow : FileText;
  const title = mode === "diagram" ? "Diagram Exam Grading" : "Handwritten Exam Grading";

  const breakdown = [
    { q: "Q1 — ER Entities & relationships", s: 8, m: 10, conf: 0.94 },
    { q: "Q2 — Cardinality constraints", s: 6, m: 10, conf: 0.81 },
    { q: "Q3 — Normalization to 3NF", s: 9, m: 10, conf: 0.97 },
    { q: "Q4 — Schema mapping", s: 5, m: 10, conf: 0.62 },
  ];
  const total = breakdown.reduce((a, b) => a + b.s, 0);
  const max = breakdown.reduce((a, b) => a + b.m, 0);
  const previewImage = done && processedImage ? processedImage : uploadedImage;
  const unmatchedCount = apiStructure?.unmatched_connections?.length ?? 0;
  const hasApiResults = done && (processedImage || apiStructure || apiDetections.length > 0);
  const diagramNodes = hasApiResults ? mapDetectionsToNodes(apiDetections) : MOCK_DIAGRAM_NODES;
  const diagramSummaryText = hasApiResults
    ? `${apiDetections.length} elements detected${unmatchedCount ? ` - ${unmatchedCount} unmatched links` : ""}`
    : `${MOCK_DIAGRAM_NODES.filter(n => n.detected).length}/${MOCK_DIAGRAM_NODES.length} elements detected - 1 issue flagged`;

  const handleImageLoad = (src: string, name?: string, file?: File | null) => {
    setUploadedImage(src);
    setUploadedFileName(name ?? "captured_photo.jpg");
    setUploadedFile(file ?? null);
    setProcessedImage(null);
    setApiStructure(null);
    setApiDetections([]);
    setApiError(null);
    setDone(false);
    setActiveTab("preview");
  };

  const handleFileChange = (file: File) => {
    if (!file) return;
    const url = URL.createObjectURL(file);
    handleImageLoad(url, file.name, file);
  };

  const onFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileChange(file);
  };

  const runMockExtract = () => {
    setProcessing(true);
    setDone(false);
    setExtractProgress(0);
    setExtractStep(0);
    const steps = [15, 35, 55, 72, 88, 100];
    steps.forEach((v, i) =>
      setTimeout(() => {
        setExtractProgress(v);
        setExtractStep(Math.floor((i / steps.length) * 5));
        if (i === steps.length - 1) {
          setTimeout(() => {
            setProcessing(false);
            setDone(true);
            setActiveTab("extracted");
          }, 400);
        }
      }, i * 320)
    );
  };

  const onExtract = async () => {
    if (!uploadedFile || mode !== "diagram") {
      runMockExtract();
      return;
    }

    setProcessing(true);
    setDone(false);
    setApiError(null);
    setExtractProgress(10);
    setExtractStep(0);

    let step = 0;
    const timerId = window.setInterval(() => {
      step = Math.min(step + 1, 4);
      setExtractStep(step);
      setExtractProgress((prev) => Math.min(prev + 8, 90));
    }, 350);

    try {
      const formData = new FormData();
      formData.append("image", uploadedFile);
      const backend = (import.meta as any).env?.VITE_BACKEND_URL ?? "http://localhost:8000";
      const response = await fetch(`${backend}/api/diagram-evaluate`, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || "Diagram evaluation failed.");
      }
      const payload = await response.json();
      if (payload.annotated_image) {
        setProcessedImage(payload.annotated_image);
      }
      if (payload.structure) {
        setApiStructure(payload.structure);
      }
      if (payload.detections) {
        setApiDetections(payload.detections);
      }
      setDone(true);
      setActiveTab("preview");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Diagram evaluation failed.";
      setApiError(message);
    } finally {
      window.clearInterval(timerId);
      setProcessing(false);
      setExtractProgress(100);
      setExtractStep(5);
    }
  };

  const clearImage = () => {
    setUploadedImage(null);
    setUploadedFileName(null);
    setUploadedFile(null);
    setProcessedImage(null);
    setApiStructure(null);
    setApiDetections([]);
    setApiError(null);
    setDone(false);
    setActiveTab("preview");
  };

  const displayFileName = uploadedFileName ?? (uploadedImage ? "student_paper.jpg" : "student_24_paper.pdf");

  return (
    <>
      {cameraOpen && (
        <CameraModal
          onCapture={(dataUrl) => {
            const file = dataUrlToFile(dataUrl, "captured_photo.jpg");
            handleImageLoad(dataUrl, file.name, file);
          }}
          onClose={() => setCameraOpen(false)}
        />
      )}

      <div className="p-8 space-y-6">
        {/* AI Page Banner */}
        <AIPageBanner model={aiModel} />

        {/* Header */}
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Icon className="size-4" /> {mode === "diagram" ? "Diagram Grader" : "Handwritten Grader"}
            </div>
            <h2 className="tracking-tight text-slate-900 mt-1">{title}</h2>
            <div className="text-sm text-slate-500 mt-1">
              Database Systems · Final Exam · {uploadedFileName ? uploadedFileName : "Paper 24/47"}
            </div>
          </div>
          <div className="flex gap-2 flex-wrap items-center">
            <AIBadgePill model={aiModel} />
            <Button variant="outline"><Save className="size-4 mr-2" />Save draft</Button>
            <Button variant="outline"><Edit3 className="size-4 mr-2" />Manual override</Button>
            <Button
              onClick={onExtract}
              disabled={processing}
              className="bg-blue-600 hover:bg-blue-700 disabled:opacity-60"
            >
              {processing ? (
                <><RefreshCw className="size-4 mr-2 animate-spin" /> Extracting…</>
              ) : (
                <><Sparkles className="size-4 mr-2" /> Extract & grade</>
              )}
            </Button>
          </div>
        </div>

        <div className="grid lg:grid-cols-5 gap-6">
          {/* ── Left: document viewer ─────────────────────────────────── */}
          <Card className="lg:col-span-3 border-slate-200 overflow-hidden flex flex-col">
            {/* toolbar */}
            <div className="px-4 py-2.5 border-b border-slate-100 flex items-center justify-between bg-slate-50 gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <FileImage className="size-4 shrink-0 text-slate-400" />
                <span className="text-sm text-slate-600 truncate">{displayFileName}</span>
                {uploadedImage && (
                  <Badge className="bg-blue-50 text-blue-700 border-0 text-[10px] shrink-0">
                    {uploadedFileName?.match(/\.(jpg|jpeg|png|webp)$/i) ? "IMAGE" : "PDF"}
                  </Badge>
                )}
              </div>
              <div className="flex items-center gap-1 shrink-0">
                {/* Tab: Preview / Extracted */}
                {done && (
                  <div className="flex bg-slate-100 rounded-lg p-0.5 mr-2">
                    <button
                      onClick={() => setActiveTab("preview")}
                      className={`text-xs px-2.5 py-1 rounded-md transition-colors ${activeTab === "preview" ? "bg-white text-slate-800 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
                    >
                      <Eye className="size-3 inline mr-1" />Preview
                    </button>
                    <button
                      onClick={() => setActiveTab("extracted")}
                      className={`text-xs px-2.5 py-1 rounded-md transition-colors ${activeTab === "extracted" ? "bg-white text-slate-800 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
                    >
                      {mode === "diagram" ? <Layers className="size-3 inline mr-1" /> : <Type className="size-3 inline mr-1" />}
                      {mode === "diagram" ? "Nodes" : "OCR text"}
                    </button>
                  </div>
                )}
                <Button size="icon" variant="ghost" className="size-8" onClick={() => setZoom(z => Math.max(50, z - 25))}>
                  <ZoomOut className="size-4" />
                </Button>
                <span className="text-xs text-slate-500 w-10 text-center">{zoom}%</span>
                <Button size="icon" variant="ghost" className="size-8" onClick={() => setZoom(z => Math.min(200, z + 25))}>
                  <ZoomIn className="size-4" />
                </Button>
                {uploadedImage && (
                  <Button size="icon" variant="ghost" className="size-8 text-red-400 hover:text-red-600" onClick={clearImage}>
                    <X className="size-4" />
                  </Button>
                )}
              </div>
            </div>

            {/* extraction progress bar */}
            {processing && (
              <div className="h-1 bg-slate-100">
                <div
                  className="h-full bg-blue-500 transition-all duration-300"
                  style={{ width: `${extractProgress}%` }}
                />
              </div>
            )}

            {/* document area */}
            <div
              className="flex-1 bg-slate-100 relative overflow-auto"
              style={{ minHeight: "420px" }}
            >
              <div
                className="min-h-full flex items-start justify-center p-6"
                style={{ transform: `scale(${zoom / 100})`, transformOrigin: "top center" }}
              >
                {/* Uploaded image */}
                {previewImage && activeTab === "preview" && (
                  <div className="relative bg-white rounded-lg shadow-md overflow-hidden max-w-full">
                    <img
                      src={previewImage}
                      alt="Uploaded student paper"
                      className="block max-w-full"
                      style={{ maxHeight: "560px", objectFit: "contain" }}
                    />
                    {done && (
                      <div className="absolute top-3 right-3">
                        <Badge className="bg-emerald-500 text-white border-0 shadow">
                          <Cpu className="size-3 mr-1" /> AI Analysed
                        </Badge>
                      </div>
                    )}
                  </div>
                )}

                {/* Extracted view for uploaded image */}
                {uploadedImage && activeTab === "extracted" && done && (
                  <div className="bg-white rounded-lg shadow-md w-full p-5 space-y-3">
                    <div className="flex items-center gap-2 text-slate-700 pb-2 border-b border-slate-100">
                      {mode === "diagram" ? <Layers className="size-4 text-blue-600" /> : <Type className="size-4 text-blue-600" />}
                      <span className="text-sm">
                        {mode === "diagram" ? "Detected diagram elements" : "OCR extracted text"}
                      </span>
                      <Badge className="ml-auto bg-blue-50 text-blue-700 border-0">
                        {mode === "diagram"
                          ? `${diagramNodes.length} elements`
                          : `${MOCK_OCR_LINES.length} lines`}
                      </Badge>
                    </div>
                    {mode === "handwritten"
                      ? <OcrOverlay lines={MOCK_OCR_LINES} />
                      : <DiagramOverlay nodes={diagramNodes} />
                    }
                  </div>
                )}

                {/* Default mock paper (no upload) */}
                {!uploadedImage && (
                  <div className="w-full max-w-lg bg-white rounded-md shadow-sm p-8 overflow-hidden">
                    <div className="text-xs text-slate-400 uppercase tracking-wider">DB Systems · Final · 2026</div>
                    <div className="mt-2 text-slate-900 tracking-tight">Question 2: ER Diagram</div>
                    <div className="text-xs text-slate-500 mt-1">Design an ER diagram for a university enrollment system…</div>

                    {mode === "diagram" ? (
                      <svg viewBox="0 0 400 260" className="mt-6 w-full">
                        <rect x="20" y="40" width="100" height="40" rx="6" fill="#dbeafe" stroke="#2563eb" />
                        <text x="70" y="65" fontSize="12" textAnchor="middle" fill="#1e40af">Student</text>
                        <rect x="280" y="40" width="100" height="40" rx="6" fill="#dbeafe" stroke="#2563eb" />
                        <text x="330" y="65" fontSize="12" textAnchor="middle" fill="#1e40af">Course</text>
                        <polygon points="200,40 240,60 200,80 160,60" fill="#fef3c7" stroke="#f59e0b" />
                        <text x="200" y="64" fontSize="11" textAnchor="middle" fill="#92400e">Enrolls</text>
                        <line x1="120" y1="60" x2="160" y2="60" stroke="#64748b" />
                        <line x1="240" y1="60" x2="280" y2="60" stroke="#64748b" />
                        <ellipse cx="70" cy="140" rx="40" ry="18" fill="#dcfce7" stroke="#10b981" />
                        <text x="70" y="144" fontSize="11" textAnchor="middle" fill="#065f46">studentID</text>
                        <line x1="70" y1="80" x2="70" y2="122" stroke="#64748b" />
                        <ellipse cx="330" cy="140" rx="40" ry="18" fill="#dcfce7" stroke="#10b981" />
                        <text x="330" y="144" fontSize="11" textAnchor="middle" fill="#065f46">courseID</text>
                        <line x1="330" y1="80" x2="330" y2="122" stroke="#64748b" />
                        <rect x="155" y="90" width="90" height="22" rx="4" fill="#fee2e2" stroke="#ef4444" strokeDasharray="3 2" />
                        <text x="200" y="105" fontSize="10" textAnchor="middle" fill="#991b1b">missing cardinality</text>
                      </svg>
                    ) : (
                      <div className="mt-5 space-y-2 [font-family:cursive] text-slate-700 text-sm leading-7">
                        <p>An ER diagram for the university system will include the entity Student with attributes studentID, name, and email. Each student enrolls in many courses…</p>
                        <p>The relationship "Enrolls" between Student and Course is many-to-many. We resolve this by introducing an associative entity Enrollment with grade and semester attributes…</p>
                        <p className="bg-yellow-100/70 inline-block px-1">In normalization, the dependency name → email violates 2NF when…</p>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* AI Loading Overlay */}
              <AILoadingOverlay
                model={aiModel}
                progress={extractProgress}
                step={extractStep}
                visible={processing}
              />
            </div>
          </Card>

          {/* ── Right: upload + results ──────────────────────────────────── */}
          <div className="lg:col-span-2 space-y-5">
            {/* Upload card */}
            <Card className="p-5 border-slate-200 space-y-3">
              <div className="flex items-center justify-between">
                <div className="text-slate-900">
                  {mode === "diagram" ? "Upload diagram / photo" : "Upload handwritten paper"}
                </div>
                {uploadedImage && (
                  <Badge className="bg-emerald-50 text-emerald-700 border-0">
                    <CheckCircle2 className="size-3 mr-1" /> Loaded
                  </Badge>
                )}
              </div>

              {/* Camera + upload row */}
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => setCameraOpen(true)}
                  className="flex flex-col items-center gap-2 py-4 px-3 rounded-xl border-2 border-dashed border-slate-200 bg-slate-50 hover:bg-blue-50 hover:border-blue-300 transition-colors cursor-pointer group"
                >
                  <div className="size-10 rounded-full bg-slate-100 group-hover:bg-blue-100 flex items-center justify-center text-slate-500 group-hover:text-blue-600 transition-colors">
                    <Camera className="size-5" />
                  </div>
                  <div className="text-center">
                    <div className="text-sm text-slate-700 group-hover:text-blue-700">Use camera</div>
                    <div className="text-xs text-slate-400 mt-0.5">Capture live photo</div>
                  </div>
                </button>

                <button
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={onFileDrop}
                  className={`flex flex-col items-center gap-2 py-4 px-3 rounded-xl border-2 border-dashed transition-colors cursor-pointer group ${
                    dragOver ? "border-blue-400 bg-blue-50" : "border-slate-200 bg-slate-50 hover:bg-blue-50 hover:border-blue-300"
                  }`}
                >
                  <div className={`size-10 rounded-full flex items-center justify-center transition-colors ${dragOver ? "bg-blue-100 text-blue-600" : "bg-slate-100 text-slate-500 group-hover:bg-blue-100 group-hover:text-blue-600"}`}>
                    <ImageIcon className="size-5" />
                  </div>
                  <div className="text-center">
                    <div className={`text-sm transition-colors ${dragOver ? "text-blue-700" : "text-slate-700 group-hover:text-blue-700"}`}>
                      {dragOver ? "Drop to upload" : "Upload file"}
                    </div>
                    <div className="text-xs text-slate-400 mt-0.5">PDF · JPG · PNG</div>
                  </div>
                </button>
              </div>

              <input
                ref={fileInputRef}
                type="file"
                accept="image/*,.pdf"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleFileChange(file);
                  e.target.value = "";
                }}
              />

              {apiError && (
                <div className="text-xs text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
                  {apiError}
                </div>
              )}

              {/* Uploaded file pill */}
              {uploadedImage && (
                <div className="flex items-center gap-2 px-3 py-2 bg-blue-50 rounded-lg border border-blue-100">
                  <FileImage className="size-4 text-blue-500 shrink-0" />
                  <span className="text-xs text-blue-700 truncate flex-1">{uploadedFileName}</span>
                  <button onClick={clearImage} className="text-blue-400 hover:text-red-500 transition-colors">
                    <X className="size-3.5" />
                  </button>
                </div>
              )}

              {/* Rubric */}
              <Button variant="outline" className="w-full justify-start">
                <FileText className="size-4 mr-2" /> Marking rubric — DB_final_rubric.pdf
                <CheckCircle2 className="size-4 ml-auto text-emerald-500" />
              </Button>

              {/* Tips */}
              {!uploadedImage && (
                <div className="text-xs text-slate-400 space-y-1 pt-1">
                  <div className="flex items-center gap-1.5"><ChevronRight className="size-3" />Ensure good lighting for camera capture</div>
                  <div className="flex items-center gap-1.5"><ChevronRight className="size-3" />Flatten paper to avoid distortion</div>
                  <div className="flex items-center gap-1.5"><ChevronRight className="size-3" />Max file size 25 MB</div>
                </div>
              )}

              {/* Extract button (in card for quick access) */}
              {uploadedImage && !done && (
                <Button
                  className="w-full bg-blue-600 hover:bg-blue-700"
                  onClick={onExtract}
                  disabled={processing}
                >
                  {processing ? (
                    <><RefreshCw className="size-4 mr-2 animate-spin" /> Extracting…</>
                  ) : (
                    <><Sparkles className="size-4 mr-2" /> {mode === "diagram" ? "Extract diagram elements" : "Run OCR & grade"}</>
                  )}
                </Button>
              )}
            </Card>

            {/* Results card */}
            {done && (
              <Card className="p-5 border-slate-200">
                <div className="flex items-center justify-between">
                  <div className="text-slate-900">Results</div>
                  <Badge className="bg-emerald-50 text-emerald-700 border-0 hover:bg-emerald-50">
                    <CheckCircle2 className="size-3 mr-1" /> Graded
                  </Badge>
                </div>

                <div className="mt-4 flex items-end gap-4">
                  <div>
                    <div className="text-xs text-slate-500 uppercase tracking-wide">Total score</div>
                    <div className="tracking-tight text-slate-900 mt-0.5">
                      <span className="text-3xl">{total}</span>
                      <span className="text-slate-400">/{max}</span>
                    </div>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
                      <span>AI confidence</span><span className="text-blue-600">87%</span>
                    </div>
                    <Progress value={87} />
                  </div>
                </div>

                {/* OCR/diagram summary pill */}
                <div className={`mt-3 flex items-center gap-2 px-3 py-2 rounded-lg text-xs ${mode === "diagram" ? "bg-blue-50 text-blue-700" : "bg-violet-50 text-violet-700"}`}>
                  {mode === "diagram" ? <Layers className="size-3.5 shrink-0" /> : <Type className="size-3.5 shrink-0" />}
                  {mode === "diagram"
                    ? diagramSummaryText
                    : `${MOCK_OCR_LINES.length} lines extracted · ${MOCK_OCR_LINES.filter(l => l.highlight).length} low-confidence regions`
                  }
                </div>

                <Separator className="my-4" />

                <div className="space-y-3">
                  {breakdown.map((b) => (
                    <div key={b.q}>
                      <div className="flex items-center justify-between text-sm">
                        <div className="text-slate-700 truncate pr-2">{b.q}</div>
                        <div className="text-slate-900 shrink-0">{b.s}/{b.m}</div>
                      </div>
                      <div className="flex items-center gap-2 mt-1.5">
                        <Progress value={(b.s / b.m) * 100} className="flex-1 h-1.5" />
                        <Badge
                          variant="secondary"
                          className={
                            b.conf >= 0.9 ? "bg-emerald-50 text-emerald-700 border-0" :
                            b.conf >= 0.75 ? "bg-amber-50 text-amber-700 border-0" :
                            "bg-red-50 text-red-700 border-0"
                          }
                        >
                          {Math.round(b.conf * 100)}%
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>

                {mode === "diagram" && apiStructure && (
                  <>
                    <Separator className="my-4" />
                    <div className="space-y-3">
                      <div className="text-xs text-slate-500 uppercase tracking-wide">Entities</div>
                      {Object.entries(apiStructure.entities || {}).length === 0 ? (
                        <div className="text-xs text-slate-400">No entities detected</div>
                      ) : (
                        Object.entries(apiStructure.entities).map(([name, details]) => (
                          <div key={name} className="text-sm text-slate-700">
                            <span className="font-medium">{name}</span>
                            <span className="text-slate-400">
                              {details.attributes?.length
                                ? ` - ${details.attributes.join(", ")}`
                                : " - No attributes"}
                            </span>
                          </div>
                        ))
                      )}
                    </div>

                    <div className="space-y-3 pt-2">
                      <div className="text-xs text-slate-500 uppercase tracking-wide">Relationships</div>
                      {apiStructure.relationships?.length ? (
                        apiStructure.relationships.map((rel) => (
                          <div key={rel.name} className="text-sm text-slate-700">
                            <span className="font-medium">{rel.name}</span>
                            <span className="text-slate-500">
                              {rel.entities?.length ? ` - ${rel.entities.join(" <-> ")}` : " - No entities"}
                            </span>
                            {rel.attributes?.length && (
                              <span className="text-slate-400"> - attrs: {rel.attributes.join(", ")}</span>
                            )}
                          </div>
                        ))
                      ) : (
                        <div className="text-xs text-slate-400">No relationships detected</div>
                      )}
                    </div>
                  </>
                )}

                <Separator className="my-4" />
                <div className="flex gap-2">
                  <Button variant="outline" className="flex-1">Review flags</Button>
                  <Button className="flex-1 bg-blue-600 hover:bg-blue-700">Publish grade</Button>
                </div>
              </Card>
            )}
          </div>
        </div>
      </div>
    </>
  );
}