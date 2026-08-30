// Print-only report layout for the Viva Assessment page. Rendered off-screen
// at all times and revealed only under @media print (see the `print:block`
// wrapper in VivaPage.tsx) so that clicking "Export report" → window.print()
// produces a clean document instead of a screenshot of the dashboard chrome.
// Browsers' native print dialog offers "Save as PDF" as a destination, which
// is the mechanism this relies on — no PDF-generation library is added for
// what a print stylesheet already covers.

import { AnalysisResult, AssessmentMode, KeyMoment, formatTime } from "./types";
import { resolveOfficialMark } from "./officialMark";

interface ReportPrintViewProps {
  videoFileName?: string;
  generatedAt: Date;
  analysisResult: AnalysisResult;
  assessmentMode: AssessmentMode;
  technicalAccuracy: number | null;
  published: boolean;
  aiInterpretation: string[];
  keyMoments: KeyMoment[];
}

export function ReportPrintView({
  videoFileName,
  generatedAt,
  analysisResult,
  assessmentMode,
  technicalAccuracy,
  published,
  aiInterpretation,
  keyMoments,
}: ReportPrintViewProps) {
  const audio = analysisResult.audio_analysis;
  const summary = analysisResult.summary;
  const engagementSummary = analysisResult.engagement_summary;
  const coverage = analysisResult.coverage;
  const llm = analysisResult.llm_evaluation;
  const qaPairs = analysisResult.qa_analysis?.pairs ?? [];
  const assessment = analysisResult.assessment;
  const aiScore = assessment?.ai_performance?.score;
  const withTech = assessmentMode === "WITH_TECHNICAL_ACCURACY";
  const technicalAccuracyAI = analysisResult.technical_accuracy_ai;
  // "partial" means some concept batches failed but the rest scored — the
  // suggestion is still real evidence and belongs in the record, flagged.
  const hasAISuggestion =
    withTech &&
    (technicalAccuracyAI?.status === "success" || technicalAccuracyAI?.status === "partial") &&
    technicalAccuracyAI.overall_score != null;
  const { finalScore, grade } = resolveOfficialMark({
    assessment,
    analysisResult,
    assessmentMode,
    technicalAccuracy,
    published,
  });

  return (
    <div className="p-10 text-black bg-white text-sm leading-relaxed">
      <div className="flex items-start justify-between border-b-2 border-black pb-4">
        <div>
          <div className="text-xl font-semibold">Viva Assessment Report</div>
          <div className="text-xs text-gray-600 mt-1">
            {videoFileName ?? "Untitled recording"}
          </div>
        </div>
        <div className="text-right text-xs text-gray-600">
          <div>Generated {generatedAt.toLocaleString()}</div>
          <div className="mt-1 font-medium">
            {published ? "Status: Published" : "Status: Draft (not yet published)"}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 mt-6">
        <div className="border border-gray-300 rounded p-3">
          <div className="text-[10px] uppercase tracking-wide text-gray-500">Official mark</div>
          <div className="text-2xl font-semibold mt-1">
            {finalScore != null ? finalScore.toFixed(1) : "—"}
            <span className="text-xs font-normal text-gray-500"> / 100</span>
          </div>
        </div>
        <div className="border border-gray-300 rounded p-3">
          <div className="text-[10px] uppercase tracking-wide text-gray-500">Grade</div>
          <div className="text-2xl font-semibold mt-1">{grade ?? "—"}</div>
        </div>
        <div className="border border-gray-300 rounded p-3">
          <div className="text-[10px] uppercase tracking-wide text-gray-500">Face coverage</div>
          <div className="text-2xl font-semibold mt-1">
            {analysisResult.coverage?.face_coverage_ratio != null
              ? `${Math.round(analysisResult.coverage.face_coverage_ratio * 100)}%`
              : "—"}
          </div>
        </div>
      </div>

      <div className="mt-6">
        <div className="font-semibold border-b border-gray-300 pb-1">Official assessment</div>
        <div className="mt-2 space-y-1">
          <div>Mode: {withTech ? "With technical accuracy" : "Without technical accuracy"}</div>
          <div>AI performance: {aiScore != null ? `${aiScore.toFixed(1)} / 100` : "—"}</div>
          {withTech && (
            <div>
              Technical accuracy: {technicalAccuracy != null ? `${technicalAccuracy} / 10` : "—"}
              {hasAISuggestion && (
                <span className="text-gray-500">
                  {" "}
                  (AI suggested {technicalAccuracyAI!.overall_score!.toFixed(1)} / 10
                  {technicalAccuracyAI?.model ? ` via ${technicalAccuracyAI.model}` : ""}; examiner{" "}
                  {technicalAccuracy === Math.round(technicalAccuracyAI!.overall_score!) ? "accepted" : "adjusted"} this value)
                </span>
              )}
            </div>
          )}
          <div className="font-medium pt-1">
            Final score: {finalScore != null ? `${finalScore.toFixed(1)} / 100` : "—"}
            {" · "}
            Grade: {grade ?? "—"}
          </div>
          {assessment?.status === "INCOMPLETE" && <div>Status: Incomplete — no official grade</div>}
        </div>
      </div>

      {hasAISuggestion && (
        <div className="mt-6">
          <div className="font-semibold border-b border-gray-300 pb-1">
            Technical accuracy — AI suggestion (advisory only)
          </div>
          <div className="mt-2 space-y-1 text-xs">
            <div>
              Suggested score: {technicalAccuracyAI!.overall_score!.toFixed(1)} / 10
              {technicalAccuracyAI?.model ? ` (model: ${technicalAccuracyAI.model})` : ""}
            </div>
            {technicalAccuracyAI?.status === "partial" && (
              <div className="text-gray-600">
                Partial result — some concepts could not be scored
                {technicalAccuracyAI.error ? `: ${technicalAccuracyAI.error}` : "."}
              </div>
            )}
            {(() => {
              const concepts = technicalAccuracyAI?.concepts ?? [];
              const covered = concepts.filter((c) => c.covered).length;
              const incorrect = concepts.filter((c) => c.covered && c.correct === false).length;
              return (
                <div>
                  {covered} of {concepts.length} rubric concepts covered in the transcript
                  {incorrect > 0 ? `, ${incorrect} flagged as incorrect` : ""}.
                </div>
              );
            })()}
            <p className="text-gray-500">
              Generated by comparing the transcript against a lecturer-uploaded subject concept
              rubric. This score only pre-fills the slider above — it never publishes on its own.
            </p>

            {/* Only concepts the student actually engaged with. Listing every
                not-covered row added pages of noise without adding evidence —
                the count line above already reports the gaps. */}
            {(() => {
              const engaged = (technicalAccuracyAI?.concepts ?? []).filter((c) => c.covered);
              if (engaged.length === 0) return null;
              return (
                <table className="w-full mt-2 border-collapse text-[10px]">
                  <thead>
                    <tr className="border-b border-gray-300 text-left">
                      <th className="py-1 pr-2 font-semibold">Concept discussed</th>
                      <th className="py-1 pr-2 font-semibold w-16">Weight</th>
                      <th className="py-1 pr-2 font-semibold w-20">Outcome</th>
                      <th className="py-1 font-semibold">Evidence from transcript</th>
                    </tr>
                  </thead>
                  <tbody>
                    {engaged.map((concept) => (
                      <tr
                        key={concept.concept_id}
                        className="border-b border-gray-100 align-top"
                        style={{ breakInside: "avoid" }}
                      >
                        <td className="py-1 pr-2">{concept.name}</td>
                        <td className="py-1 pr-2">{concept.weight?.toFixed(1) ?? "—"}</td>
                        <td className="py-1 pr-2">
                          {concept.correct === false ? "Incorrect" : "Correct"}
                        </td>
                        <td className="py-1 text-gray-600">
                          {concept.evidence_quote ? `"${concept.evidence_quote}"` : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              );
            })()}
          </div>
        </div>
      )}

      {/* A technical viva with no usable suggestion must say so: silence would
          read as "the AI agreed with the examiner". */}
      {withTech && !hasAISuggestion && (
        <div className="mt-6" style={{ breakInside: "avoid" }}>
          <div className="font-semibold border-b border-gray-300 pb-1">
            Technical accuracy — AI suggestion
          </div>
          <p className="mt-2 text-xs text-gray-600">
            {technicalAccuracyAI?.error ||
              (technicalAccuracyAI?.status === "skipped"
                ? "No subject concept rubric was linked to this viva, so no AI suggestion was produced. The technical accuracy score is the examiner's own."
                : "No AI technical-accuracy suggestion was available for this recording. The technical accuracy score is the examiner's own.")}
          </p>
        </div>
      )}

      {aiInterpretation.length > 0 && (
        <div className="mt-6">
          <div className="font-semibold border-b border-gray-300 pb-1">AI Interpretation</div>
          <ul className="mt-2 list-disc pl-5 space-y-1">
            {aiInterpretation.map((note, i) => (
              <li key={i}>{note}</li>
            ))}
          </ul>
        </div>
      )}

      {keyMoments.length > 0 && (
        <div className="mt-6">
          <div className="font-semibold border-b border-gray-300 pb-1">Key Moments</div>
          <ul className="mt-2 space-y-1">
            {keyMoments.map((m, i) => (
              <li key={i} className="flex gap-2">
                <span className="font-mono text-xs text-gray-500 shrink-0">{m.timeLabel}</span>
                <span>
                  {m.title}
                  {m.detail ? ` — ${m.detail}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-6" style={{ breakInside: "avoid" }}>
        <div className="font-semibold border-b border-gray-300 pb-1">Audio &amp; Transcript</div>
        {audio?.status === "success" || audio?.status === "degraded" || audio?.status === "insufficient_audio" ? (
          <>
            <div className="grid grid-cols-2 gap-x-6 gap-y-1 mt-2 text-xs">
              <div>Pitch profile: {audio.pitch_profile?.level ?? "unknown"}</div>
              <div>
                Duration: {audio.acoustic_features?.duration_seconds != null
                  ? formatTime(audio.acoustic_features.duration_seconds)
                  : "—"}
              </div>
              <div>Detected emotion: {audio.audio_emotion?.predicted_emotion ?? "unknown"}</div>
              <div>Transcript: {audio.transcript_word_count ?? 0} student words, {audio.segment_count ?? 0} segments</div>
            </div>
            {(audio.diarization?.speaker_count ?? 0) >= 2 && (
              <p className="mt-1 text-xs text-gray-600">
                Two or more speakers detected. Grade uses the on-camera student track ({audio.diarization?.student_speaker}) only.
              </p>
            )}
            {audio.transcript && (
              <p className="mt-2 text-xs whitespace-pre-wrap border border-gray-200 rounded p-2 bg-gray-50">
                {audio.transcript}
              </p>
            )}
            {audio.examiner_transcript && (
              <p className="mt-2 text-xs whitespace-pre-wrap border border-gray-200 rounded p-2 bg-gray-50">
                Panel: {audio.examiner_transcript}
              </p>
            )}
          </>
        ) : (
          <p className="mt-2 text-xs text-gray-500">
            Audio analysis unavailable{audio?.error ? `: ${audio.error}` : "."}
          </p>
        )}
      </div>

      {/* Engagement, emotion and face coverage: shown on the dashboard but
          previously absent from the report, so an exported record could not be
          checked against what the examiner actually saw. */}
      <div className="mt-6" style={{ breakInside: "avoid" }}>
        <div className="font-semibold border-b border-gray-300 pb-1">
          Engagement &amp; emotion
        </div>
        <div className="grid grid-cols-2 gap-x-6 gap-y-1 mt-2 text-xs">
          <div>
            Emotional tone: {(summary.positive_ratio * 100).toFixed(0)}% positive ·{" "}
            {(summary.neutral_ratio * 100).toFixed(0)}% neutral ·{" "}
            {(summary.negative_ratio * 100).toFixed(0)}% negative
          </div>
          <div>
            Engagement (Stage-1 CNN):{" "}
            {engagementSummary?.average_engagement_score != null
              ? `${(engagementSummary.average_engagement_score * 100).toFixed(1)} / 100`
              : "—"}
          </div>
          <div>
            High or very high engagement:{" "}
            {engagementSummary
              ? `${(((engagementSummary.high_ratio ?? 0) + (engagementSummary.very_high_ratio ?? 0)) * 100).toFixed(0)}% of session`
              : "—"}
          </div>
          <div>
            Face coverage:{" "}
            {coverage?.face_coverage_ratio != null
              ? `${(coverage.face_coverage_ratio * 100).toFixed(0)}% (${coverage.frames_with_face ?? 0} of ${coverage.frames_sampled ?? 0} frames)`
              : "—"}
          </div>
          <div>
            Facial positivity (supporting):{" "}
            {analysisResult.confidence_score != null
              ? `${analysisResult.confidence_score.toFixed(1)} / 100`
              : "—"}
          </div>
          <div>
            Blinks:{" "}
            {coverage?.blinks_measured && coverage.blinks_per_minute != null
              ? `${coverage.blinks_per_minute.toFixed(1)} / min`
              : "not measured"}
          </div>
        </div>
      </div>

      {/* Supporting LLM rubric scores. Explicitly not the official mark — the
          report says so, because the numbers look gradeable and are not. */}
      {llm && (llm.communication_clarity || llm.confidence || llm.engagement) && (
        <div className="mt-6" style={{ breakInside: "avoid" }}>
          <div className="font-semibold border-b border-gray-300 pb-1">
            Supporting LLM assessment (not the official mark)
          </div>
          <div className="mt-2 space-y-1 text-xs">
            {(
              [
                ["Communication clarity", llm.communication_clarity],
                ["Confidence", llm.confidence],
                ["Engagement", llm.engagement],
              ] as const
            ).map(([label, criterion]) =>
              criterion ? (
                <div key={label}>
                  <span className="font-medium">
                    {label}: {criterion.score} / 10
                  </span>
                  {criterion.justification ? (
                    <span className="text-gray-600"> — {criterion.justification}</span>
                  ) : null}
                </div>
              ) : null,
            )}
            {llm.status && llm.status !== "success" && (
              <div className="text-gray-500">Status: {llm.status}</div>
            )}
          </div>
        </div>
      )}

      {/* Question-and-answer relevance: the record of whether the student
          actually answered what the panel asked. */}
      {qaPairs.length > 0 && (
        <div className="mt-6">
          <div className="font-semibold border-b border-gray-300 pb-1">
            Question &amp; answer relevance ({qaPairs.length} pair
            {qaPairs.length === 1 ? "" : "s"})
          </div>
          <div className="mt-2 space-y-2 text-xs">
            {qaPairs.map((pair, i) => (
              <div key={i} style={{ breakInside: "avoid" }}>
                <div className="font-medium">
                  Q{i + 1}: {pair.question || "—"}
                </div>
                <div className="text-gray-700">A: {pair.answer || "—"}</div>
                <div className="text-gray-500">
                  {pair.addresses_question === true
                    ? "Addresses the question"
                    : pair.addresses_question === false
                      ? "Does not address the question"
                      : "Not assessed"}
                  {pair.relevance ? ` · relevance: ${String(pair.relevance)}` : ""}
                  {pair.answer_type ? ` · ${String(pair.answer_type)}` : ""}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-8 pt-3 border-t border-gray-300 text-[10px] text-gray-400">
        Generated by GradeX AI · VOCA viva assessment engine.{" "}
        {withTech
          ? `Technical viva — the final score fuses this AI performance score with a technical accuracy score${
              hasAISuggestion ? " (AI-suggested, examiner-reviewed)" : " entered by the examiner"
            }, reviewed and published by the evaluator.`
          : "Non-technical viva — this AI performance score was disclosed as automatic at analysis time and saves without a separate examiner review step."}
      </div>
    </div>
  );
}
