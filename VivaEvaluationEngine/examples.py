"""
Example Usage of Audio Analysis for Viva Evaluation
Demonstrates various ways to use the audio analyzer
"""

import os
import json
from audio_analyzer import AudioAnalyzer, find_video_files


def example_1_basic_usage():
    """Example 1: Basic usage - process first video found"""
    print("\n" + "="*60)
    print("Example 1: Basic Usage")
    print("="*60)
    
    # Find videos
    videos = find_video_files()
    if not videos:
        print("No video files found. Please add videos to the 'videos/' directory")
        return
    
    print(f"Found {len(videos)} video(s)")
    video_path = videos[0]
    print(f"Processing: {video_path}\n")
    
    # Run analyzer
    analyzer = AudioAnalyzer(video_path)
    success = analyzer.run_pipeline()
    
    if success:
        print("\n✓ Analysis completed successfully!")
        print("Check 'outputs/' directory for results")
    

def example_2_process_multiple_videos():
    """Example 2: Process multiple videos"""
    print("\n" + "="*60)
    print("Example 2: Process Multiple Videos")
    print("="*60)
    
    videos = find_video_files()
    if not videos:
        print("No video files found")
        return
    
    print(f"Processing {len(videos)} video(s)...\n")
    
    for i, video_path in enumerate(videos[:3], 1):  # Process first 3 videos
        print(f"\n[{i}/{len(videos[:3])}] Processing: {video_path}")
        analyzer = AudioAnalyzer(video_path, output_dir=f"outputs/video_{i}")
        analyzer.run_pipeline()


def example_3_extract_and_use_features():
    """Example 3: Extract features and use them for analysis"""
    print("\n" + "="*60)
    print("Example 3: Extract and Use Features")
    print("="*60)
    
    # Check if output exists
    if not os.path.exists("outputs/audio_analysis_output.json"):
        print("Audio analysis output not found. Run Example 1 first.")
        return
    
    # Load results
    with open("outputs/audio_analysis_output.json", "r") as f:
        results = json.load(f)
    
    print("\nAnalysis Results Summary:")
    print("-" * 40)
    
    # Print metadata
    metadata = results.get("metadata", {})
    print(f"Timestamp: {metadata.get('timestamp', 'N/A')}")
    print(f"Video: {metadata.get('video_source', 'N/A')}")
    print()
    
    # Print grading summary
    grading = results.get("grading_summary", {})
    
    if grading.get("audio_quality"):
        print("Audio Quality:")
        aq = grading["audio_quality"]
        print(f"  Duration: {aq.get('duration_seconds', 0):.2f}s")
        print(f"  Clarity: {aq.get('clarity', 0):.1%}")
        print(f"  Stability: {aq.get('stability', 0):.1%}")
    
    if grading.get("speech_emotion"):
        print("\nSpeech Emotion:")
        se = grading["speech_emotion"]
        print(f"  Detected: {se.get('predicted_emotion', 'N/A')}")
        print(f"  Confidence: {se.get('confidence', 0):.1%}")
        
        # Print emotion scores
        emotions = se.get("emotion_scores", {})
        for emotion, score in sorted(emotions.items(), key=lambda x: x[1], reverse=True):
            if score > 0.1:  # Only show significant scores
                print(f"    {emotion}: {score:.1%}")
    
    if grading.get("speech_content"):
        print("\nSpeech Content:")
        sc = grading["speech_content"]
        print(f"  Transcript length: {sc.get('full_transcript_length', 0)} chars")
        print(f"  Number of segments: {sc.get('num_segments', 0)}")
    
    print()


def example_4_create_grading_report():
    """Example 4: Create a grading report from analysis"""
    print("\n" + "="*60)
    print("Example 4: Create Grading Report")
    print("="*60)
    
    if not os.path.exists("outputs/audio_analysis_output.json"):
        print("Audio analysis output not found. Run Example 1 first.")
        return
    
    with open("outputs/audio_analysis_output.json", "r") as f:
        results = json.load(f)
    
    # Create a grading report
    report = {
        "report_type": "Audio Analysis Grading Report",
        "grades": {},
        "detailed_feedback": {}
    }
    
    grading = results.get("grading_summary", {})
    
    # Grade audio quality (0-100)
    if grading.get("audio_quality"):
        aq = grading["audio_quality"]
        clarity_score = aq.get("clarity", 0) * 100
        stability_score = aq.get("stability", 0) * 100
        audio_quality_grade = (clarity_score + stability_score) / 2
        
        report["grades"]["audio_quality"] = round(audio_quality_grade, 1)
        report["detailed_feedback"]["audio_quality"] = {
            "clarity": f"{clarity_score:.1f}/100",
            "stability": f"{stability_score:.1f}/100"
        }
    
    # Grade emotional expression (0-100)
    if grading.get("speech_emotion"):
        se = grading["speech_emotion"]
        confidence = se.get("confidence", 0) * 100
        emotion = se.get("predicted_emotion", "neutral")
        
        report["grades"]["emotional_expression"] = round(confidence, 1)
        report["detailed_feedback"]["emotional_expression"] = {
            "emotion": emotion,
            "confidence": f"{confidence:.1f}%"
        }
    
    # Print report
    print("\n📊 GRADING REPORT")
    print("=" * 40)
    
    for category, grade in report.get("grades", {}).items():
        print(f"{category:.<30} {grade}/100")
    
    print("\n📝 DETAILED FEEDBACK")
    print("=" * 40)
    for category, feedback in report.get("detailed_feedback", {}).items():
        print(f"\n{category}:")
        for key, value in feedback.items():
            print(f"  • {key}: {value}")
    
    print()


def example_5_batch_analysis_config():
    """Example 5: Configuration for batch analysis"""
    print("\n" + "="*60)
    print("Example 5: Batch Analysis Configuration")
    print("="*60)
    
    config = {
        "batch_settings": {
            "max_videos_per_batch": 10,
            "processing_order": "alphabetical",
            "skip_existing": True,
            "output_format": "json"
        },
        "feature_extraction": {
            "extract_acoustic_features": True,
            "extract_emotion": True,
            "transcribe_audio": True,
            "extract_formants": True,
            "extract_jitter_shimmer": True
        },
        "output_options": {
            "save_full_analysis": True,
            "save_grading_summary": True,
            "save_individual_features": False
        }
    }
    
    print("\nBatch Configuration:")
    print(json.dumps(config, indent=2))
    
    # Save configuration
    with open("batch_config.json", "w") as f:
        json.dump(config, f, indent=2)
    
    print("\nConfiguration saved to: batch_config.json")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Audio Analysis Examples for Viva Evaluation")
    print("="*60)
    
    print("\nAvailable Examples:")
    print("  1. Basic usage - process first video found")
    print("  2. Process multiple videos")
    print("  3. Extract and use features")
    print("  4. Create grading report")
    print("  5. Batch analysis configuration")
    
    try:
        choice = input("\nSelect example (1-5) or press Enter for example 1: ").strip()
        
        if choice == "2":
            example_2_process_multiple_videos()
        elif choice == "3":
            example_3_extract_and_use_features()
        elif choice == "4":
            example_4_create_grading_report()
        elif choice == "5":
            example_5_batch_analysis_config()
        else:
            example_1_basic_usage()
    
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
    except Exception as e:
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()
