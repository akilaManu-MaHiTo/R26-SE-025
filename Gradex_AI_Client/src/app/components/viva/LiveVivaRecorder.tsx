import { useEffect, useRef, useState } from "react";
import { Camera, Circle, Loader2, Mic, Square } from "lucide-react";
import { Button } from "../ui/button";

interface LiveVivaRecorderProps {
  onRecorded: (file: File) => void;
  disabled?: boolean;
}

function pickRecorderMime(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  const candidates = [
    "video/webm;codecs=vp9,opus",
    "video/webm;codecs=vp8,opus",
    "video/webm",
    "video/mp4",
  ];
  return candidates.find((type) => MediaRecorder.isTypeSupported(type));
}

function extensionForMime(mime: string): string {
  if (mime.includes("mp4")) return "mp4";
  return "webm";
}

function formatElapsed(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

export function LiveVivaRecorder({ onRecorded, disabled = false }: LiveVivaRecorderProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);

  const [phase, setPhase] = useState<"idle" | "starting" | "ready" | "recording" | "stopping">("idle");
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState("");

  const stopTracks = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  };

  const clearTimer = () => {
    if (timerRef.current != null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  useEffect(() => {
    return () => {
      clearTimer();
      if (recorderRef.current && recorderRef.current.state !== "inactive") {
        try {
          recorderRef.current.stop();
        } catch {
          // already stopped
        }
      }
      stopTracks();
    };
  }, []);

  const attachStream = async (stream: MediaStream) => {
    streamRef.current = stream;
    const video = videoRef.current;
    if (!video) return;
    video.srcObject = stream;
    video.muted = true;
    video.playsInline = true;
    await video.play().catch(() => undefined);
  };

  const startPreview = async () => {
    setError("");
    setPhase("starting");
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error("This browser does not support webcam capture.");
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: { echoCancellation: true, noiseSuppression: true },
      });
      await attachStream(stream);
      setPhase("ready");
    } catch (err) {
      stopTracks();
      const message =
        err instanceof Error && err.name === "NotAllowedError"
          ? "Camera or microphone permission was denied. Allow access and try again."
          : err instanceof Error
            ? err.message
            : "Could not start the camera.";
      setError(message);
      setPhase("idle");
    }
  };

  const startRecording = () => {
    const stream = streamRef.current;
    if (!stream || disabled) return;
    const mime = pickRecorderMime();
    if (!mime && typeof MediaRecorder === "undefined") {
      setError("Recording is not supported in this browser.");
      return;
    }
    chunksRef.current = [];
    try {
      const recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      recorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };
      recorder.onerror = () => {
        setError("Recording failed. Try again or use Upload recording.");
        setPhase("ready");
        clearTimer();
      };
      recorder.start(1000);
      setElapsed(0);
      setPhase("recording");
      clearTimer();
      timerRef.current = window.setInterval(() => setElapsed((value) => value + 1), 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start recording.");
    }
  };

  const stopRecording = () => {
    const recorder = recorderRef.current;
    if (!recorder || recorder.state === "inactive") return;
    setPhase("stopping");
    clearTimer();
    recorder.onstop = () => {
      const mime = recorder.mimeType || "video/webm";
      const blob = new Blob(chunksRef.current, { type: mime.split(";")[0] || "video/webm" });
      chunksRef.current = [];
      recorderRef.current = null;
      stopTracks();
      const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
      const file = new File([blob], `viva-live-${stamp}.${extensionForMime(mime)}`, {
        type: blob.type || "video/webm",
      });
      setPhase("idle");
      if (blob.size < 10_000) {
        setError("Recording was too short or empty. Start the camera and try again.");
        return;
      }
      onRecorded(file);
    };
    recorder.stop();
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Point the laptop webcam at the student, record the viva, then the same engine grades the
        session (transcript, Q&amp;A, official mark). Analysis runs after you stop.
      </p>

      <div className="relative mx-auto w-full max-w-xl overflow-hidden rounded-xl border border-border bg-black aspect-video">
        <video ref={videoRef} className="h-full w-full object-cover" playsInline muted />
        {phase === "idle" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-white/80">
            <Camera className="size-8" />
            <span className="text-sm">Camera preview off</span>
          </div>
        )}
        {phase === "starting" && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/40">
            <Loader2 className="size-8 animate-spin text-white" />
          </div>
        )}
        {phase === "recording" && (
          <div className="absolute top-3 left-3 inline-flex items-center gap-2 rounded-full bg-rose-600 px-2.5 py-1 text-xs font-medium text-white">
            <span className="size-2 rounded-full bg-white animate-pulse" />
            REC {formatElapsed(elapsed)}
          </div>
        )}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="flex flex-wrap items-center gap-2">
        {phase === "idle" && (
          <Button type="button" onClick={startPreview} disabled={disabled}>
            <Camera className="size-4" />
            Enable camera
          </Button>
        )}
        {phase === "ready" && (
          <>
            <Button type="button" onClick={startRecording} disabled={disabled}>
              <Circle className="size-4 fill-rose-500 text-rose-500" />
              Start viva
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                stopTracks();
                setElapsed(0);
                setPhase("idle");
              }}
              disabled={disabled}
            >
              Turn off camera
            </Button>
          </>
        )}
        {phase === "recording" && (
          <Button type="button" variant="destructive" onClick={stopRecording} disabled={disabled}>
            <Square className="size-4" />
            Stop and analyze
          </Button>
        )}
        {phase === "stopping" && (
          <Button type="button" disabled>
            <Loader2 className="size-4 animate-spin" />
            Saving recording…
          </Button>
        )}
        <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
          <Mic className="size-3.5" />
          Microphone is recorded with the camera
        </span>
      </div>
    </div>
  );
}
