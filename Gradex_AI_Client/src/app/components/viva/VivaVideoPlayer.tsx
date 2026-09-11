import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { GripVertical, X } from "lucide-react";

export interface VivaVideoPlayerHandle {
  seekTo: (seconds: number) => void;
}

interface VivaVideoPlayerProps {
  src: string;
  durationLabel?: string;
  onDurationChange?: (seconds: number) => void;
  /** Detach into a draggable floating player once the inline slot scrolls off-screen. */
  enablePictureInPicture?: boolean;
}

const PIP_WIDTH = 320;
const PIP_MARGIN = 16;
const PIP_HEADER_HEIGHT = 30;
const PIP_HEIGHT = Math.round((PIP_WIDTH * 9) / 16) + PIP_HEADER_HEIGHT;
const PIP_POSITION_KEY = "viva:pip-position";

interface PipPosition {
  left: number;
  top: number;
}

/** Bottom-right of the viewport — the default resting place for the floating player. */
function defaultPipPosition(): PipPosition {
  return {
    left: Math.max(PIP_MARGIN, window.innerWidth - PIP_WIDTH - PIP_MARGIN),
    top: Math.max(PIP_MARGIN, window.innerHeight - PIP_HEIGHT - PIP_MARGIN),
  };
}

function clampToViewport(pos: PipPosition): PipPosition {
  const maxLeft = Math.max(PIP_MARGIN, window.innerWidth - PIP_WIDTH - PIP_MARGIN);
  const maxTop = Math.max(PIP_MARGIN, window.innerHeight - PIP_HEIGHT - PIP_MARGIN);
  return {
    left: Math.min(Math.max(PIP_MARGIN, pos.left), maxLeft),
    top: Math.min(Math.max(PIP_MARGIN, pos.top), maxTop),
  };
}

/**
 * Thin wrapper around the native <video> element that exposes an
 * imperative `seekTo` so sibling panels (key moments, timeline) can jump
 * playback to a specific second without lifting player state up.
 *
 * With `enablePictureInPicture`, the very same <video> node — never a clone,
 * so playback position and play/pause state survive — is re-styled as a fixed,
 * draggable panel whenever its inline slot scrolls out of view. That keeps the
 * recording watchable while the reader is further down in the key-moments list.
 */
export const VivaVideoPlayer = forwardRef<VivaVideoPlayerHandle, VivaVideoPlayerProps>(
  function VivaVideoPlayer(
    { src, durationLabel, onDurationChange, enablePictureInPicture = false },
    ref
  ) {
    const videoRef = useRef<HTMLVideoElement>(null);
    const slotRef = useRef<HTMLDivElement>(null);
    const frameRef = useRef<HTMLDivElement>(null);

    const [isOffScreen, setIsOffScreen] = useState(false);
    const [dismissed, setDismissed] = useState(false);
    const [position, setPosition] = useState<PipPosition | null>(null);
    const [isDragging, setIsDragging] = useState(false);
    const dragOffset = useRef<PipPosition>({ left: 0, top: 0 });

    useImperativeHandle(ref, () => ({
      seekTo: (seconds: number) => {
        const video = videoRef.current;
        if (!video) return;
        video.currentTime = seconds;
        if (video.paused) {
          void video.play().catch(() => {
            // Autoplay can be blocked by the browser; seeking already succeeded.
          });
        }
        // A seek is an explicit request to watch, so bring a dismissed
        // floating player back instead of jumping somewhere invisible.
        setDismissed(false);
      },
    }));

    // Track whether the inline slot is on screen; off-screen means float.
    useEffect(() => {
      if (!enablePictureInPicture) {
        setIsOffScreen(false);
        return;
      }
      const slot = slotRef.current;
      if (!slot) return;

      const observer = new IntersectionObserver(
        ([entry]) => setIsOffScreen(!entry.isIntersecting),
        // A sliver of video still on screen is not worth watching, so float as
        // soon as most of the player has scrolled away.
        { threshold: 0.35 }
      );
      observer.observe(slot);
      return () => observer.disconnect();
    }, [enablePictureInPicture]);

    // Scrolling back up to the real player clears any manual dismissal, so the
    // next scroll-down offers the floating player again.
    useEffect(() => {
      if (!isOffScreen) setDismissed(false);
    }, [isOffScreen]);

    // Restore the last drag position (or fall back to bottom-right) the first
    // time the player floats, before paint so it never flashes at 0,0.
    useLayoutEffect(() => {
      if (!isOffScreen || position) return;
      let restored: PipPosition | null = null;
      try {
        const raw = window.localStorage.getItem(PIP_POSITION_KEY);
        if (raw) {
          const parsed = JSON.parse(raw) as Partial<PipPosition>;
          if (typeof parsed.left === "number" && typeof parsed.top === "number") {
            restored = { left: parsed.left, top: parsed.top };
          }
        }
      } catch {
        // Storage can be unavailable or hold stale junk; the default is fine.
      }
      setPosition(clampToViewport(restored ?? defaultPipPosition()));
    }, [isOffScreen, position]);

    // Keep the panel on screen when the window is resized.
    useEffect(() => {
      if (!isOffScreen) return;
      const onResize = () => setPosition((prev) => (prev ? clampToViewport(prev) : prev));
      window.addEventListener("resize", onResize);
      return () => window.removeEventListener("resize", onResize);
    }, [isOffScreen]);

    const onDragStart = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
      const frame = frameRef.current;
      if (!frame) return;
      const rect = frame.getBoundingClientRect();
      dragOffset.current = { left: e.clientX - rect.left, top: e.clientY - rect.top };
      setIsDragging(true);
      e.currentTarget.setPointerCapture(e.pointerId);
      e.preventDefault();
    }, []);

    const onDragMove = useCallback(
      (e: React.PointerEvent<HTMLDivElement>) => {
        if (!isDragging) return;
        setPosition(
          clampToViewport({
            left: e.clientX - dragOffset.current.left,
            top: e.clientY - dragOffset.current.top,
          })
        );
      },
      [isDragging]
    );

    const onDragEnd = useCallback(
      (e: React.PointerEvent<HTMLDivElement>) => {
        if (!isDragging) return;
        setIsDragging(false);
        e.currentTarget.releasePointerCapture(e.pointerId);
        setPosition((prev) => {
          if (prev) {
            try {
              window.localStorage.setItem(PIP_POSITION_KEY, JSON.stringify(prev));
            } catch {
              // Persisting the position is a convenience, not a requirement.
            }
          }
          return prev;
        });
      },
      [isDragging]
    );

    const floating = isOffScreen && !dismissed && position !== null;

    const player = (
      <div
        ref={frameRef}
        className={
          floating
            ? "fixed z-50 overflow-hidden rounded-xl border border-border bg-background shadow-2xl"
            : "relative w-full h-full rounded-xl overflow-hidden bg-black border border-border"
        }
        style={floating ? { left: position.left, top: position.top, width: PIP_WIDTH } : undefined}
      >
        {floating && (
          <div
            className={
              "flex items-center gap-1.5 border-b border-border bg-muted/60 px-2 py-1.5 select-none touch-none " +
              (isDragging ? "cursor-grabbing" : "cursor-grab")
            }
            onPointerDown={onDragStart}
            onPointerMove={onDragMove}
            onPointerUp={onDragEnd}
            onPointerCancel={onDragEnd}
          >
            <GripVertical className="size-3.5 shrink-0 text-muted-foreground" />
            <span className="text-xs font-medium text-foreground">Recording</span>
            {durationLabel && (
              <span className="text-xs text-muted-foreground tabular-nums">{durationLabel}</span>
            )}
            <button
              type="button"
              className="ml-auto rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
              aria-label="Hide floating player"
              onPointerDown={(e) => e.stopPropagation()}
              onClick={() => setDismissed(true)}
            >
              <X className="size-3.5" />
            </button>
          </div>
        )}
        <div className={floating ? "bg-black aspect-video" : "w-full h-full"}>
          <video
            ref={videoRef}
            src={src}
            className="w-full h-full object-contain"
            controls
            controlsList="nodownload"
            playsInline
            aria-label="Viva recording"
            onLoadedMetadata={(e) => {
              const duration = e.currentTarget.duration;
              if (Number.isFinite(duration) && duration > 0) {
                onDurationChange?.(duration);
              }
            }}
          />
        </div>
        {!floating && durationLabel && (
          <div className="pointer-events-none absolute top-2 right-2 rounded-md bg-black/60 px-2 py-0.5 text-xs font-medium text-white">
            {durationLabel}
          </div>
        )}
      </div>
    );

    // The slot reserves the inline space (and is what the observer watches), so
    // the page does not jump when the player detaches into the floating panel.
    return (
      <div ref={slotRef} className="relative mx-auto w-full max-w-xl aspect-video">
        {floating ? (
          <div className="absolute inset-0 flex items-center justify-center rounded-xl border border-dashed border-border bg-muted/30 text-xs text-muted-foreground">
            Playing in floating window
          </div>
        ) : null}
        <div className={floating ? undefined : "absolute inset-0"}>{player}</div>
      </div>
    );
  }
);
