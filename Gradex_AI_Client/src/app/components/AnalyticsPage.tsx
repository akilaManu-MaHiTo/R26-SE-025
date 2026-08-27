import React, { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowLeft, Download, FileText, BarChart3, Users, ChevronRight, Sparkles } from "lucide-react";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import { ProgressLoader, type LoadStep } from "./ProgressLoader";
import { AIPageBanner } from "./AIBrand";
import {
  fetchExams,
  fetchExamAnalytics,
  fetchExamAnalyticsStream,
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

function PremiumLoader({
  steps,
  currentStep,
  liveMessage,
}: {
  steps: LoadStep[];
  currentStep: number;
  liveMessage?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 space-y-6">
      <motion.div
        animate={{ rotate: 360 }}
        transition={{ duration: 1.2, repeat: Infinity, ease: "linear" }}
        className="size-10 rounded-full border-2 border-primary/20 border-t-primary"
      />
      <div className="space-y-2 text-center max-w-xl">
        <motion.p
          key={currentStep}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-sm font-medium"
        >
          {steps[currentStep]?.label || "Loading..."}
        </motion.p>
        {liveMessage && (
          <motion.p
            key={liveMessage}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-xs text-muted-foreground font-mono bg-muted/50 rounded-lg px-3 py-2 border"
          >
            {liveMessage}
          </motion.p>
        )}
        <div className="flex gap-1.5 justify-center">
          {steps.map((_, i) => (
            <motion.div
              key={i}
              className={`h-1.5 rounded-full ${i === currentStep ? "bg-primary w-6" : i < currentStep ? "bg-primary/60 w-1.5" : "bg-muted w-1.5"}`}
              animate={{ scale: i === currentStep ? 1.2 : 1 }}
              transition={{ duration: 0.3 }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

export default function AnalyticsPage() {
  const [exams, setExams] = useState<ExamListItem[]>([]);
  const [selectedExam, setSelectedExam] = useState<ExamListItem | null>(null);
  const [analytics, setAnalytics] = useState<ExamAnalytics | null>(null);
  const [teachingActions, setTeachingActions] = useState<TeachingAction[]>([]);
  const [loadingExams, setLoadingExams] = useState(true);
  const [loadingAnalytics, setLoadingAnalytics] = useState(false);
  const [loadingActions, setLoadingActions] = useState(false);
  const [loadSteps, setLoadSteps] = useState<LoadStep[]>([]);
  const [currentLoadStep, setCurrentLoadStep] = useState(0);
  const [liveModelMessage, setLiveModelMessage] = useState<string>("PULSE·AI — Initializing...");
  const [selectedTopic, setSelectedTopic] = useState<CanonicalTopic | null>(null);
  const [selectedQuestion, setSelectedQuestion] = useState<any>(null);

  useEffect(() => {
    setLoadSteps([{ label: "Fetching exams..." }]);
    setCurrentLoadStep(0);
    fetchExams().then((data) => { setExams(data); setLoadingExams(false); }).catch(console.error);
  }, []);

  const handleSelectExam = useCallback(async (exam: ExamListItem) => {
    setSelectedExam(exam);
    setLoadingAnalytics(true);
    setAnalytics(null);
    setLiveModelMessage("PULSE·AI — Starting analysis...");

    const steps: LoadStep[] = [
      { label: "PULSE·AI — Ingesting submissions..." },
      { label: "PULSE·AI — Checking Bloom levels & classifying topics..." },
      { label: "PULSE·AI — Computing statistics & insights..." },
    ];
    setLoadSteps(steps);
    setCurrentLoadStep(0);

    try {
      setCurrentLoadStep(0);
      setLiveModelMessage("PULSE·AI — Connecting to model...");
      // Try streaming for real-time Bloom/topic messages, fallback to plain fetch
      let data: ExamAnalytics;
      try {
        data = await fetchExamAnalyticsStream(
          exam.course_code,
          exam.session_name,
          exam.year,
          exam.month,
          exam.semester,
          (msg) => {
            setLiveModelMessage(msg);
            // Advance loader step based on message content
            if (msg.includes("Ingesting") || msg.includes("Analyzing student")) setCurrentLoadStep(0);
            else if (msg.includes("Bloom") || msg.includes("Topic") || msg.includes("Q")) setCurrentLoadStep(1);
            else if (msg.includes("Computing") || msg.includes("weak") || msg.includes("Finalizing") || msg.includes("Saving")) setCurrentLoadStep(2);
          },
        );
      } catch {
        setLiveModelMessage("PULSE·AI — Streaming unavailable, loading...");
        data = await fetchExamAnalytics(exam.course_code, exam.session_name, exam.year, exam.month, exam.semester);
      }
      setAnalytics(data);
      setLiveModelMessage("PULSE·AI — Analysis complete");
      setCurrentLoadStep(2);

      setLoadingActions(true);
      fetchTeachingActions(exam.course_code, exam.session_name, exam.year, exam.month, exam.semester)
        .then(setTeachingActions)
        .catch(() => setTeachingActions([]))
        .finally(() => setLoadingActions(false));
    } catch (err) {
      console.error(err);
      setLiveModelMessage("PULSE·AI — Analysis failed");
    } finally {
      setLoadingAnalytics(false);
    }
  }, []);

  // Exam List View — premium
  if (!selectedExam) {
    return (
      <div className="p-6 md:p-8 space-y-6">
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
          <AIPageBanner model="pulse" />
        </motion.div>
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.08 }} className="space-y-2">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <BarChart3 className="size-4" /> Analytics
            <ChevronRight className="size-4" /> Exam Selection
          </div>
          <h2 className="tracking-tight text-foreground bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text">Lecturer Analytics</h2>
          <p className="text-sm text-muted-foreground max-w-2xl">
            Select an exam to view detailed performance insights including topic mastery, cognitive analysis, and AI-powered teaching recommendations.
          </p>
        </motion.div>
        {loadingExams ? (
          <PremiumLoader steps={loadSteps} currentStep={currentLoadStep} />
        ) : exams.length === 0 ? (
          <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }}>
            <Card className="p-12 text-center border-border bg-gradient-to-b from-card to-muted/20">
              <BarChart3 className="h-12 w-12 mx-auto mb-4 text-muted-foreground/40" />
              <p className="text-muted-foreground">No exams found</p>
            </Card>
          </motion.div>
        ) : (
          <motion.div layout className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <AnimatePresence>
              {exams.map((exam, idx) => (
                <motion.div
                  key={`${exam.course_code}-${exam.session_name}`}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.35, delay: idx * 0.04 }}
                  whileHover={{ y: -4, transition: { duration: 0.2 } }}
                  className="h-full"
                >
                  <Card
                    className="group p-5 border-border bg-card/80 backdrop-blur hover:border-primary/30 hover:shadow-lg hover:shadow-primary/5 transition-all duration-300 cursor-pointer h-full flex flex-col"
                    onClick={() => handleSelectExam(exam)}
                  >
                    <div className="flex items-start justify-between mb-4">
                      <div className="size-10 rounded-xl bg-gradient-to-br from-primary to-primary/70 text-primary-foreground flex items-center justify-center shadow-md group-hover:shadow-primary/20 transition-shadow">
                        <BarChart3 className="size-5" />
                      </div>
                      <Badge variant="secondary" className="bg-muted text-muted-foreground backdrop-blur">
                        {exam.student_count} students
                      </Badge>
                    </div>
                    <div className="font-semibold text-lg">{exam.course_code}</div>
                    <div className="text-sm text-muted-foreground mt-0.5">{exam.subject_name}</div>
                    <div className="flex flex-wrap items-center gap-1.5 mt-3">
                      <Badge variant="outline" className="text-xs border-border/60 bg-background/50">Year {exam.year}</Badge>
                      <Badge variant="outline" className="text-xs border-border/60 bg-background/50">Month {exam.month}</Badge>
                      <Badge variant="outline" className="text-xs border-border/60 bg-background/50">Sem {exam.semester}</Badge>
                    </div>
                    <div className="mt-4 pt-4 border-t border-border/60 flex-1 flex flex-col justify-end">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">Class Average</span>
                        <span className="font-semibold text-lg tabular-nums bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text">{exam.average_percentage.toFixed(1)}%</span>
                      </div>
                      <div className="h-2 bg-muted rounded-full overflow-hidden mt-2">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${Math.min(exam.average_percentage, 100)}%` }}
                          transition={{ duration: 0.8, delay: 0.3 + idx * 0.05, ease: "easeOut" }}
                          className="h-full bg-gradient-to-r from-primary to-primary/80 rounded-full"
                        />
                      </div>
                    </div>
                  </Card>
                </motion.div>
              ))}
            </AnimatePresence>
          </motion.div>
        )}
      </div>
    );
  }

  // Analytics View — premium staggered sections
  return (
    <div className="p-6 md:p-8 space-y-6">
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-2">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <BarChart3 className="size-4" /> Analytics
          <ChevronRight className="size-4" /> {selectedExam.course_code}
          <Button variant="ghost" size="sm" className="ml-auto" onClick={() => setSelectedExam(null)}>Back</Button>
        </div>
        <div className="flex items-center justify-between">
          <div>
            <h2 className="tracking-tight text-foreground bg-gradient-to-r from-foreground via-foreground to-foreground/60 bg-clip-text">{selectedExam.subject_name}</h2>
            <p className="text-sm text-muted-foreground mt-1">{selectedExam.session_name} · {selectedExam.year}</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" disabled title="Coming soon" className="backdrop-blur">
              <Download className="h-4 w-4 mr-1" /> Export
            </Button>
            <Button variant="outline" size="sm" disabled title="Coming soon" className="backdrop-blur">
              <FileText className="h-4 w-4 mr-1" /> Report
            </Button>
          </div>
        </div>
      </motion.div>

      {loadingAnalytics ? (
        <PremiumLoader steps={loadSteps} currentStep={currentLoadStep} liveMessage={liveModelMessage} />
      ) : analytics ? (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.4 }} className="space-y-6">
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
            <KpiCards statistics={analytics.statistics} />
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12 }} className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="rounded-xl border bg-card/50 backdrop-blur p-1"><CanonicalTopicTable topics={analytics.canonical_topic_performance} onSelectTopic={setSelectedTopic} /></div>
            <div className="rounded-xl border bg-card/50 backdrop-blur p-1"><AttentionAreasPanel areas={analytics.canonical_attention_areas} /></div>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.18 }} className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="rounded-xl border bg-card/50 backdrop-blur p-1"><BloomChart bloomPerformance={analytics.bloom_performance} /></div>
            <div className="rounded-xl border bg-card/50 backdrop-blur p-1"><QuestionPerformanceTable questions={analytics.question_performance} onSelectQuestion={setSelectedQuestion} /></div>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.24 }}>
            <InsightsPanel insights={analytics.canonical_insights} />
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.30 }}>
            <TeachingActions actions={teachingActions} loading={loadingActions} />
          </motion.div>
        </motion.div>
      ) : null}

      <TopicDetailModal topic={selectedTopic} open={!!selectedTopic} onClose={() => setSelectedTopic(null)} />
      <QuestionDetailModal question={selectedQuestion} open={!!selectedQuestion} onClose={() => setSelectedQuestion(null)} />
    </div>
  );
}

