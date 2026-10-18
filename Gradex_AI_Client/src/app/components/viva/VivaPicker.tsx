import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { listVivas, type Viva } from "./vivasApi";
import { listSubjectContent } from "./subjectContentApi";

/**
 * Chooses which viva a recording or live session is filed under — "what is this viva for".
 * The choice lives in the URL (?viva=<id>), which is what the Viva Assessment and Live Viva
 * pages already read, so picking here and arriving from the Viva Workspace behave the same.
 *
 * Only the signed-in lecturer's own vivas are offered, since the server refuses analysis under
 * anyone else's. A technical viva whose subject content has not been added yet is listed but
 * cannot be chosen.
 */
export function VivaPicker({
  currentId,
  disabled = false,
  id = "viva-picker",
  className = "",
}: {
  currentId: string;
  disabled?: boolean;
  id?: string;
  className?: string;
}) {
  const [, setSearchParams] = useSearchParams();
  const [vivas, setVivas] = useState<Viva[]>([]);
  const [contentCodes, setContentCodes] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([listVivas(), listSubjectContent().catch(() => [])])
      .then(([items, subjects]) => {
        if (cancelled) return;
        setVivas(items);
        setContentCodes(new Set(subjects.map((subject) => subject.subject_code)));
        setFailed(false);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const groups = useMemo(() => {
    const bySubject = new Map<string, Viva[]>();
    for (const viva of vivas) {
      bySubject.set(viva.subject_code, [...(bySubject.get(viva.subject_code) ?? []), viva]);
    }
    return Array.from(bySubject.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [vivas]);

  const choose = (vivaId: string) => {
    setSearchParams(vivaId ? { viva: vivaId } : {}, { replace: true });
  };

  return (
    <div className={className}>
      <select
        id={id}
        aria-label="Viva"
        className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm disabled:opacity-60"
        value={vivas.some((viva) => viva.viva_id === currentId) ? currentId : ""}
        onChange={(event) => choose(event.target.value)}
        disabled={disabled || loading || vivas.length === 0}
      >
        <option value="">
          {loading
            ? "Loading vivas…"
            : failed
              ? "Could not load your vivas"
              : vivas.length === 0
                ? "No vivas yet"
                : "Select a viva…"}
        </option>
        {groups.map(([code, items]) => (
          <optgroup key={code} label={`${code} · ${items[0].subject_name}`}>
            {items.map((viva) => {
              const technical = viva.category === "technical";
              const needsContent = technical && !contentCodes.has(viva.subject_code);
              return (
                <option key={viva.viva_id} value={viva.viva_id} disabled={needsContent}>
                  {viva.name} · sem {viva.semester} {viva.year} · {technical ? "Technical" : "Non-technical"}
                  {needsContent ? " (subject content needed)" : ""}
                </option>
              );
            })}
          </optgroup>
        ))}
      </select>
      {!loading && vivas.length === 0 && (
        <p className="mt-1 text-xs text-muted-foreground">
          <Link to="/viva-evaluation/vivas" className="underline text-foreground">
            Create a viva
          </Link>{" "}
          first.
        </p>
      )}
    </div>
  );
}
