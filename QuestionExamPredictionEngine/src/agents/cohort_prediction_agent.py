from src.agents.contracts import (
    AgentStatus,
    AgentWarning,
    AnswerAnalysisResult,
    CohortPredictionResult,
)
from src.analytics.cognitive_gap_analysis import CognitiveGapAnalyzer
from src.analytics.misunderstood_questions import MisunderstoodQuestionsAnalyzer
from src.analytics.question_analysis import analyze_questions
from src.analytics.student_analysis import analyze_student_performance
from src.analytics.weak_topic_analysis import WeakTopicAnalyzer
from src.prediction.trend_analysis import analyze_trends


class CohortPredictionAgent:
    def run(
        self,
        exam_id: str,
        exam_data: dict,
        analyses: list[AnswerAnalysisResult],
        *,
        weak_threshold: float = 0.5,
        weak_min_students: int = 2,
        weak_min_below_share: float = 0.4,
    ) -> CohortPredictionResult:
        records = [
            analysis.to_analytics_record()
            for analysis in analyses
        ]
        warning = AgentWarning(
            code="forecaster_unavailable",
            message=(
                "Historical trends are descriptive; no validated topic "
                "forecaster is configured"
            ),
            capability="future_topic_forecasting",
        )
        return CohortPredictionResult(
            exam_id=exam_id,
            question_summaries=analyze_questions(
                records,
                weak_threshold=weak_threshold,
            ),
            student_summaries=analyze_student_performance(
                records,
                weak_threshold=weak_threshold,
            ),
            misunderstood_questions=MisunderstoodQuestionsAnalyzer(
                threshold=weak_threshold,
                minimum_students=weak_min_students,
                minimum_below_share=weak_min_below_share,
            ).analyze(records),
            cognitive_gaps=CognitiveGapAnalyzer().analyze(records),
            weak_topics=WeakTopicAnalyzer(
                exam_data=exam_data,
                threshold=weak_threshold,
            ).analyze(records),
            historical_trends=analyze_trends(
                records,
                by="topic",
                time_key="year",
            ),
            future_topic_probabilities=[],
            forecast_model_version=None,
            status=AgentStatus.PARTIAL,
            warnings=[warning],
        )
