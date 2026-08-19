"use client";

import { useEffect, useMemo, useRef, useState } from "react";
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
import { LlmJudgePanel } from "./viva/LlmJudgePanel";
import { QaRelevancePanel } from "./viva/QaRelevancePanel";
import { LiveVivaRecorder } from "./viva/LiveVivaRecorder";
import { EvaluationPanel } from "./viva/EvaluationPanel";
import { ReportPrintView } from "./viva/ReportPrintView";
import {
  AnalysisResult,
  AssessmentMode,
  buildAIInterpretation,
  buildKeyMoments,
  formatTime,
} from "./viva/types";

export function VivaPage() {
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [videoPreview, setVideoPreview] = useState<string>("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string>("");
  const [isDragging, setIsDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [displayProgress, setDisplayProgress] = useState(0);
  const [uploadStartTime, setUploadStartTime] = useState<number | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [analysisPhase, setAnalysisPhase] = useState<"idle" | "uploading" | "processing" | "complete">("idle");
  const [videoDuration, setVideoDuration] = useState<number | null>(null);

  const [assessmentMode, setAssessmentMode] = useState<AssessmentMode>("WITHOUT_TECHNICAL_ACCURACY");
  const [technicalAccuracy, setTechnicalAccuracy] = useState<number | null>(null);
  const [studentId, setStudentId] = useState("");
  const [published, setPublished] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [sourceTab, setSourceTab] = useState<"upload" | "live">("upload");

  const fileInputRef = useRef<HTMLInputElement>(null);
  const videoPlayerRef = useRef<VivaVideoPlayerHandle>(null);
  const backendBaseUrl =
    ((import.meta as ImportMeta & { env?: { VITE_BACKEND_URL?: string } }).env?.VITE_BACKEND_URL) ??
    "http://localhost:8000";

  const resetAssessmentState = () => {
    setAssessmentMode("WITHOUT_TECHNICAL_ACCURACY");
    setTechnicalAccuracy(null);
    setStudentId("");
    setPublished(false);
    setPublishing(false);
  };

  const handlePublish = async () => {
    const markId = analysisResult?.mark_id;
    if (!markId) {
      toast.error("Cannot publish", {
        description: "No saved mark_id from analysis — Mongo may be offline.",
      });
      return;
    }
    if (published || publishing) return;

    setPublishing(true);
    try {
      const response = await fetch(`${backendBaseUrl}/api/viva-marks/${markId}/publish`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          assessment_mode: assessmentMode,
          technical_accuracy:
            assessmentMode === "WITH_TECHNICAL_ACCURACY" ? technicalAccuracy : null,
          student_id: studentId.trim() || null,
          published: true,
        }),
      });
      if (!response.ok) {
        let detail = `HTTP ${response.status}`;
        try {
          const payload = await response.json();
          if (typeof payload?.detail === "string" && payload.detail.trim()) {
            detail = payload.detail.trim();
          }
        } catch {
          // ignore
        }
        throw new Error(detail);
      }
      setPublished(true);
      toast.success("Assessment published", {
        description: "Final score and grade saved from the engine scorer.",
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to publish";
      toast.error("Publish failed", { description: message });
    } finally {
      setPublishing(false);
    }
  };

  const uploadProgressRef = useRef(0);
  useEffect(() => {
    uploadProgressRef.current = uploadProgress;
  }, [uploadProgress]);

  // Eases the displayed percentage toward the real XHR progress instead of snapping
  // straight to 100% when a small file uploads to localhost almost instantly.
  useEffect(() => {
    if (!isAnalyzing) {
      setDisplayProgress(0);
      return;
    }
    let rafId: number;
    const step = () => {
      setDisplayProgress((prev) => {
        const target = uploadProgressRef.current;
        const next = prev + (target - prev) * 0.15;
        return Math.abs(target - next) < 0.4 ? target : next;
      });
      rafId = requestAnimationFrame(step);
    };
    rafId = requestAnimationFrame(step);
    return () => cancelAnimationFrame(rafId);
  }, [isAnalyzing]);

  // Ticks the elapsed-time readout live rather than only on the rare XHR progress events.
  useEffect(() => {
    if (!isAnalyzing || uploadStartTime == null) return;
    const id = setInterval(() => setElapsedMs(Date.now() - uploadStartTime), 100);
    return () => clearInterval(id);
  }, [isAnalyzing, uploadStartTime]);

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

  const handleFileSelect = (file: File, options?: { autoAnalyze?: boolean }) => {
    const isVideo = file.type.startsWith("video/") || /\.(mp4|webm|mov|avi|mkv)$/i.test(file.name);
    if (!isVideo) {
      setError("Please upload a valid video file (MP4, WEBM, AVI, MOV, etc.)");
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
    if (options?.autoAnalyze) {
      void analyzeVideo(file);
    }
  };

  const analyzeVideo = async (file: File) => {
    if (!file) return;

    setIsAnalyzing(true);
    setError("");
    setUploadProgress(0);
    setDisplayProgress(0);
    setElapsedMs(0);
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

        // The bytes finish transferring well before the server responds (it runs the
        // full analysis inside this same request), so flip to "processing" as soon as
        // the upload itself completes rather than waiting for the whole response.
        xhr.upload.addEventListener("load", () => {
          setUploadProgress(100);
          setAnalysisPhase("processing");
        });

        xhr.addEventListener("load", () => {
          if (xhr.status === 200) {
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
      setPublished(false);
      setPublishing(false);
      setAssessmentMode("WITHOUT_TECHNICAL_ACCURACY");
      setTechnicalAccuracy(null);
      if (data.assessment) {
        toast.success("Analysis complete", {
          description:
            data.assessment.status === "INCOMPLETE"
              ? "Recording is incomplete — no official grade."
              : `AI performance ${data.assessment.ai_performance?.score ?? "—"} / 100.`,
        });
      }
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

  const audioAnalysis = analysisResult?.audio_analysis;

  return (
    <>
    <div className="p-4 sm:p-6 lg:p-8 space-y-6 print:hidden">
      <AIPageBanner model="voca" />

      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className="tracking-tight text-foreground">Viva Assessment</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Upload a recording or run a live webcam viva, then transcribe and score with AI.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <AIBadgePill model="voca" />
          <Button disabled={!analysisResult} onClick={() => window.print()}>
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
          <Tabs value={sourceTab} onValueChange={(value) => setSourceTab(value as "upload" | "live")}>
            <TabsList>
              <TabsTrigger value="upload">Upload recording</TabsTrigger>
              <TabsTrigger value="live">Live viva</TabsTrigger>
            </TabsList>
            <TabsContent value="upload" className="mt-4">
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
                <div className="text-xs text-muted-foreground mt-1">Supports MP4, WEBM, AVI, MOV · up to 1 GB</div>
              </div>
            </TabsContent>
            <TabsContent value="live" className="mt-4">
              {sourceTab === "live" ? (
                <LiveVivaRecorder
                  disabled={isAnalyzing}
                  onRecorded={(file) => handleFileSelect(file, { autoAnalyze: true })}
                />
              ) : null}
            </TabsContent>
          </Tabs>
        </Card>
      )}

      {videoPreview && !analysisResult && (
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="text-foreground font-medium">Recording</div>
            <Badge className="bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400 border-0">
              <CheckCircle2 className="size-3 mr-1" />
              {uploadedFile?.name.startsWith("viva-live-") ? "Recorded" : "Uploaded"}
            </Badge>
          </div>

          <div className="mx-auto w-full max-w-xl">
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
          </div>

          {isAnalyzing && (
            <div className="mt-5 space-y-3">
              {analysisPhase === "uploading" && (
                <div className="p-4 rounded-lg bg-primary/5 border border-primary/10">
                  <div className="flex items-center gap-3 mb-2">
                    <Loader2 className="size-5 text-primary animate-spin" />
                    <div className="text-sm font-medium text-foreground tabular-nums">
                      Uploading video ({Math.round(displayProgress)}%)
                    </div>
                  </div>
                  <div className="w-full h-2 rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full bg-primary"
                      style={{ width: `${displayProgress}%` }}
                    />
                  </div>
                  <div className="text-xs text-muted-foreground mt-2 tabular-nums">
                    {uploadedFile ? `${(uploadedFile.size / 1024 / 1024).toFixed(2)} MB` : ""}
                    {uploadStartTime ? ` · Elapsed ${(elapsedMs / 1000).toFixed(1)}s` : ""}
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
                        <div className="text-xs text-muted-foreground mt-1 tabular-nums">
                          Processing frames, extracting audio, transcribing…
                          {uploadStartTime && ` (${(elapsedMs / 1000).toFixed(1)}s elapsed)`}
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
            videoStatus={analysisResult.video_status}
            faceCoverageRatio={analysisResult.coverage?.face_coverage_ratio}
            framesRejectedQuality={analysisResult.coverage?.frames_rejected_quality}
            framesEnhanced={analysisResult.coverage?.frames_enhanced}
            framesQualityWarning={analysisResult.coverage?.frames_quality_warning}
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
                <div className="mx-auto w-full max-w-xl">
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
                    <TabsTrigger value="qa">Q&A</TabsTrigger>
                    <TabsTrigger value="llm">Interpretation</TabsTrigger>
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
                    <TranscriptPanel audioAnalysis={audioAnalysis} onSeek={seekVideo} />
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

                  <TabsContent value="qa" className="mt-4">
                    <QaRelevancePanel
                      qaAnalysis={analysisResult.qa_analysis}
                      turns={audioAnalysis?.conversation?.turns}
                      structure={audioAnalysis?.conversation?.structure}
                      onSeek={seekVideo}
                    />
                  </TabsContent>

                  <TabsContent value="llm" className="mt-4 space-y-4">
                    <LlmJudgePanel
                      evaluation={analysisResult.llm_evaluation}
                      transcriptFeatures={audioAnalysis?.transcript_features}
                    />
                  </TabsContent>
                </Tabs>
              </Card>
            </div>

            <div className="lg:sticky lg:top-6 self-start">
              <Card className="p-5">
                <EvaluationPanel
                  assessment={analysisResult.assessment}
                  assessmentMode={assessmentMode}
                  onChangeMode={setAssessmentMode}
                  technicalAccuracy={technicalAccuracy}
                  onChangeTechnicalAccuracy={setTechnicalAccuracy}
                  studentId={studentId}
                  onChangeStudentId={setStudentId}
                  aiRecommendation={aiRecommendation}
                  published={published}
                  publishing={publishing}
                  onPublish={handlePublish}
                />
              </Card>
            </div>
          </div>
        </>
      )}
    </div>

    {analysisResult && (
      <div className="hidden print:block">
        <ReportPrintView
          videoFileName={uploadedFile?.name}
          generatedAt={new Date()}
          analysisResult={analysisResult}
          assessmentMode={assessmentMode}
          technicalAccuracy={technicalAccuracy}
          published={published}
          aiInterpretation={aiInterpretation}
          keyMoments={keyMoments}
        />
      </div>
    )}
    </>
  );
}
