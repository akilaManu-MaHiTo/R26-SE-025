"""
Audio Analysis Pipeline for Viva Evaluation
Combines audio extraction, transcription, acoustic features, and emotion detection
Outputs comprehensive audio features for grading enhancement
"""

import os
import json
import sys
from datetime import datetime
from pathlib import Path

# Import audio processing modules
from extract_audio import extract_audio
from transcribe import transcribe_audio
from extract_features import extract_acoustic_features
from extract_emotion import extract_speech_emotion


class AudioAnalyzer:
    """Main orchestrator for audio analysis pipeline"""
    
    def __init__(self, video_path, output_dir="outputs"):
        self.video_path = video_path
        self.audio_path = "audio_temp.wav"
        self.output_dir = output_dir
        self.results = {}
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
    def run_pipeline(self):
        """Execute the complete audio analysis pipeline"""
        print("=" * 60)
        print("Starting Audio Analysis Pipeline")
        print("=" * 60)
        print(f"Video: {self.video_path}")
        print(f"Output directory: {self.output_dir}")
        print()
        
        try:
            # Step 1: Extract audio from video
            print("[1/4] Extracting audio from video...")
            self._step_extract_audio()
            
            # Step 2: Transcribe audio
            print("\n[2/4] Transcribing audio...")
            self._step_transcribe()
            
            # Step 3: Extract acoustic features
            print("\n[3/4] Extracting acoustic features...")
            self._step_extract_features()
            
            # Step 4: Extract emotion features
            print("\n[4/4] Extracting emotion features...")
            self._step_extract_emotion()
            
            # Consolidate all results
            print("\nConsolidating results...")
            self._consolidate_results()
            
            # Save comprehensive output
            self._save_output()
            
            print("\n" + "=" * 60)
            print("Audio Analysis Pipeline Completed Successfully!")
            print("=" * 60)
            return True
            
        except Exception as e:
            print(f"\n[ERROR] Pipeline failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            # Clean up temporary audio file
            if os.path.exists(self.audio_path):
                os.remove(self.audio_path)
                print(f"\nCleaned up temporary audio file")
    
    def _step_extract_audio(self):
        """Extract audio from video"""
        try:
            if not os.path.exists(self.video_path):
                raise FileNotFoundError(f"Video file not found: {self.video_path}")
            
            print(f"  Processing: {self.video_path}")
            extract_audio(self.video_path, self.audio_path)
            
            if not os.path.exists(self.audio_path):
                raise RuntimeError("Failed to extract audio")
            
            self.results['audio_extraction'] = {
                'status': 'success',
                'audio_path': self.audio_path,
                'file_size_mb': os.path.getsize(self.audio_path) / (1024 * 1024)
            }
            print("  ✓ Audio extraction completed")
            
        except Exception as e:
            self.results['audio_extraction'] = {
                'status': 'failed',
                'error': str(e)
            }
            raise
    
    def _step_transcribe(self):
        """Transcribe audio using Whisper"""
        try:
            if not os.path.exists(self.audio_path):
                raise FileNotFoundError(f"Audio file not found: {self.audio_path}")
            
            transcript, segments = transcribe_audio(self.audio_path, model_size="base")
            
            self.results['transcription'] = {
                'status': 'success',
                'transcript': transcript,
                'num_segments': len(segments),
                'duration_seconds': segments[-1]['end'] if segments else 0,
                'language': 'english'
            }
            print("  ✓ Transcription completed")
            
        except Exception as e:
            self.results['transcription'] = {
                'status': 'failed',
                'error': str(e)
            }
            print(f"  ⚠ Transcription failed: {str(e)}")
    
    def _step_extract_features(self):
        """Extract acoustic features from audio"""
        try:
            if not os.path.exists(self.audio_path):
                raise FileNotFoundError(f"Audio file not found: {self.audio_path}")
            
            acoustic_features = extract_acoustic_features(self.audio_path)
            
            self.results['acoustic_features'] = {
                'status': 'success',
                'features': acoustic_features,
                'num_features': len(acoustic_features),
                'key_metrics': {
                    'duration_seconds': acoustic_features.get('duration_seconds', 0),
                    'tempo_bpm': acoustic_features.get('tempo', 0),
                    'pitch_mean_hz': acoustic_features.get('pitch_mean', 0),
                    'energy_rms': acoustic_features.get('rms_mean', 0),
                    'harmonics_to_noise_ratio': acoustic_features.get('hnr_mean', 0),
                    'jitter_local': acoustic_features.get('jitter_local', 0),
                    'shimmer_local': acoustic_features.get('shimmer_local', 0)
                }
            }
            print("  ✓ Acoustic features extraction completed")
            
        except Exception as e:
            self.results['acoustic_features'] = {
                'status': 'failed',
                'error': str(e)
            }
            print(f"  ⚠ Feature extraction failed: {str(e)}")
    
    def _step_extract_emotion(self):
        """Extract emotion features from audio"""
        try:
            if not os.path.exists(self.audio_path):
                raise FileNotFoundError(f"Audio file not found: {self.audio_path}")
            
            emotion_features = extract_speech_emotion(self.audio_path)
            
            self.results['emotion_features'] = {
                'status': 'success',
                'predicted_emotion': emotion_features.get('predicted_emotion', 'unknown'),
                'emotion_index': emotion_features.get('emotion_index', -1),
                'confidence': emotion_features.get('confidence', 0),
                'emotion_probabilities': emotion_features.get('emotion_probabilities', {}),
                'all_features': emotion_features
            }
            print("  ✓ Emotion features extraction completed")
            
        except Exception as e:
            self.results['emotion_features'] = {
                'status': 'failed',
                'error': str(e)
            }
            print(f"  ⚠ Emotion extraction failed: {str(e)}")
    
    def _consolidate_results(self):
        """Consolidate all results into a single structure"""
        self.results['metadata'] = {
            'timestamp': datetime.now().isoformat(),
            'video_source': self.video_path,
            'pipeline_version': '1.0',
            'components': {
                'audio_extraction': self.results.get('audio_extraction', {}).get('status', 'unknown'),
                'transcription': self.results.get('transcription', {}).get('status', 'unknown'),
                'acoustic_features': self.results.get('acoustic_features', {}).get('status', 'unknown'),
                'emotion_features': self.results.get('emotion_features', {}).get('status', 'unknown')
            }
        }
        
        # Create grading-relevant summary
        self.results['grading_summary'] = self._create_grading_summary()
    
    def _create_grading_summary(self):
        """Create a summary focused on grading metrics"""
        summary = {}
        
        # Acoustic metrics for grading
        acoustic = self.results.get('acoustic_features', {})
        if acoustic.get('status') == 'success':
            metrics = acoustic.get('key_metrics', {})
            summary['audio_quality'] = {
                'duration_seconds': metrics.get('duration_seconds', 0),
                'clarity': 1.0 - (metrics.get('jitter_local', 0) * 100),  # Approximate clarity score
                'stability': 1.0 - (metrics.get('shimmer_local', 0) * 10),  # Approximate stability score
                'energy_level': metrics.get('energy_rms', 0),
                'pitch_variation': metrics.get('pitch_mean_hz', 0)
            }
        
        # Emotion for grading
        emotion = self.results.get('emotion_features', {})
        if emotion.get('status') == 'success':
            summary['speech_emotion'] = {
                'predicted_emotion': emotion.get('predicted_emotion', 'unknown'),
                'confidence': emotion.get('confidence', 0),
                'emotion_scores': emotion.get('emotion_probabilities', {})
            }
        
        # Transcription for grading
        transcription = self.results.get('transcription', {})
        if transcription.get('status') == 'success':
            summary['speech_content'] = {
                'transcript': transcription.get('transcript', '')[:200] + '...',  # First 200 chars
                'full_transcript_length': len(transcription.get('transcript', '')),
                'num_segments': transcription.get('num_segments', 0)
            }
        
        return summary
    
    def _save_output(self):
        """Save consolidated results to JSON"""
        output_file = os.path.join(self.output_dir, 'audio_analysis_output.json')
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n✓ Results saved to: {output_file}")
        
        # Also save a summary file
        summary_file = os.path.join(self.output_dir, 'grading_summary.json')
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump({
                'metadata': self.results.get('metadata', {}),
                'grading_summary': self.results.get('grading_summary', {})
            }, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"✓ Grading summary saved to: {summary_file}")
        
        # Print summary
        self._print_summary()
    
    def _print_summary(self):
        """Print a summary of the analysis results"""
        print("\n" + "=" * 60)
        print("Analysis Summary")
        print("=" * 60)
        
        metadata = self.results.get('metadata', {})
        print(f"Timestamp: {metadata.get('timestamp', 'N/A')}")
        print(f"Video: {metadata.get('video_source', 'N/A')}")
        print()
        
        print("Component Status:")
        components = metadata.get('components', {})
        for component, status in components.items():
            symbol = "✓" if status == 'success' else "✗"
            print(f"  {symbol} {component}: {status}")
        print()
        
        grading = self.results.get('grading_summary', {})
        if grading.get('audio_quality'):
            print("Audio Quality Metrics:")
            aq = grading['audio_quality']
            print(f"  Duration: {aq.get('duration_seconds', 0):.2f} seconds")
            print(f"  Clarity: {aq.get('clarity', 0):.2%}")
            print(f"  Stability: {aq.get('stability', 0):.2%}")
        
        if grading.get('speech_emotion'):
            print("\nSpeech Emotion:")
            se = grading['speech_emotion']
            print(f"  Detected: {se.get('predicted_emotion', 'N/A')}")
            print(f"  Confidence: {se.get('confidence', 0):.2%}")
        
        if grading.get('speech_content'):
            print("\nSpeech Content:")
            sc = grading['speech_content']
            print(f"  Transcript length: {sc.get('full_transcript_length', 0)} characters")
            print(f"  Number of segments: {sc.get('num_segments', 0)}")


def find_video_files(directory="videos"):
    """Find all video files in a directory"""
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm']
    videos = []
    
    if os.path.isdir(directory):
        for file in os.listdir(directory):
            if any(file.lower().endswith(ext) for ext in video_extensions):
                videos.append(os.path.join(directory, file))
    
    return sorted(videos)


def main():
    """Main entry point"""
    print("\n" + "=" * 60)
    print("Audio Analysis Pipeline for Viva Evaluation")
    print("=" * 60 + "\n")
    
    # Find videos to process
    video_files = find_video_files()
    
    if not video_files:
        print("No video files found in 'videos' directory")
        print("Usage: python audio_analyzer.py [video_path]")
        sys.exit(1)
    
    # Process the first video found (or specified)
    video_path = sys.argv[1] if len(sys.argv) > 1 else video_files[0]
    
    if not os.path.exists(video_path):
        print(f"Error: Video file not found: {video_path}")
        sys.exit(1)
    
    # Run the analyzer
    analyzer = AudioAnalyzer(video_path)
    success = analyzer.run_pipeline()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
