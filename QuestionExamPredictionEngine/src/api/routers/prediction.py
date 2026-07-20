import logging

from fastapi import APIRouter, HTTPException, status

from src.api.schemas.requests import AnalyzeTrendsRequest, PredictTopicsRequest
from src.api.schemas.responses import AnalyzeTrendsResponse, PredictTopicsResponse, TopicPrediction, TrendSummary
from src.prediction.topic_prediction import predict_topics as _predict_topics
from src.prediction.trend_analysis import analyze_trends as _analyze_trends

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/predict", tags=["Prediction"])


@router.post("/topics", response_model=PredictTopicsResponse)
def predict_topics(req: PredictTopicsRequest):
    try:
        results = _predict_topics(req.answer, req.exam_data, top_n=req.top_n)
        return PredictTopicsResponse(
            predictions=[TopicPrediction(**r) for r in results]
        )
    except Exception as e:
        logger.exception("Topic prediction failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/trends", response_model=AnalyzeTrendsResponse)
def analyze_trends(req: AnalyzeTrendsRequest):
    try:
        results = _analyze_trends(req.reports, by=req.by, time_key=req.time_key)
        trends = {k: TrendSummary(**v) for k, v in results.items()}
        return AnalyzeTrendsResponse(trends=trends)
    except Exception as e:
        logger.exception("Trend analysis failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
