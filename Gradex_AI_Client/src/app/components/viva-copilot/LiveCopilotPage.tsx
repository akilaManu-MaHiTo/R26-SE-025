import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Loader2, Play, Sparkles, Square, X } from "lucide-react";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { ScrollArea } from "../ui/scroll-area";
import { CopilotCamera, CopilotCameraHandle, SpeechResult } from "./CopilotCamera";
import {
  analyzeCopilotSession,
  askCopilotQuestion,
  CopilotAssessmentMode,
  CopilotEvent,
  CopilotPhase,
  copilotWsUrl,
  createCopilotSession,
  endCopilotSession,
  finalizeCopilotUtterance,
  normalizeSuggestion,
  normalizeSuggestions,
  setCopilotPhase,
  TranscriptTurn,
} from "./copilotApi";
import {
  AnalysisResult,
  AssessmentMode,
  buildAIInterpretation,
  buildKeyMoments,
} from "../viva/types";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../ui/tabs";
import { EmotionDistribution } from "../viva/EmotionDistribution";
import { EngagementTimeline } from "../viva/EngagementTimeline";
import { KeyMoments } from "../viva/KeyMoments";
import { TranscriptPanel } from "../viva/TranscriptPanel";
import { LlmJudgePanel } from "../viva/LlmJudgePanel";
import { QaRelevancePanel } from "../viva/QaRelevancePanel";
import { ScoreOverview } from "../viva/ScoreOverview";
import { AudioAnalysisPanel } from "../viva/AudioAnalysisPanel";
import { AISummary } from "../viva/AISummary";
import { CopilotErrorBoundary } from "./CopilotErrorBoundary";

export function LiveCopilotPage() {
  return (
    <CopilotErrorBoundary>
      <LiveCopilotScreen />
    </CopilotErrorBoundary>
  );
}

interface SuggestionItem {
  id: string;
  question: string;
  reason: string;
}

// If the partial transcript stops changing for this long, ask the backend to
// finalize the current utterance instead of waiting for a silent audio slice.
const AUTO_FINALIZE_IDLE_MS = 1200;

function LiveCopilotScreen() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [phase, setPhase] = useState<CopilotPhase>("idle");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [turns, setTurns] = useState<TranscriptTurn[]>([]);
  const [partial, setPartial] = useState("");
  const [wsReady, setWsReady] = useState(false);
  const [suggestions, setSuggestions] = useState<SuggestionItem[]>([]);
  // Chosen before the session starts and locked for its duration — same rule
  // as an uploaded viva (see VivaPage.tsx): the examiner cannot switch mode
  // after the fact and re-roll the grade.
  const [assessmentMode, setAssessmentMode] = useState<CopilotAssessmentMode>(
    "WITHOUT_TECHNICAL_ACCURACY",
  );
  const [studentId, setStudentId] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);

  const cameraRef = useRef<CopilotCameraHandle>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const lastErrorToastRef = useRef("");
  const idleTimerRef = useRef<number | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  const streaming = phase === "viva" && Boolean(sessionId);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, partial]);

  const clearIdleTimer = useCallback(() => {
    if (idleTimerRef.current !== null) {
      window.clearTimeout(idleTimerRef.current);
      idleTimerRef.current = null;
    }
  }, []);

  const scheduleAutoFinalize = useCallback(() => {
    clearIdleTimer();
    idleTimerRef.current = window.setTimeout(() => {
      const id = sessionIdRef.current;
      if (id) finalizeCopilotUtterance(id).catch(() => undefined);
    }, AUTO_FINALIZE_IDLE_MS);
  }, [clearIdleTimer]);


  const applyEvent = useCallback(
    (event: CopilotEvent) => {
      switch (event.event) {
        case "transcript.partial":
          setPartial(event.text || "");
          if ((event.text || "").trim()) {
            scheduleAutoFinalize();
          } else {
            clearIdleTimer();
          }
          break;
        case "transcript.final":
          clearIdleTimer();
          setPartial("");
          if (event.text) {
            setTurns((prev) => [
              ...prev,
              { speaker: event.speaker || "candidate", text: event.text || "", final: true, timestamp: Date.now() },
            ]);
          }
          break;
        case "followup.suggestion.partial": {
          // Streamed early — shown the moment Groq emits the first complete
          // suggestion, well before the full follow-up JSON has finished.
          const incoming = normalizeSuggestion(event.data?.suggestion);
          if (incoming) {
            setSuggestions((prev) => {
              if (prev.some((item) => item.question === incoming.question)) return prev;
              const fresh: SuggestionItem = {
                id: `${Date.now()}-partial-${incoming.question.slice(0, 20)}`,
                question: incoming.question,
                reason: incoming.reason,
              };
              return [fresh, ...prev].slice(0, 6);
            });
            toast.success("New question suggested", {
              description: incoming.question,
              duration: 4500,
            });
          }
          break;
        }
        case "followup.suggestions.generated": {
          const incoming = normalizeSuggestions(event.data?.suggestions);
          if (incoming.length > 0) {
            setSuggestions((prev) => {
              const fresh: SuggestionItem[] = incoming.map((item, index) => ({
                id: `${Date.now()}-${index}-${item.question.slice(0, 20)}`,
                question: item.question,
                reason: item.reason,
              }));
              const seen = new Set(fresh.map((item) => item.question));
              const older = prev.filter((item) => !seen.has(item.question));
              return [...fresh, ...older].slice(0, 6);
            });
            toast.success("New question suggested", {
              description: incoming[0].question,
              duration: 4500,
            });
          }
          break;
        }
        case "session.phase":
          if (event.phase === "presentation" || event.phase === "viva" || event.phase === "ended") {
            setPhase(event.phase);
          }
          break;
        case "session.state": {
          const data = event.data;
          if (!data) break;
          if (data.phase === "idle" || data.phase === "presentation" || data.phase === "viva" || data.phase === "ended") {
            setPhase(data.phase);
          }
          if (data.suggestions) {
            const incoming = normalizeSuggestions(data.suggestions);
            setSuggestions(
              incoming.map((item, index) => ({
                id: `restore-${index}-${item.question.slice(0, 20)}`,
                question: item.question,
                reason: item.reason,
              })),
            );
          }
          if (data.transcript?.length) {
            setTurns(
              data.transcript.map((turn) => ({
                speaker: turn.speaker,
                text: turn.text,
                final: turn.final,
                timestamp: turn.timestamp,
              })),
            );
          }
          break;
        }
        case "copilot.error": {
          const message = event.message || "Live viva error";
          setError(message);
          if (lastErrorToastRef.current !== message) {
            lastErrorToastRef.current = message;
            toast.error("Live viva issue", { description: message });
          }
          break;
        }
        default:
          break;
      }
    },
    [clearIdleTimer, scheduleAutoFinalize],
  );


  const disconnectWs = useCallback(() => {
    const socket = wsRef.current;
    wsRef.current = null;
    setWsReady(false);
    if (socket && socket.readyState < 2) socket.close();
  }, []);

  const connectWs = useCallback(
    (id: string) => {
      disconnectWs();
      const socket = new WebSocket(copilotWsUrl(id));
      wsRef.current = socket;
      socket.binaryType = "arraybuffer";
      socket.onopen = () => setWsReady(true);
      socket.onclose = () => setWsReady(false);
      socket.onerror = () => setError("Live connection failed. Check the backend is running.");
      socket.onmessage = (message) => {
        try {
          const raw =
            typeof message.data === "string"
              ? message.data
              : new TextDecoder().decode(message.data as ArrayBuffer);
          applyEvent(JSON.parse(raw) as CopilotEvent);
        } catch (err) {
          console.warn("[copilot] ignored socket message", err);
        }
      };
    },
    [applyEvent, disconnectWs],
  );

  useEffect(() => {
    return () => {
      disconnectWs();
      clearIdleTimer();
    };
  }, [disconnectWs, clearIdleTimer]);

  const handleChunk = useCallback((blob: Blob) => {
    const socket = wsRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    blob.arrayBuffer().then((buffer) => socket.send(buffer)).catch(() => undefined);
  }, []);

  // Fast path: instant browser Web Speech API results, sent as JSON text
  // frames over the same socket used for audio. The Groq Whisper path
  // (handleChunk above) keeps running in parallel as an accuracy backstop.
  const handleSpeechResult = useCallback((result: SpeechResult) => {
    const socket = wsRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({ type: "speech", text: result.text, isFinal: result.isFinal }));
    if (result.text.trim()) {
      scheduleAutoFinalize();
    }
  }, [scheduleAutoFinalize]);


  const startLiveViva = async () => {
    setError("");
    setResult(null);
    setBusy(true);
    try {
      await cameraRef.current?.start();

      const created = await createCopilotSession({
        project: "Live Viva Examination",
        module: "Viva Evaluation",
        notes: "Real-time question recommendation",
      });
      sessionIdRef.current = created.sessionId;
      setSessionId(created.sessionId);
      connectWs(created.sessionId);

      await setCopilotPhase(created.sessionId, "viva");
      setPhase("viva");

      toast.success("Live viva started", {
        description: "Listening to the candidate — AI questions will pop up as they speak.",
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to start live viva session.";
      setError(message);
      toast.error("Could not start session", { description: message });
    } finally {
      setBusy(false);
    }
  };

  const endViva = async () => {
    const id = sessionId;
    disconnectWs();
    clearIdleTimer();

    // Close the recorder BEFORE tearing down the tracks, otherwise the final
    // blob is truncated. The session is deleted only after analysis, since the
    // backend reads the live transcript off it.
    let recording: Blob | null = null;
    try {
      recording = (await cameraRef.current?.stopAndCollectRecording()) ?? null;
    } catch {
      recording = null;
    }
    cameraRef.current?.stop();

    if (id && recording && recording.size > 0) {
      setAnalyzing(true);
      try {
        const analysis = await analyzeCopilotSession(id, recording, {
          assessmentMode,
          studentId: studentId.trim() || undefined,
        });
        setResult(analysis as unknown as AnalysisResult);
        toast.success("Session analyzed and scored");
      } catch (err) {
        const message = err instanceof Error ? err.message : "Analysis failed";
        setError(message);
        toast.error(message);
      } finally {
        setAnalyzing(false);
      }
    } else if (id) {
      toast.warning("No recording was captured, so no score could be produced.");
    }

    if (id) {
      try {
        await endCopilotSession(id);
      } catch {
        // already stopped
      }
    }
    sessionIdRef.current = null;
    setSessionId(null);
    setPhase("idle");
    setTurns([]);
    setPartial("");
    setSuggestions([]);
    toast.info("Live viva session ended");
  };

  const handleAsk = async (item: SuggestionItem) => {
    if (!sessionId) return;
    try {
      await askCopilotQuestion(sessionId, item.question);
      setSuggestions((prev) => prev.filter((entry) => entry.id !== item.id));
      toast.success("Marked as the active examiner question");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not set question");
    }
  };

  const dismissSuggestion = (id: string) => {
    setSuggestions((prev) => prev.filter((entry) => entry.id !== id));
  };


  return (
    <div
      className={
        result
          ? "flex flex-col min-h-[calc(100vh-4rem)] p-4 gap-4 overflow-y-auto"
          : "flex flex-col h-[calc(100vh-4rem)] p-4 gap-4"
      }
    >
      <div className="flex items-center justify-between gap-3 shrink-0">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-foreground">Live Viva</h1>
          <p className="text-xs text-muted-foreground">
            Record the candidate, follow the live transcript, and use AI-suggested questions.
          </p>
        </div>

        {!sessionId ? (
          <div className="flex items-end gap-2">
            <div className="flex flex-col gap-1">
              <label htmlFor="copilot-mode" className="text-[11px] text-muted-foreground">
                Assessment type (locked once the session starts)
              </label>
              <select
                id="copilot-mode"
                value={assessmentMode}
                onChange={(event) =>
                  setAssessmentMode(event.target.value as CopilotAssessmentMode)
                }
                disabled={busy}
                className="h-9 rounded-md border border-input bg-background px-2 text-xs"
              >
                <option value="WITHOUT_TECHNICAL_ACCURACY">
                  Non-technical — auto-publishes
                </option>
                <option value="WITH_TECHNICAL_ACCURACY">
                  Technical — saved as draft for review
                </option>
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor="copilot-student" className="text-[11px] text-muted-foreground">
                Student ID (optional)
              </label>
              <input
                id="copilot-student"
                value={studentId}
                onChange={(event) => setStudentId(event.target.value)}
                placeholder="e.g. STU-001"
                disabled={busy}
                className="h-9 w-32 rounded-md border border-input bg-background px-2 text-xs"
              />
            </div>
            <Button type="button" onClick={startLiveViva} disabled={busy} className="gap-2">
              {busy ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4 fill-current" />}
              Start Session
            </Button>
          </div>
        ) : (
          <Button
            type="button"
            variant="destructive"
            onClick={endViva}
            disabled={analyzing}
            className="gap-2"
          >
            {analyzing ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Square className="size-3.5 fill-current" />
            )}
            {analyzing ? "Analyzing…" : "End Session"}
          </Button>
        )}
      </div>

      {error && (
        <Card className="p-3 border-destructive/40 bg-destructive/10 text-destructive text-sm flex items-center justify-between shrink-0">
          <span>{error}</span>
          <Button variant="ghost" size="sm" onClick={() => setError("")} className="text-xs h-7">
            Dismiss
          </Button>
        </Card>
      )}

      <div
        className={
          result
            ? "grid grid-cols-1 lg:grid-cols-2 gap-4 shrink-0 h-[60vh]"
            : "grid grid-cols-1 lg:grid-cols-2 gap-4 flex-1 min-h-0"
        }
      >
        <div className="flex flex-col gap-4 min-h-0">
          <div className="min-h-0 flex-1">
            <CopilotCamera
              ref={cameraRef}
              streaming={streaming && wsReady}
              onChunk={handleChunk}
              onSpeechResult={handleSpeechResult}
            />
          </div>

          <Card className="flex flex-col flex-1 min-h-0 p-3">
            <h2 className="text-sm font-semibold text-foreground mb-2 shrink-0">Live Transcript</h2>
            <ScrollArea className="flex-1 min-h-0 pr-2">
              <div className="space-y-2 text-sm">
                {turns.length === 0 && !partial && (
                  <p className="text-xs text-muted-foreground">
                    Transcript will appear here once the candidate starts speaking.
                  </p>
                )}
                {turns.map((turn, index) => (
                  <p key={index} className="leading-snug">
                    <span className="text-[10px] uppercase tracking-wide text-muted-foreground mr-1.5">
                      {turn.speaker === "interviewer" ? "Panel" : "Student"}
                    </span>
                    <span className="text-foreground">{turn.text}</span>
                  </p>
                ))}
                {partial && (
                  <p className="leading-snug italic text-muted-foreground">
                    <span className="text-[10px] uppercase tracking-wide text-emerald-600 dark:text-emerald-400 not-italic mr-1.5">
                      Live
                    </span>
                    {partial}
                  </p>
                )}
                <div ref={transcriptEndRef} />
              </div>
            </ScrollArea>
          </Card>
        </div>

        <div className="flex flex-col min-h-0">
          <Card className="flex flex-col flex-1 min-h-0 p-3">
            <h2 className="text-sm font-semibold text-foreground mb-2 flex items-center gap-1.5 shrink-0">
              <Sparkles className="size-4 text-amber-500" />
              AI Suggested Questions
            </h2>
            <ScrollArea className="flex-1 min-h-0 pr-2">
              <div className="space-y-2">
                {suggestions.length === 0 && (
                  <p className="text-xs text-muted-foreground">
                    Suggested follow-up questions will appear here as the candidate speaks.
                  </p>
                )}
                {suggestions.map((item) => (
                  <div key={item.id} className="rounded-lg border border-border bg-muted/30 p-2.5 space-y-1.5">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm font-medium text-foreground leading-snug">{item.question}</p>
                      <button
                        type="button"
                        onClick={() => dismissSuggestion(item.id)}
                        className="text-muted-foreground hover:text-foreground shrink-0"
                        aria-label="Dismiss suggestion"
                      >
                        <X className="size-3.5" />
                      </button>
                    </div>
                    {item.reason && <p className="text-xs text-muted-foreground leading-snug">{item.reason}</p>}
                    <Button
                      size="sm"
                      type="button"
                      variant="secondary"
                      className="h-7 text-xs w-full"
                      disabled={!sessionId}
                      onClick={() => handleAsk(item)}
                    >
                      Ask this question
                    </Button>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </Card>
        </div>
      </div>

      {analyzing && (
        <Card className="p-4 flex items-center gap-3 shrink-0">
          <Loader2 className="size-4 animate-spin text-muted-foreground" />
          <div>
            <p className="text-sm font-medium text-foreground">Analyzing the session recording…</p>
            <p className="text-xs text-muted-foreground">
              Running emotion, engagement, audio and transcript scoring. This can take a
              few minutes for a long viva.
            </p>
          </div>
        </Card>
      )}

      {result && (
        <div className="flex flex-col gap-4 shrink-0 pb-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-foreground">Session Assessment</h2>
              <p className="text-xs text-muted-foreground">
                Scored with the same engine and rubric as an uploaded viva recording.
              </p>
            </div>
            <Button variant="ghost" size="sm" className="text-xs h-7" onClick={() => setResult(null)}>
              Dismiss
            </Button>
          </div>

          <ScoreOverview
            assessment={result.assessment}
            analysisResult={result}
            assessmentMode={assessmentMode as AssessmentMode}
            technicalAccuracy={null}
            published={Boolean((result as { published?: boolean }).published)}
            videoStatus={result.video_status}
            faceCoverageRatio={result.coverage?.face_coverage_ratio}
            confidenceScore={result.confidence_score}
            engagementScore={result.engagement_score}
          />

          <AudioAnalysisPanel audioAnalysis={result.audio_analysis} />
          <AISummary notes={buildAIInterpretation(result)} />

          <Card className="p-4">
            <Tabs defaultValue="overview">
              <TabsList>
                <TabsTrigger value="overview">Overview</TabsTrigger>
                <TabsTrigger value="transcript">Transcript</TabsTrigger>
                <TabsTrigger value="engagement">Engagement</TabsTrigger>
                <TabsTrigger value="qa">Q&amp;A relevance</TabsTrigger>
                <TabsTrigger value="judge">AI judge</TabsTrigger>
              </TabsList>

              <TabsContent value="overview" className="mt-4 space-y-4">
                {result.summary && <EmotionDistribution summary={result.summary} />}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-sm font-medium text-foreground">Key moments</div>
                    <span className="text-xs text-muted-foreground">AI-detected</span>
                  </div>
                  <KeyMoments moments={buildKeyMoments(result.timeline)} />
                </div>
              </TabsContent>

              <TabsContent value="transcript" className="mt-4">
                <TranscriptPanel audioAnalysis={result.audio_analysis} />
              </TabsContent>

              <TabsContent value="engagement" className="mt-4 space-y-4">
                <EngagementTimeline timeline={result.timeline} />
                <p className="text-xs text-muted-foreground">
                  {result.timeline.filter((frame) => frame.valid).length} frames analyzed.
                </p>
              </TabsContent>

              <TabsContent value="qa" className="mt-4">
                <QaRelevancePanel
                  qaAnalysis={result.qa_analysis}
                  turns={result.audio_analysis?.conversation?.turns}
                  structure={result.audio_analysis?.conversation?.structure}
                />
              </TabsContent>

              <TabsContent value="judge" className="mt-4">
                <LlmJudgePanel
                  evaluation={result.llm_evaluation}
                  transcriptFeatures={result.audio_analysis?.transcript_features}
                />
              </TabsContent>
            </Tabs>
          </Card>
        </div>
      )}
    </div>
  );
}
