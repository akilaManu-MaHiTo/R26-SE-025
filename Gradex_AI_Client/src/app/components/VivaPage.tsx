"use client";

import { useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import {
  Upload,
  CheckCircle2,
  FileDown,
  Loader2,
  AlertCircle,
  RotateCcw,
  Clock3,
} from "lucide-react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Skeleton } from "./ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { AIPageBanner, AIBadgePill } from "./AIBrand";
import { VivaVideoPlayer, VivaVideoPlayerHandle } from "./viva/VivaVideoPlayer";
import { ScoreOverview } from "./viva/ScoreOverview";
import { AISummary } from "./viva/AISummary";
import { KeyMoments } from "./viva/KeyMoments";
import { EmotionDistribution } from "./viva/EmotionDistribution";
import { EngagementTimeline } from "./viva/EngagementTimeline";
import { TranscriptPanel } from "./viva/TranscriptPanel";
import { AudioAnalysisPanel } from "./viva/AudioAnalysisPanel";
import { EvaluationPanel } from "./viva/EvaluationPanel";
import {
  AnalysisResult,
  DEFAULT_RUBRIC,
  RubricCriterion,
  buildAIInterpretation,
  buildKeyMoments,
  formatTime,
  suggestGrade,
} from "./viva/types";

export function VivaPage() {
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [videoPreview, setVideoPreview] = useState<string>("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string>("");
  const [isDragging, setIsDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStartTime, setUploadStartTime] = useState<number | null>(null);
  const [analysisPhase, setAnalysisPhase] = useState<"idle" | "uploading" | "processing" | "complete">("idle");
  const [videoDuration, setVideoDuration] = useState<number | null>(null);

  const [criteria, setCriteria] = useState<RubricCriterion[]>(DEFAULT_RUBRIC);
  const [finalGrade, setFinalGrade] = useState<string>("A");
  const [published, setPublished] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const videoPlayerRef = useRef<VivaVideoPlayerHandle>(null);
  const backendBaseUrl =
    ((import.meta as ImportMeta & { env?: { VITE_BACKEND_URL?: string } }).env?.VITE_BACKEND_URL) ??
    "http://localhost:8000";

  const resetAssessmentState = () => {
    setCriteria(DEFAULT_RUBRIC);
    setFinalGrade("A");
    setPublished(false);
  };

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
    if (!file.type.startsWith("video/")) {
      setError("Please upload a valid video file (MP4, AVI, MOV, etc.)");
      return;
    }

    const maxSize = 1024 * 1024 * 1024; // 1 GB
    if (file.size > maxSize) {
      setError("File size must be less than 1 GB");
      return;
    }

    setError("");
    setUploadedFile(file);
    setAnalysisResult(null);
    setVideoDuration(null);
    resetAssessmentState();

    const preview = URL.createObjectURL(file);
    setVideoPreview(preview);
  };

  const analyzeVideo = async (file: File) => {
    if (!file) return;

    setIsAnalyzing(true);
    setError("");
    setUploadProgress(0);
    setUploadStartTime(Date.now());
    setAnalysisPhase("uploading");
    const formData = new FormData();
    formData.append("video", file);

    try {
      const apiUrl = `${backendBaseUrl}/api/viva-analyze`;

      const response = await new Promise<string>((resolve, reject) => {
        const xhr = new XMLHttpRequest();

        xhr.upload.addEventListener("progress", (e: ProgressEvent) => {
          if (e.lengthComputable) {
            const progress = (e.loaded / e.total) * 100;
            setUploadProgress(Math.round(progress));
          }
        });

        xhr.addEventListener("load", () => {
          if (xhr.status === 200) {
            setAnalysisPhase("processing");
            resolve(xhr.responseText);
          } else {
            let backendDetail = "";
            try {
              const errorPayload = JSON.parse(xhr.responseText || "{}");
              if (typeof errorPayload?.detail === "string" && errorPayload.detail.trim()) {
                backendDetail = errorPayload.detail.trim();
              }
            } catch {
              // Ignore JSON parse errors and fallback to status text.
            }

            const fallback = `HTTP ${xhr.status}: ${xhr.statusText || "Request failed"}`;
            reject(new Error(backendDetail || fallback));
          }
        });

        xhr.addEventListener("error", () => reject(new Error("Upload failed")));
        xhr.addEventListener("abort", () => reject(new Error("Upload aborted")));

        xhr.open("POST", apiUrl, true);
        xhr.send(formData);
      });

      const data = JSON.parse(response) as AnalysisResult;
      setAnalysisResult(data);
      setAnalysisPhase("complete");
      resetAssessmentState();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to analyze video";
      setError(message);
      setAnalysisPhase("idle");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const seekVideo = (seconds: number) => videoPlayerRef.current?.seekTo(seconds);

  const keyMoments = useMemo(
    () => (analysisResult ? buildKeyMoments(analysisResult.timeline) : []),
    [analysisResult]
  );

  const aiInterpretation = useMemo(
    () => (analysisResult ? buildAIInterpretation(analysisResult) : []),
    [analysisResult]
  );

  const aiRecommendation = analysisResult
    ? aiInterpretation[0] ?? "Analysis complete — review the recording to finalize scoring."
    : "Upload a video to see AI-generated recommendations.";

  const suggestedGrade = useMemo(() => {
    if (!published) return null;
    const total = criteria.reduce((s, c) => s + c.score, 0);
    const max = criteria.reduce((s, c) => s + c.max, 0);
    return suggestGrade(total, max);
  }, [criteria, published]);

  const handlePublish = () => {
    setPublished(true);
    toast.success("Assessment published", {
      description: `Final grade ${finalGrade} saved for this session.`,
    });
  };

  const audioAnalysis = analysisResult?.audio_analysis;

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6">
      <AIPageBanner model="voca" />

      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className="tracking-tight text-foreground">Viva Assessment</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Upload, transcribe and score viva voce sessions with AI assistance.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <AIBadgePill model="voca" />
          <Button disabled={!analysisResult}>
            <FileDown className="size-4" />
            Export report
          </Button>
        </div>
      </div>

      {error && (
        <Card className="p-4 border-destructive/30 bg-destructive/5">
          <div className="flex items-start gap-3">
            <AlertCircle className="size-5 text-destructive mt-0.5 shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-destructive">Analysis Error</div>
              <div className="text-sm text-destructive/90 mt-1">{error}</div>
            </div>
            {uploadedFile && (
              <Button size="sm" variant="outline" onClick={() => analyzeVideo(uploadedFile)}>
                <RotateCcw className="size-3.5" />
                Retry
              </Button>
            )}
          </div>
        </Card>
      )}

      {!videoPreview && (
        <Card className="p-6">
          <div
            className={`rounded-xl border-2 border-dashed p-10 text-center cursor-pointer transition-colors ${
              isDragging
                ? "border-primary bg-primary/5"
                : "border-border bg-muted/30 hover:border-primary/40 hover:bg-muted/50"
            }`}
            onDragEnter={handleDragEnter}
            onDragLeave={handleDragLeave}
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") fileInputRef.current?.click();
            }}
            aria-label="Upload a viva recording"
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="video/*"
              onChange={handleFileChange}
              className="hidden"
            />
            <div className="size-14 rounded-full bg-primary/10 mx-auto flex items-center justify-center text-primary">
              <Upload className="size-6" />
            </div>
            <div className="text-sm text-foreground mt-4">Drag & drop a viva recording, or click to browse</div>
            <div className="text-xs text-muted-foreground mt-1">Supports MP4, AVI, MOV · up to 1 GB</div>
          </div>
        </Card>
      )}

      {videoPreview && !analysisResult && (
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="text-foreground font-medium">Recording</div>
            <Badge className="bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400 border-0">
              <CheckCircle2 className="size-3 mr-1" /> Uploaded
            </Badge>
          </div>

          <VivaVideoPlayer
            ref={videoPlayerRef}
            src={videoPreview}
            durationLabel={videoDuration != null ? formatTime(videoDuration) : undefined}
            onDurationChange={setVideoDuration}
          />

          <div className="mt-3 flex items-center gap-3">
            <Button onClick={() => uploadedFile && analyzeVideo(uploadedFile)} disabled={isAnalyzing}>
              {isAnalyzing ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Analyzing…
                </>
              ) : (
                "Analyze"
              )}
            </Button>
            <Button
              variant="outline"
              disabled={isAnalyzing}
              onClick={() => {
                setUploadedFile(null);
                setVideoPreview("");
                setAnalysisResult(null);
                setError("");
                resetAssessmentState();
              }}
            >
              Remove
            </Button>
            {uploadedFile && (
              <span className="text-xs text-muted-foreground ml-auto truncate max-w-[40%]">
                {uploadedFile.name}
              </span>
            )}
          </div>

          {isAnalyzing && (
            <div className="mt-5 space-y-3">
              {analysisPhase === "uploading" && (
                <div className="p-4 rounded-lg bg-primary/5 border border-primary/10">
                  <div className="flex items-center gap-3 mb-2">
                    <Loader2 className="size-5 text-primary animate-spin" />
                    <div className="text-sm font-medium text-foreground">
                      Uploading video ({uploadProgress}%)
                    </div>
                  </div>
                  <div className="w-full h-2 rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full bg-primary transition-all duration-300"
                      style={{ width: `${uploadProgress}%` }}
                    />
                  </div>
                  <div className="text-xs text-muted-foreground mt-2">
                    {uploadedFile ? `${(uploadedFile.size / 1024 / 1024).toFixed(2)} MB` : ""}
                    {uploadStartTime ? ` · Elapsed ${Math.round((Date.now() - uploadStartTime) / 1000)}s` : ""}
                  </div>
                </div>
              )}

              {analysisPhase === "processing" && (
                <div className="space-y-3">
                  <div className="p-4 rounded-lg bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/20">
                    <div className="flex items-center gap-3">
                      <Loader2 className="size-5 text-amber-600 dark:text-amber-400 animate-spin" />
                      <div className="text-sm text-foreground">
                        <div className="font-medium">Analyzing video</div>
                        <div className="text-xs text-muted-foreground mt-1">
                          Processing frames, extracting audio, transcribing…
                          {uploadStartTime && ` (${Math.round((Date.now() - uploadStartTime) / 1000)}s elapsed)`}
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <Skeleton className="h-20" />
                    <Skeleton className="h-20" />
                    <Skeleton className="h-20" />
                  </div>
                  <Skeleton className="h-32" />
                </div>
              )}
            </div>
          )}
        </Card>
      )}

      {analysisResult && (
        <>
          <ScoreOverview
            confidenceScore={analysisResult.confidence_score}
            engagementScore={analysisResult.engagement_score}
            audioGrade={audioAnalysis?.audio_grade}
          />

          <div className="grid lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              <Card className="p-4 sm:p-6">
                <div className="flex items-center justify-between mb-3">
                  <div className="text-foreground font-medium">Recording</div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Clock3 className="size-3.5" />
                    {videoDuration != null ? formatTime(videoDuration) : "—"}
                  </div>
                </div>
                <VivaVideoPlayer
                  ref={videoPlayerRef}
                  src={videoPreview}
                  durationLabel={videoDuration != null ? formatTime(videoDuration) : undefined}
                  onDurationChange={setVideoDuration}
                />
                <div className="mt-3 flex items-center gap-3">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => uploadedFile && analyzeVideo(uploadedFile)}
                    disabled={isAnalyzing}
                  >
                    {isAnalyzing ? <Loader2 className="size-3.5 animate-spin" /> : <RotateCcw className="size-3.5" />}
                    Re-analyze
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={isAnalyzing}
                    onClick={() => {
                      setUploadedFile(null);
                      setVideoPreview("");
                      setAnalysisResult(null);
                      setError("");
                      resetAssessmentState();
                    }}
                  >
                    Remove
                  </Button>
                </div>
              </Card>

              <AISummary notes={aiInterpretation} />

              <Card className="p-4 sm:p-6">
                <Tabs defaultValue="overview">
                  <TabsList>
                    <TabsTrigger value="overview">Overview</TabsTrigger>
                    <TabsTrigger value="transcript">Transcript</TabsTrigger>
                    <TabsTrigger value="engagement">Engagement</TabsTrigger>
                    <TabsTrigger value="audio">Audio</TabsTrigger>
                  </TabsList>

                  <TabsContent value="overview" className="mt-4 space-y-6">
                    <div>
                      <div className="text-sm font-medium text-foreground mb-2">Emotional distribution</div>
                      <EmotionDistribution summary={analysisResult.summary} />
                    </div>
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <div className="text-sm font-medium text-foreground">Key moments</div>
                        <span className="text-xs text-muted-foreground">AI-detected</span>
                      </div>
                      <KeyMoments moments={keyMoments} onSeek={seekVideo} />
                    </div>
                  </TabsContent>

                  <TabsContent value="transcript" className="mt-4">
                    <TranscriptPanel audioAnalysis={audioAnalysis} />
                  </TabsContent>

                  <TabsContent value="engagement" className="mt-4 space-y-4">
                    <EngagementTimeline timeline={analysisResult.timeline} onSeek={seekVideo} />
                    <p className="text-xs text-muted-foreground">
                      {analysisResult.timeline.filter((f) => f.valid).length} frames analyzed · click a bar to jump
                      the recording to that moment.
                    </p>
                  </TabsContent>

                  <TabsContent value="audio" className="mt-4">
                    <AudioAnalysisPanel audioAnalysis={audioAnalysis} />
                  </TabsContent>
                </Tabs>
              </Card>
            </div>

            <div className="lg:sticky lg:top-6 self-start">
              <Card className="p-5">
                <EvaluationPanel
                  criteria={criteria}
                  onChangeCriteria={setCriteria}
                  aiRecommendation={aiRecommendation}
                  finalGrade={finalGrade}
                  onChangeFinalGrade={setFinalGrade}
                  published={published}
                  onPublish={handlePublish}
                />
                {suggestedGrade && suggestedGrade !== finalGrade && (
                  <p className="mt-2 text-xs text-muted-foreground text-center">
                    Note: AI-suggested grade was {suggestedGrade}.
                  </p>
                )}
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
