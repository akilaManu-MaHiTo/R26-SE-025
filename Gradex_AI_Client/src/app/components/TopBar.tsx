import { useEffect, useState } from "react";
import { Bell, HelpCircle, Moon, Sun, CheckCircle2, UserRound, Clock, AlertCircle } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "./ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";
import { motion } from "framer-motion";

type AnalysisStatus = "queued" | "analyzing" | "complete" | "failed";
type TopbarAnalysis = { active: boolean; studentId?: string; jobId?: string; examLabel?: string; message?: string; progress?: number; status?: AnalysisStatus };

type AnalysisItem = { studentId: string; jobId: string; examLabel?: string; message: string; progress: number; active: boolean; status: AnalysisStatus; updatedAt: number };

export function TopBar({ title, subtitle }: { title: string; subtitle?: string }) {
  const { resolvedTheme, setTheme } = useTheme();
  const toggleTheme = () => setTheme(resolvedTheme === "dark" ? "light" : "dark");
  const [items, setItems] = useState<AnalysisItem[]>([]);
  const [hasUnread, setHasUnread] = useState(false);

  const activeItems = items.filter((i) => i.active);

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<TopbarAnalysis>).detail;
      if (!detail || !detail.studentId) return;
      const prog = typeof detail.progress === "number" ? Math.max(0, Math.min(100, detail.progress)) : undefined;
      const jobId = detail.jobId ?? detail.studentId;
      setItems((prev) => {
        const existing = prev.find((i) => i.jobId === jobId);
        const progress = prog ?? existing?.progress ?? 0;
        const item: AnalysisItem = {
          studentId: detail.studentId!, jobId, examLabel: detail.examLabel ?? existing?.examLabel,
          message: detail.message || existing?.message || `Analyzing ${detail.studentId}…`,
          progress, active: detail.active,
          status: detail.status ?? (detail.active ? "analyzing" : progress === 100 ? "complete" : "failed"),
          updatedAt: Date.now(),
        };
        return existing ? prev.map((i) => i.jobId === jobId ? item : i) : [...prev, item];
      });
      setHasUnread(true);
    };
    window.addEventListener("topbar-student-analysis" as any, handler as EventListener);
    return () => window.removeEventListener("topbar-student-analysis" as any, handler as EventListener);
  }, []);

  return (
    <header className="print:hidden bg-background border-b border-border px-8 py-4 flex items-center gap-4 sticky top-0 z-20 backdrop-blur bg-background/80">
      <div className="flex-1 min-w-0">
        <h1 className="tracking-tight text-xl">{title}</h1>
        {subtitle && <div className="text-sm text-muted-foreground mt-0.5">{subtitle}</div>}
      </div>

      <Popover onOpenChange={(open) => { if (open) setHasUnread(false); }}>
        <PopoverTrigger asChild>
          <Button variant="ghost" size="icon" className="relative" aria-label="Notifications">
            <Bell className="size-5 text-muted-foreground" />
            {activeItems.length > 0 ? (
              <span aria-hidden="true" className="absolute -top-1 -right-1 min-w-4 h-4 px-1 rounded-full bg-primary text-primary-foreground text-[10px] leading-none flex items-center justify-center font-medium border border-background">
                {activeItems.length}
              </span>
            ) : hasUnread && (
              <span aria-hidden="true" className="absolute top-1.5 right-1.5 size-2 rounded-full bg-primary" />
            )}
          </Button>
        </PopoverTrigger>
        <PopoverContent align="end" aria-label="Notifications" className="w-80 max-w-[calc(100vw-2rem)] p-0 overflow-hidden max-h-[420px] flex flex-col">
          <div className="p-3 border-b flex items-center gap-2 shrink-0">
            <Bell className="size-4 text-muted-foreground" />
            <span className="text-sm font-medium">Notifications</span>
            <span className="ml-auto text-xs text-muted-foreground">{items.length} total</span>
          </div>
          <div className="overflow-y-auto flex-1">
            {items.length === 0 ? (
              <div className="text-center py-8 px-3">
                <Bell className="size-6 mx-auto text-muted-foreground/30" />
                <p className="text-sm text-muted-foreground mt-2">No new notifications</p>
                <p className="text-xs text-muted-foreground/70 mt-1">Click a student View to start analysis. Real progress shows here.</p>
              </div>
            ) : (
              <div className="p-2 space-y-2">
                {[...items].sort((a, b) => (b.active ? 1 : 0) - (a.active ? 1 : 0) || b.updatedAt - a.updatedAt).map((it) => (
                  <div
                    key={it.jobId}
                    className={`rounded-xl border p-4 space-y-3 ${it.active ? "bg-primary/5 border-primary/20" : it.progress === 100 ? "bg-emerald-50 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-900" : "bg-muted/30"}`}
                  >
                    <div className="flex items-center gap-2 text-sm font-medium">
                      {it.status === "queued" ? (
                        <Clock className="size-4 text-muted-foreground shrink-0" />
                      ) : it.status === "failed" ? (
                        <AlertCircle className="size-4 text-destructive shrink-0" />
                      ) : it.active ? (
                        <UserRound className="size-4 text-primary shrink-0" />
                      ) : it.progress === 100 ? (
                        <CheckCircle2 className="size-4 text-emerald-600 shrink-0" />
                      ) : (
                        <Bell className="size-4 text-muted-foreground shrink-0" />
                      )}
                      <div className="min-w-0">
                        <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Student number</p>
                        <p className="truncate font-mono" title={it.studentId}>{it.studentId}</p>
                        {it.examLabel && <p className="text-xs text-muted-foreground truncate" title={it.examLabel}>{it.examLabel}</p>}
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2" title={it.message}>
                      {it.message}
                    </p>
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>{it.status === "queued" ? "Queued" : it.status === "failed" ? "Failed" : it.active ? "Analyzing…" : "Complete"}</span>
                        <span className="tabular-nums">{it.progress}%</span>
                      </div>
                      <div role="progressbar" aria-label={`Analysis progress for ${it.studentId}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={it.progress} className="h-1.5 bg-muted rounded-full overflow-hidden">
                        <motion.div
                          className={`h-full rounded-full ${it.active ? "bg-primary" : it.progress === 100 ? "bg-emerald-500" : "bg-muted-foreground"}`}
                          initial={{ width: 0 }}
                          animate={{ width: `${it.progress}%` }}
                          transition={{ duration: 0.4, ease: "easeOut" }}
                        />
                      </div>
                    </div>
                    {!it.active && it.progress === 100 && (
                      <p className="text-xs text-emerald-700 dark:text-emerald-400">Performance ready — AI tips excluded.</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
          {items.length > 0 && (
            <div className="p-2 border-t bg-muted/20 flex justify-between items-center shrink-0">
              <span className="text-xs text-muted-foreground">{items.filter((i) => i.status === "queued").length} queued · {items.filter((i) => i.status === "analyzing").length} analyzing</span>
              <Button variant="ghost" size="sm" className="h-7 text-xs" disabled={!items.some((i) => !i.active)} onClick={() => setItems((prev) => prev.filter((i) => i.active))}>Clear finished</Button>
            </div>
          )}
        </PopoverContent>
      </Popover>

      <Button variant="ghost" size="icon" onClick={toggleTheme} aria-label="Toggle theme">
        {resolvedTheme === "dark" ? (
          <Sun className="size-5 text-muted-foreground" />
        ) : (
          <Moon className="size-5 text-muted-foreground" />
        )}
      </Button>
      <Button variant="ghost" size="icon">
        <HelpCircle className="size-5 text-muted-foreground" />
      </Button>

    </header>
  );
}
