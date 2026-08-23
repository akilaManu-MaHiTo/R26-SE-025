import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Textarea } from "../ui/textarea";
import { CopilotCamera } from "./CopilotCamera";
import { CopilotTranscript } from "./CopilotTranscript";
import { SuggestionPanel } from "./SuggestionPanel";
import { SuggestionToasts, SuggestionToastItem } from "./SuggestionToasts";
import {
  askCopilotQuestion,
  CopilotAnalysis,
  CopilotEvent,
  CopilotPhase,
  CopilotSuggestion,
  copilotWsUrl,
  createCopilotSession,
  endCopilotSession,
  finalizeCopilotUtterance,
  normalizeAnalysis,
  normalizeSuggestions,
  ProjectContext,
  setCopilotPhase,
  TranscriptTurn,
  updateCopilotContext,
} from "./copilotApi";
import { CopilotErrorBoundary } from "./CopilotErrorBoundary";

const emptyContext: ProjectContext = { project: "", module: "", notes: "" };

export function LiveCopilotPage() {
  return (
    <CopilotErrorBoundary>
      <LiveCopilotScreen />
    </CopilotErrorBoundary>
  );
}

function LiveCopilotScreen() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [phase, setPhase] = useState<CopilotPhase>("idle");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [project, setProject] = useState<ProjectContext>(emptyContext);
  const [turns, setTurns] = useState<TranscriptTurn[]>([]);
  const [partial, setPartial] = useState("");
  const [points, setPoints] = useState<string[]>([]);
  const [suggestions, setSuggestions] = useState<CopilotSuggestion[]>([]);
  const [analysis, setAnalysis] = useState<CopilotAnalysis | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<string | null>(null);
  const [wsReady, setWsReady] = useState(false);
  const [toasts, setToasts] = useState<SuggestionToastItem[]>([]);

  const wsRef = useRef<WebSocket | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const lastErrorToastRef = useRef("");

  const streaming = phase === "presentation" || phase === "viva";

  const applyEvent = useCallback((event: CopilotEvent) => {
    switch (event.event) {
      case "transcript.partial":
        setPartial(event.text || "");
        break;
      case "transcript.final":
        setPartial("");
        if (event.text) {
          setTurns((prev) => [
            ...prev,
            { speaker: event.speaker || "candidate", text: event.text || "", final: true, timestamp: Date.now() },
          ]);
        }
        break;
      case "presentation.points.extracted":
        setPoints(Array.isArray(event.data?.points) ? event.data.points.map(String) : []);
        setAnalysis(normalizeAnalysis(event.data?.analysis));
        break;
      case "followup.suggestions.generated": {
        const incoming = normalizeSuggestions(event.data?.suggestions);
        setSuggestions(incoming);
        setAnalysis(normalizeAnalysis(event.data?.analysis));
        if (incoming.length) {
          setToasts((prev) => {
            const fresh = incoming.map((item, index) => ({
              ...item,
              id: `${Date.now()}-${index}-${item.question.slice(0, 20)}`,
            }));
            const seen = new Set(fresh.map((item) => item.question));
            const older = prev.filter((item) => !seen.has(item.question));
            return [...fresh, ...older].slice(0, 6);
          });
        }
        break;
      }
      case "interviewer.question.asked":
        setCurrentQuestion(event.text || null);
        break;
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
        if (data.mainPoints) setPoints(data.mainPoints.map(String));
        if (data.suggestions) setSuggestions(normalizeSuggestions(data.suggestions));
        setAnalysis(normalizeAnalysis(data.analysis));
        if (data.currentQuestion !== undefined) setCurrentQuestion(data.currentQuestion ?? null);
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
        const message = event.message || "Copilot error";
        setError(message);
        if (lastErrorToastRef.current !== message) {
          lastErrorToastRef.current = message;
          toast.error("Copilot issue", { description: message });
        }
        break;
      }
      case "session.expired": {
        const message =
          event.message || "Session expired after inactivity. Create a new session to continue.";
        setError(message);
        toast.warning("Session expired", { description: message });
        setPhase("ended");
        break;
      }
      default:
        break;
    }
  }, []);

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
    return () => disconnectWs();
  }, [disconnectWs]);

  const handleChunk = useCallback((blob: Blob) => {
    const socket = wsRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    blob.arrayBuffer().then((buffer) => socket.send(buffer)).catch(() => undefined);
  }, []);

  const startSession = async () => {
    setError("");
    setBusy(true);
    try {
      const created = await createCopilotSession(project);
      sessionIdRef.current = created.sessionId;
      setSessionId(created.sessionId);
      connectWs(created.sessionId);
      toast.success("Session created", {
        description: "Now click Start presentation while the student speaks.",
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Could not create session";
      setError(message);
      toast.error("Create session failed", { description: message });
    } finally {
      setBusy(false);
    }
  };

  const saveContext = async () => {
    if (!sessionId) return;
    try {
      await updateCopilotContext(sessionId, project);
      toast.success("Project notes saved for this session");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save notes");
    }
  };

  const beginPresentation = async () => {
    if (!sessionId) return;
    setError("");
    setBusy(true);
    try {
      await setCopilotPhase(sessionId, "presentation");
      setPhase("presentation");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start presentation");
    } finally {
      setBusy(false);
    }
  };

  const panelEnters = async () => {
    if (!sessionId) return;
    setError("");
    setBusy(true);
    try {
      await finalizeCopilotUtterance(sessionId);
      await setCopilotPhase(sessionId, "viva");
      setPhase("viva");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start viva");
    } finally {
      setBusy(false);
    }
  };

  const markAnswerComplete = async () => {
    if (!sessionId) return;
    try {
      await finalizeCopilotUtterance(sessionId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not finalize answer");
    }
  };

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const handleAsk = async (question: string) => {
    if (!sessionId) return;
    try {
      await askCopilotQuestion(sessionId, question);
      setCurrentQuestion(question);
      setToasts((prev) => prev.filter((item) => item.question !== question));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not pin question");
    }
  };

  const endSession = async () => {
    const id = sessionId;
    disconnectWs();
    if (id) {
      try {
        await endCopilotSession(id);
      } catch {
        // session may already be gone
      }
    }
    sessionIdRef.current = null;
    setSessionId(null);
    setPhase("idle");
    setTurns([]);
    setPartial("");
    setPoints([]);
    setSuggestions([]);
    setAnalysis(null);
    setCurrentQuestion(null);
    setError("");
    setToasts([]);
  };

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-4">
      <SuggestionToasts
        items={toasts}
        onAsk={handleAsk}
        onDismiss={dismissToast}
        askDisabled={!sessionId || phase === "idle"}
      />
      <div>
        <h2 className="tracking-tight text-foreground">Live Interviewer Copilot</h2>
        <p className="text-sm text-muted-foreground mt-1 max-w-3xl">
          Point the laptop camera at the student. Create a session, start the presentation, then let
          the panel enter. Follow-up questions appear on the right — the lecturer chooses what to ask.
        </p>
      </div>

      {error && (
        <Card className="p-4 border-destructive/30 bg-destructive/5 text-sm text-destructive">{error}</Card>
      )}

      <Card className="p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="text-sm font-medium">Session</div>
          <span className="text-xs text-muted-foreground">
            {sessionId ? `Ready · ${phase}` : "No session yet"}
            {wsReady ? " · live link on" : sessionId ? " · connecting…" : ""}
          </span>
        </div>
        <div className="grid sm:grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="copilot-project">Project</Label>
            <Input
              id="copilot-project"
              value={project.project}
              onChange={(event) => setProject((prev) => ({ ...prev, project: event.target.value }))}
              placeholder="Optional project name"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="copilot-module">Module</Label>
            <Input
              id="copilot-module"
              value={project.module}
              onChange={(event) => setProject((prev) => ({ ...prev, module: event.target.value }))}
              placeholder="Optional module"
            />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="copilot-notes">Notes for the copilot</Label>
          <Textarea
            id="copilot-notes"
            value={project.notes}
            onChange={(event) => setProject((prev) => ({ ...prev, notes: event.target.value }))}
            placeholder="Stack, expected topics, constraints…"
            rows={2}
            className="min-h-16"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {!sessionId ? (
            <Button type="button" onClick={startSession} disabled={busy}>
              {busy ? <Loader2 className="size-4 animate-spin" /> : null}
              Create session
            </Button>
          ) : (
            <Button type="button" variant="outline" onClick={saveContext}>
              Save notes
            </Button>
          )}
          <Button
            type="button"
            onClick={beginPresentation}
            disabled={!sessionId || busy || phase !== "idle"}
          >
            Start presentation
          </Button>
          <Button
            type="button"
            onClick={panelEnters}
            disabled={!sessionId || busy || phase !== "presentation"}
          >
            Panel enters / start viva
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={markAnswerComplete}
            disabled={!sessionId || !streaming}
          >
            Answer complete
          </Button>
          <Button type="button" variant="ghost" onClick={endSession} disabled={!sessionId}>
            End session
          </Button>
        </div>
        {!sessionId && (
          <p className="text-xs text-muted-foreground">
            Click <span className="text-foreground font-medium">Create session</span> first. The camera
            can stay on; transcription starts after you create a session and start the presentation.
          </p>
        )}
        {sessionId && phase === "idle" && (
          <p className="text-xs text-emerald-600 dark:text-emerald-400">
            Session created. Click <span className="font-medium">Start presentation</span> so the
            student&apos;s speech is transcribed.
          </p>
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(16rem,0.85fr)] min-w-0">
        <div className="space-y-4 min-w-0">
          <Card className="p-4 space-y-4 overflow-hidden">
            <div className="flex items-center justify-between gap-2">
              <div className="text-sm font-medium">Student camera</div>
              <span className="text-xs text-muted-foreground capitalize">
                {phase === "idle" ? "preview" : phase}
                {streaming && wsReady ? " · capturing" : ""}
              </span>
            </div>
            <CopilotCamera streaming={streaming && wsReady} onChunk={handleChunk} />
          </Card>
        </div>

        <div className="space-y-4 min-w-0">
          <Card className="p-4 space-y-3">
            <div className="text-sm font-medium">Live transcript</div>
            <CopilotTranscript turns={turns} partial={partial} />
          </Card>
          <Card className="p-4 space-y-2">
            <div className="text-sm font-medium">Main points from presentation</div>
            {points.length === 0 ? (
              <p className="text-sm text-muted-foreground">Captured as the student presents.</p>
            ) : (
              <ul className="list-disc pl-5 text-sm space-y-1">
                {points.map((point) => (
                  <li key={point}>{point}</li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        <SuggestionPanel
          suggestions={suggestions}
          analysis={analysis}
          currentQuestion={currentQuestion}
          onAsk={handleAsk}
          disabled={!sessionId || phase === "idle"}
        />
      </div>
    </div>
  );
}
