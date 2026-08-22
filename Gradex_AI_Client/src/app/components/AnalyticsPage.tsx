import React, { useState, useEffect, useCallback } from "react";
import { ArrowLeft, Download, FileText } from "lucide-react";
import { Button } from "./ui/button";
import { Skeleton } from "./ui/skeleton";
import { AIPageBanner } from "./AIBrand";
import {
  fetchExams,
  fetchExamAnalytics,
  fetchTeachingActions,
  type ExamListItem,
  type ExamAnalytics,
  type CanonicalTopic,
  type TeachingAction,
} from "../api/lecturerApi";
import { KpiCards } from "./analytics/KpiCards";
import { CanonicalTopicTable } from "./analytics/CanonicalTopicTable";
import { AttentionAreasPanel } from "./analytics/AttentionAreasPanel";
import { BloomChart } from "./analytics/BloomChart";
import { QuestionPerformanceTable } from "./analytics/QuestionPerformanceTable";
import { InsightsPanel } from "./analytics/InsightsPanel";
import { TeachingActions } from "./analytics/TeachingActions";
import { TopicDetailModal } from "./analytics/TopicDetailModal";
import { QuestionDetailModal } from "./analytics/QuestionDetailModal";

export default function AnalyticsPage() {
  const [exams, setExams] = useState<ExamListItem[]>([]);
  const [selectedExam, setSelectedExam] = useState<ExamListItem | null>(null);
  const [analytics, setAnalytics] = useState<ExamAnalytics | null>(null);
  const [teachingActions, setTeachingActions] = useState<TeachingAction[]>([]);
  const [loadingExams, setLoadingExams] = useState(true);
  const [loadingAnalytics, setLoadingAnalytics] = useState(false);
  const [loadingActions, setLoadingActions] = useState(false);
  const [selectedTopic, setSelectedTopic] = useState<CanonicalTopic | null>(null);
  const [selectedQuestion, setSelectedQuestion] = useState<any>(null);

  useEffect(() => {
    fetchExams().then((data) => { setExams(data); setLoadingExams(false); }).catch(console.error);
  }, []);

  const handleSelectExam = useCallback(async (exam: ExamListItem) => {
    setSelectedExam(exam);
    setLoadingAnalytics(true);
    setAnalytics(null);
    try {
      const data = await fetchExamAnalytics(exam.course_code, exam.session_name);
      setAnalytics(data);
      setLoadingActions(true);
      fetchTeachingActions(exam.course_code, exam.session_name)
        .then(setTeachingActions)
        .catch(() => setTeachingActions([]))
        .finally(() => setLoadingActions(false));
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingAnalytics(false);
    }
  }, []);

  // Exam List View
  if (!selectedExam) {
    return (
      <div className="space-y-6">
        <AIPageBanner model="pulse" />
        <h1 className="text-2xl font-bold">Lecturer Analytics</h1>
        {loadingExams ? (
          <div className="space-y-3">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-16 w-full" />)}</div>
        ) : (
          <div className="space-y-2">
            {exams.map((exam) => (
              <button
                key={`${exam.course_code}-${exam.session_name}`}
                onClick={() => handleSelectExam(exam)}
                className="w-full flex items-center justify-between p-4 rounded-lg border bg-card hover:bg-accent/50 text-left transition-colors"
              >
                <div>
                  <div className="font-medium">{exam.course_code} — {exam.subject_name}</div>
                  <div className="text-sm text-muted-foreground">{exam.session_name} · {exam.year}</div>
                </div>
                <div className="text-right text-sm">
                  <div>{exam.student_count} students</div>
                  <div className="text-muted-foreground">Avg: {exam.average_percentage.toFixed(1)}%</div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  // Analytics View
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => { setSelectedExam(null); setAnalytics(null); setTeachingActions([]); }}>
          <ArrowLeft className="h-4 w-4 mr-1" /> Back
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">{selectedExam.course_code} — {selectedExam.subject_name}</h1>
          <p className="text-sm text-muted-foreground">{selectedExam.session_name} · {selectedExam.year}</p>
        </div>
        <Button variant="outline" size="sm" disabled title="Coming soon">
          <Download className="h-4 w-4 mr-1" /> Export
        </Button>
        <Button variant="outline" size="sm" disabled title="Coming soon">
          <FileText className="h-4 w-4 mr-1" /> Report
        </Button>
      </div>

      {loadingAnalytics ? (
        <div className="space-y-4">
          <div className="grid grid-cols-6 gap-4">{Array(6).fill(0).map((_, i) => <Skeleton key={i} className="h-24" />)}</div>
          <Skeleton className="h-64" />
        </div>
      ) : analytics ? (
        <>
          <KpiCards statistics={analytics.statistics} />

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <CanonicalTopicTable
              topics={analytics.canonical_topic_performance}
              onSelectTopic={setSelectedTopic}
            />
            <AttentionAreasPanel areas={analytics.canonical_attention_areas} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <BloomChart bloomPerformance={analytics.bloom_performance} />
            <QuestionPerformanceTable
              questions={analytics.question_performance}
              onSelectQuestion={setSelectedQuestion}
            />
          </div>

          <InsightsPanel insights={analytics.canonical_insights} />

          <TeachingActions actions={teachingActions} loading={loadingActions} />
        </>
      ) : null}

      <TopicDetailModal topic={selectedTopic} open={!!selectedTopic} onClose={() => setSelectedTopic(null)} />
      <QuestionDetailModal question={selectedQuestion} open={!!selectedQuestion} onClose={() => setSelectedQuestion(null)} />
    </div>
  );
}
