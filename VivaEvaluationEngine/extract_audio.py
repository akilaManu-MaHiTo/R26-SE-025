import glob
import os
import shutil
import subprocess


def _find_ffmpeg() -> str | None:
    """Locate ffmpeg even when this process's PATH is stale.

    On Windows, a User-scope PATH change (e.g. from a winget install) is
    only visible to processes started *after* the change. A long-lived
    terminal/IDE that was already open won't see it until fully restarted,
    which isn't always practical mid-session. As a fallback, search the
    common per-user install locations directly.
    """
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        return ffmpeg_bin

    local_app_data = os.environ.get("LOCALAPPDATA", "")
    candidates = []
    if local_app_data:
        candidates.extend(
            glob.glob(
                os.path.join(
                    local_app_data,
                    "Microsoft", "WinGet", "Packages",
                    "Gyan.FFmpeg_*", "ffmpeg-*-full_build", "bin", "ffmpeg.exe",
                )
            )
        )
    candidates.extend(glob.glob(r"C:\ffmpeg\bin\ffmpeg.exe"))
    candidates.extend(glob.glob(r"C:\ProgramData\chocolatey\bin\ffmpeg.exe"))

    return candidates[0] if candidates else None


def _ensure_ffmpeg_on_path() -> str | None:
    """Find ffmpeg and, if it's not already resolvable via PATH, prepend its
    directory to this process's os.environ["PATH"].

    This matters beyond our own subprocess call below: openai-whisper's
    internal audio loader (whisper.audio.load_audio) *also* shells out to a
    bare "ffmpeg" command via subprocess, independently of anything this
    module does. Patching the process-wide PATH here (called before
    transcribe_audio runs) fixes that call site too, not just this one.
    """
    ffmpeg_bin = _find_ffmpeg()
    if ffmpeg_bin is None:
        return None

    ffmpeg_dir = os.path.dirname(ffmpeg_bin)
    path_entries = os.environ.get("PATH", "").split(os.pathsep)
    if ffmpeg_dir not in path_entries:
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

    return ffmpeg_bin


def extract_audio(video_path: str, output_wav_path: str) -> str:
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    ffmpeg_bin = _ensure_ffmpeg_on_path()
    if ffmpeg_bin is None:
        raise RuntimeError("ffmpeg not found on PATH. Install ffmpeg and retry.")

    cmd = [
        ffmpeg_bin,
        "-i",
        video_path,
        "-ac",
        "1",
        "-ar",
        "16000",
        "-acodec",
        "pcm_s16le",
        output_wav_path,
        "-y",
    ]

    completed = subprocess.run(cmd, capture_output=True, text=True)
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        raise RuntimeError(f"Audio extraction failed: {stderr}")

    return output_wav_path
