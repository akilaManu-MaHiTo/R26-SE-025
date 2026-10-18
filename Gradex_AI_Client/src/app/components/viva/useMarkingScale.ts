import { useEffect, useSyncExternalStore } from "react";
import { apiFetch } from "../../api/authApi";
import { SERVER_BASE_URL } from "../../api/gradingApiBase";
import {
  DEFAULT_MARKING_SCALE,
  MarkingScale,
  buildMarkingScale,
  getMarkingScale,
  parseMarkingScale,
  setMarkingScale,
  subscribeMarkingScale,
} from "./markingScale";

let loading: Promise<void> | null = null;
/** The server's default scale (VIVA_MARK_MAX), used when a viva has no total of its own. */
let serverScale: MarkingScale = DEFAULT_MARKING_SCALE;
/** The total marks of the viva on screen, when it has one: it wins over the server default. */
let vivaTotal: number | null = null;

/** The server's scale moved to a viva's own total (the technical score uses the same total). */
function scaleForTotal(total: number | null): MarkingScale {
  if (total == null || total === serverScale.markMax) return serverScale;
  return buildMarkingScale(
    total,
    total,
    serverScale.decimals,
    serverScale.gradeBands.map((band) => [band.grade, band.minPercent]),
  );
}

/** Fetch the scale once per page load. A failed fetch leaves the defaults in place and retries later. */
export function loadMarkingScale(): Promise<void> {
  if (!loading) {
    loading = apiFetch(`${SERVER_BASE_URL}/api/viva-config`)
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const scale = parseMarkingScale(await response.json());
        if (!scale) throw new Error("Unusable marking scale");
        serverScale = scale;
        setMarkingScale(scaleForTotal(vivaTotal));
      })
      .catch(() => {
        loading = null;
      });
  }
  return loading;
}

/** The current marking scale; the component re-renders when the server's scale arrives. */
export function useMarkingScale(): MarkingScale {
  useEffect(() => {
    void loadMarkingScale();
  }, []);
  return useSyncExternalStore(subscribeMarkingScale, getMarkingScale, getMarkingScale);
}

/**
 * Mark the screen on the viva's own total marks (entered in the Viva Workspace) instead of the
 * server default. Pass nothing while no viva is selected; the default applies again on unmount.
 */
export function useVivaMarkingScale(totalMarks: number | null | undefined): MarkingScale {
  const total = Number(totalMarks) > 0 ? Number(totalMarks) : null;
  useEffect(() => {
    vivaTotal = total;
    setMarkingScale(scaleForTotal(total));
    return () => {
      vivaTotal = null;
      setMarkingScale(serverScale);
    };
  }, [total]);
  return useMarkingScale();
}
