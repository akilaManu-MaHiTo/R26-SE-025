import { useEffect, useState } from "react";
import { Bell, HelpCircle, Moon, Sun, Loader2, CheckCircle2, Sparkles } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "./ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";
import { motion, AnimatePresence } from "framer-motion";

type TopbarAnalysis = { active: boolean; studentId?: string; message?: string; progress?: number };

type AnalysisItem = { studentId: string; message: string; progress: number; active: boolean; updatedAt: number };

export function TopBar({ title, subtitle }: { title: string; subtitle?: string }) {
  const { resolvedTheme, setTheme } = useTheme();
  const toggleTheme = () => setTheme(resolvedTheme === "dark" ? "light" : "dark");
  const [items, setItems] = useState<AnalysisItem[]>([]);
  const [hasUnread, setHasUnread] = useState(false);
  const [lastDone, setLastDone] = useState<string | null>(null);

  // derived: latest active item for inline pill
  const activeItems = items.filter((i) => i.active);
  const latestActive = activeItems.length ? activeItems[activeItems.length - 1] : null;
  const overallProgress = activeItems.length ? Math.max(...activeItems.map((i) => i.progress)) : 0;

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<TopbarAnalysis>).detail;
      if (!detail || !detail.studentId) return;
      const prog = typeof detail.progress === "number" ? Math.max(0, Math.min(100, detail.progress)) : undefined;
      if (detail.active) {
        setItems((prev) => {
          const exists = prev.find((i) => i.studentId === detail.studentId);
          if (exists) {
            return prev.map((i) =>
              i.studentId === detail.studentId
                ? { ...i, message: detail.message || i.message, progress: prog ?? i.progress, active: true, updatedAt: Date.now() }
                : i
            );
          }
          return [...prev, { studentId: detail.studentId!, message: detail.message || `Analyzing ${detail.studentId}…`, progress: prog ?? 0, active: true, updatedAt: Date.now() }];
        });
        setHasUnread(true);
      } else {
        // completion / close
        setItems((prev) => prev.map((i) => (i.studentId === detail.studentId ? { ...i, active: false, progress: prog ?? i.progress, message: detail.message || i.message, updatedAt: Date.now() } : i)));
        if (detail.message?.toLowerCase().includes("complete") && detail.studentId) {
          setLastDone(detail.studentId);
          setHasUnread(true);
          setTimeout(() => setHasUnread(false), 5000);
        } else {
          setTimeout(() => setHasUnread(false), 3000);
        }
      }
    };
    window.addEventListener("topbar-student-analysis" as any, handler as EventListener);
    return () => window.removeEventListener("topbar-student-analysis" as any, handler as EventListener);
  }, []);

  return (
    <header className="bg-background border-b border-border px-8 py-4 flex items-center gap-4 sticky top-0 z-20 backdrop-blur bg-background/80">
      <div className="flex-1 min-w-0">
        <h1 className="tracking-tight text-xl">{title}</h1>
        {subtitle && <div className="text-sm text-muted-foreground mt-0.5">{subtitle}</div>}
      </div>

      {/* Inline progress when analyzing student — shows latest active with real % */}
      <AnimatePresence>
        {latestActive && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            className="hidden md:flex items-center gap-2.5 rounded-full border bg-card/90 backdrop-blur px-3 py-1.5 shadow-sm max-w-[420px]"
          >
            <span className="relative flex size-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-60" />
              <span className="relative inline-flex rounded-full size-2 bg-primary" />
            </span>
            <Loader2 className="size-3.5 animate-spin text-primary shrink-0" />
            <span className="text-xs font-medium truncate max-w-[220px]" title={latestActive.message}>
              {latestActive.message || `Analyzing ${latestActive.studentId}…`}
            </span>
            <span className="text-xs font-mono tabular-nums bg-primary/10 text-primary px-1.5 py-0.5 rounded border border-primary/20 shrink-0">
              {latestActive.progress}%
            </span>
            <span className="text-xs text-muted-foreground shrink-0 hidden lg:inline">PULSE·AI</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Bell notification — keep icon, popover shows per-student real progress bars */}
      <Popover>
        <PopoverTrigger asChild>
          <Button variant="ghost" size="icon" className="relative">
            {activeItems.length > 0 ? (
              <Loader2 className="size-5 text-primary animate-spin" />
            ) : (
              <Bell className="size-5 text-muted-foreground" />
            )}
            {(hasUnread || activeItems.length > 0) && (
              <span className={`absolute top-1.5 right-1.5 size-2 rounded-full ${activeItems.length > 0 ? "bg-primary animate-pulse" : "bg-destructive"}`} />
            )}
            {activeItems.length > 1 && (
              <span className="absolute -top-1 -right-1 size-4 rounded-full bg-primary text-primary-foreground text-[10px] leading-none flex items-center justify-center font-medium border border-background">
                {activeItems.length}
              </span>
            )}
          </Button>
        </PopoverTrigger>
        <PopoverContent align="end" className="w-80 p-0 overflow-hidden max-h-[420px] flex flex-col">
          <div className="p-3 border-b flex items-center gap-2 shrink-0">
            <Bell className="size-4 text-muted-foreground" />
            <span className="text-sm font-medium">Notifications</span>
            <span className="ml-auto text-xs text-muted-foreground">{items.length} total</span>
            {activeItems.length > 0 && <span className="size-2 rounded-full bg-primary animate-pulse" />}
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
                    key={it.studentId}
                    className={`rounded-lg border p-3 space-y-2 ${it.active ? "bg-primary/5 border-primary/20" : it.progress === 100 ? "bg-emerald-50 dark:bg-emerald-950/20 border-emerald-200" : "bg-muted/30"}`}
                  >
                    <div className="flex items-center gap-2 text-sm font-medium">
                      {it.active ? (
                        <Loader2 className="size-4 animate-spin text-primary shrink-0" />
                      ) : it.progress === 100 ? (
                        <CheckCircle2 className="size-4 text-emerald-600 shrink-0" />
                      ) : (
                        <Bell className="size-4 text-muted-foreground shrink-0" />
                      )}
                      <span className="truncate">{it.studentId}</span>
                      <span className={`ml-auto text-xs font-mono tabular-nums px-1.5 py-0.5 rounded border shrink-0 ${it.active ? "bg-primary/10 text-primary border-primary/20" : it.progress === 100 ? "bg-emerald-500/10 text-emerald-700 border-emerald-500/20" : "bg-muted text-muted-foreground"}`}>
                        {it.progress}%
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground font-mono bg-background rounded px-2 py-1.5 border line-clamp-2" title={it.message}>
                      {it.message}
                    </p>
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span className="flex items-center gap-1"><Sparkles className="size-3" /> {it.active ? "Analyzing…" : it.progress === 100 ? "Complete" : "Pending"}</span>
                        <span className="tabular-nums">{it.progress}%</span>
                      </div>
                      <div className="h-2 bg-muted rounded-full overflow-hidden">
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
              <span className="text-xs text-muted-foreground">{activeItems.length} analyzing · {items.filter((i) => i.progress === 100 && !i.active).length} done</span>
              <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => setItems([])}>Clear</Button>
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

      {/* Thin top progress bar — real overall progress */}
      <AnimatePresence>
        {activeItems.length > 0 && (
          <motion.div
            className="absolute left-0 right-0 bottom-0 h-0.5 bg-primary origin-left"
            style={{ boxShadow: "0 0 8px hsl(var(--primary))" }}
            initial={{ scaleX: 0 }}
            animate={{ scaleX: overallProgress / 100 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
          />
        )}
      </AnimatePresence>
    </header>
  );
}
