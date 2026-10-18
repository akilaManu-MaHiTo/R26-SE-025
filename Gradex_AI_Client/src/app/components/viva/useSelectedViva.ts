import { useEffect, useState } from "react";
import { useSearchParams } from "react-router";
import { fetchViva, type Viva } from "./vivasApi";

/** Resolves the viva named by `?viva=<id>`; the upload and live pages work only inside one. */
export function useSelectedViva() {
  const [params] = useSearchParams();
  const vivaId = params.get("viva") ?? "";
  const [viva, setViva] = useState<Viva | null>(null);
  const [loading, setLoading] = useState(Boolean(vivaId));
  const [error, setError] = useState("");

  useEffect(() => {
    if (!vivaId) {
      setViva(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError("");
    fetchViva(vivaId)
      .then((value) => {
        if (!cancelled) setViva(value);
      })
      .catch((err) => {
        if (!cancelled) {
          setViva(null);
          setError(err instanceof Error ? err.message : "Could not load the viva");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [vivaId]);

  return { vivaId, viva, loading, error };
}
