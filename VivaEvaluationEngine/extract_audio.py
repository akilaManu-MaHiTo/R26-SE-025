import os
import shutil
import subprocess


def extract_audio(video_path: str, output_wav_path: str) -> str:
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    ffmpeg_bin = shutil.which("ffmpeg")
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
