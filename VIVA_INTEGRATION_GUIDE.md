# Viva Evaluation Engine Integration Guide

## Overview

This document describes the integration of the VivaEvaluationEngine with the Gradex_AI_Server backend and Gradex_AI_Client frontend. Users can now upload videos directly through the UI, and the system will:

1. Analyze the video frame-by-frame for emotion detection
2. Calculate engagement levels
3. Generate confidence and engagement scores
4. Display results with timeline visualization

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│           Gradex_AI_Client (React/Next.js)              │
│                                                         │
│  VivaPage.tsx:                                          │
│  - Drag & drop upload                                   │
│  - Video preview                                        │
│  - Results visualization                               │
└────────────────────┬────────────────────────────────────┘
                     │ POST /api/viva-analyze (FormData)
                     ▼
┌─────────────────────────────────────────────────────────┐
│       Gradex_AI_Server (FastAPI on port 8000)           │
│                                                         │
│  main.py:                                               │
│  - Endpoint: POST /api/viva-analyze                    │
│  - Receives video file                                 │
│  - Calls viva_service.analyze_video_file()            │
│  - Returns analysis results                            │
│                                                         │
│  viva_service.py:                                       │
│  - Wrapper for VivaEvaluationEngine                    │
│  - Imports AppConfig & analyze_video                   │
│  - Passes video to engine                              │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
      ┌──────────────────────────────┐
      │ VivaEvaluationEngine         │
      │                              │
      │ - Face detection             │
      │ - Emotion classification     │
      │ - Engagement detection       │
      │ - Scoring computation        │
      └──────────────────────────────┘
```

## Implementation Details

### 1. Backend: Gradex_AI_Server

#### New File: `app/viva_service.py`

This module wraps the VivaEvaluationEngine and provides:

```python
def analyze_video_file(video_path: str, debug: bool = False) -> Dict[str, Any]:
    """
    Analyzes a video using VivaEvaluationEngine
    Returns: {timeline, confidence_score, engagement_score, summary}
    """
```

**Key features:**
- Automatically adds VivaEvaluationEngine to Python path
- Creates AppConfig with video path
- Runs analysis with summary
- Returns structured JSON result

#### Modified File: `app/main.py`

Added new endpoint:

```python
@app.post("/api/viva-analyze")
async def viva_analyze(video: UploadFile = File(...)):
    """
    Receives video file → Analyzes with VivaEvaluationEngine → Returns results
    
    Returns:
    {
        "timeline": [
            {
                "time": 0.0,
                "emotion": "disgust",
                "emotion_confidence": 0.3092,
                "engagement_label": "high",
                "engagement_confidence": 0.75,
                "engagement_model_score": 0.82,
                "valid": true
            },
            ...
        ],
        "confidence_score": 9.33,
        "engagement_score": 52.0,
        "summary": {
            "positive_ratio": 0.0333,
            "neutral_ratio": 0.1667,
            "negative_ratio": 0.8
        }
    }
    """
```

**Features:**
- Validates video MIME type
- Saves uploaded file to `UPLOAD_DIR`
- Calls viva_service for analysis
- Auto-cleans uploaded file after analysis
- Returns comprehensive JSON response
- Error handling with descriptive messages

### 2. Frontend: Gradex_AI_Client

#### Modified File: `src/app/components/VivaPage.tsx`

Converted to functional component with state management:

```typescript
interface AnalysisResult {
  timeline: TimelineItem[];
  confidence_score: number;
  engagement_score: number;
  summary: {
    positive_ratio: number;
    neutral_ratio: number;
    negative_ratio: number;
  };
}
```

**Features:**

1. **File Upload**
   - Drag & drop support
   - Click to browse
   - File validation (video type, size ≤ 1GB)
   - Visual feedback during drag

2. **Analysis**
   - Auto-starts after upload
   - Loading spinner with message
   - Error handling with user-friendly alerts
   - Progress indication

3. **Results Display**
   - **Score Cards**
     - Confidence Score (0-10)
     - Engagement Score (0-100%)
   
   - **Emotion Distribution**
     - Positive ratio (progress bar)
     - Neutral ratio (progress bar)
     - Negative ratio (progress bar)
   
   - **Key Moments**
     - AI-detected emotional peaks
     - Emotion transitions
     - Timestamped with clickable timeline
   
   - **Frame-by-Frame Timeline**
     - First 20 frames displayed
     - Timestamp, emotion, confidence
     - Color-coded emotion badges

4. **Video Preview**
   - HTML5 video player
   - Native controls
   - Aspect ratio preserved

## Usage Flow

### Step 1: Start the Backend Server

```bash
cd c:\Users\buddh\Desktop\R26-SE-025\Gradex_AI_Server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

### Step 2: Start the Frontend

```bash
cd c:\Users\buddh\Desktop\R26-SE-025\Gradex_AI_Client
npm run dev
```

**Expected output:**
```
▲ Next.js 15.x.x
- Local:        http://localhost:3000
```

### Step 3: Upload Video

1. Navigate to Viva Assessment page
2. Drag & drop a video OR click to browse
3. Video validates and begins analysis
4. Wait for results (typically 30-120 seconds depending on video length)
5. View results:
   - Confidence & engagement scores
   - Emotion distribution
   - Key moments and frame-by-frame data

## Data Structure

### Input
- **File**: Video file (MP4, AVI, MOV, etc.)
- **Max Size**: 1 GB
- **Format**: FormData with "video" field

### Output (JSON)
```json
{
  "timeline": [
    {
      "time": 0.0,
      "emotion": "disgust",
      "emotion_confidence": 0.3092,
      "engagement_label": "high",
      "engagement_confidence": 0.75,
      "engagement_model_score": 0.82,
      "valid": true
    }
  ],
  "confidence_score": 9.33,
  "engagement_score": 52.0,
  "summary": {
    "positive_ratio": 0.0333,
    "neutral_ratio": 0.1667,
    "negative_ratio": 0.8
  }
}
```

## Emotion Classification

### Categories
- **Positive**: happy, surprise
- **Neutral**: neutral
- **Negative**: sad, angry, fear, disgust, contempt

### Confidence Score (0-10)
- Measures overall face detection and emotion classification confidence
- Higher = more reliable analysis

### Engagement Score (0-100%)
- Measures student engagement level
- Based on facial expressions, gaze, blinks, head movement

## Error Handling

### Frontend
- File validation (type, size)
- Network error handling
- Display user-friendly error messages
- Retry capability

### Backend
- Video file validation
- Engine import error handling
- Analysis failure handling
- Automatic cleanup on errors

## Configuration

### Backend Configuration
- **Port**: 8000
- **Upload Directory**: `Gradex_AI_Server/app/uploads/`
- **CORS**: Enabled for all origins
- **Reload**: Enabled for development

### Frontend Configuration
- **API URL**: `http://localhost:8000/api/viva-analyze`
- **Max File Size**: 1 GB (enforced client-side and server-side)

## Performance Considerations

- **Analysis Time**: Depends on video length (typically 1-2 minutes per minute of video)
- **Memory**: Ensure sufficient RAM for video processing
- **Disk Space**: Temporary files cleaned up after analysis
- **Network**: Ensure stable connection for large uploads

## Troubleshooting

### Issue: "Viva analysis unavailable: Failed to import VivaEvaluationEngine modules"

**Solution**: Ensure VivaEvaluationEngine has all dependencies installed:
```bash
cd VivaEvaluationEngine
pip install -r requirements.txt
```

### Issue: "Failed to analyze video"

**Solution**: 
- Check video file integrity
- Ensure video has at least one frame with a visible face
- Check server logs for detailed error

### Issue: Frontend doesn't connect to backend

**Solution**:
- Verify backend is running on `http://localhost:8000`
- Check browser console for CORS errors
- Verify network connectivity

### Issue: Long analysis times

**Solution**:
- This is normal for long videos
- Shorter videos (< 5 minutes) analyze fastest
- Consider splitting very long videos

## Files Summary

### Created Files
- `Gradex_AI_Server/app/viva_service.py` - 45 lines

### Modified Files
- `Gradex_AI_Server/app/main.py` - Added 40-line endpoint
- `Gradex_AI_Client/src/app/components/VivaPage.tsx` - Refactored to ~500 lines

### Total Changes
- ~585 lines of new/modified code
- No breaking changes to existing systems
- Backward compatible

## Future Enhancements

1. **Transcript Generation**: Add speech-to-text via Whisper API
2. **Scoring Criteria**: Map emotion/engagement to rubric scores
3. **Report Export**: PDF/Excel report generation
4. **Session History**: Store analysis results with metadata
5. **Real-time Processing**: WebSocket for live analysis updates
6. **Custom Thresholds**: Allow configurable emotion/engagement thresholds

## Testing

To test the integration:

1. Use the provided test video: `VivaEvaluationEngine/videos/video_test-01.mp4`
2. Upload through UI
3. Verify results match CLI output:
   - `confidence_score: 9.33`
   - `engagement_score: 52.0`
   - `timeline` matches frame-by-frame analysis

## Support

For issues or questions:
1. Check logs in browser console and terminal
2. Verify all services are running
3. Ensure video file is valid
4. Check network connectivity
