// Print-only report layout for the Viva Assessment page. Rendered off-screen
// at all times and revealed only under @media print (see the `print:block`
// wrapper in VivaPage.tsx) so that clicking "Export report" → window.print()
// produces a clean document instead of a screenshot of the dashboard chrome.
// Browsers' native print dialog offers "Save as PDF" as a destination, which
// is the mechanism this relies on — no PDF-generation library is added for
// what a print stylesheet already covers.

import { AnalysisResult, KeyMoment, RubricCriterion, formatTime } from "./types";

interface ReportPrintViewProps {
  videoFileName?: string;
  generatedAt: Date;
  analysisResult: AnalysisResult;
  criteria: RubricCriterion[];
  finalGrade: string;
  published: boolean;
  aiInterpretation: string[];
  keyMoments: KeyMoment[];
}

export function ReportPrintView({
  videoFileName,
  generatedAt,
  analysisResult,
  criteria,
  finalGrade,
  published,
  aiInterpretation,
  keyMoments,
}: ReportPrintViewProps) {
  const total = criteria.reduce((sum, c) => sum + c.score, 0);
  const max = criteria.reduce((sum, c) => sum + c.max, 0);
  const audio = analysisResult.audio_analysis;

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
          {analysisResult.mark_id && <div>Reference ID: {analysisResult.mark_id}</div>}
          <div className="mt-1 font-medium">
            {published ? "Status: Published" : "Status: Draft (not yet published)"}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 mt-6">
        <div className="border border-gray-300 rounded p-3">
          <div className="text-[10px] uppercase tracking-wide text-gray-500">Facial Positivity</div>
          <div className="text-2xl font-semibold mt-1">
            {analysisResult.confidence_score != null ? analysisResult.confidence_score.toFixed(1) : "—"}
            <span className="text-xs font-normal text-gray-500"> / 100</span>
          </div>
        </div>
        <div className="border border-gray-300 rounded p-3">
          <div className="text-[10px] uppercase tracking-wide text-gray-500">Engagement</div>
          <div className="text-2xl font-semibold mt-1">
            {analysisResult.engagement_score != null ? analysisResult.engagement_score.toFixed(1) : "—"}
            <span className="text-xs font-normal text-gray-500">%</span>
          </div>
        </div>
        <div className="border border-gray-300 rounded p-3">
          <div className="text-[10px] uppercase tracking-wide text-gray-500">Audio Quality</div>
          <div className="text-2xl font-semibold mt-1">
            {audio?.audio_grade != null ? audio.audio_grade.toFixed(2) : "—"}
            <span className="text-xs font-normal text-gray-500"> / 10</span>
          </div>
        </div>
      </div>

      <div className="mt-6">
        <div className="font-semibold border-b border-gray-300 pb-1">Evaluation Rubric</div>
        <table className="w-full mt-2 text-sm">
          <tbody>
            {criteria.map((c) => (
              <tr key={c.id} className="border-b border-gray-200">
                <td className="py-1.5 pr-2 align-top">
                  <div>{c.name}</div>
                  <div className="text-xs text-gray-500">{c.description}</div>
                </td>
                <td className="py-1.5 text-right align-top whitespace-nowrap font-medium">
                  {c.score} / {c.max}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="flex items-center justify-between mt-2 pt-2 border-t border-gray-300">
          <div className="font-medium">
            Total: {total} / {max}
          </div>
          <div className="font-medium">Final grade: {finalGrade}</div>
        </div>
      </div>

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
              <div>Transcript: {audio.transcript_word_count ?? 0} words, {audio.segment_count ?? 0} segments</div>
            </div>
            {audio.transcript && (
              <p className="mt-2 text-xs whitespace-pre-wrap border border-gray-200 rounded p-2 bg-gray-50">
                {audio.transcript}
              </p>
            )}
          </>
        ) : (
          <p className="mt-2 text-xs text-gray-500">
            Audio analysis unavailable{audio?.error ? `: ${audio.error}` : "."}
          </p>
        )}
      </div>

      <div className="mt-8 pt-3 border-t border-gray-300 text-[10px] text-gray-400">
        Generated by GradeX AI · VOCA viva assessment engine. Scores are AI-assisted and
        reviewed by the evaluator prior to publishing.
      </div>
    </div>
  );
}
