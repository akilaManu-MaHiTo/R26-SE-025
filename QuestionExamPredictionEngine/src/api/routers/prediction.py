import logging

from fastapi import APIRouter, HTTPException, status

from src.api.schemas.requests import AnalyzeTrendsRequest, PredictTopicsRequest
from src.api.schemas.responses import (
    AnalyzeTrendsResponse,
    PredictTopicsResponse,
    TopicPrediction,
    TrendSummary,
)
from src.prediction.topic_prediction import match_topics
from src.prediction.trend_analysis import analyze_trends

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/predict", tags=["Prediction"])


def _topic_match_response(req: PredictTopicsRequest) -> PredictTopicsResponse:
    results = match_topics(req.answer, req.exam_data, top_n=req.top_n)
    return PredictTopicsResponse(
        predictions=[TopicPrediction(**result) for result in results]
    )


@router.post("/topic-match", response_model=PredictTopicsResponse)
def topic_match(req: PredictTopicsRequest):
    """Match answer text to existing exam topics; this is not forecasting."""
    try:
        return _topic_match_response(req)
    except Exception as exc:
        logger.exception("Topic matching failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post(
    "/topics",
    response_model=PredictTopicsResponse,
    deprecated=True,
)
def predict_topics_legacy(req: PredictTopicsRequest):
    """Compatibility alias for the original, ambiguously named endpoint."""
    return topic_match(req)


@router.post("/trends", response_model=AnalyzeTrendsResponse)
def analyze_historical_trends(req: AnalyzeTrendsRequest):
    try:
        results = analyze_trends(req.reports, by=req.by, time_key=req.time_key)
        return AnalyzeTrendsResponse(
            trends={
                key: TrendSummary(**summary)
                for key, summary in results.items()
            }
        )
    except Exception as exc:
        logger.exception("Trend analysis failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
