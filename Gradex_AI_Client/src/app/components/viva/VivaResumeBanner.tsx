import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { CheckCircle2, Info, Loader2 } from "lucide-react";
import { SERVER_BASE_URL } from "../../api/gradingApiBase";
import { Card } from "../ui/card";
import { Button } from "../ui/button";
import {
  VivaAnalyzeProgress,
  VivaProgressSnapshot,
  fetchVivaAnalyzeProgress,
  subscribeVivaAnalyzeProgress,
} from "./VivaAnalyzeProgress";
import { InflightJob, clearInflightJob, readInflightJob } from "./inflightJob";

type Status = "running" | "done" | "lost";

/**
 * Shown on the Viva Assessment page after a reload (or after leaving and coming back)
 * while an analysis was still running. The analysis itself is never interrupted —
 * this just reattaches to its progress and links to the finished result.
 */
export function VivaResumeBanner() {
  const navigate = useNavigate();
  const [job, setJob] = useState<InflightJob | null>(() => readInflightJob());
  const [snapshot, setSnapshot] = useState<VivaProgressSnapshot | null>(null);
  const [status, setStatus] = useState<Status>("running");
  const [elapsed, setElapsed] = useState(() => (job ? (Date.now() - job.startedAt) / 1000 : 0));

  useEffect(() => {
    if (!job || status !== "running") return;
    const timer = window.setInterval(() => setElapsed((Date.now() - job.startedAt) / 1000), 1000);
    return () => window.clearInterval(timer);
  }, [job, status]);

  useEffect(() => {
    if (!job) return;
    let cancelled = false;
    let poll: number | null = null;

    const handle = (next: VivaProgressSnapshot) => {
      if (cancelled) return;
      setSnapshot(next);
      if (next.finished) {
        clearInflightJob();
        setStatus("done");
      } else if (!next.stage && !(next.version ?? 0)) {
        // The server has no record of this job: it restarted, the entry expired, or the
        // upload never finished before the page went away.
        clearInflightJob();
        setStatus("lost");
      }
    };

    const startPolling = () => {
      if (cancelled || poll !== null) return;
      const tick = async () => {
        const next = await fetchVivaAnalyzeProgress(SERVER_BASE_URL, job.progressId);
        if (next) handle(next);
      };
      void tick();
      poll = window.setInterval(() => void tick(), 3000);
    };

    const unsubscribe = subscribeVivaAnalyzeProgress(SERVER_BASE_URL, job.progressId, handle, startPolling);
    return () => {
      cancelled = true;
      unsubscribe();
      if (poll !== null) window.clearInterval(poll);
    };
  }, [job]);

  if (!job) return null;

  const dismiss = () => {
    clearInflightJob();
    setJob(null);
  };

  if (status === "lost") {
    return (
      <Card className="p-5">
        <div className="flex items-start gap-3">
          <Info className="size-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="flex-1 text-sm">
            <div className="font-medium text-foreground">Could not reconnect to the analysis of {job.fileName}</div>
            <p className="text-muted-foreground mt-1">
              The server has no record of it — the upload may not have finished before the page was
              closed. If it did finish, the result is already saved under Viva Results. Otherwise,
              upload the recording again.
            </p>
            <div className="mt-3 flex gap-2">
              <Button size="sm" onClick={() => navigate("/viva-evaluation/viva-results")}>
                Open Viva Results
              </Button>
              <Button size="sm" variant="ghost" onClick={dismiss}>
                Dismiss
              </Button>
            </div>
          </div>
        </div>
      </Card>
    );
  }

  if (status === "done") {
    const markId = snapshot?.mark_id;
    return (
      <Card className="p-5">
        <div className="flex items-start gap-3">
          <CheckCircle2 className="size-5 text-emerald-600 shrink-0 mt-0.5" />
          <div className="flex-1 text-sm">
            <div className="font-medium text-foreground">Analysis of {job.fileName} is complete</div>
            <p className="text-muted-foreground mt-1">
              The page was reloaded while it ran, but the analysis finished and the result was saved.
            </p>
            <div className="mt-3 flex gap-2">
              <Button
                size="sm"
                onClick={() =>
                  navigate(markId ? `/viva-evaluation/viva-results?mark=${encodeURIComponent(markId)}` : "/viva-evaluation/viva-results")
                }
              >
                {markId ? "Open result" : "Open Viva Results"}
              </Button>
              <Button size="sm" variant="ghost" onClick={dismiss}>
                Dismiss
              </Button>
            </div>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-5 space-y-3">
      <div className="flex items-center gap-3">
        <Loader2 className="size-5 text-primary animate-spin" />
        <div className="text-sm">
          <div className="font-medium text-foreground">Analysis still running: {job.fileName}</div>
          <div className="text-muted-foreground">
            The page was reloaded, but the analysis carries on. This updates by itself and links to the
            result when it is done.
          </div>
        </div>
      </div>
      <VivaAnalyzeProgress snapshot={snapshot} elapsedSeconds={elapsed} />
    </Card>
  );
}
