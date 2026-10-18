/** Remembers a running viva analysis so a reloaded page can reattach to it.
 *
 * The server keeps analysing after the browser goes away (it runs in a worker),
 * but the page forgets everything on reload. This keeps just enough — the progress
 * id the server tracks the job under — in the browser to pick the thread back up. */

const KEY = "viva_inflight_job";
/** Server progress rows expire after 15 minutes, so older entries are useless. */
const MAX_AGE_MS = 15 * 60 * 1000;

export interface InflightJob {
  progressId: string;
  fileName: string;
  startedAt: number;
}

export function saveInflightJob(progressId: string, fileName: string): void {
  try {
    const job: InflightJob = { progressId, fileName, startedAt: Date.now() };
    window.localStorage.setItem(KEY, JSON.stringify(job));
  } catch {
    // storage unavailable (private window etc.) — resuming simply will not be offered
  }
}

export function clearInflightJob(): void {
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    // ignore
  }
}

export function readInflightJob(): InflightJob | null {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return null;
    const job = JSON.parse(raw) as Partial<InflightJob>;
    if (
      typeof job.progressId !== "string" ||
      typeof job.startedAt !== "number" ||
      Date.now() - job.startedAt > MAX_AGE_MS
    ) {
      window.localStorage.removeItem(KEY);
      return null;
    }
    return { progressId: job.progressId, fileName: job.fileName ?? "recording", startedAt: job.startedAt };
  } catch {
    return null;
  }
}
