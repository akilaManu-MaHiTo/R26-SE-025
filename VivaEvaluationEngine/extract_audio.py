import subprocess
import os

def extract_audio(video_path, output_wav_path):
    """Extract audio from video file and convert to 16kHz mono WAV"""
    subprocess.run([
        "ffmpeg", "-i", video_path,
        "-ac", "1",          # mono
        "-ar", "16000",      # 16kHz sample rate
        "-acodec", "pcm_s16le",
        output_wav_path, "-y"
    ], check=True)
    print(f"Audio extracted successfully: {output_wav_path}")

if __name__ == "__main__":
    # Extract audio from the first test video
    video_path = "videos/video_test-01.mp4"
    output_wav_path = "audio.wav"
    
    if os.path.exists(video_path):
        extract_audio(video_path, output_wav_path)
    else:
        print(f"Video file not found: {video_path}")
        # Try the second video
        video_path = "videos/video_test-02.mp4"
        if os.path.exists(video_path):
            extract_audio(video_path, output_wav_path)
        else:
            print("No video files found in videos directory")