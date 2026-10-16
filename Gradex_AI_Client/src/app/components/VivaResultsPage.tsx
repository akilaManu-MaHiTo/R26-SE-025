"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router";
import { toast } from "sonner";
import { ArrowLeft, Loader2, RefreshCw, Save, Search, UserRound } from "lucide-react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Input } from "./ui/input";
import { Skeleton } from "./ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { AIPageBanner } from "./AIBrand";
import { ScoreOverview } from "./viva/ScoreOverview";
import { AISummary } from "./viva/AISummary";
import { KeyMoments } from "./viva/KeyMoments";
import { EmotionDistribution } from "./viva/EmotionDistribution";
import { EngagementTimeline } from "./viva/EngagementTimeline";
import { TranscriptPanel } from "./viva/TranscriptPanel";
import { AudioAnalysisPanel } from "./viva/AudioAnalysisPanel";
import { LlmJudgePanel } from "./viva/LlmJudgePanel";
import { QaRelevancePanel } from "./viva/QaRelevancePanel";
import {
  VivaMarkDocument,
  VivaMarkSummary,
  fetchVivaMark,
  formatServerDate,
  listVivaMarks,
  publishVivaMark,
  setVivaMarkStudent,
} from "./viva/vivaMarksApi";
import {
  AnalysisResult,
  AssessmentMode,
  buildAIInterpretation,
  buildKeyMoments,
} from "./viva/types";

/** Group key for marks saved without a student ID. */
const UNASSIGNED = "";

function statusOf(item: VivaMarkSummary): { label: string; className: string } {
  if (item.status === "INCOMPLETE") {
    return { label: "Incomplete", className: "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400" };
  }
  if (item.published) {
    return { label: "Published", className: "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400" };
  }
  return { label: "Draft", className: "bg-slate-100 text-slate-700 dark:bg-slate-500/10 dark:text-slate-300" };
}

function formatMark(item: VivaMarkSummary): string {
  return item.final_score != null ? `${item.final_score.toFixed(1)} / 100` : "—";
}

/**
 * Saved viva results, grouped by student. Results come from the marks the server
 * stores after every analysis, so they survive a refresh. The recording itself is
 * not kept on the server, so a reopened result has no video to play.
 */
export function VivaResultsPage() {
  const [items, setItems] = useState<VivaMarkSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const [selected, setSelected] = useState<VivaMarkDocument | null>(null);
  const [opening, setOpening] = useState<string | null>(null);
  const [studentDraft, setStudentDraft] = useState("");
  const [savingStudent, setSavingStudent] = useState(false);
  const [publishing, setPublishing] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await listVivaMarks(100));
      setLoadError(null);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Could not load results");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // A link such as /viva-results?mark=<id> opens that result straight away.
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedMark = searchParams.get("mark");
  useEffect(() => {
    if (!requestedMark) return;
    setSearchParams({}, { replace: true });
    void openMark(requestedMark);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestedMark]);

  const groups = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const matches = items.filter((item) => {
      if (!needle) return true;
      return [item.student_id, item.video_filename, item.subject_code]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(needle));
    });
    const byStudent = new Map<string, VivaMarkSummary[]>();
    for (const item of matches) {
      const key = item.student_id?.trim() || UNASSIGNED;
      byStudent.set(key, [...(byStudent.get(key) ?? []), item]);
    }
    return [...byStudent.entries()]
      .sort(([a], [b]) => {
        if (a === UNASSIGNED) return 1;
        if (b === UNASSIGNED) return -1;
        return a.localeCompare(b);
      })
      .map(([student, rows]) => ({ student, rows }));
  }, [items, query]);

  async function openMark(markId: string) {
    setOpening(markId);
    try {
      const doc = await fetchVivaMark(markId);
      setSelected(doc);
      setStudentDraft(doc.student_id ?? "");
    } catch (err) {
      toast.error("Could not open result", {
        description: err instanceof Error ? err.message : "Request failed",
      });
    } finally {
      setOpening(null);
    }
  }

  async function saveStudent() {
    if (!selected) return;
    setSavingStudent(true);
    try {
      const saved = await setVivaMarkStudent(selected._id, studentDraft);
      setSelected({ ...selected, student_id: saved.student_id });
      setStudentDraft(saved.student_id ?? "");
      await refresh();
      toast.success(saved.student_id ? "Student assigned" : "Student cleared", {
        description: saved.student_id ?? "This result is now unassigned.",
      });
    } catch (err) {
      toast.error("Could not save student ID", {
        description: err instanceof Error ? err.message : "Request failed",
      });
    } finally {
      setSavingStudent(false);
    }
  }

  /** Publish a technical draft with the examiner's technical score (0-10). */
  async function publishTechnical(technical: number) {
    if (!selected) return;
    setPublishing(true);
    try {
      await publishVivaMark(selected._id, {
        assessment_mode: "WITH_TECHNICAL_ACCURACY",
        technical_accuracy: technical,
        student_id: selected.student_id ?? null,
        published: true,
      });
      // Re-read the mark: publishing rewrites its assessment and final score.
      setSelected(await fetchVivaMark(selected._id));
      await refresh();
      toast.success("Mark published", { description: `Technical accuracy ${technical} / 10 saved.` });
    } catch (err) {
      toast.error("Could not publish", {
        description: err instanceof Error ? err.message : "Request failed",
      });
    } finally {
      setPublishing(false);
    }
  }

  if (selected) {
    return (
      <ResultDetail
        doc={selected}
        onPublish={publishTechnical}
        publishing={publishing}
        studentDraft={studentDraft}
        onStudentDraft={setStudentDraft}
        onSaveStudent={saveStudent}
        savingStudent={savingStudent}
        onBack={() => setSelected(null)}
      />
    );
  }

  return (
    <div className="space-y-6">
      <AIPageBanner model="voca" />

      <Card className="p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-foreground">Viva results</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Every analysed viva, grouped by student. Open one to review its scores, transcript and
              engagement. Recordings are not stored, so a reopened result has no video.
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={() => void refresh()} disabled={loading}>
            {loading ? <Loader2 className="size-3.5 animate-spin" /> : <RefreshCw className="size-3.5" />}
            Refresh
          </Button>
        </div>

        <div className="relative mt-4 max-w-sm">
          <Search className="size-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
          <Input
            className="pl-9"
            placeholder="Search student ID, recording or subject"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      </Card>

      {loadError && (
        <Card className="p-4 text-sm text-amber-700 dark:text-amber-400">
          Could not load results: {loadError}
        </Card>
      )}

      {loading && items.length === 0 ? (
        <div className="space-y-3">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      ) : groups.length === 0 ? (
        <Card className="p-6 text-sm text-muted-foreground">
          {items.length === 0
            ? "No results yet. Analyse a recording on the Viva Assessment page and it will appear here."
            : "No results match your search."}
        </Card>
      ) : (
        groups.map(({ student, rows }) => (
          <Card key={student || "__unassigned__"} className="p-5">
            <div className="flex items-center gap-2 mb-3">
              <UserRound className="size-4 text-primary" />
              <span className="text-sm font-medium text-foreground">
                {student || "Unassigned"}
              </span>
              <Badge variant="outline" className="text-xs">
                {rows.length} result{rows.length === 1 ? "" : "s"}
              </Badge>
              {!student && (
                <span className="text-xs text-muted-foreground">
                  Open a result to assign it to a student.
                </span>
              )}
            </div>
            <div className="divide-y divide-border rounded-lg border border-border">
              {rows.map((row) => {
                const status = statusOf(row);
                return (
                  <button
                    key={row.mark_id}
                    type="button"
                    onClick={() => void openMark(row.mark_id)}
                    disabled={opening != null}
                    className="flex w-full cursor-pointer flex-wrap items-center gap-x-4 gap-y-1 px-3 py-2.5 text-left transition-colors hover:bg-muted/50 disabled:cursor-wait"
                  >
                    <span className="min-w-0 flex-1 truncate text-sm text-foreground">
                      {row.video_filename || "Untitled recording"}
                    </span>
                    <span className="text-xs text-muted-foreground tabular-nums">
                      {formatServerDate(row.processed_at)}
                    </span>
                    <Badge variant="outline" className="text-xs">
                      {row.assessment_mode === "WITH_TECHNICAL_ACCURACY" ? "Technical" : "Non-technical"}
                      {row.subject_code ? ` · ${row.subject_code}` : ""}
                    </Badge>
                    <span className="w-24 text-right text-sm font-medium tabular-nums text-foreground">
                      {formatMark(row)}
                    </span>
                    <span className="w-8 text-sm text-muted-foreground">{row.final_grade ?? ""}</span>
                    <Badge className={`border-0 text-xs ${status.className}`}>{status.label}</Badge>
                    {opening === row.mark_id && <Loader2 className="size-3.5 animate-spin" />}
                  </button>
                );
              })}
            </div>
          </Card>
        ))
      )}
    </div>
  );
}

interface ResultDetailProps {
  doc: VivaMarkDocument;
  onPublish: (technical: number) => void;
  publishing: boolean;
  studentDraft: string;
  onStudentDraft: (value: string) => void;
  onSaveStudent: () => void;
  savingStudent: boolean;
  onBack: () => void;
}

function ResultDetail({
  doc,
  onPublish,
  publishing,
  studentDraft,
  onStudentDraft,
  onSaveStudent,
  savingStudent,
  onBack,
}: ResultDetailProps) {
  const stored = doc.result as unknown as AnalysisResult | undefined;
  // A technical draft has no mode on the mark itself until it is published, so fall
  // back to the mode saved inside the analysis (otherwise it would look non-technical
  // and show the AI-only score as the official mark).
  const assessmentMode =
    ((doc.assessment_mode ?? stored?.assessment_mode) as AssessmentMode | undefined) ||
    "WITHOUT_TECHNICAL_ACCURACY";

  // Prefer the mark's own assessment: publishing rewrites it, the stored result keeps the first one.
  const analysis = useMemo<AnalysisResult | null>(() => {
    if (!stored) return null;
    const assessment = (doc.assessment ?? stored.assessment) as AnalysisResult["assessment"];
    return {
      ...stored,
      assessment,
      mark_id: doc._id,
      published: Boolean(doc.published),
      assessment_mode: assessmentMode,
      final_score: doc.final_score ?? stored.final_score,
      final_grade: doc.final_grade ?? stored.final_grade,
    };
  }, [doc, stored, assessmentMode]);

  const interpretation = useMemo(() => (analysis ? buildAIInterpretation(analysis) : []), [analysis]);
  const keyMoments = useMemo(
    () => (analysis ? buildKeyMoments(analysis.timeline ?? []) : []),
    [analysis],
  );
  const audioAnalysis = analysis?.audio_analysis;
  const familyScores =
    (analysis?.assessment?.ai_performance?.family_scores as Record<string, number | null> | undefined) ??
    {};
  const noSeek = () => {};
  const isTechnicalDraft = assessmentMode === "WITH_TECHNICAL_ACCURACY" && !doc.published;
  const aiSuggestion = analysis?.technical_accuracy_ai?.overall_score;
  const [technicalDraft, setTechnicalDraft] = useState<string>(
    aiSuggestion != null ? String(Math.round(aiSuggestion)) : "",
  );
  const technicalValue = technicalDraft.trim() === "" ? null : Number(technicalDraft);
  const technicalValid =
    technicalValue != null && Number.isFinite(technicalValue) && technicalValue >= 0 && technicalValue <= 10;
  const aiScore = analysis?.assessment?.ai_performance?.score ?? null;
  const previewFinal =
    technicalValid && aiScore != null ? 0.5 * aiScore + 0.5 * (technicalValue as number) * 10 : null;
  const dirty = (doc.student_id ?? "") !== studentDraft.trim();

  return (
    <div className="space-y-6">
      <AIPageBanner model="voca" />

      <Card className="p-5">
        <Button variant="ghost" size="sm" onClick={onBack} className="-ml-2 mb-3">
          <ArrowLeft className="size-4" />
          All results
        </Button>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="text-foreground font-medium truncate">
              {doc.video_filename || "Untitled recording"}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              {formatServerDate(doc.processed_at)}
              {doc.subject_code ? ` · ${doc.subject_code}` : ""}
              {doc.scoring_version ? ` · scorer ${doc.scoring_version}` : ""}
            </div>
          </div>
          <div className="flex items-end gap-2">
            <div>
              <label className="text-xs text-muted-foreground" htmlFor="result-student-id">
                Student ID
              </label>
              <Input
                id="result-student-id"
                className="mt-1 w-52"
                value={studentDraft}
                onChange={(e) => onStudentDraft(e.target.value)}
                placeholder="e.g. IT22557056"
                maxLength={64}
              />
            </div>
            <Button size="sm" onClick={onSaveStudent} disabled={!dirty || savingStudent}>
              {savingStudent ? <Loader2 className="size-3.5 animate-spin" /> : <Save className="size-3.5" />}
              Save
            </Button>
          </div>
        </div>
      </Card>

      {!analysis ? (
        <Card className="p-6 text-sm text-muted-foreground">
          This mark has no stored analysis, so there is nothing to show.
        </Card>
      ) : (
        <>
          <ScoreOverview
            assessment={analysis.assessment}
            analysisResult={analysis}
            assessmentMode={assessmentMode}
            technicalAccuracy={doc.technical_accuracy ?? null}
            published={Boolean(doc.published)}
            confidenceScore={analysis.confidence_score}
            engagementScore={analysis.engagement_score}
            audioGrade={audioAnalysis?.audio_grade}
            videoStatus={analysis.video_status}
            faceCoverageRatio={analysis.coverage?.face_coverage_ratio}
          />

          <div className="grid lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              <AISummary notes={interpretation} />

              <Card className="p-4 sm:p-6">
                <Tabs defaultValue="overview">
                  <TabsList>
                    <TabsTrigger value="overview">Overview</TabsTrigger>
                    <TabsTrigger value="transcript">Transcript</TabsTrigger>
                    <TabsTrigger value="engagement">Engagement</TabsTrigger>
                    <TabsTrigger value="audio">Audio</TabsTrigger>
                    <TabsTrigger value="qa">Q&A</TabsTrigger>
                    <TabsTrigger value="llm">Interpretation</TabsTrigger>
                  </TabsList>

                  <TabsContent value="overview" className="mt-4 space-y-6">
                    <div>
                      <div className="text-sm font-medium text-foreground mb-2">Emotional distribution</div>
                      <EmotionDistribution summary={analysis.summary} />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-foreground mb-2">Key moments</div>
                      <KeyMoments moments={keyMoments} onSeek={noSeek} />
                    </div>
                  </TabsContent>

                  <TabsContent value="transcript" className="mt-4">
                    <TranscriptPanel audioAnalysis={audioAnalysis} />
                  </TabsContent>

                  <TabsContent value="engagement" className="mt-4 space-y-4">
                    <EngagementTimeline timeline={analysis.timeline ?? []} />
                  </TabsContent>

                  <TabsContent value="audio" className="mt-4">
                    <AudioAnalysisPanel audioAnalysis={audioAnalysis} />
                  </TabsContent>

                  <TabsContent value="qa" className="mt-4">
                    <QaRelevancePanel
                      qaAnalysis={analysis.qa_analysis}
                      turns={audioAnalysis?.conversation?.turns}
                      structure={audioAnalysis?.conversation?.structure}
                      onSeek={noSeek}
                    />
                  </TabsContent>

                  <TabsContent value="llm" className="mt-4 space-y-4">
                    <LlmJudgePanel
                      evaluation={analysis.llm_evaluation}
                      transcriptFeatures={audioAnalysis?.transcript_features}
                    />
                  </TabsContent>
                </Tabs>
              </Card>
            </div>

            <div className="lg:sticky lg:top-6 self-start">
              <Card className="p-5 space-y-3">
                <div className="text-sm font-medium text-foreground">Mark summary</div>
                <dl className="space-y-2 text-sm">
                  <SummaryRow label="Final mark" value={doc.final_score != null ? `${doc.final_score.toFixed(1)} / 100` : "—"} />
                  <SummaryRow label="Grade" value={doc.final_grade ?? "—"} />
                  <SummaryRow label="AI performance" value={doc.ai_performance_score != null ? `${doc.ai_performance_score.toFixed(1)} / 100` : "—"} />
                  {assessmentMode === "WITH_TECHNICAL_ACCURACY" && (
                    <>
                      <SummaryRow label="Technical accuracy" value={doc.technical_accuracy != null ? `${doc.technical_accuracy} / 10` : "Not entered"} />
                      {analysis.technical_accuracy_ai?.overall_score != null && (
                        <SummaryRow
                          label="AI-suggested technical"
                          value={`${analysis.technical_accuracy_ai.overall_score.toFixed(1)} / 10`}
                        />
                      )}
                    </>
                  )}
                  <SummaryRow
                    label="Type"
                    value={assessmentMode === "WITH_TECHNICAL_ACCURACY" ? "Technical" : "Non-technical"}
                  />
                  <SummaryRow
                    label="Status"
                    value={
                      analysis.assessment?.status === "INCOMPLETE"
                        ? "Incomplete"
                        : doc.published
                          ? "Published"
                          : "Draft"
                    }
                  />
                </dl>
                {isTechnicalDraft && (
                  <div className="border-t border-border pt-3 space-y-2">
                    <div className="text-sm font-medium text-foreground">Publish technical mark</div>
                    <p className="text-xs text-muted-foreground">
                      Enter your technical accuracy score. The final mark is 50% AI performance and 50%
                      technical accuracy, and is saved when you publish.
                    </p>
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        min={0}
                        max={10}
                        step={0.5}
                        className="w-24"
                        value={technicalDraft}
                        onChange={(e) => setTechnicalDraft(e.target.value)}
                        placeholder="0–10"
                        aria-label="Technical accuracy out of 10"
                      />
                      <span className="text-xs text-muted-foreground">/ 10</span>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {previewFinal != null
                        ? `Final mark will be ${previewFinal.toFixed(1)} / 100`
                        : "Final mark appears once a score is entered."}
                    </div>
                    <Button
                      size="sm"
                      className="w-full"
                      disabled={!technicalValid || publishing}
                      onClick={() => technicalValid && onPublish(technicalValue as number)}
                    >
                      {publishing ? <Loader2 className="size-3.5 animate-spin" /> : null}
                      Publish mark
                    </Button>
                  </div>
                )}
                {Object.keys(familyScores).length > 0 && (
                  <div className="border-t border-border pt-3 space-y-2 text-sm">
                    {(["engagement", "audio_acoustics", "transcript"] as const).map((family) => (
                      <SummaryRow
                        key={family}
                        label={family === "audio_acoustics" ? "Audio acoustics" : family === "engagement" ? "Engagement" : "Transcript"}
                        value={familyScores[family] != null ? `${Math.round((familyScores[family] as number) * 100)} / 100` : "—"}
                      />
                    ))}
                  </div>
                )}
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium text-foreground tabular-nums">{value}</dd>
    </div>
  );
}
