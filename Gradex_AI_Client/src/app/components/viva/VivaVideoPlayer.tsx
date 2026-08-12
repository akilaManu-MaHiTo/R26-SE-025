import { forwardRef, useImperativeHandle, useRef } from "react";

export interface VivaVideoPlayerHandle {
  seekTo: (seconds: number) => void;
}

interface VivaVideoPlayerProps {
  src: string;
  durationLabel?: string;
  onDurationChange?: (seconds: number) => void;
}

/**
 * Thin wrapper around the native <video> element that exposes an
 * imperative `seekTo` so sibling panels (key moments, timeline) can jump
 * playback to a specific second without lifting player state up.
 */
export const VivaVideoPlayer = forwardRef<VivaVideoPlayerHandle, VivaVideoPlayerProps>(
  function VivaVideoPlayer({ src, durationLabel, onDurationChange }, ref) {
    const videoRef = useRef<HTMLVideoElement>(null);

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
      },
    }));

    return (
      <div className="relative rounded-xl overflow-hidden bg-black aspect-video border border-border">
        <video
          ref={videoRef}
          src={src}
          className="w-full h-full object-contain"
          controls
          controlsList="nodownload"
          playsInline
          aria-label="Viva recording"
          onLoadedMetadata={(e) => onDurationChange?.(e.currentTarget.duration)}
        />
        {durationLabel && (
          <div className="pointer-events-none absolute top-2 right-2 rounded-md bg-black/60 px-2 py-0.5 text-xs font-medium text-white">
            {durationLabel}
          </div>
        )}
      </div>
    );
  }
);
