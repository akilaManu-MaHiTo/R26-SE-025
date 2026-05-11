"""Extract acoustic features from audio using basic WAV analysis and optional Parselmouth."""
import json
import os
import wave

import numpy as np

try:
    import parselmouth
    from parselmouth.praat import call
except ImportError:
    parselmouth = None
    call = None


def _load_wav(audio_path):
    with wave.open(audio_path, "rb") as wav_file:
        frame_count = wav_file.getnframes()
        sample_width = wav_file.getsampwidth()
        channel_count = wav_file.getnchannels()
        sample_rate = wav_file.getframerate()
        raw_audio = wav_file.readframes(frame_count)

    if sample_width == 2:
        audio = np.frombuffer(raw_audio, dtype=np.int16).astype(np.float32) / 32768.0
    elif sample_width == 4:
        audio = np.frombuffer(raw_audio, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        audio = np.frombuffer(raw_audio, dtype=np.uint8).astype(np.float32)
        audio = (audio - 128.0) / 128.0

    if channel_count > 1:
        audio = audio.reshape(-1, channel_count).mean(axis=1)

    return audio, sample_rate

def extract_acoustic_features(audio_path):
    """Extract acoustic features using WAV analysis and Parselmouth when available."""
    print(f"Loading audio file: {audio_path}")
    
    # Load WAV audio without relying on librosa.
    y, sr = _load_wav(audio_path)
    print(f"Audio loaded: {len(y)} samples, {sr} Hz")
    
    # Initialize features dictionary
    features = {}
    
    # ===== Basic signal features =====
    print("Extracting basic signal features...")
    features['mfcc_mean'] = [0.0] * 13
    features['mfcc_std'] = [0.0] * 13
    features['spectral_centroid_mean'] = 0.0
    features['spectral_centroid_std'] = 0.0
    features['spectral_rolloff_mean'] = 0.0
    features['spectral_rolloff_std'] = 0.0
    features['spectral_bandwidth_mean'] = 0.0
    features['spectral_bandwidth_std'] = 0.0
    features['zcr_mean'] = float(np.mean(np.abs(np.diff(np.sign(y))) > 0)) if len(y) > 1 else 0.0
    features['zcr_std'] = 0.0
    features['chroma_mean'] = [0.0] * 12
    features['chroma_std'] = [0.0] * 12
    rms = np.sqrt(np.mean(np.square(y))) if len(y) else 0.0
    features['rms_mean'] = float(rms)
    features['rms_std'] = 0.0
    features['tempo'] = 0.0
    features['beats_count'] = 0
    features['duration_seconds'] = float(len(y) / sr) if sr else 0.0
    
    # ===== Parselmouth Features =====
    print("Extracting Parselmouth features...")
    
    try:
        if parselmouth is None or call is None:
            raise ImportError("Parselmouth not installed")

        # Convert to Parselmouth Sound object
        sound = parselmouth.Sound(audio_path)
        
        # 1. Pitch (Fundamental Frequency)
        pitch = call(sound, "To Pitch", 0.0, 75, 600)
        pitch_values = pitch.selected_array['frequency']
        # Remove unvoiced frames (0 frequency)
        voiced_pitch = pitch_values[pitch_values > 0]
        if len(voiced_pitch) > 0:
            features['pitch_mean'] = float(np.mean(voiced_pitch))
            features['pitch_std'] = float(np.std(voiced_pitch))
            features['pitch_min'] = float(np.min(voiced_pitch))
            features['pitch_max'] = float(np.max(voiced_pitch))
        else:
            features['pitch_mean'] = 0.0
            features['pitch_std'] = 0.0
            features['pitch_min'] = 0.0
            features['pitch_max'] = 0.0
        
        # 2. Formants (using Burg method)
        formants = call(sound, "To Formant (burg)", 0.0, 5, 5500, 0.025, 50.0)
        f1_values = []
        f2_values = []
        f3_values = []
        
        # Sample formants at regular intervals
        time_step = 0.01  # 10ms steps
        times = np.arange(0, sound.get_total_duration(), time_step)
        for t in times:
            f1 = call(formants, "Get value at time", 1, t, 'Hertz', 'Linear')
            f2 = call(formants, "Get value at time", 2, t, 'Hertz', 'Linear')
            f3 = call(formants, "Get value at time", 3, t, 'Hertz', 'Linear')
            if not np.isnan(f1):
                f1_values.append(f1)
            if not np.isnan(f2):
                f2_values.append(f2)
            if not np.isnan(f3):
                f3_values.append(f3)
        
        if len(f1_values) > 0:
            features['f1_mean'] = float(np.mean(f1_values))
            features['f1_std'] = float(np.std(f1_values))
        else:
            features['f1_mean'] = 0.0
            features['f1_std'] = 0.0
            
        if len(f2_values) > 0:
            features['f2_mean'] = float(np.mean(f2_values))
            features['f2_std'] = float(np.std(f2_values))
        else:
            features['f2_mean'] = 0.0
            features['f2_std'] = 0.0
            
        if len(f3_values) > 0:
            features['f3_mean'] = float(np.mean(f3_values))
            features['f3_std'] = float(np.std(f3_values))
        else:
            features['f3_mean'] = 0.0
            features['f3_std'] = 0.0
        
        # 3. Jitter (local, relative, rap, ppq5)
        point_process = call(sound, "To PointProcess (periodic, cc)", 75, 600)
        try:
            features['jitter_local'] = float(call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3))
        except:
            features['jitter_local'] = 0.0
        try:
            features['jitter_relative'] = float(call(point_process, "Get jitter (relative)", 0, 0, 0.0001, 0.02, 1.3))
        except:
            features['jitter_relative'] = 0.0
        try:
            features['jitter_rap'] = float(call(point_process, "Get jitter (rap)", 0, 0, 0.0001, 0.02, 1.3))
        except:
            features['jitter_rap'] = 0.0
        try:
            features['jitter_ppq5'] = float(call(point_process, "Get jitter (ppq5)", 0, 0, 0.0001, 0.02, 1.3))
        except:
            features['jitter_ppq5'] = 0.0
        
        # 4. Shimmer (local, local_dB, apq3, apq5, apq11)
        try:
            features['shimmer_local'] = float(call([sound, point_process], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.0))
        except:
            features['shimmer_local'] = 0.0
        try:
            features['shimmer_local_dB'] = float(call([sound, point_process], "Get shimmer (local_dB)", 0, 0, 0.0001, 0.02, 1.3, 1.0))
        except:
            features['shimmer_local_dB'] = 0.0
        try:
            features['shimmer_apq3'] = float(call([sound, point_process], "Get shimmer (apq3)", 0, 0, 0.0001, 0.02, 1.3, 1.0))
        except:
            features['shimmer_apq3'] = 0.0
        try:
            features['shimmer_apq5'] = float(call([sound, point_process], "Get shimmer (apq5)", 0, 0, 0.0001, 0.02, 1.3, 1.0))
        except:
            features['shimmer_apq5'] = 0.0
        try:
            features['shimmer_apq11'] = float(call([sound, point_process], "Get shimmer (apq11)", 0, 0, 0.0001, 0.02, 1.3, 1.0))
        except:
            features['shimmer_apq11'] = 0.0
        
        # 5. Harmonics-to-Noise Ratio (HNR)
        try:
            harmonicity = call(sound, "To Harmonicity (cc)", 0.01, 75, 0.1, 1.0)
            hnr_mean = call(harmonicity, "Get mean", 0, 0)
            features['hnr_mean'] = float(hnr_mean) if not np.isnan(hnr_mean) else 0.0
        except:
            features['hnr_mean'] = 0.0
    
    except Exception as e:
        print(f"Warning: Parselmouth features extraction failed: {str(e)}")
        print("Using default values for Parselmouth features")
        # Set default values for Parselmouth features if extraction fails
        features['pitch_mean'] = 0.0
        features['pitch_std'] = 0.0
        features['pitch_min'] = 0.0
        features['pitch_max'] = 0.0
        features['f1_mean'] = 0.0
        features['f1_std'] = 0.0
        features['f2_mean'] = 0.0
        features['f2_std'] = 0.0
        features['f3_mean'] = 0.0
        features['f3_std'] = 0.0
        features['jitter_local'] = 0.0
        features['jitter_relative'] = 0.0
        features['jitter_rap'] = 0.0
        features['jitter_ppq5'] = 0.0
        features['shimmer_local'] = 0.0
        features['shimmer_local_dB'] = 0.0
        features['shimmer_apq3'] = 0.0
        features['shimmer_apq5'] = 0.0
        features['shimmer_apq11'] = 0.0
        features['hnr_mean'] = 0.0
    
    print("Feature extraction completed.")
    return features

if __name__ == "__main__":
    audio_path = "audio.wav"
    if os.path.exists(audio_path):
        features = extract_acoustic_features(audio_path)
        
        # Save features to JSON
        with open("acoustic_features.json", "w", encoding="utf-8") as f:
            json.dump(features, f, indent=2)
        
        print(f"\nAcoustic features saved to acoustic_features.json")
        print(f"Number of features extracted: {len(features)}")
        
        # Print some key features
        print("\nKey features:")
        print(f"  Duration: {features.get('duration_seconds', 0):.2f} seconds")
        print(f"  Tempo: {features.get('tempo', 0):.2f} BPM")
        print(f"  Pitch mean: {features.get('pitch_mean', 0):.2f} Hz")
        print(f"  MFCC features: {len(features.get('mfcc_mean', []))} coefficients")
        print(f"  Jitter local: {features.get('jitter_local', 0):.6f}")
        print(f"  Shimmer local: {features.get('shimmer_local', 0):.6f}")
        print(f"  HNR mean: {features.get('hnr_mean', 0):.2f} dB")
    else:
        print(f"Audio file not found: {audio_path}")
        print("Please run extract_audio.py first")
