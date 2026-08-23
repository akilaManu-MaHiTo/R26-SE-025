import { useState, useEffect, useCallback } from "react";
import { Sparkles, Plus, Pencil, X, AlertTriangle, BookOpen, BarChart3, ChevronRight, Layers } from "lucide-react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { ProgressLoader, type LoadStep } from "./ProgressLoader";
import { AIPageBanner } from "./AIBrand";
import {
  fetchExams,
  fetchRecommendations,
  type ExamListItem,
  type RecommendationsResponse,
  type Recommendation,
} from "../api/lecturerApi";

function PriorityBadge({ priority }: { priority: string }) {
  const color =
    priority === "High"
      ? "bg-red-500 text-white"
      : priority === "Medium"
        ? "bg-amber-500 text-white"
        : "bg-muted text-muted-foreground";
  return <Badge className={color}>{priority}</Badge>;
}

function RecommendationCard({
  rec,
  onAdd,
  onEdit,
  onReject,
}: {
  rec: Recommendation;
  onAdd: () => void;
  onEdit: () => void;
  onReject: () => void;
}) {
  return (
    <Card className="p-4 border-border hover:border-primary/30 transition-colors space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-wrap gap-1.5">
          <Badge variant="outline" className="border-border text-xs">
            {rec.canonical_topic}
          </Badge>
          <Badge variant="secondary" className="text-xs">
            {rec.bloom_level}
          </Badge>
          <Badge variant="secondary" className="text-xs">
            {rec.difficulty}
          </Badge>
          {rec.marks > 0 && <Badge variant="outline" className="text-xs">{rec.marks} marks</Badge>}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs text-muted-foreground tabular-nums">{(rec.recommendation_score * 100).toFixed(1)}</span>
          <PriorityBadge priority={rec.priority} />
        </div>
      </div>

      <p className="text-sm leading-relaxed line-clamp-3">{rec.text}</p>

      <div className="rounded-md bg-muted/50 p-3 space-y-1.5 text-xs">
        <div className="font-medium flex items-center gap-1.5">
          <BarChart3 className="size-3.5" /> Why recommended
        </div>
        <div className="grid grid-cols-2 gap-1 text-muted-foreground">
          <span>Student success: {(100 - rec.reason.weakness_pct).toFixed(1)}% (weakness {rec.reason.weakness_pct}%)</span>
          <span>Lecture: {rec.reason.lecture ? "covered" : "not covered"}</span>
          <span>Tutorial: {rec.reason.tutorial_count} questions</span>
          <span>Recent exam: {rec.reason.exam_recent_count} times</span>
          <span>Bloom gap: {(rec.bloom_gap * 100).toFixed(0)}%</span>
          <span>Source: {rec.source_id}</span>
        </div>
      </div>

      <div className="flex gap-2">
        <Button size="sm" onClick={onAdd} className="flex-1">
          <Plus className="size-4 mr-1" /> Add to Exam
        </Button>
        <Button size="sm" variant="outline" onClick={onEdit}>
          <Pencil className="size-4 mr-1" /> Edit
        </Button>
        <Button size="sm" variant="ghost" onClick={onReject} className="text-muted-foreground">
          <X className="size-4 mr-1" /> Reject
        </Button>
      </div>
    </Card>
  );
}

export function ExamCreator() {
  const [exams, setExams] = useState<ExamListItem[]>([]);
  const [selectedExam, setSelectedExam] = useState<ExamListItem | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendationsResponse | null>(null);
  const [draftIds, setDraftIds] = useState<Set<string>>(new Set());
  const [rejectedIds, setRejectedIds] = useState<Set<string>>(new Set());
  const [loadingExams, setLoadingExams] = useState(true);
  const [loadingRecs, setLoadingRecs] = useState(false);
  const [loadSteps, setLoadSteps] = useState<LoadStep[]>([]);
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    setLoadSteps([{ label: "Fetching exams..." }]);
    fetchExams()
      .then(setExams)
      .catch(console.error)
      .finally(() => setLoadingExams(false));
  }, []);

  const handleSelectExam = useCallback(async (exam: ExamListItem) => {
    setSelectedExam(exam);
    setLoadingRecs(true);
    setRecommendations(null);
    setDraftIds(new Set());
    setRejectedIds(new Set());
    const steps: LoadStep[] = [
      { label: "Loading student weakness..." },
      { label: "Scoring against curriculum..." },
      { label: "Ranking recommendations..." },
    ];
    setLoadSteps(steps);
    setCurrentStep(0);
    try {
      setCurrentStep(0);
      const data = await fetchRecommendations(exam.course_code, exam.session_name, exam.year, exam.month, exam.semester, 12);
      setCurrentStep(2);
      setRecommendations(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingRecs(false);
    }
  }, []);

  const handleAdd = (rec: Recommendation) => {
    setDraftIds((prev) => new Set(prev).add(rec.question_id));
  };
  const handleReject = (rec: Recommendation) => {
    setRejectedIds((prev) => new Set(prev).add(rec.question_id));
  };

  const visibleRecs = recommendations?.recommendations.filter((r) => !rejectedIds.has(r.question_id)) ?? [];
  const high = visibleRecs.filter((r) => r.priority === "High");
  const medium = visibleRecs.filter((r) => r.priority === "Medium");
  const low = visibleRecs.filter((r) => r.priority === "Low");

  // Exam creator list view
  if (!selectedExam) {
    return (
      <div className="p-6 md:p-8 space-y-6">
        <AIPageBanner model="pulse" />
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Layers className="size-4" /> Exam Creator
            <ChevronRight className="size-4" /> Select Exam
          </div>
          <h2 className="tracking-tight text-foreground">Adaptive Exam Question Recommendation Engine</h2>
          <p className="text-sm text-muted-foreground max-w-2xl">
            Based on student analytics + curriculum + previous assessments. Select an exam to get weak-area-driven question recommendations.
          </p>
        </div>
        {loadingExams ? (
          <ProgressLoader steps={loadSteps} currentStep={currentStep} className="min-h-[300px]" />
        ) : exams.length === 0 ? (
          <Card className="p-12 text-center border-border">
            <BookOpen className="h-12 w-12 mx-auto mb-4 text-muted-foreground/50" />
            <p className="text-muted-foreground">No exams found. Ingest submissions first.</p>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {exams.map((exam) => (
              <Card
                key={`${exam.course_code}-${exam.year}-${exam.session_name}`}
                className="group p-5 border-border hover:border-primary/40 cursor-pointer transition-colors"
                onClick={() => handleSelectExam(exam)}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="size-10 rounded-lg bg-primary text-primary-foreground flex items-center justify-center">
                    <Sparkles className="size-5" />
                  </div>
                  <Badge variant="secondary">{exam.student_count} students</Badge>
                </div>
                <div className="font-semibold">{exam.course_code} — {exam.session_name}</div>
                <div className="text-sm text-muted-foreground">{exam.subject_name} · {exam.year}</div>
                <div className="text-xs text-muted-foreground mt-2">Avg {exam.average_percentage.toFixed(1)}% · Pass {exam.pass_rate.toFixed(0)}%</div>
              </Card>
            ))}
          </div>
        )}
      </div>
    );
  }

  // Detail view with recommendations + draft
  return (
    <div className="p-6 md:p-8 space-y-6">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Layers className="size-4" /> Exam Creator
        <ChevronRight className="size-4" /> {selectedExam.course_code} {selectedExam.year}
        <Button variant="ghost" size="sm" className="ml-auto" onClick={() => setSelectedExam(null)}>
          Change exam
        </Button>
      </div>

      <div className="flex items-center justify-between">
        <div>
          <h2 className="tracking-tight text-foreground">Exam Question Recommendations</h2>
          <p className="text-sm text-muted-foreground">Based on student analytics + curriculum + previous assessments</p>
        </div>
        <Badge variant="outline" className="border-border">
          Draft: {draftIds.size} questions
        </Badge>
      </div>

      {loadingRecs ? (
        <ProgressLoader steps={loadSteps} currentStep={currentStep} className="min-h-[400px]" />
      ) : recommendations ? (
        <>
          {/* Weak areas summary */}
          <Card className="p-4 border-border">
            <div className="flex items-center gap-2 font-medium mb-3">
              <AlertTriangle className="size-4 text-amber-500" /> Weak Areas to Assess
            </div>
            <div className="flex flex-wrap gap-2">
              {recommendations.ranked_weak_topics.map(([topic, weakness]) => (
                <Badge
                  key={topic}
                  variant="outline"
                  className={
                    weakness >= 0.4 ? "border-red-300 text-red-600 bg-red-50" : weakness >= 0.3 ? "border-amber-300 text-amber-600 bg-amber-50" : "border-border"
                  }
                >
                  {topic} — {(weakness * 100).toFixed(0)}% weak
                </Badge>
              ))}
            </div>
          </Card>

          {/* Draft preview */}
          {draftIds.size > 0 && (
            <Card className="p-4 border-primary/30 bg-primary/5">
              <div className="font-medium mb-2 flex items-center gap-2">
                <Layers className="size-4" /> Draft Exam ({draftIds.size})
              </div>
              <div className="flex flex-wrap gap-1.5">
                {Array.from(draftIds).map((id) => (
                  <Badge key={id} variant="secondary" className="text-xs">
                    {id}
                  </Badge>
                ))}
              </div>
            </Card>
          )}

          {/* High priority */}
          <div className="space-y-3">
            <h3 className="font-semibold flex items-center gap-2">
              <span className="size-2 rounded-full bg-red-500" /> High Priority
              <span className="text-sm font-normal text-muted-foreground">({high.length})</span>
            </h3>
            {high.length === 0 ? (
              <p className="text-sm text-muted-foreground">No high priority recommendations. Good coverage.</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {high.map((rec) => (
                  <RecommendationCard
                    key={rec.question_id}
                    rec={rec}
                    onAdd={() => handleAdd(rec)}
                    onEdit={() => console.log("Edit", rec.question_id)}
                    onReject={() => handleReject(rec)}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Medium priority */}
          {medium.length > 0 && (
            <div className="space-y-3">
              <h3 className="font-semibold flex items-center gap-2">
                <span className="size-2 rounded-full bg-amber-500" /> Medium Priority
                <span className="text-sm font-normal text-muted-foreground">({medium.length})</span>
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {medium.map((rec) => (
                  <RecommendationCard
                    key={rec.question_id}
                    rec={rec}
                    onAdd={() => handleAdd(rec)}
                    onEdit={() => console.log("Edit", rec.question_id)}
                    onReject={() => handleReject(rec)}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Low priority collapsed */}
          {low.length > 0 && (
            <details className="space-y-3">
              <summary className="font-semibold cursor-pointer flex items-center gap-2">
                <span className="size-2 rounded-full bg-muted-foreground" /> Low Priority
                <span className="text-sm font-normal text-muted-foreground">({low.length}) — click to expand</span>
              </summary>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">
                {low.map((rec) => (
                  <RecommendationCard
                    key={rec.question_id}
                    rec={rec}
                    onAdd={() => handleAdd(rec)}
                    onEdit={() => console.log("Edit", rec.question_id)}
                    onReject={() => handleReject(rec)}
                  />
                ))}
              </div>
            </details>
          )}
        </>
      ) : null}
    </div>
  );
}
