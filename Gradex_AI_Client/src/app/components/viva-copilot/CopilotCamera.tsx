import { useEffect, useRef, useState } from "react";
import { Camera, Loader2, Mic, VideoOff } from "lucide-react";
import { Button } from "../ui/button";

interface CopilotCameraProps {
  streaming: boolean;
  onChunk: (blob: Blob) => void;
  disabled?: boolean;
}

function pickMime(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "video/webm;codecs=vp8,opus",
    "video/webm",
    "audio/mp4",
    "video/mp4",
  ];
  return candidates.find((type) => MediaRecorder.isTypeSupported(type));
}

const SLICE_MS = 12000;

export function CopilotCamera({ streaming, onChunk, disabled = false }: CopilotCameraProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const loopRef = useRef(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const onChunkRef = useRef(onChunk);
  const [previewOn, setPreviewOn] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    onChunkRef.current = onChunk;
  }, [onChunk]);

  const stopTracks = () => {
    loopRef.current = false;
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      try {
        recorderRef.current.stop();
      } catch {
        // already stopped
      }
    }
    recorderRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setPreviewOn(false);
  };

  useEffect(() => {
    return () => stopTracks();
  }, []);

  const enableCamera = async () => {
    setError("");
    setStarting(true);
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error("This browser does not support webcam capture.");
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: { echoCancellation: true, noiseSuppression: true },
      });
      streamRef.current = stream;
      const video = videoRef.current;
      if (video) {
        video.srcObject = stream;
        video.muted = true;
        video.playsInline = true;
        await video.play().catch(() => undefined);
      }
      setPreviewOn(true);
    } catch (err) {
      stopTracks();
      const message =
        err instanceof Error && err.name === "NotAllowedError"
          ? "Camera or microphone permission was denied. Allow access and try again."
          : err instanceof Error
            ? err.message
            : "Could not start the camera.";
      setError(message);
    } finally {
      setStarting(false);
    }
  };

  useEffect(() => {
    if (!streaming || !previewOn || disabled) {
      loopRef.current = false;
      return;
    }
    const stream = streamRef.current;
    if (!stream) return;

    const audioTracks = stream.getAudioTracks();
    const recordStream =
      audioTracks.length > 0 ? new MediaStream(audioTracks) : stream;
    const mime = pickMime();
    let cancelled = false;
    loopRef.current = true;

    const recordSlice = () => {
      if (cancelled || !loopRef.current) return;
      if (typeof MediaRecorder === "undefined") {
        setError("Recording is not supported in this browser.");
        return;
      }
      const chunks: Blob[] = [];
      let recorder: MediaRecorder;
      try {
        recorder = mime ? new MediaRecorder(recordStream, { mimeType: mime }) : new MediaRecorder(recordStream);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not start audio capture.");
        return;
      }
      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) chunks.push(event.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunks, { type: recorder.mimeType || mime || "audio/webm" });
        if (blob.size > 800 && loopRef.current) {
          onChunkRef.current(blob);
        }
        if (!cancelled && loopRef.current) {
          window.setTimeout(recordSlice, 40);
        }
      };
      recorder.start();
      recorderRef.current = recorder;
      window.setTimeout(() => {
        if (recorder.state !== "inactive") recorder.stop();
      }, SLICE_MS);
    };

    recordSlice();
    return () => {
      cancelled = true;
      loopRef.current = false;
      if (recorderRef.current && recorderRef.current.state !== "inactive") {
        try {
          recorderRef.current.stop();
        } catch {
          // already stopped
        }
      }
      recorderRef.current = null;
    };
  }, [streaming, previewOn, disabled]);

  return (
    <div className="space-y-3">
      <div className="relative w-full max-h-[280px] overflow-hidden rounded-xl border border-border bg-black aspect-video">
        <video ref={videoRef} className="h-full w-full object-cover" playsInline muted />
        {!previewOn && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-white/80">
            <Camera className="size-8" />
            <span className="text-sm">Point the camera at the student</span>
          </div>
        )}
        {starting && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/40">
            <Loader2 className="size-8 animate-spin text-white" />
          </div>
        )}
        {streaming && previewOn && (
          <div className="absolute top-3 left-3 inline-flex items-center gap-2 rounded-full bg-rose-600 px-2.5 py-1 text-xs font-medium text-white">
            <span className="size-2 rounded-full bg-white animate-pulse" />
            LIVE
          </div>
        )}
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="flex flex-wrap items-center gap-2">
        {!previewOn ? (
          <Button type="button" onClick={enableCamera} disabled={disabled || starting}>
            <Camera className="size-4" />
            Enable camera
          </Button>
        ) : (
          <Button type="button" variant="outline" onClick={stopTracks} disabled={streaming}>
            <VideoOff className="size-4" />
            Turn off camera
          </Button>
        )}
        <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
          <Mic className="size-3.5" />
          Microphone is sent about every 12 seconds in one audio slice (bulk STT, not per-word API calls)
        </span>
      </div>
    </div>
  );
}
