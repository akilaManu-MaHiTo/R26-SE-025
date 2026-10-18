/**
 * The marking scale the viva screens use: what the official mark and the examiner's technical
 * score are out of, and the letter-grade bands.
 *
 * The server owns the real values (VivaEvaluationEngine/services/marking_scale.py, shared at
 * GET /api/viva-config). This module only holds the current copy so the pure helpers in types.ts
 * and officialMark.ts can read it, and starts from the same defaults the server uses until the
 * real scale has loaded. Nothing else in the client should hard-code "20".
 */

export interface GradeBand {
  grade: string;
  /** Minimum percentage of the full mark. */
  minPercent: number;
  /** The same minimum on the current mark scale. */
  minMark: number;
}

export interface MarkingScale {
  /** What the official mark is out of. */
  markMax: number;
  /** What the examiner's technical score is out of. */
  technicalMax: number;
  /** Decimals an official mark is rounded to. */
  decimals: number;
  /** Highest band first, last band starts at 0. */
  gradeBands: GradeBand[];
}

const DEFAULT_GRADE_BANDS_PERCENT: Array<[string, number]> = [
  ["A+", 90],
  ["A", 80],
  ["B+", 70],
  ["B", 60],
  ["C+", 50],
  ["C", 40],
  ["F", 0],
];

/** Build a scale from its numbers; band minimums are derived so they can never disagree. */
export function buildMarkingScale(
  markMax: number,
  technicalMax: number = markMax,
  decimals = 2,
  bandsPercent: Array<[string, number]> = DEFAULT_GRADE_BANDS_PERCENT,
): MarkingScale {
  return {
    markMax,
    technicalMax,
    decimals,
    gradeBands: bandsPercent.map(([grade, minPercent]) => ({
      grade,
      minPercent,
      minMark: Math.round(((minPercent / 100) * markMax) * 10 ** decimals) / 10 ** decimals,
    })),
  };
}

export const DEFAULT_MARKING_SCALE: MarkingScale = buildMarkingScale(20);

/** Validate the server payload; returns null when it is not a usable scale. */
export function parseMarkingScale(raw: unknown): MarkingScale | null {
  if (typeof raw !== "object" || raw === null) return null;
  const data = raw as Record<string, unknown>;
  const markMax = Number(data.mark_max);
  const technicalMax = Number(data.technical_max);
  const decimals = Number(data.decimals);
  const bands = Array.isArray(data.grade_bands) ? data.grade_bands : [];
  if (!(markMax > 0) || !(technicalMax > 0) || !Number.isInteger(decimals) || decimals < 0 || bands.length === 0) {
    return null;
  }
  const gradeBands: GradeBand[] = [];
  for (const band of bands) {
    const b = band as Record<string, unknown>;
    if (typeof b.grade !== "string" || !Number.isFinite(Number(b.min_percent)) || !Number.isFinite(Number(b.min_mark))) {
      return null;
    }
    gradeBands.push({ grade: b.grade, minPercent: Number(b.min_percent), minMark: Number(b.min_mark) });
  }
  return { markMax, technicalMax, decimals, gradeBands };
}

let current: MarkingScale = DEFAULT_MARKING_SCALE;
const listeners = new Set<() => void>();

export function getMarkingScale(): MarkingScale {
  return current;
}

export function setMarkingScale(next: MarkingScale): void {
  current = next;
  listeners.forEach((listener) => listener());
}

/** For React's useSyncExternalStore: re-render when the scale changes. */
export function subscribeMarkingScale(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
