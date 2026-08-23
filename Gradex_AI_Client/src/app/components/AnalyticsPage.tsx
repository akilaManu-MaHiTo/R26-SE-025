import React, { useState, useEffect, useCallback } from "react";
import { ArrowLeft, Download, FileText, BarChart3 } from "lucide-react";
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
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Lecturer Analytics</h1>
          <p className="text-muted-foreground mt-1">Select an exam to view detailed performance insights</p>
        </div>
        {loadingExams ? (
          <div className="space-y-4">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-24 w-full" />)}</div>
        ) : exams.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            <BarChart3 className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>No exams found</p>
          </div>
        ) : (
          <div className="space-y-3">
            {exams.map((exam) => (
              <button
                key={`${exam.course_code}-${exam.session_name}`}
                onClick={() => handleSelectExam(exam)}
                className="w-full text-left p-5 rounded-xl border bg-card hover:bg-accent/50 transition-all hover:shadow-md"
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="font-semibold text-lg">{exam.course_code} — {exam.subject_name}</div>
                    <div className="text-sm text-muted-foreground mt-1">
                      {exam.session_name} · {exam.year}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-bold tabular-nums">{exam.average_percentage.toFixed(1)}%</div>
                    <div className="text-sm text-muted-foreground">{exam.student_count} students</div>
                  </div>
                </div>
                <div className="mt-3 h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-teal-500 to-emerald-500 rounded-full"
                    style={{ width: `${Math.min(exam.average_percentage, 100)}%` }}
                  />
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
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => { setSelectedExam(null); setAnalytics(null); setTeachingActions([]); }}>
          <ArrowLeft className="h-4 w-4 mr-1" /> Back
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight">{selectedExam.course_code} — {selectedExam.subject_name}</h1>
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
        <div className="space-y-6">
          <div className="grid grid-cols-6 gap-4">{Array(6).fill(0).map((_, i) => <Skeleton key={i} className="h-32" />)}</div>
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
      ) : analytics ? (
        <>
          {/* Section 1: KPI Cards */}
          <KpiCards statistics={analytics.statistics} />

          {/* Section 2: Topics + Attention */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <CanonicalTopicTable
              topics={analytics.canonical_topic_performance}
              onSelectTopic={setSelectedTopic}
            />
            <AttentionAreasPanel areas={analytics.canonical_attention_areas} />
          </div>

          {/* Section 3: Bloom + Questions */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <BloomChart bloomPerformance={analytics.bloom_performance} />
            <QuestionPerformanceTable
              questions={analytics.question_performance}
              onSelectQuestion={setSelectedQuestion}
            />
          </div>

          {/* Section 4: Insights */}
          <InsightsPanel insights={analytics.canonical_insights} />

          {/* Section 5: Teaching Actions */}
          <TeachingActions actions={teachingActions} loading={loadingActions} />
        </>
      ) : null}

      {/* Modals */}
      <TopicDetailModal topic={selectedTopic} open={!!selectedTopic} onClose={() => setSelectedTopic(null)} />
      <QuestionDetailModal question={selectedQuestion} open={!!selectedQuestion} onClose={() => setSelectedQuestion(null)} />
    </div>
  );
}
