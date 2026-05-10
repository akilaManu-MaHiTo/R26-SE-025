import { useState, useRef } from "react";
import { Upload, Play, CheckCircle2, Mic, FileDown, Sparkles, Pause, Loader2 } from "lucide-react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Progress } from "./ui/progress";
import { Input } from "./ui/input";
import { Checkbox } from "./ui/checkbox";
import { AIPageBanner, AIBadgePill } from "./AIBrand";

const criteria = [
  { name: "Communication Skills", score: 8, max: 10 },
  { name: "Technical Knowledge", score: 7, max: 10 },
  { name: "Problem-Solving", score: 9, max: 10 },
  { name: "Presentation Quality", score: 7, max: 10 },
];

const emotionColor: Record<string, string> = {
  happy: "bg-emerald-500",
  sad: "bg-blue-500",
  angry: "bg-red-500",
  disgust: "bg-amber-500",
  fear: "bg-purple-500",
  surprise: "bg-pink-500",
  contempt: "bg-orange-500",
  neutral: "bg-slate-400",
};

type TimelineEntry = {
  time: number;
  emotion: string;
  emotion_confidence: number;
  valid: boolean;
};

type VivaResult = {
  confidence_score: number;
  engagement_score: number;
  summary?: {
    positive_ratio: number;
    neutral_ratio: number;
    negative_ratio: number;
  };
  timeline?: TimelineEntry[];
};

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

export function VivaPage() {
  const total = criteria.reduce((a, b) => a + b.score, 0);
  const max = criteria.reduce((a, b) => a + b.max, 0);
  
  const [uploadStatus, setUploadStatus] = useState<"idle" | "uploaded" | "processing" | "success" | "error">("idle");
  const [result, setResult] = useState<VivaResult | null>(null);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (file: File) => {
    setVideoFile(file);
    setVideoUrl(URL.createObjectURL(file));
    setUploadStatus("uploaded");
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith("video/")) {
      handleFileSelect(file);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const startAnalysis = async () => {
    if (!videoFile) return;
    
    setUploadStatus("processing");
    
    const formData = new FormData();
    formData.append("video", videoFile);
    
    try {
      const response = await fetch("/api/viva/evaluate", {
        method: "POST",
        body: formData,
      });
      
      if (!response.ok) {
        throw new Error(await response.text());
      }
      
      const data = await response.json();
      setResult(data);
      setUploadStatus("success");
    } catch (error) {
      console.error("Upload failed:", error);
      setUploadStatus("error");
    }
  };

  const triggerFileSelect = () => {
    if (uploadStatus === "processing") return;
    fileInputRef.current?.click();
  };

  const isProcessing = uploadStatus === "processing";
  const hasVideo = videoFile !== null;

  return (
    <div className="p-8 space-y-6">
      <AIPageBanner model="voca" />

      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className="tracking-tight text-slate-900">Viva Assessment</h2>
          <p className="text-sm text-slate-500 mt-1">Upload, transcribe and score viva voce sessions with AI assistance.</p>
        </div>
        <div className="flex items-center gap-3">
          <AIBadgePill model="voca" />
          <Button className="bg-blue-600 hover:bg-blue-700"><FileDown className="size-4 mr-2" />Export report</Button>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Card className="p-6 border-slate-200">
            <div className="flex items-center justify-between">
              <div className="text-slate-900">Recording</div>
              <Badge className={
                uploadStatus === "success" 
                  ? "bg-emerald-50 text-emerald-700 border-0 hover:bg-emerald-50"
                  : uploadStatus === "processing"
                  ? "bg-blue-50 text-blue-700 border-0"
                  : uploadStatus === "uploaded"
                  ? "bg-amber-50 text-amber-700 border-0"
                  : "bg-slate-100 text-slate-500 border-0"
              }>
                {uploadStatus === "success" ? (
                  <>
                    <CheckCircle2 className="size-3 mr-1" /> Analyzed
                  </>
                ) : uploadStatus === "processing" ? (
                  <>Processing...</>
                ) : uploadStatus === "uploaded" ? (
                  <>Ready to analyze</>
                ) : (
                  <>Pending upload</>
                )}
              </Badge>
            </div>

            {!hasVideo ? (
              <div 
                className="mt-4 rounded-xl border-2 border-dashed border-slate-200 bg-slate-50/40 p-6 hover:border-blue-300 hover:bg-blue-50/40 transition-colors cursor-pointer text-center"
                onDrop={handleDrop}
                onDragOver={(e) => e.preventDefault()}
                onClick={triggerFileSelect}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="video/*"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <div className="size-12 rounded-full bg-blue-100 mx-auto flex items-center justify-center text-blue-600">
                  <Upload className="size-6" />
                </div>
                <div className="text-sm text-slate-900 mt-3">
                  Drag & drop a viva recording
                </div>
                <div className="text-xs text-slate-500 mt-1">Supports MP4, AVI, MOV · up to 1 GB</div>
              </div>
            ) : (
              <div className="mt-4 space-y-4">
                <div className="rounded-xl bg-slate-900 aspect-video relative overflow-hidden">
                  {isProcessing && (
                    <div className="absolute inset-0 bg-black/60 flex items-center justify-center z-10">
                      <div className="text-center">
                        <Loader2 className="size-10 animate-spin text-white mx-auto mb-2" />
                        <div className="text-white text-sm">Analyzing video...</div>
                      </div>
                    </div>
                  )}
                  <video
                    src={videoUrl || undefined}
                    className="w-full h-full object-contain"
                    controls={uploadStatus === "success"}
                    muted
                  />
                  <div className="absolute top-3 left-3 flex items-center gap-2">
                    <span className="size-2 rounded-full bg-red-500 animate-pulse" />
                    <span className="text-white/80 text-xs">{videoFile?.name || "viva_session_24.mp4"}</span>
                  </div>
                </div>

                {uploadStatus === "uploaded" && (
                  <div className="flex justify-center">
                    <Button 
                      className="bg-blue-600 hover:bg-blue-700"
                      onClick={startAnalysis}
                    >
                      Analyze Video
                    </Button>
                  </div>
                )}

                {uploadStatus === "error" && (
                  <div className="flex justify-center">
                    <Button 
                      className="bg-blue-600 hover:bg-blue-700"
                      onClick={startAnalysis}
                    >
                      Retry Analysis
                    </Button>
                  </div>
                )}
              </div>
            )}

            {uploadStatus === "success" && result && (
              <div className="mt-6 grid grid-cols-2 gap-4">
                <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl p-4 border border-blue-200">
                  <div className="text-xs text-blue-700 uppercase tracking-wide">Confidence Score</div>
                  <div className="text-3xl font-bold text-blue-900 mt-1">{result.confidence_score.toFixed(1)}<span className="text-lg text-blue-600">/100</span></div>
                </div>
                <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-xl p-4 border border-purple-200">
                  <div className="text-xs text-purple-700 uppercase tracking-wide">Engagement Score</div>
                  <div className="text-3xl font-bold text-purple-900 mt-1">{result.engagement_score.toFixed(1)}<span className="text-lg text-purple-600">/100</span></div>
                </div>
              </div>
            )}

            {uploadStatus === "success" && result?.summary && (
              <div className="mt-4 p-3 rounded-lg bg-slate-50 border border-slate-200">
                <div className="text-xs font-medium text-slate-700 mb-2">Emotion Summary</div>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div>
                    <div className="text-xs text-emerald-600">Positive</div>
                    <div className="font-semibold text-slate-900">{Math.round(result.summary.positive_ratio * 100)}%</div>
                  </div>
                  <div>
                    <div className="text-xs text-blue-600">Neutral</div>
                    <div className="font-semibold text-slate-900">{Math.round(result.summary.neutral_ratio * 100)}%</div>
                  </div>
                  <div>
                    <div className="text-xs text-amber-600">Negative</div>
                    <div className="font-semibold text-slate-900">{Math.round(result.summary.negative_ratio * 100)}%</div>
                  </div>
                </div>
              </div>
            )}

            {uploadStatus === "success" && result?.timeline && result.timeline.length > 0 && (
              <div className="mt-5">
                <div className="flex items-center justify-between mb-2">
                  <div className="text-sm text-slate-900">Emotion Timeline</div>
                  <div className="text-xs text-slate-500">Frame-by-frame analysis</div>
                </div>
                <div className="max-h-64 overflow-y-auto pr-2 space-y-1">
                  {result.timeline.map((entry, i) => {
                    const emotionColorClass = emotionColor[entry.emotion] || "bg-slate-400";
                    return (
                      <div key={i} className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-slate-50">
                        <span className={`size-2 rounded-full ${emotionColorClass}`} />
                        <span className="text-xs font-mono text-slate-500 w-16">{formatTime(entry.time)}</span>
                        <span className="text-sm text-slate-700 capitalize flex-1">{entry.emotion}</span>
                        <span className="text-xs text-slate-500 w-12 text-right">
                          {Math.round(entry.emotion_confidence * 100)}%
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </Card>

          <Card className="p-6 border-slate-200">
            <div className="flex items-center justify-between">
              <div className="text-slate-900">Transcript</div>
              <Badge variant="secondary" className="bg-blue-50 text-blue-700 border-0">
                <Sparkles className="size-3 mr-1" /> AI generated
              </Badge>
            </div>
            <div className="mt-4 space-y-4 max-h-72 overflow-y-auto pr-2">
              {[
                { who: "Examiner", t: "00:12", text: "Could you walk us through the architecture of your database project?" },
                { who: "Student", t: "00:24", text: "Sure. The system uses a normalized schema with five core entities. The user table stores authentication data, while the activities table…" },
                { who: "Examiner", t: "02:08", text: "How did you decide between B+ trees and hash indexing?" },
                { who: "Student", t: "02:15", text: "I chose B+ trees for the user_id column because we run a lot of range queries on creation date, and B+ trees keep keys sorted on disk pages…", highlight: true },
                { who: "Examiner", t: "05:00", text: "What about your isolation level — are you comfortable with the trade-offs?" },
                { who: "Student", t: "05:08", text: "I think... I used the default level. I'm not entirely sure what each level guarantees…", flag: true },
              ].map((m, i) => (
                <div key={i} className="flex gap-3">
                  <div className="text-xs font-mono text-slate-400 w-12 shrink-0 mt-0.5">{m.t}</div>
                  <div className="flex-1">
                    <div className="text-xs text-slate-500">{m.who}</div>
                    <div className={
                      "text-sm mt-0.5 " +
                      (m.highlight ? "text-emerald-800 bg-emerald-50 px-2 py-1 rounded" :
                       m.flag ? "text-amber-800 bg-amber-50 px-2 py-1 rounded" :
                       "text-slate-700")
                    }>
                      {m.text}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        <div className="space-y-6">
          <Card className="p-5 border-slate-200">
            <div className="text-slate-900">Recording checklist</div>
            <div className="mt-3 space-y-2.5">
              {[
                "Audio is clear & free of noise",
                "Both examiner and student visible",
                "Session ≥ 10 minutes",
                "Slides/notes shared on screen",
                "Consent acknowledged",
              ].map((g, i) => (
                <label key={g} className="flex items-center gap-2.5 text-sm text-slate-700">
                  <Checkbox defaultChecked={i < 4} /> {g}
                </label>
              ))}
            </div>
          </Card>

          <Card className="p-5 border-slate-200">
            <div className="flex items-center justify-between">
              <div className="text-slate-900">Evaluation rubric</div>
              <Badge className="bg-blue-50 text-blue-700 border-0 hover:bg-blue-50">AI scored</Badge>
            </div>
            <div className="mt-4 space-y-4">
              {criteria.map((c) => (
                <div key={c.name}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-700">{c.name}</span>
                    <span className="text-slate-900">{c.score}/{c.max}</span>
                  </div>
                  <Progress value={(c.score / c.max) * 100} className="h-1.5 mt-1.5" />
                </div>
              ))}
            </div>

            <div className="mt-5 pt-4 border-t border-slate-100">
              <div className="flex items-end justify-between">
                <div>
                  <div className="text-xs text-slate-500 uppercase tracking-wide">Total</div>
                  <div className="tracking-tight text-slate-900 mt-0.5">
                    <span className="text-3xl">{total}</span><span className="text-slate-400">/{max}</span>
                  </div>
                </div>
                <Badge className="bg-emerald-50 text-emerald-700 border-0 hover:bg-emerald-50">Distinction</Badge>
              </div>
            </div>

            <div className="mt-4 p-3 rounded-lg bg-blue-50 border border-blue-100 text-xs text-blue-900">
              <span className="text-blue-700">AI recommendation:</span> Strong technical clarity. Consider deeper questions on isolation levels in next viva.
            </div>

            <div className="mt-4">
              <label className="text-sm text-slate-700">Final grade (override)</label>
              <Input className="mt-1.5" defaultValue="A" />
            </div>
            <Button className="w-full mt-4 bg-blue-600 hover:bg-blue-700">Save & publish</Button>
          </Card>
        </div>
      </div>
    </div>
  );
}