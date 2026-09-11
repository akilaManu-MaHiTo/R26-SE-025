import { useEffect, useImperativeHandle, useRef, useState, forwardRef } from "react";
import { Camera, Loader2 } from "lucide-react";

export interface CopilotCameraHandle {
  start: () => Promise<void>;
  stop: () => void;
  /** Stop the full-session recorder and hand back the complete recording.
   * Resolves null when nothing usable was captured. */
  stopAndCollectRecording: () => Promise<Blob | null>;
}

export interface SpeechResult {
  text: string;
  isFinal: boolean;
}

interface CopilotCameraProps {
  streaming: boolean;
  onChunk: (blob: Blob) => void;
  /** Instant, on-device/browser transcript results (Web Speech API). This is
   * the low-latency path — see LiveCopilotPage/pipeline.ingest_text. It runs
   * alongside the Groq Whisper audio-chunk path, not instead of it, so
   * accuracy is unaffected if the browser API is unavailable or unreliable. */
  onSpeechResult?: (result: SpeechResult) => void;
}

// Minimal typings for the non-standard Web Speech API (Chrome/Edge only as
// of writing; Safari/Firefox fall back silently to the Groq Whisper path).
interface SpeechRecognitionAlternative {
  transcript: string;
}
interface SpeechRecognitionResultLike {
  isFinal: boolean;
  length: number;
  [index: number]: SpeechRecognitionAlternative;
}
interface SpeechRecognitionResultList {
  length: number;
  [index: number]: SpeechRecognitionResultLike;
}
interface SpeechRecognitionEventLike {
  resultIndex: number;
  results: SpeechRecognitionResultList;
}
interface SpeechRecognitionLike extends EventTarget {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}
type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function getSpeechRecognitionCtor(): SpeechRecognitionCtor | undefined {
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition || w.webkitSpeechRecognition;
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

// The live STT loop above only ever needs audio. The *session* recorder below
// is separate and deliberately keeps video: the official Stage-1 mark depends
// on face coverage, the engagement CNN and lip-motion checks, none of which can
// be derived from a transcript. See viva_copilot/analysis.py.
function pickSessionMime(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  const candidates = [
    "video/webm;codecs=vp9,opus",
    "video/webm;codecs=vp8,opus",
    "video/webm",
    "video/mp4",
  ];
  return candidates.find((type) => MediaRecorder.isTypeSupported(type));
}

// Flush a blob every 5s so a crash/disconnect still leaves a usable partial
// recording instead of losing the whole session.
const SESSION_TIMESLICE_MS = 5000;

// Larger slices reduce STT queueing/rate-limit overhead per chunk while the
// Web Speech API (see LiveCopilotPage) delivers instant partial transcripts.
const SLICE_MS = 4000;

export const CopilotCamera = forwardRef<CopilotCameraHandle, CopilotCameraProps>(function CopilotCamera(
  { streaming, onChunk, onSpeechResult },
  ref,
) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const loopRef = useRef(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const onChunkRef = useRef(onChunk);
  const onSpeechResultRef = useRef(onSpeechResult);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const sessionRecorderRef = useRef<MediaRecorder | null>(null);
  const sessionChunksRef = useRef<Blob[]>([]);
  const sessionMimeRef = useRef<string>("video/webm");
  const recognitionStoppingRef = useRef(false);
  const [previewOn, setPreviewOn] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    onChunkRef.current = onChunk;
  }, [onChunk]);

  useEffect(() => {
    onSpeechResultRef.current = onSpeechResult;
  }, [onSpeechResult]);

  const stopTracks = () => {
    loopRef.current = false;
    recognitionStoppingRef.current = true;
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // already stopped
      }
    }
    recognitionRef.current = null;
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      try {
        recorderRef.current.stop();
      } catch {
        // already stopped
      }
    }
    recorderRef.current = null;
    if (sessionRecorderRef.current && sessionRecorderRef.current.state !== "inactive") {
      try {
        sessionRecorderRef.current.stop();
      } catch {
        // already stopped
      }
    }
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setPreviewOn(false);
  };

  useEffect(() => {
    return () => stopTracks();
  }, []);

  /** Records the whole session (video+audio) in one continuous file.
   * Independent of the 4s STT slice loop above — stopping or restarting that
   * loop must never interrupt this one. */
  const startSessionRecorder = (stream: MediaStream) => {
    if (typeof MediaRecorder === "undefined") return;
    sessionChunksRef.current = [];
    const mime = pickSessionMime();
    try {
      const recorder = mime
        ? new MediaRecorder(stream, { mimeType: mime })
        : new MediaRecorder(stream);
      sessionMimeRef.current = recorder.mimeType || mime || "video/webm";
      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) sessionChunksRef.current.push(event.data);
      };
      recorder.start(SESSION_TIMESLICE_MS);
      sessionRecorderRef.current = recorder;
    } catch {
      // Session recording unavailable — the live copilot still works, but the
      // end-of-session score cannot be produced. Surfaced on stop.
      sessionRecorderRef.current = null;
    }
  };

  const stopAndCollectRecording = (): Promise<Blob | null> =>
    new Promise((resolve) => {
      const recorder = sessionRecorderRef.current;
      const finish = () => {
        const chunks = sessionChunksRef.current;
        sessionChunksRef.current = [];
        sessionRecorderRef.current = null;
        if (!chunks.length) {
          resolve(null);
          return;
        }
        resolve(new Blob(chunks, { type: sessionMimeRef.current }));
      };
      if (!recorder || recorder.state === "inactive") {
        finish();
        return;
      }
      recorder.onstop = finish;
      try {
        recorder.stop();
      } catch {
        finish();
      }
    });

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
      startSessionRecorder(stream);
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
      throw err;
    } finally {
      setStarting(false);
    }
  };

  useImperativeHandle(ref, () => ({
    start: enableCamera,
    stop: stopTracks,
    stopAndCollectRecording,
  }));


  useEffect(() => {
    if (!streaming || !previewOn) {
      loopRef.current = false;
      return;
    }
    const stream = streamRef.current;
    if (!stream) return;

    const audioTracks = stream.getAudioTracks();
    const recordStream = audioTracks.length > 0 ? new MediaStream(audioTracks) : stream;
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
          window.setTimeout(recordSlice, 20);
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
  }, [streaming, previewOn]);

  // Instant browser transcription (Track A). Runs in parallel with the
  // MediaRecorder → Groq Whisper path above; whichever finalizes an
  // utterance first wins server-side (de-duplicated by content hash), so
  // this only ever helps latency and never conflicts with the accuracy
  // backstop.
  useEffect(() => {
    if (!streaming || !previewOn) return;
    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) return; // Unsupported browser (Safari/Firefox) — silently skip.

    let stopped = false;
    recognitionStoppingRef.current = false;

    const startRecognition = () => {
      if (stopped) return;
      const recognition = new Ctor();
      recognition.lang = "en-US";
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.onresult = (event) => {
        let interim = "";
        let final = "";
        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          const result = event.results[i];
          const transcript = result[0]?.transcript ?? "";
          if (result.isFinal) {
            final += transcript;
          } else {
            interim += transcript;
          }
        }
        if (final.trim()) {
          onSpeechResultRef.current?.({ text: final.trim(), isFinal: true });
        } else if (interim.trim()) {
          onSpeechResultRef.current?.({ text: interim.trim(), isFinal: false });
        }
      };
      recognition.onerror = () => {
        // Transient errors (no-speech, network blip) — let onend restart it.
      };
      recognition.onend = () => {
        recognitionRef.current = null;
        if (!stopped && !recognitionStoppingRef.current) {
          // The API auto-stops after silence; restart to keep listening for
          // the whole session.
          window.setTimeout(startRecognition, 250);
        }
      };
      try {
        recognition.start();
        recognitionRef.current = recognition;
      } catch {
        // Already-started or transient failure; onend/timeout will retry.
      }
    };

    startRecognition();

    return () => {
      stopped = true;
      recognitionStoppingRef.current = true;
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {
          // already stopped
        }
      }
      recognitionRef.current = null;
    };
  }, [streaming, previewOn]);


  return (
    <div className="relative w-full h-full overflow-hidden rounded-xl border border-border bg-black">
      <video ref={videoRef} className="h-full w-full object-cover" playsInline muted />

      {!previewOn && !starting && !error && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-white/70">
          <Camera className="size-8" />
          <span className="text-sm">Camera is off</span>
        </div>
      )}
      {starting && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/40">
          <Loader2 className="size-8 animate-spin text-white" />
        </div>
      )}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/70 p-6 text-center">
          <p className="text-sm text-rose-300">{error}</p>
        </div>
      )}

      {streaming && previewOn && (
        <div className="absolute top-3 left-3 inline-flex items-center gap-1.5 rounded-full bg-rose-600/90 px-2.5 py-1 text-xs font-semibold text-white shadow">
          <span className="size-1.5 rounded-full bg-white animate-pulse" />
          LIVE
        </div>
      )}
    </div>
  );
});


