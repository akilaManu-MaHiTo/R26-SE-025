import { useEffect, useSyncExternalStore } from "react";
import { apiFetch } from "../../api/authApi";
import { SERVER_BASE_URL } from "../../api/gradingApiBase";
import {
  MarkingScale,
  getMarkingScale,
  parseMarkingScale,
  setMarkingScale,
  subscribeMarkingScale,
} from "./markingScale";

let loading: Promise<void> | null = null;

/** Fetch the scale once per page load. A failed fetch leaves the defaults in place and retries later. */
export function loadMarkingScale(): Promise<void> {
  if (!loading) {
    loading = apiFetch(`${SERVER_BASE_URL}/api/viva-config`)
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const scale = parseMarkingScale(await response.json());
        if (!scale) throw new Error("Unusable marking scale");
        setMarkingScale(scale);
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
