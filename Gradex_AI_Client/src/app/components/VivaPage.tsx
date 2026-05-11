"use client";

import { Upload, Play, CheckCircle2, Mic, FileDown, Sparkles, Pause, Loader2, AlertCircle, Clock } from "lucide-react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Progress } from "./ui/progress";
import { Input } from "./ui/input";
import { Checkbox } from "./ui/checkbox";
import { AIPageBanner, AIBadgePill } from "./AIBrand";
import { useState, useRef } from "react";

const criteria = [
  { name: "Communication Skills", score: 8, max: 10 },
  { name: "Technical Knowledge", score: 7, max: 10 },
  { name: "Problem-Solving", score: 9, max: 10 },
  { name: "Presentation Quality", score: 7, max: 10 },
];

const toneColor: Record<string, string> = {
  good: "bg-emerald-500",
  warn: "bg-amber-500",
  neutral: "bg-blue-500",
  negative: "bg-red-500",
};

interface TimelineItem {
  time: number;
  emotion: string;
  emotion_confidence: number;
  engagement_label?: string;
  engagement_confidence?: number;
  engagement_model_score?: number;
  valid: boolean;
}

interface AnalysisResult {
  timeline: TimelineItem[];
  confidence_score: number;
  engagement_score: number;
  summary: {
    positive_ratio: number;
    neutral_ratio: number;
    negative_ratio: number;
  };
}

export function VivaPage() {
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [videoPreview, setVideoPreview] = useState<string>("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string>("");
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const total = criteria.reduce((a, b) => a + b.score, 0);
  const max = criteria.reduce((a, b) => a + b.max, 0);

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileSelect(files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileSelect(e.target.files[0]);
    }
  };

  const handleFileSelect = (file: File) => {
    // Validate file type
    if (!file.type.startsWith("video/")) {
      setError("Please upload a valid video file (MP4, AVI, MOV, etc.)");
      return;
    }

    // Validate file size (1 GB)
    const maxSize = 1024 * 1024 * 1024; // 1 GB
    if (file.size > maxSize) {
      setError("File size must be less than 1 GB");
      return;
    }

    setError("");
    setUploadedFile(file);

    // Create preview URL
    const preview = URL.createObjectURL(file);
    setVideoPreview(preview);
    // Do not auto-start analysis — wait for user to click Analyze
  };

  const analyzeVideo = async (file: File) => {
    if (!file) return;

    setIsAnalyzing(true);
    setError("");
    const formData = new FormData();
    formData.append("video", file);

    try {
      // Use Vite env flag in development, absolute in production
      const apiUrl = import.meta.env.DEV
        ? "/api/viva-analyze"
        : "http://localhost:8000/api/viva-analyze";
      
      const response = await fetch(apiUrl, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Analysis failed with status ${response.status}`);
      }

      const data = await response.json();
      setAnalysisResult(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to analyze video";
      setError(message);
      console.error("Analysis error:", err);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  };

  const getEmotionColor = (emotion: string): string => {
    const positive = ["happy", "surprise"];
    const negative = ["sad", "angry", "fear", "disgust", "contempt"];
    
    if (positive.includes(emotion.toLowerCase())) return "bg-emerald-500";
    if (negative.includes(emotion.toLowerCase())) return "bg-red-500";
    return "bg-blue-500";
  };

  const generateKeyMoments = (): Array<{ t: string; label: string; tone: string; time: number }> => {
    if (!analysisResult || analysisResult.timeline.length === 0) return [];

    const timeline = analysisResult.timeline.filter(item => item.valid);
    const moments = [];

    // Find emotional peaks
    let maxConfidence = 0;
    let maxIndex = 0;
    for (let i = 0; i < timeline.length; i++) {
      if (timeline[i].emotion_confidence > maxConfidence) {
        maxConfidence = timeline[i].emotion_confidence;
        maxIndex = i;
      }
    }

    // Add the peak moment
    if (maxConfidence > 0.5) {
      moments.push({
        t: formatTime(timeline[maxIndex].time),
        label: `Strong ${timeline[maxIndex].emotion} detected (${(maxConfidence * 100).toFixed(0)}%)`,
        tone: timeline[maxIndex].emotion === "contempt" || timeline[maxIndex].emotion === "disgust" ? "negative" : "good",
        time: timeline[maxIndex].time,
      });
    }

    // Add transitions
    for (let i = 1; i < timeline.length; i++) {
      if (timeline[i].emotion !== timeline[i - 1].emotion) {
        moments.push({
          t: formatTime(timeline[i].time),
          label: `Emotional shift to ${timeline[i].emotion}`,
          tone: getEmotionColor(timeline[i].emotion) === "bg-emerald-500" ? "good" : "warn",
          time: timeline[i].time,
        });
        if (moments.length >= 5) break;
      }
    }

    return moments.slice(0, 5);
  };

  const keyMoments = generateKeyMoments();

  return (
    <div className="p-8 space-y-6">
      {/* AI Page Banner */}
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
          {/* Error Alert */}
          {error && (
            <Card className="p-4 border-red-200 bg-red-50">
              <div className="flex items-start gap-3">
                <AlertCircle className="size-5 text-red-600 mt-0.5 shrink-0" />
                <div className="flex-1">
                  <div className="text-sm font-medium text-red-900">Analysis Error</div>
                  <div className="text-sm text-red-800 mt-1">{error}</div>
                </div>
              </div>
            </Card>
          )}

          {/* Upload */}
          <Card className="p-6 border-slate-200">
            <div className="flex items-center justify-between">
              <div className="text-slate-900">Recording</div>
              {uploadedFile && (
                <Badge className="bg-emerald-50 text-emerald-700 border-0 hover:bg-emerald-50">
                  <CheckCircle2 className="size-3 mr-1" /> Uploaded
                </Badge>
              )}
            </div>

            {/* Upload area — becomes preview + actions after file is selected */}
            {!videoPreview ? (
              <div
                className={`mt-4 rounded-xl border-2 border-dashed p-6 text-center cursor-pointer transition-colors ${
                  isDragging
                    ? "border-blue-400 bg-blue-50/60"
                    : "border-slate-200 bg-slate-50/40 hover:border-blue-300 hover:bg-blue-50/40"
                }`}
                onDragEnter={handleDragEnter}
                onDragLeave={handleDragLeave}
                onDragOver={handleDragOver}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
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
                <div className="text-sm text-slate-900 mt-3">Drag & drop a viva recording</div>
                <div className="text-xs text-slate-500 mt-1">Supports MP4, AVI, MOV · up to 1 GB</div>
                {uploadedFile && <div className="text-xs text-emerald-700 mt-2 font-medium">{uploadedFile.name}</div>}
              </div>
            ) : (
              <>
                <div className="mt-4 rounded-xl bg-slate-900 aspect-video relative overflow-hidden">
                  <video
                    src={videoPreview}
                    className="w-full h-full object-cover"
                    controls
                    controlsList="nodownload"
                  />
                </div>

                <div className="mt-3 flex items-center gap-3">
                  <Button
                    className="bg-blue-600 hover:bg-blue-700"
                    onClick={() => uploadedFile && analyzeVideo(uploadedFile)}
                    disabled={isAnalyzing}
                  >
                    {isAnalyzing ? (
                      <>
                        <Loader2 className="size-4 animate-spin mr-2" />Analyzing...
                      </>
                    ) : (
                      "Analyze"
                    )}
                  </Button>

                  <Button
                    variant="outline"
                    onClick={() => {
                      setUploadedFile(null);
                      setVideoPreview("");
                      setAnalysisResult(null);
                      setError("");
                    }}
                  >
                    Remove
                  </Button>
                </div>
              </>
            )}

            {/* Loading state */}
            {isAnalyzing && (
              <div className="mt-5 p-4 rounded-lg bg-blue-50 border border-blue-100">
                <div className="flex items-center gap-3">
                  <Loader2 className="size-5 text-blue-600 animate-spin" />
                  <div className="text-sm text-blue-900">
                    Analyzing video for emotion detection and engagement scoring...
                  </div>
                </div>
              </div>
            )}

            {/* Analysis Results */}
            {analysisResult && (
              <>
                {/* Scores Display */}
                <div className="mt-5 grid grid-cols-2 gap-4">
                  <div className="p-4 rounded-lg bg-gradient-to-br from-purple-50 to-purple-100/50 border border-purple-200">
                    <div className="text-xs text-purple-700 uppercase tracking-wide font-medium">Confidence Score</div>
                    <div className="text-3xl font-bold text-purple-900 mt-2">
                      {analysisResult.confidence_score.toFixed(2)}
                      <span className="text-sm text-purple-700 font-normal">/10</span>
                    </div>
                    <div className="text-xs text-purple-700 mt-1">Overall detection confidence</div>
                  </div>
                  <div className="p-4 rounded-lg bg-gradient-to-br from-emerald-50 to-emerald-100/50 border border-emerald-200">
                    <div className="text-xs text-emerald-700 uppercase tracking-wide font-medium">Engagement Score</div>
                    <div className="text-3xl font-bold text-emerald-900 mt-2">
                      {analysisResult.engagement_score.toFixed(1)}
                      <span className="text-sm text-emerald-700 font-normal">%</span>
                    </div>
                    <div className="text-xs text-emerald-700 mt-1">Engagement level</div>
                  </div>
                </div>

                {/* Summary Stats */}
                <div className="mt-5 p-4 rounded-lg bg-slate-50 border border-slate-200">
                  <div className="text-sm font-medium text-slate-900 mb-3">Emotion Distribution</div>
                  <div className="space-y-2">
                    <div className="flex items-center gap-3">
                      <div className="text-xs text-slate-600 w-16">Positive</div>
                      <div className="flex-1 h-2 rounded-full bg-slate-200 overflow-hidden">
                        <div
                          className="h-full bg-emerald-500"
                          style={{ width: `${analysisResult.summary.positive_ratio * 100}%` }}
                        />
                      </div>
                      <div className="text-xs font-medium text-slate-900 w-12">
                        {(analysisResult.summary.positive_ratio * 100).toFixed(0)}%
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="text-xs text-slate-600 w-16">Neutral</div>
                      <div className="flex-1 h-2 rounded-full bg-slate-200 overflow-hidden">
                        <div
                          className="h-full bg-blue-500"
                          style={{ width: `${analysisResult.summary.neutral_ratio * 100}%` }}
                        />
                      </div>
                      <div className="text-xs font-medium text-slate-900 w-12">
                        {(analysisResult.summary.neutral_ratio * 100).toFixed(0)}%
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="text-xs text-slate-600 w-16">Negative</div>
                      <div className="flex-1 h-2 rounded-full bg-slate-200 overflow-hidden">
                        <div
                          className="h-full bg-red-500"
                          style={{ width: `${analysisResult.summary.negative_ratio * 100}%` }}
                        />
                      </div>
                      <div className="text-xs font-medium text-slate-900 w-12">
                        {(analysisResult.summary.negative_ratio * 100).toFixed(0)}%
                      </div>
                    </div>
                  </div>
                </div>

                {/* Timeline of moments */}
                {keyMoments.length > 0 && (
                  <div className="mt-5">
                    <div className="flex items-center justify-between mb-2">
                      <div className="text-sm text-slate-900">Key moments</div>
                      <div className="text-xs text-slate-500">AI-detected</div>
                    </div>
                    <div className="space-y-1.5">
                      {keyMoments.map((m) => (
                        <div key={m.time} className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-slate-50 cursor-pointer">
                          <span className={`size-2 rounded-full ${toneColor[m.tone]}`} />
                          <span className="text-xs font-mono text-slate-500 w-12">{m.t}</span>
                          <span className="text-sm text-slate-700 flex-1">{m.label}</span>
                          <Play className="size-3.5 text-slate-400" />
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Full Timeline View */}
                <div className="mt-5">
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-sm text-slate-900">Frame-by-frame analysis</div>
                    <div className="text-xs text-slate-500">{analysisResult.timeline.filter(f => f.valid).length} frames</div>
                  </div>
                  <div className="max-h-64 overflow-y-auto pr-2 space-y-1">
                    {analysisResult.timeline
                      .filter((item) => item.valid)
                      .slice(0, 20)
                      .map((item, idx) => (
                        <div key={idx} className="flex items-center gap-2 text-xs px-2 py-1 rounded hover:bg-slate-50">
                          <Clock className="size-3 text-slate-400" />
                          <span className="font-mono text-slate-500 w-12">{formatTime(item.time)}</span>
                          <span
                            className={`px-2 py-0.5 rounded text-white text-xs font-medium capitalize ${getEmotionColor(
                              item.emotion
                            )}`}
                          >
                            {item.emotion}
                          </span>
                          <span className="text-slate-600">({(item.emotion_confidence * 100).toFixed(0)}%)</span>
                        </div>
                      ))}
                  </div>
                </div>
              </>
            )}
          </Card>

          {/* Transcript - Placeholder */}
          <Card className="p-6 border-slate-200">
            <div className="flex items-center justify-between">
              <div className="text-slate-900">Transcript</div>
              <Badge variant="secondary" className="bg-blue-50 text-blue-700 border-0">
                <Sparkles className="size-3 mr-1" /> AI generated
              </Badge>
            </div>
            <div className="mt-4 p-4 rounded-lg bg-slate-50 border border-slate-100 text-center text-sm text-slate-600">
              {analysisResult ? "Transcript generation coming soon" : "Upload a video to generate transcript"}
            </div>
          </Card>
        </div>

        <div className="space-y-6">
          {/* Guidelines */}
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

          {/* Criteria */}
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
              <span className="text-blue-700">AI recommendation:</span> {analysisResult
                ? `${analysisResult.summary.negative_ratio > 0.5 ? "Negative emotions detected in" : "Mixed emotional responses in"} the recording.`
                : "Upload a video to see AI-generated recommendations."}
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