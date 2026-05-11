import { useState, useRef, useEffect, useCallback } from "react";
import {
  Upload, FileText, Sparkles, Save, Edit3, CheckCircle2,
  FileImage, Workflow, ZoomIn, ZoomOut, Camera, X, RotateCcw,
  ScanLine, ImageIcon, RefreshCw, AlertCircle, ChevronRight,
  Eye, Layers, Type, Cpu, BookOpen, Users, TrendingUp, Filter,
  Download, FileSpreadsheet, Calendar, Clock, Hash, FolderOpen,
  Table, BarChart3, ArrowRight, ArrowLeft, PenTool, Settings, Plus, Trash2,
} from "lucide-react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Progress } from "./ui/progress";
import { Separator } from "./ui/separator";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";
import { AIPageBanner, AILoadingOverlay, AIBadgePill, type AIModel } from "./AIBrand";

const API_BASE_URL = (import.meta as { env?: Record<string, string> }).env?.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

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

/* ─── Types ──────────────────────────────────────────────────────────────── */
type OcrLine = { text: string; conf: number; highlight?: boolean };
type DiagramNode = {
  id: string; label: string; type: "entity" | "relation" | "attribute";
  x: number; y: number; w: number; h: number; detected: boolean; issue?: string;
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
  // If diagram mode, render the original single-page UI
  if (mode === "diagram") {
    return <DiagramGradingPage />;
  }
  // If handwritten mode, render the new 7-page workflow
  return <HandwrittenGradingWorkflow />;
}

/* ─── Diagram Grading (Original) ───────────────────────────────────────────── */
function DiagramGradingPage() {
  const [processing, setProcessing] = useState(false);
  const [done, setDone] = useState(false);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [uploadedImage, setUploadedImage] = useState<string | null>(null);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [zoom, setZoom] = useState(100);
  const [dragOver, setDragOver] = useState(false);
  const [activeTab, setActiveTab] = useState<"preview" | "extracted">("preview");
  const [extractProgress, setExtractProgress] = useState(0);
  const [extractStep, setExtractStep] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const aiModel: AIModel = "structr";
  const Icon = Workflow;
  const title = "Diagram Exam Grading";

  const breakdown = [
    { q: "Q1 — ER Entities & relationships", s: 8, m: 10, conf: 0.94 },
    { q: "Q2 — Cardinality constraints", s: 6, m: 10, conf: 0.81 },
    { q: "Q3 — Normalization to 3NF", s: 9, m: 10, conf: 0.97 },
    { q: "Q4 — Schema mapping", s: 5, m: 10, conf: 0.62 },
  ];
  const total = breakdown.reduce((a, b) => a + b.s, 0);
  const max = breakdown.reduce((a, b) => a + b.m, 0);

  const handleImageLoad = (src: string, name?: string) => {
    setUploadedImage(src);
    setUploadedFileName(name ?? "captured_photo.jpg");
    setDone(false);
    setActiveTab("preview");
  };

  const handleFileChange = (file: File) => {
    if (!file) return;
    const url = URL.createObjectURL(file);
    handleImageLoad(url, file.name);
  };

  const onFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileChange(file);
  };

  const onExtract = () => {
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

  const clearImage = () => {
    setUploadedImage(null);
    setUploadedFileName(null);
    setDone(false);
    setActiveTab("preview");
  };

  const displayFileName = uploadedFileName ?? (uploadedImage ? "student_paper.jpg" : "student_24_paper.pdf");

  return (
    <>
      {cameraOpen && (
        <CameraModal
          onCapture={(dataUrl) => handleImageLoad(dataUrl)}
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
              <Icon className="size-4" /> Diagram Grader
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
                      <Layers className="size-3 inline mr-1" />Nodes
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
                {uploadedImage && activeTab === "preview" && (
                  <div className="relative bg-white rounded-lg shadow-md overflow-hidden max-w-full">
                    <img
                      src={uploadedImage}
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
                      <Layers className="size-4 text-blue-600" />
                      <span className="text-sm">Detected diagram elements</span>
                      <Badge className="ml-auto bg-blue-50 text-blue-700 border-0">
                        {MOCK_DIAGRAM_NODES.length} elements
                      </Badge>
                    </div>
                    <DiagramOverlay nodes={MOCK_DIAGRAM_NODES} />
                  </div>
                )}

                {/* Default mock paper (no upload) */}
                {!uploadedImage && (
                  <div className="w-full max-w-lg bg-white rounded-md shadow-sm p-8 overflow-hidden">
                    <div className="text-xs text-slate-400 uppercase tracking-wider">DB Systems · Final · 2026</div>
                    <div className="mt-2 text-slate-900 tracking-tight">Question 2: ER Diagram</div>
                    <div className="text-xs text-slate-500 mt-1">Design an ER diagram for a university enrollment system…</div>

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
                <div className="text-slate-900">Upload diagram / photo</div>
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
                    <><Sparkles className="size-4 mr-2" /> Extract diagram elements</>
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
                <div className="mt-3 flex items-center gap-2 px-3 py-2 rounded-lg text-xs bg-blue-50 text-blue-700">
                  <Layers className="size-3.5 shrink-0" />
                  {MOCK_DIAGRAM_NODES.filter(n => n.detected).length}/{MOCK_DIAGRAM_NODES.length} elements detected · 1 issue flagged
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

/* ═══════════════════════════════════════════════════════════════════════════
   HANDWRITTEN GRADING: 7-PAGE WORKFLOW
   ═══════════════════════════════════════════════════════════════════════════ */

type CriterionEntry = {
  point: string;
  marks: number;
};

type RubricEntry = {
  questionNo: string;
  questionText: string;
  criteria: CriterionEntry[];
};

function coerceMarks(v: unknown): number {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function sumQuestionMarks(entry: RubricEntry): number {
  return entry.criteria.reduce((s, c) => s + coerceMarks(c.marks), 0);
}

function mapQuestionsFromBackend(questions: unknown): RubricEntry[] {
  const list = Array.isArray(questions) ? questions : [];
  return list.map((q: Record<string, unknown>, index) => {
    const questionText = String(
      q?.question_text ?? q?.question ?? `Question ${index + 1}`
    ).trim();
    const rawNo = q?.question_no ?? index + 1;
    const digits = String(rawNo).match(/\d+/);
    const questionNo = digits ? digits[0].padStart(2, "0") : String(index + 1).padStart(2, "0");
    const maxFromDoc = coerceMarks(q?.max_marks);

    let criteria: CriterionEntry[] = [];
    const rawCrit = q?.criteria;

    if (Array.isArray(rawCrit)) {
      criteria = rawCrit
        .map((item: unknown) => {
          if (item && typeof item === "object") {
            const o = item as Record<string, unknown>;
            return {
              point: String(o.point ?? o.description ?? o.text ?? "").trim(),
              marks: coerceMarks(o.marks),
            };
          }
          const text = String(item ?? "").trim();
          return { point: text, marks: 0 };
        })
        .filter((c) => c.point.length > 0);
    } else if (typeof rawCrit === "string" && rawCrit.trim()) {
      const parts = rawCrit
        .split(";")
        .map((s) => s.trim())
        .filter(Boolean);
      const per =
        parts.length > 0 && maxFromDoc > 0
          ? Math.round((maxFromDoc / parts.length) * 10000) / 10000
          : 0;
      criteria = parts.map((point) => ({ point, marks: per }));
    }

    let sumCrit = criteria.reduce((s, c) => s + coerceMarks(c.marks), 0);
    if (criteria.length > 0 && sumCrit === 0 && maxFromDoc > 0) {
      const per =
        Math.round((maxFromDoc / criteria.length) * 10000) / 10000;
      criteria = criteria.map((c) => ({ ...c, marks: per }));
      sumCrit = criteria.reduce((s, c) => s + coerceMarks(c.marks), 0);
    }

    if (criteria.length === 0 && maxFromDoc > 0) {
      criteria = [{ point: "Marking criterion (edit)", marks: maxFromDoc }];
    }

    return {
      questionNo,
      questionText,
      criteria,
    };
  });
}

type DashboardStudent = {
  id: string;
  submissionId?: string;
  status: "processing" | "completed" | "warning";
  ocrConf?: number;
  quickGrade?: number;
  maxGrade: number;
  rawTranscript?: string;
  evaluation?: Record<string, unknown>;
};

function mapSubmissionToDashboard(doc: Record<string, unknown>): DashboardStudent {
  const evaluation = doc.evaluation as Record<string, unknown> | undefined;
  const totalScore =
    evaluation && typeof evaluation.total_score === "number" ? evaluation.total_score : undefined;
  const maxPaper =
    typeof doc.max_marks_paper_total === "number" ? doc.max_marks_paper_total : 0;
  const st = String(doc.status ?? "graded");
  let uiStatus: DashboardStudent["status"] = "completed";
  if (st === "processing") uiStatus = "processing";
  else if (st === "failed" || st === "warning" || st === "skipped") uiStatus = "warning";

  return {
    id: String(doc.student_id ?? ""),
    submissionId: typeof doc._id === "string" ? doc._id : undefined,
    status: uiStatus,
    quickGrade: totalScore,
    maxGrade: maxPaper,
    rawTranscript:
      typeof doc.raw_ocr_transcript === "string" ? doc.raw_ocr_transcript : undefined,
    evaluation,
  };
}

type RubricListItem = {
  _id: string;
  session_name?: string;
  subject_code?: string;
  filename?: string;
  parsed_at?: number;
};

type GradingHistory = {
  sessionName: string;
  subjectCode: string;
  date: string;
  avgScore: number;
  status: "Completed" | "Alerts";
};

function HandwrittenGradingWorkflow() {
  const [page, setPage] = useState<1 | 2 | 3 | 4 | 5 | 6 | 7>(1);

  // Page 2: Session Initialization
  const [subject, setSubject] = useState("SE3040");
  const [examName, setExamName] = useState("Semester 1 Final Exam");
  const [rubricFile, setRubricFile] = useState<File | null>(null);
  const [rubricId, setRubricId] = useState<string | null>(null);
  const [rubricLoading, setRubricLoading] = useState(false);
  const [rubricSaving, setRubricSaving] = useState(false);
  const [rubricError, setRubricError] = useState<string | null>(null);
  const [rubricSuccess, setRubricSuccess] = useState<string | null>(null);
  const [rubricFetchLoading, setRubricFetchLoading] = useState(false);

  // Page 3: Rubric Verification — populated from POST /upload-rubric or GET /rubric/{id}
  const [rubric, setRubric] = useState<RubricEntry[]>([]);

  // Page 4: Batch Upload → backend staging + grade-batch
  const [gradingRubricId, setGradingRubricId] = useState<string | null>(null);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [batchStudentFolderCount, setBatchStudentFolderCount] = useState<number | null>(null);
  const [uploadedFiles, setUploadedFiles] = useState<string[]>([]);
  const [batchUploadError, setBatchUploadError] = useState<string | null>(null);
  const [batchUploading, setBatchUploading] = useState(false);
  const [gradingRunning, setGradingRunning] = useState(false);
  /** True when page 4 was opened via “Continue to batch grading” without uploading a rubric on page 2 (Back → session setup). */
  const [batchBackFromSessionSkip, setBatchBackFromSessionSkip] = useState(false);
  const [rubricPickerOpen, setRubricPickerOpen] = useState(false);
  const [rubricsList, setRubricsList] = useState<RubricListItem[]>([]);
  const [rubricsListLoading, setRubricsListLoading] = useState(false);
  const [pendingRubricId, setPendingRubricId] = useState<string | null>(null);
  const zipInputRef = useRef<HTMLInputElement>(null);

  // Page 5: Master Evaluation Dashboard (from GET /submissions)
  const [dashboardStudents, setDashboardStudents] = useState<DashboardStudent[]>([]);
  const [submissionsLoading, setSubmissionsLoading] = useState(false);
  const [filterWarnings, setFilterWarnings] = useState(false);
  const [selectedStudent, setSelectedStudent] = useState<DashboardStudent | null>(null);

  // Page 6: AI-Assisted Review
  const [zoom, setZoom] = useState(100);
  const [reviewTab, setReviewTab] = useState<"parsed" | "analysis">("parsed");
  const [parsedText, setParsedText] = useState(MOCK_OCR_LINES.map(l => l.text).join("\n"));
  const [lecturerNote, setLecturerNote] = useState("");
  const [currentStudentIndex, setCurrentStudentIndex] = useState(0);

  // Page 7: Analytics
  const gradeDistribution = [12, 18, 25, 20, 15, 10];

  // Mock history
  const history: GradingHistory[] = [
    { sessionName: "Mid-Semester Exam", subjectCode: "SE3040", date: "2026-03-15", avgScore: 72, status: "Completed" },
    { sessionName: "Quiz 3", subjectCode: "CS2020", date: "2026-04-01", avgScore: 65, status: "Alerts" },
  ];

  const rubricFileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  const fetchSubmissionsForRubric = async (rid: string) => {
    setSubmissionsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/submissions?rubric_id=${encodeURIComponent(rid)}`);
      const data = (await readJsonResponse(response)) as { items?: Record<string, unknown>[] };
      if (!response.ok) {
        throw new Error(parseApiError(data, "Failed to load submissions."));
      }
      const rows = (data.items ?? []).map((doc) => mapSubmissionToDashboard(doc));
      setDashboardStudents(rows);
    } catch (e) {
      console.error(e);
      setDashboardStudents([]);
    } finally {
      setSubmissionsLoading(false);
    }
  };

  const loadRubricsForPicker = async () => {
    setRubricsListLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/rubrics`);
      const data = (await readJsonResponse(response)) as { items?: RubricListItem[] };
      if (!response.ok) {
        throw new Error(parseApiError(data, "Failed to load rubrics."));
      }
      setRubricsList(data.items ?? []);
    } catch {
      setRubricsList([]);
    } finally {
      setRubricsListLoading(false);
    }
  };

  useEffect(() => {
    if (page === 5 && gradingRubricId) {
      fetchSubmissionsForRubric(gradingRubricId);
    }
  }, [page, gradingRubricId]);

  useEffect(() => {
    if (!rubricPickerOpen) return;
    loadRubricsForPicker();
    setPendingRubricId(gradingRubricId);
  }, [rubricPickerOpen]);

  useEffect(() => {
    if (page === 4 && rubricId) {
      setGradingRubricId((prev) => prev ?? rubricId);
      setPendingRubricId((prev) => prev ?? rubricId);
    }
  }, [page, rubricId]);

  const handleRubricUpload = (file: File) => {
    setRubricFile(file);
    setRubricError(null);
    setRubricSuccess(null);
  };

  useEffect(() => {
    if (page !== 3 || !rubricId) return;
    let cancelled = false;
    (async () => {
      setRubricFetchLoading(true);
      setRubricError(null);
      try {
        const response = await fetch(`${API_BASE_URL}/rubric/${rubricId}`);
        const data = (await readJsonResponse(response)) as Record<string, unknown>;
        if (!response.ok) {
          throw new Error(parseApiError(data, "Failed to load rubric."));
        }
        const mapped = mapQuestionsFromBackend(data?.questions);
        if (!cancelled) {
          setRubric(mapped);
        }
        if (!cancelled) {
          if (typeof data.session_name === "string" && data.session_name.trim()) {
            setExamName(data.session_name);
          }
          if (typeof data.subject_code === "string" && data.subject_code.trim()) {
            setSubject(data.subject_code);
          }
        }
      } catch (error) {
        if (!cancelled) {
          setRubricError(error instanceof Error ? error.message : "Failed to load rubric.");
        }
      } finally {
        if (!cancelled) setRubricFetchLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [page, rubricId]);

  const uploadRubricToBackend = async () => {
    if (!rubricFile) {
      setRubricError("Please upload a rubric file first.");
      return;
    }
    setRubricLoading(true);
    setRubricError(null);
    setRubricSuccess(null);
    try {
      const formData = new FormData();
      formData.append("file", rubricFile);
      formData.append("session_name", examName);
      formData.append("subject_code", subject);

      const response = await fetch(`${API_BASE_URL}/upload-rubric`, {
        method: "POST",
        body: formData,
      });
      const data = (await readJsonResponse(response)) as Record<string, unknown>;
      if (!response.ok) {
        throw new Error(parseApiError(data, "Failed to upload rubric."));
      }

      setRubricId((data?.mongodb_id as string) ?? null);
      const mapped = mapQuestionsFromBackend(data?.preview);
      if (mapped.length > 0) {
        setRubric(mapped);
      }
      setRubricSuccess("Rubric extracted successfully.");
      setBatchBackFromSessionSkip(false);
      setPage(3);
    } catch (error) {
      setRubricError(error instanceof Error ? error.message : "Failed to upload rubric.");
    } finally {
      setRubricLoading(false);
    }
  };

  /** Continue from session setup: extract PDF when provided, otherwise jump to batch grading and pick a rubric there. */
  const handleSessionContinue = async () => {
    if (rubricFile) {
      await uploadRubricToBackend();
      return;
    }
    setRubricError(null);
    setRubricSuccess(null);
    setBatchBackFromSessionSkip(true);
    setPage(4);
  };

  const saveRubricEdits = async () => {
    if (!rubricId) {
      setRubricError("Rubric ID missing. Upload the rubric again.");
      return;
    }
    if (rubric.length === 0) {
      setRubricError("Add at least one question before saving.");
      return;
    }
    setRubricSaving(true);
    setRubricError(null);
    setRubricSuccess(null);
    try {
      const payload = {
        session_name: examName,
        subject_code: subject,
        questions: rubric.map((entry) => {
          const criteriaRows = entry.criteria
            .filter((c) => c.point.trim().length > 0)
            .map((c) => ({
              point: c.point.trim(),
              marks: coerceMarks(c.marks),
            }));
          const maxMarks = criteriaRows.reduce((s, c) => s + c.marks, 0);
          return {
            question_no: entry.questionNo,
            question_text: entry.questionText.trim(),
            criteria: criteriaRows,
            max_marks: maxMarks,
          };
        }),
      };

      if (
        payload.questions.some((q) => q.criteria.length === 0 || q.max_marks <= 0)
      ) {
        setRubricError(
          "Each question needs at least one criterion with text, and per-criterion marks must sum to more than zero."
        );
        setRubricSaving(false);
        return;
      }

      const response = await fetch(`${API_BASE_URL}/rubric/${rubricId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = (await readJsonResponse(response)) as { item?: { questions?: unknown[] } };
      if (!response.ok) {
        throw new Error(parseApiError(data, "Failed to save rubric changes."));
      }

      const mapped = mapQuestionsFromBackend(data?.item?.questions);
      if (mapped.length > 0) {
        setRubric(mapped);
      }
      setRubricSuccess("Rubric updated successfully.");
      if (rubricId) {
        setGradingRubricId(rubricId);
        setPendingRubricId(rubricId);
      }
      setBatchBackFromSessionSkip(false);
      setPage(4);
    } catch (error) {
      setRubricError(error instanceof Error ? error.message : "Failed to save rubric changes.");
    } finally {
      setRubricSaving(false);
    }
  };

  const uploadBatchZip = async (file: File) => {
    setBatchUploadError(null);
    setBatchUploading(true);
    setBatchId(null);
    setBatchStudentFolderCount(null);
    try {
      const formData = new FormData();
      formData.append("archive", file);
      const response = await fetch(`${API_BASE_URL}/upload-student-batch/zip`, {
        method: "POST",
        body: formData,
      });
      const data = (await readJsonResponse(response)) as {
        batch_id?: string;
        student_folder_count?: number;
      };
      if (!response.ok) {
        throw new Error(parseApiError(data, "Upload failed."));
      }
      setBatchId(data.batch_id ?? null);
      setBatchStudentFolderCount(
        typeof data.student_folder_count === "number" ? data.student_folder_count : null
      );
      setUploadedFiles([file.name]);
    } catch (e) {
      setBatchUploadError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      setBatchUploading(false);
    }
  };

  const uploadBatchFolder = async (fileList: FileList) => {
    setBatchUploadError(null);
    setBatchUploading(true);
    setBatchId(null);
    setBatchStudentFolderCount(null);
    try {
      const formData = new FormData();
      const files = Array.from(fileList);
      for (const f of files) {
        const rel =
          (f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name;
        formData.append("files", f, rel);
      }
      setUploadedFiles(files.map((f) => (f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name));

      const response = await fetch(`${API_BASE_URL}/upload-student-batch/files`, {
        method: "POST",
        body: formData,
      });
      const data = (await readJsonResponse(response)) as {
        batch_id?: string;
        student_folder_count?: number;
      };
      if (!response.ok) {
        throw new Error(parseApiError(data, "Upload failed."));
      }
      setBatchId(data.batch_id ?? null);
      setBatchStudentFolderCount(
        typeof data.student_folder_count === "number" ? data.student_folder_count : null
      );
    } catch (e) {
      setBatchUploadError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      setBatchUploading(false);
    }
  };

  const runBatchGrading = async () => {
    if (!gradingRubricId || !batchId) {
      setBatchUploadError("Select a rubric and upload a batch first.");
      return;
    }
    setBatchUploadError(null);
    setGradingRunning(true);
    try {
      const response = await fetch(`${API_BASE_URL}/grade-batch/${gradingRubricId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ batch_id: batchId }),
      });
      const data = await readJsonResponse(response);
      if (!response.ok) {
        throw new Error(parseApiError(data, "Grading failed."));
      }
      await fetchSubmissionsForRubric(gradingRubricId);
      setPage(5);
    } catch (e) {
      setBatchUploadError(e instanceof Error ? e.message : "Grading failed.");
    } finally {
      setGradingRunning(false);
    }
  };

  const viewStudentDetail = (student: DashboardStudent) => {
    setSelectedStudent(student);
    setCurrentStudentIndex(dashboardStudents.indexOf(student));
    setParsedText(student.rawTranscript ?? "");
    setPage(6);
  };

  const navigateStudent = (direction: "next" | "prev") => {
    const newIndex =
      direction === "next"
        ? Math.min(currentStudentIndex + 1, dashboardStudents.length - 1)
        : Math.max(currentStudentIndex - 1, 0);
    setCurrentStudentIndex(newIndex);
    const st = dashboardStudents[newIndex];
    setSelectedStudent(st);
    setParsedText(st?.rawTranscript ?? "");
  };

  const filteredStudents = filterWarnings
    ? dashboardStudents.filter(
        (s) =>
          s.quickGrade !== undefined &&
          s.maxGrade > 0 &&
          s.quickGrade < s.maxGrade * 0.4
      )
    : dashboardStudents;

  const updateQuestionField = (qIdx: number, field: "questionNo" | "questionText", value: string) => {
    setRubric((prev) => {
      const next = [...prev];
      next[qIdx] = { ...next[qIdx], [field]: value };
      return next;
    });
  };

  const updateCriterion = (qIdx: number, cIdx: number, patch: Partial<CriterionEntry>) => {
    setRubric((prev) => {
      const next = [...prev];
      const row = { ...next[qIdx], criteria: [...next[qIdx].criteria] };
      row.criteria[cIdx] = { ...row.criteria[cIdx], ...patch };
      next[qIdx] = row;
      return next;
    });
  };

  const addCriterion = (qIdx: number) => {
    setRubric((prev) => {
      const next = [...prev];
      next[qIdx] = {
        ...next[qIdx],
        criteria: [...next[qIdx].criteria, { point: "", marks: 0 }],
      };
      return next;
    });
  };

  const removeCriterion = (qIdx: number, cIdx: number) => {
    setRubric((prev) => {
      const next = [...prev];
      next[qIdx] = {
        ...next[qIdx],
        criteria: next[qIdx].criteria.filter((_, i) => i !== cIdx),
      };
      return next;
    });
  };

  const paperTotalMarks = rubric.reduce((sum, r) => sum + sumQuestionMarks(r), 0);

  const canFinalizeRubric =
    rubric.length > 0 &&
    !rubricFetchLoading &&
    rubric.every(
      (q) =>
        q.criteria.length > 0 &&
        q.criteria.some((c) => c.point.trim().length > 0) &&
        sumQuestionMarks(q) > 0
    );

  return (
    <div className="p-8 space-y-6">
      <AIPageBanner model="lexo" />

      {/* ═══ PAGE 1: Command Center ═══ */}
      {page === 1 && (
        <div className="space-y-6">
          <div>
            <h2 className="tracking-tight text-slate-900">Project Nexus: AI Evaluation Suite</h2>
            <p className="text-sm text-slate-500 mt-1">Command center for AI-assisted answer grading</p>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            {/* Card 1: Start AI Answer Grading */}
            <Card
              className="p-6 border-violet-200 bg-gradient-to-br from-violet-50 to-purple-50 hover:shadow-lg transition-shadow cursor-pointer"
              onClick={() => setPage(2)}
            >
              <div className="flex items-start gap-4">
                <div className="size-14 rounded-2xl bg-violet-600 flex items-center justify-center shrink-0">
                  <Sparkles className="size-7 text-white" />
                </div>
                <div className="flex-1">
                  <h3 className="text-lg text-slate-900 mb-1">Start AI Answer Grading</h3>
                  <p className="text-sm text-slate-600">
                    Launch the OCR + RAG pipeline to grade handwritten exams with AI assistance.
                  </p>
                  <div className="mt-3 flex items-center gap-2 text-violet-700">
                    <span className="text-sm">Begin session</span>
                    <ArrowRight className="size-4" />
                  </div>
                </div>
              </div>
            </Card>

            {/* Card 2: Ongoing Grading Tasks */}
            <Card className="p-6 border-slate-200 bg-slate-50">
              <div className="flex items-start gap-4">
                <div className="size-14 rounded-2xl bg-blue-100 flex items-center justify-center shrink-0">
                  <RefreshCw className="size-7 text-blue-600" />
                </div>
                <div className="flex-1">
                  <h3 className="text-lg text-slate-900 mb-1">Ongoing Grading Tasks</h3>
                  <p className="text-sm text-slate-500">No background tasks running</p>
                  <div className="mt-3 text-xs text-slate-400">
                    Tasks will appear here when batch processing is active.
                  </div>
                </div>
              </div>
            </Card>
          </div>

          {/* Recent Grading History */}
          <Card className="p-6 border-slate-200">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg text-slate-900">Recent Grading History</h3>
              <Badge className="bg-slate-100 text-slate-600 border-0">{history.length} sessions</Badge>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="border-b border-slate-200">
                  <tr className="text-left text-xs text-slate-500 uppercase tracking-wide">
                    <th className="pb-3">Session Name</th>
                    <th className="pb-3">Subject Code</th>
                    <th className="pb-3">Date</th>
                    <th className="pb-3">Avg. Score</th>
                    <th className="pb-3">Status</th>
                  </tr>
                </thead>
                <tbody className="text-sm">
                  {history.map((h, i) => (
                    <tr key={i} className="border-b border-slate-100 hover:bg-slate-50">
                      <td className="py-3 text-slate-900">{h.sessionName}</td>
                      <td className="py-3 text-slate-600">{h.subjectCode}</td>
                      <td className="py-3 text-slate-600">{h.date}</td>
                      <td className="py-3 text-slate-700">{h.avgScore}%</td>
                      <td className="py-3">
                        <Badge className={h.status === "Completed" ? "bg-emerald-50 text-emerald-700 border-0" : "bg-amber-50 text-amber-700 border-0"}>
                          {h.status}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}

      {/* ═══ PAGE 2: Session Initialization ═══ */}
      {page === 2 && (
        <div className="space-y-6 max-w-3xl">
          <div>
            <h2 className="tracking-tight text-slate-900">Session Initialization</h2>
            <p className="text-sm text-slate-500 mt-1">Define the context before AI processing begins</p>
          </div>

          <Card className="p-6 border-slate-200 space-y-5">
            <div>
              <label className="text-sm text-slate-700 mb-2 block">Subject Selection</label>
              <Input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="e.g., SE3040, CS2020" />
            </div>

            <div>
              <label className="text-sm text-slate-700 mb-2 block">Exam/Session Name</label>
              <Input value={examName} onChange={(e) => setExamName(e.target.value)} placeholder="e.g., Semester 1 Final Exam" />
            </div>

            <div>
              <label className="text-sm text-slate-700 mb-2 block">Rubric upload (optional)</label>
              <div
                onClick={() => rubricFileInputRef.current?.click()}
                className="border-2 border-dashed border-slate-200 rounded-xl p-6 hover:bg-slate-50 cursor-pointer transition-colors"
              >
                {rubricFile ? (
                  <div className="flex items-center gap-3">
                    <FileText className="size-10 text-violet-600" />
                    <div>
                      <div className="text-sm text-slate-900">{rubricFile.name}</div>
                      <div className="text-xs text-slate-500 mt-0.5">Marking scheme loaded</div>
                    </div>
                  </div>
                ) : (
                  <div className="text-center">
                    <Upload className="size-10 text-slate-400 mx-auto mb-2" />
                    <div className="text-sm text-slate-600">Drop marking scheme here or click to browse</div>
                    <div className="text-xs text-slate-400 mt-1">
                      Optional — skip and choose an existing rubric when you run batch grading.
                    </div>
                  </div>
                )}
              </div>
              <input
                ref={rubricFileInputRef}
                type="file"
                accept=".pdf,application/pdf"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleRubricUpload(file);
                }}
              />
            </div>
          </Card>

          <div className="flex gap-3">
            <Button variant="outline" onClick={() => setPage(1)}>
              <ArrowLeft className="size-4 mr-2" /> Back
            </Button>
            <Button
              className="bg-violet-600 hover:bg-violet-700"
              onClick={handleSessionContinue}
              disabled={!subject || !examName || rubricLoading}
            >
              {rubricLoading ? (
                <><RefreshCw className="size-4 mr-2 animate-spin" /> Extracting rubric...</>
              ) : rubricFile ? (
                <>Extract rubric and verify <ArrowRight className="size-4 ml-2" /></>
              ) : (
                <>Continue to batch grading <ArrowRight className="size-4 ml-2" /></>
              )}
            </Button>
          </div>
          {rubricError && <div className="text-sm text-red-600">{rubricError}</div>}
          {rubricSuccess && <div className="text-sm text-emerald-600">{rubricSuccess}</div>}
        </div>
      )}

      {/* ═══ PAGE 3: Rubric Verification ═══ */}
      {page === 3 && (
        <div className="space-y-6">
          <div>
            <h2 className="tracking-tight text-slate-900">Rubric Verification</h2>
            <p className="text-sm text-slate-500 mt-1">
              Verify and edit the extracted marking scheme before grading, or skip to batch grading and select a rubric there.
            </p>
            {rubricId && (
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <Hash className="size-3.5 shrink-0" />
                <span className="font-mono break-all">Rubric ID: {rubricId}</span>
                {rubricFetchLoading && (
                  <span className="text-violet-600 flex items-center gap-1">
                    <RefreshCw className="size-3 animate-spin" /> Syncing from server…
                  </span>
                )}
              </div>
            )}
          </div>

          <Card className="p-6 border-slate-200">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-slate-900">Extracted Rubric</h3>
              <Badge className="bg-violet-50 text-violet-700 border-0">
                Paper total: {paperTotalMarks} marks
              </Badge>
            </div>

            {rubricFetchLoading ? (
              <div className="flex items-center justify-center gap-2 py-12 text-sm text-slate-500 border border-slate-200 rounded-lg">
                <RefreshCw className="size-5 animate-spin" />
                Loading rubric from the API…
              </div>
            ) : rubric.length === 0 ? (
              <div className="py-12 px-4 text-center text-sm text-slate-500 border border-slate-200 rounded-lg space-y-3">
                <p>
                  No questions were returned. Upload a PDF on session setup, go back to try again, or use{" "}
                  <span className="font-medium text-slate-700">Skip to batch grading</span> below and pick an existing rubric on the next screen.
                </p>
                <p className="text-xs">
                  Backend: <span className="font-mono text-slate-700">{API_BASE_URL}</span>
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {rubric.map((entry, qi) => (
                  <Card key={`${entry.questionNo}-${qi}`} className="p-4 border-slate-200 shadow-sm">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="flex flex-wrap items-end gap-3">
                        <div className="space-y-1">
                          <label className="text-xs text-slate-500">Question #</label>
                          <Input
                            value={entry.questionNo}
                            onChange={(e) => updateQuestionField(qi, "questionNo", e.target.value)}
                            className="w-24 font-mono"
                            aria-label="Question number"
                          />
                        </div>
                      </div>
                      <Badge className="bg-violet-50 text-violet-800 border-violet-100 shrink-0">
                        Question total: {sumQuestionMarks(entry)} marks
                      </Badge>
                    </div>
                    <div className="mt-3 space-y-1">
                      <label className="text-xs text-slate-500">Question wording</label>
                      <Input
                        value={entry.questionText}
                        onChange={(e) => updateQuestionField(qi, "questionText", e.target.value)}
                      />
                    </div>
                    <div className="mt-4">
                      <div className="text-xs font-medium text-slate-600 mb-2">Criteria (each row is one marking point with its marks)</div>
                      <div className="rounded-lg border border-slate-200 overflow-hidden">
                        <table className="w-full text-sm">
                          <thead className="bg-slate-50 border-b border-slate-200">
                            <tr className="text-left text-xs text-slate-600 uppercase tracking-wide">
                              <th className="p-2 pl-3">Criterion</th>
                              <th className="p-2 w-28 text-right">Marks</th>
                              <th className="p-2 w-12" />
                            </tr>
                          </thead>
                          <tbody>
                            {entry.criteria.length === 0 ? (
                              <tr>
                                <td colSpan={3} className="p-4 text-xs text-slate-500">
                                  No criteria yet — use &quot;Add criterion&quot; below.
                                </td>
                              </tr>
                            ) : (
                              entry.criteria.map((c, ci) => (
                                <tr key={ci} className="border-b border-slate-100 last:border-0">
                                  <td className="p-2 pl-3 align-top">
                                    <Textarea
                                      value={c.point}
                                      onChange={(e) => updateCriterion(qi, ci, { point: e.target.value })}
                                      rows={2}
                                      className="text-sm resize-y min-h-[2.75rem]"
                                      placeholder="What is assessed"
                                    />
                                  </td>
                                  <td className="p-2 align-top text-right">
                                    <Input
                                      type="number"
                                      min={0}
                                      step={0.5}
                                      value={c.marks}
                                      onChange={(e) => {
                                        const v = e.target.value;
                                        updateCriterion(qi, ci, {
                                          marks: v === "" ? 0 : Number(v),
                                        });
                                      }}
                                      className="w-full text-right tabular-nums"
                                    />
                                  </td>
                                  <td className="p-2 align-top">
                                    <Button
                                      type="button"
                                      variant="ghost"
                                      size="icon"
                                      className="text-slate-400 hover:text-red-600"
                                      onClick={() => removeCriterion(qi, ci)}
                                      aria-label="Remove criterion"
                                    >
                                      <Trash2 className="size-4" />
                                    </Button>
                                  </td>
                                </tr>
                              ))
                            )}
                          </tbody>
                        </table>
                      </div>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="mt-2"
                        onClick={() => addCriterion(qi)}
                      >
                        <Plus className="size-4 mr-1" /> Add criterion
                      </Button>
                    </div>
                  </Card>
                ))}
              </div>
            )}

            <div className="mt-4 flex items-center gap-2 text-xs text-slate-500">
              <CheckCircle2 className="size-4 text-emerald-500 shrink-0" />
              Edit below, then click Finalize — changes are saved with{" "}
              <span className="font-mono">PUT /rubric/&lt;id&gt;</span>.
            </div>
          </Card>

          <div className="flex flex-wrap gap-3">
            <Button variant="outline" onClick={() => setPage(2)}>
              <ArrowLeft className="size-4 mr-2" /> Back
            </Button>
            <Button
              type="button"
              variant="outline"
              className="border-slate-300"
              onClick={() => {
                setRubricError(null);
                setBatchBackFromSessionSkip(false);
                setPage(4);
              }}
            >
              Skip to batch grading <ChevronRight className="size-4 ml-1" />
            </Button>
            <Button
              className="bg-violet-600 hover:bg-violet-700 ml-auto sm:ml-0"
              onClick={saveRubricEdits}
              disabled={rubricSaving || !canFinalizeRubric}
            >
              {rubricSaving ? (
                <><RefreshCw className="size-4 mr-2 animate-spin" /> Saving rubric...</>
              ) : (
                <>Finalize Rubric & Upload Scripts <ArrowRight className="size-4 ml-2" /></>
              )}
            </Button>
          </div>
          {rubricError && <div className="text-sm text-red-600">{rubricError}</div>}
          {rubricSuccess && <div className="text-sm text-emerald-600">{rubricSuccess}</div>}
        </div>
      )}

      {/* ═══ PAGE 4: Batch Script Ingestion ═══ */}
      {page === 4 && (
        <div className="space-y-6 max-w-3xl">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="tracking-tight text-slate-900">Batch Script Ingestion</h2>
              <p className="text-sm text-slate-500 mt-1">
                Choose a marking rubric (required for grading), then upload a ZIP or folder of student scripts (one folder per student ID). You can upload a new scheme earlier in the flow or pick one already stored on the server.
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={() => setRubricPickerOpen(true)}>
              <BookOpen className="size-4 mr-2" /> Choose rubric
            </Button>
          </div>

          <Card className="p-5 border-slate-200 space-y-3">
            <div className="text-sm text-slate-700">Selected rubric</div>
            {gradingRubricId ? (
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <Badge variant="outline" className="font-mono">
                  {gradingRubricId}
                </Badge>
                <span className="text-slate-500">
                  Use “Choose rubric” to pick another scheme from the server.
                </span>
              </div>
            ) : (
              <p className="text-sm text-amber-700">No rubric selected — click “Choose rubric”.</p>
            )}
          </Card>

          <Card className="p-6 border-slate-200 space-y-5">
            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-slate-700 mb-2 block">Upload ZIP archive</label>
                <div
                  onClick={() => !batchUploading && zipInputRef.current?.click()}
                  className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${
                    batchUploading ? "opacity-60 pointer-events-none border-slate-100" : "border-slate-200 hover:bg-slate-50"
                  }`}
                >
                  <Upload className="size-10 text-violet-500 mx-auto mb-2" />
                  <div className="text-sm text-slate-700">Click to select .zip</div>
                  <div className="text-xs text-slate-400 mt-1">Structure: StudentID/page.jpg …</div>
                </div>
                <input
                  ref={zipInputRef}
                  type="file"
                  accept=".zip,application/zip"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) uploadBatchZip(f);
                    e.target.value = "";
                  }}
                />
              </div>
              <div>
                <label className="text-sm text-slate-700 mb-2 block">Or upload folder</label>
                <div
                  onClick={() => !batchUploading && folderInputRef.current?.click()}
                  className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${
                    batchUploading ? "opacity-60 pointer-events-none border-slate-100" : "border-slate-200 hover:bg-slate-50"
                  }`}
                >
                  <FolderOpen className="size-10 text-violet-600 mx-auto mb-2" />
                  <div className="text-sm text-slate-700">Select folder (Chrome / Edge)</div>
                  <div className="text-xs text-slate-400 mt-1">Preserves paths → student subfolders</div>
                </div>
                {/* webkitdirectory enables folder picker in Chromium */}
                <input
                  ref={folderInputRef}
                  type="file"
                  multiple
                  accept="image/*,.pdf"
                  className="hidden"
                  {...({ webkitdirectory: "" } as Record<string, string>)}
                  onChange={(e) => {
                    const files = e.target.files;
                    if (files && files.length > 0) uploadBatchFolder(files);
                    e.target.value = "";
                  }}
                />
              </div>
            </div>

            {batchUploading && (
              <div className="flex items-center gap-2 text-sm text-violet-600">
                <RefreshCw className="size-4 animate-spin" /> Uploading to server…
              </div>
            )}

            {batchId && (
              <div className="rounded-lg bg-emerald-50 border border-emerald-100 px-3 py-2 text-sm text-emerald-900">
                Batch staged: <span className="font-mono">{batchId}</span>
                {batchStudentFolderCount !== null && (
                  <> · {batchStudentFolderCount} student folder(s)</>
                )}
              </div>
            )}

            {uploadedFiles.length > 0 && (
              <div className="space-y-2">
                <div className="text-sm text-slate-700">{uploadedFiles.length} path(s) uploaded</div>
                <div className="max-h-48 overflow-y-auto space-y-1 bg-slate-50 rounded-lg p-2 text-xs font-mono">
                  {uploadedFiles.slice(0, 80).map((name, i) => (
                    <div key={i} className="truncate text-slate-600">
                      {name}
                    </div>
                  ))}
                  {uploadedFiles.length > 80 && (
                    <div className="text-slate-400">… and {uploadedFiles.length - 80} more</div>
                  )}
                </div>
              </div>
            )}
          </Card>

          <div className="flex flex-wrap gap-3">
            <Button
              variant="outline"
              onClick={() => {
                if (batchBackFromSessionSkip) {
                  setBatchBackFromSessionSkip(false);
                  setPage(2);
                } else {
                  setPage(rubricId ? 3 : 2);
                }
              }}
            >
              <ArrowLeft className="size-4 mr-2" /> Back
            </Button>
            <Button
              className="bg-violet-600 hover:bg-violet-700"
              onClick={runBatchGrading}
              disabled={
                !gradingRubricId ||
                !batchId ||
                batchUploading ||
                gradingRunning
              }
            >
              {gradingRunning ? (
                <><RefreshCw className="size-4 mr-2 animate-spin" /> Running OCR & grading…</>
              ) : (
                <>Start processing <Sparkles className="size-4 ml-2" /></>
              )}
            </Button>
          </div>
          {batchUploadError && <div className="text-sm text-red-600">{batchUploadError}</div>}
        </div>
      )}

      {/* ═══ PAGE 5: Master Evaluation Dashboard ═══ */}
      {page === 5 && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="tracking-tight text-slate-900">Master Evaluation Dashboard</h2>
              <p className="text-sm text-slate-500 mt-1">Monitor batch processing progress</p>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => setFilterWarnings(!filterWarnings)}>
                <Filter className="size-4 mr-2" />
                {filterWarnings ? "Show all" : "Show warnings only"}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => gradingRubricId && fetchSubmissionsForRubric(gradingRubricId)}
                disabled={!gradingRubricId || submissionsLoading}
              >
                <RefreshCw className={`size-4 mr-2 ${submissionsLoading ? "animate-spin" : ""}`} />
                Refresh
              </Button>
              <Badge className="bg-violet-50 text-violet-700 border-0">
                {dashboardStudents.filter((s) => s.status === "completed").length}/
                {dashboardStudents.length} graded
              </Badge>
            </div>
          </div>

          <Card className="p-6 border-slate-200">
            {submissionsLoading && dashboardStudents.length === 0 ? (
              <div className="flex items-center gap-2 py-8 text-slate-500 text-sm justify-center">
                <RefreshCw className="size-5 animate-spin" /> Loading submissions…
              </div>
            ) : dashboardStudents.length === 0 ? (
              <p className="text-sm text-slate-500 py-6 text-center">
                No submissions for this rubric yet. Run batch grading from the previous step.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="border-b border-slate-200">
                    <tr className="text-left text-xs text-slate-500 uppercase tracking-wide">
                      <th className="pb-3">Student ID</th>
                      <th className="pb-3">Status</th>
                      <th className="pb-3">OCR confidence</th>
                      <th className="pb-3">Quick grade</th>
                      <th className="pb-3">Action</th>
                    </tr>
                  </thead>
                  <tbody className="text-sm">
                    {filteredStudents.map((student) => (
                      <tr key={student.submissionId ?? student.id} className="border-b border-slate-100 hover:bg-slate-50">
                        <td className="py-3 text-slate-900 font-mono text-xs">{student.id}</td>
                        <td className="py-3">
                          <Badge
                            className={
                              student.status === "completed"
                                ? "bg-emerald-50 text-emerald-700 border-0"
                                : student.status === "processing"
                                  ? "bg-blue-50 text-blue-700 border-0"
                                  : "bg-amber-50 text-amber-700 border-0"
                            }
                          >
                            {student.status === "processing" && (
                              <RefreshCw className="size-3 mr-1 animate-spin" />
                            )}
                            {student.status === "warning" && <AlertCircle className="size-3 mr-1" />}
                            {student.status === "completed" && <CheckCircle2 className="size-3 mr-1" />}
                            {student.status.charAt(0).toUpperCase() + student.status.slice(1)}
                          </Badge>
                        </td>
                        <td className="py-3 text-xs text-slate-500">
                          {typeof student.ocrConf === "number" ? `${student.ocrConf}%` : "—"}
                        </td>
                        <td className="py-3">
                          {student.quickGrade !== undefined ? (
                            <span className="text-slate-900 tabular-nums">
                              {student.quickGrade}/{student.maxGrade || "—"}
                            </span>
                          ) : (
                            <span className="text-slate-400">—</span>
                          )}
                        </td>
                        <td className="py-3">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => viewStudentDetail(student)}
                            disabled={student.status === "processing"}
                          >
                            View full report
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <div className="flex gap-3">
            <Button variant="outline" onClick={() => setPage(1)}>
              <ArrowLeft className="size-4 mr-2" /> Back to Dashboard
            </Button>
            <Button className="bg-violet-600 hover:bg-violet-700" onClick={() => setPage(7)}>
              View Analytics & Export <ArrowRight className="size-4 ml-2" />
            </Button>
          </div>
        </div>
      )}

      {/* ═══ PAGE 6: AI-Assisted Review ═══ */}
      {page === 6 && selectedStudent && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="tracking-tight text-slate-900">AI-Assisted Review</h2>
              <p className="text-sm text-slate-500 mt-1">Student ID: {selectedStudent.id}</p>
            </div>
            <AIBadgePill model="lexo" />
          </div>

          <div className="grid lg:grid-cols-2 gap-6">
            {/* Left: Original Scan */}
            <Card className="border-slate-200 overflow-hidden flex flex-col">
              <div className="px-4 py-2.5 border-b border-slate-100 flex items-center justify-between bg-slate-50">
                <div className="flex items-center gap-2 text-sm text-slate-600">
                  <FileImage className="size-4" />
                  Original Scan
                </div>
                <div className="flex items-center gap-1">
                  <Button size="icon" variant="ghost" className="size-7" onClick={() => setZoom(z => Math.max(50, z - 25))}>
                    <ZoomOut className="size-3.5" />
                  </Button>
                  <span className="text-xs text-slate-500 w-10 text-center">{zoom}%</span>
                  <Button size="icon" variant="ghost" className="size-7" onClick={() => setZoom(z => Math.min(200, z + 25))}>
                    <ZoomIn className="size-3.5" />
                  </Button>
                </div>
              </div>

              <div className="flex-1 bg-slate-100 overflow-auto" style={{ minHeight: "500px" }}>
                <div className="p-6 flex items-start justify-center" style={{ transform: `scale(${zoom / 100})`, transformOrigin: "top center" }}>
                  <div className="bg-white rounded-lg shadow-sm p-6 max-w-lg w-full">
                    <div className="text-xs text-slate-400 uppercase tracking-wider">OCR transcript preview</div>
                    <div className="mt-2 text-slate-900 tracking-tight text-sm">Student ID: {selectedStudent.id}</div>
                    <div className="mt-4 text-slate-700 text-sm leading-relaxed whitespace-pre-wrap max-h-[420px] overflow-y-auto border border-slate-100 rounded-md p-3 bg-slate-50/50">
                      {parsedText || "No OCR text stored for this submission."}
                    </div>
                  </div>
                </div>
              </div>
            </Card>

            {/* Right: Digital Workspace */}
            <div className="space-y-4">
              <Card className="border-slate-200">
                <div className="border-b border-slate-100 bg-slate-50">
                  <div className="flex gap-1 p-1">
                    <button
                      onClick={() => setReviewTab("parsed")}
                      className={`flex-1 px-3 py-2 rounded text-sm transition-colors ${reviewTab === "parsed" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
                    >
                      <Type className="size-4 inline mr-2" />
                      Parsed Text
                    </button>
                    <button
                      onClick={() => setReviewTab("analysis")}
                      className={`flex-1 px-3 py-2 rounded text-sm transition-colors ${reviewTab === "analysis" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
                    >
                      <Cpu className="size-4 inline mr-2" />
                      AI Analysis
                    </button>
                  </div>
                </div>

                <div className="p-5">
                  {reviewTab === "parsed" ? (
                    <div>
                      <div className="text-xs text-slate-500 mb-2">OCR Output (editable)</div>
                      <Textarea
                        value={parsedText}
                        onChange={(e) => setParsedText(e.target.value)}
                        className="font-mono text-xs"
                        rows={18}
                      />
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="text-xs text-slate-500 mb-3">Score breakdown (from API)</div>
                      {Array.isArray(selectedStudent.evaluation?.results) &&
                      (selectedStudent.evaluation?.results as unknown[]).length > 0 ? (
                        (selectedStudent.evaluation?.results as Record<string, unknown>[]).map((row, i) => {
                          const score = typeof row.score === "number" ? row.score : Number(row.score ?? 0);
                          const qNo = row.q_no ?? row.question_no ?? i + 1;
                          const justification = String(row.justification ?? "");
                          const feedback = String(row.feedback ?? "");
                          return (
                            <div key={i} className="pb-3 border-b border-slate-100 last:border-0">
                              <div className="flex items-center justify-between mb-2">
                                <span className="text-sm text-slate-700">Q{String(qNo)}</span>
                                <span className="text-sm text-slate-900 tabular-nums">{Number.isFinite(score) ? score : "—"}</span>
                              </div>
                              {justification && (
                                <p className="text-xs text-slate-600 leading-relaxed">{justification}</p>
                              )}
                              {feedback && (
                                <p className="text-xs text-slate-500 mt-1 italic">{feedback}</p>
                              )}
                            </div>
                          );
                        })
                      ) : (
                        <p className="text-sm text-slate-500">
                          No structured results on this submission yet.
                        </p>
                      )}
                      {selectedStudent.evaluation &&
                        typeof selectedStudent.evaluation.total_score === "number" && (
                          <div className="pt-2 text-sm font-medium text-slate-800">
                            Total: {selectedStudent.evaluation.total_score as number}
                          </div>
                        )}
                    </div>
                  )}
                </div>
              </Card>

              <Card className="p-5 border-slate-200">
                <div className="text-sm text-slate-700 mb-2">Manual Override</div>
                <Textarea
                  value={lecturerNote}
                  onChange={(e) => setLecturerNote(e.target.value)}
                  placeholder="Add lecturer notes or adjust marks manually…"
                  rows={3}
                />
                <Button className="w-full mt-3 bg-blue-600 hover:bg-blue-700">
                  <Save className="size-4 mr-2" /> Save Changes
                </Button>
              </Card>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <Button variant="outline" onClick={() => setPage(5)}>
              <ArrowLeft className="size-4 mr-2" /> Back to Dashboard
            </Button>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => navigateStudent("prev")} disabled={currentStudentIndex === 0}>
                <ArrowLeft className="size-4 mr-2" /> Previous Student
              </Button>
              <Button variant="outline" onClick={() => navigateStudent("next")} disabled={currentStudentIndex >= dashboardStudents.length - 1}>
                Next Student <ArrowRight className="size-4 ml-2" />
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ═══ PAGE 7: Analytics & Export ═══ */}
      {page === 7 && (
        <div className="space-y-6">
          <div>
            <h2 className="tracking-tight text-slate-900">Analytics & Export</h2>
            <p className="text-sm text-slate-500 mt-1">Final insights and export options</p>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            {/* Grade Distribution */}
            <Card className="p-6 border-slate-200">
              <h3 className="text-lg text-slate-900 mb-4">Grade Distribution</h3>
              <div className="space-y-3">
                {["0-40", "40-50", "50-60", "60-70", "70-80", "80-100"].map((range, i) => (
                  <div key={i}>
                    <div className="flex items-center justify-between text-sm mb-1">
                      <span className="text-slate-600">{range}</span>
                      <span className="text-slate-900">{gradeDistribution[i]} students</span>
                    </div>
                    <div className="bg-slate-100 rounded-full h-2 overflow-hidden">
                      <div
                        className="h-full bg-violet-600 rounded-full transition-all"
                        style={{ width: `${(gradeDistribution[i] / 25) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </Card>

            {/* Topic Mastery */}
            <Card className="p-6 border-slate-200">
              <h3 className="text-lg text-slate-900 mb-4">Topic Mastery</h3>
              <div className="space-y-3">
                {rubric.map((r, i) => (
                  <div key={i}>
                    <div className="flex items-center justify-between text-sm mb-1">
                      <span className="text-slate-600">{r.questionNo}</span>
                      <span className="text-slate-900">{[72, 58, 85, 64][i]}% avg</span>
                    </div>
                    <div className="bg-slate-100 rounded-full h-2 overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${[72, 58, 85, 64][i] >= 70 ? "bg-emerald-500" : [72, 58, 85, 64][i] >= 50 ? "bg-amber-500" : "bg-red-500"}`}
                        style={{ width: `${[72, 58, 85, 64][i]}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          {/* Export Actions */}
          <Card className="p-6 border-slate-200">
            <h3 className="text-lg text-slate-900 mb-4">Export Actions</h3>
            <div className="grid md:grid-cols-2 gap-4">
              <Button variant="outline" className="justify-start h-auto py-4">
                <div className="flex items-start gap-3 w-full">
                  <FileSpreadsheet className="size-5 text-emerald-600 shrink-0 mt-0.5" />
                  <div className="text-left flex-1">
                    <div className="text-sm text-slate-900">Download CSV</div>
                    <div className="text-xs text-slate-500 mt-0.5">Student ID and marks for university records</div>
                  </div>
                  <Download className="size-4 text-slate-400 shrink-0" />
                </div>
              </Button>

              <Button variant="outline" className="justify-start h-auto py-4">
                <div className="flex items-start gap-3 w-full">
                  <FileText className="size-5 text-blue-600 shrink-0 mt-0.5" />
                  <div className="text-left flex-1">
                    <div className="text-sm text-slate-900">Generate PDF Pack</div>
                    <div className="text-xs text-slate-500 mt-0.5">Individual feedback reports for every student</div>
                  </div>
                  <Download className="size-4 text-slate-400 shrink-0" />
                </div>
              </Button>
            </div>
          </Card>

          <div className="flex gap-3">
            <Button variant="outline" onClick={() => setPage(5)}>
              <ArrowLeft className="size-4 mr-2" /> Back to Dashboard
            </Button>
            <Button className="bg-violet-600 hover:bg-violet-700" onClick={() => setPage(1)}>
              <CheckCircle2 className="size-4 mr-2" /> Finish Session
            </Button>
          </div>
        </div>
      )}

      <Dialog open={rubricPickerOpen} onOpenChange={setRubricPickerOpen}>
        <DialogContent className="sm:max-w-lg max-h-[90vh] flex flex-col">
          <DialogHeader>
            <DialogTitle>Select rubric for batch grading</DialogTitle>
            <DialogDescription>
              Pick the marking scheme (MongoDB document) to use for OCR + AI grading. Your current session rubric is selected by default when available.
            </DialogDescription>
          </DialogHeader>
          <div className="min-h-0 flex-1 overflow-y-auto space-y-2 pr-1">
            {rubricsListLoading ? (
              <div className="flex justify-center py-10 text-slate-500">
                <RefreshCw className="size-6 animate-spin" />
              </div>
            ) : rubricsList.length === 0 ? (
              <p className="text-sm text-slate-500 py-4">
                No rubrics in the database yet. Use Session Initialization to upload a marking PDF, or seed rubrics via the API.
              </p>
            ) : (
              rubricsList.map((r) => (
                <button
                  key={r._id}
                  type="button"
                  onClick={() => setPendingRubricId(r._id)}
                  className={`w-full text-left rounded-lg border p-3 text-sm transition-colors ${
                    pendingRubricId === r._id
                      ? "border-violet-500 bg-violet-50"
                      : "border-slate-200 hover:bg-slate-50"
                  }`}
                >
                  <div className="font-mono text-[11px] text-slate-500 break-all">{r._id}</div>
                  <div className="font-medium text-slate-900 mt-0.5">{r.session_name ?? "—"}</div>
                  <div className="text-xs text-slate-600 mt-0.5">
                    {r.subject_code ?? "—"}
                    {r.filename ? ` · ${r.filename}` : ""}
                  </div>
                </button>
              ))
            )}
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="outline" onClick={() => setRubricPickerOpen(false)}>
              Cancel
            </Button>
            <Button
              type="button"
              className="bg-violet-600 hover:bg-violet-700"
              disabled={!pendingRubricId}
              onClick={() => {
                if (pendingRubricId) {
                  setGradingRubricId(pendingRubricId);
                  setRubricPickerOpen(false);
                }
              }}
            >
              Use this rubric
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}