import { useState } from "react";
import { Search, Plus, GripVertical, FileDown, Printer, FileText, Trash2, Sparkles } from "lucide-react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Badge } from "./ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Progress } from "./ui/progress";
import { BarChart, Bar, ResponsiveContainer, XAxis, YAxis, CartesianGrid, Tooltip, Cell } from "recharts";

const bank = [
  { id: "Q-1041", topic: "ER Modeling", diff: "Easy", bloom: "Remember", marks: 5, text: "Define an entity and give two examples." },
  { id: "Q-1042", topic: "Normalization", diff: "Medium", bloom: "Apply", marks: 10, text: "Normalize the given relation to 3NF showing each step." },
  { id: "Q-1043", topic: "SQL", diff: "Medium", bloom: "Apply", marks: 8, text: "Write a query to find top 3 departments by avg salary." },
  { id: "Q-1044", topic: "Indexing", diff: "Hard", bloom: "Evaluate", marks: 12, text: "Compare B+ tree vs hash indexing for range queries." },
  { id: "Q-1045", topic: "Transactions", diff: "Hard", bloom: "Analyze", marks: 10, text: "Explain ACID violations in the given schedule." },
  { id: "Q-1046", topic: "Concurrency", diff: "Hard", bloom: "Create", marks: 15, text: "Design a 2PL protocol that avoids deadlocks for given workload." },
];

const diffColor: Record<string, string> = {
  Easy: "bg-emerald-50 text-emerald-700",
  Medium: "bg-amber-50 text-amber-700",
  Hard: "bg-red-50 text-red-700",
};

export function ExamCreator() {
  const [selected, setSelected] = useState<string[]>(["Q-1041", "Q-1042", "Q-1043", "Q-1045"]);

  interface ExamRecommendation {
    topic?: string;
    bloom_level?: string;
    question_type?: string;
    mark_range?: number[];
    priority_score?: number;
    evidence?: Record<string, unknown>;
  }

  const backendBaseUrl =
    (import.meta as ImportMeta & { env?: { VITE_BACKEND_URL?: string } }).env?.VITE_BACKEND_URL ??
    "http://localhost:8000";

  const [recs, setRecs] = useState<ExamRecommendation[]>([]);
  const [recStatus, setRecStatus] = useState<"idle" | "loading" | "loaded" | "no_run" | "error">("idle");
  const [recError, setRecError] = useState<string | null>(null);

  const loadRecommendations = async () => {
    setRecStatus("loading");
    setRecError(null);
    try {
      const response = await fetch(`${backendBaseUrl}/api/predict/exam-recommendations`);
      if (!response.ok) {
        throw new Error((await response.text()) || "Failed to load recommendations.");
      }
      const data = await response.json();
      setRecs(data.recommendations ?? []);
      setRecStatus(data.status === "no_run" ? "no_run" : "loaded");
    } catch (error) {
      setRecStatus("error");
      setRecError(error instanceof Error ? error.message : "Failed to load recommendations.");
    }
  };

  const exam = bank.filter((q) => selected.includes(q.id));
  const total = exam.reduce((a, b) => a + b.marks, 0);

  const bloomDist = ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"].map((b) => ({
    b,
    v: exam.filter((q) => q.bloom === b).reduce((a, c) => a + c.marks, 0),
  }));

  const toggle = (id: string) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className="tracking-tight text-slate-900">Exam Creator</h2>
          <p className="text-sm text-slate-500 mt-1">Compose, balance and export structured exams.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline"><Printer className="size-4 mr-2" />Print</Button>
          <Button variant="outline"><FileText className="size-4 mr-2" />Word</Button>
          <Button className="bg-blue-600 hover:bg-blue-700"><FileDown className="size-4 mr-2" />Export PDF</Button>
        </div>
      </div>

      {/* AI exam recommendations */}
      <Card className="p-4 border-border">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-foreground">AI exam recommendations</div>
            <div className="text-xs text-muted-foreground mt-0.5">
              Evidence-based topic × Bloom targets from the predictive engine.
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void loadRecommendations()}
            disabled={recStatus === "loading"}
          >
            <Sparkles className="size-4 mr-1.5 text-primary" />
            {recStatus === "loading" ? "Loading…" : "Refresh"}
          </Button>
        </div>
        <div className="mt-3">
          {recStatus === "idle" && (
            <p className="text-xs text-muted-foreground">
              Click Auto-balance to load topic × Bloom recommendations.
            </p>
          )}
          {recStatus === "no_run" && (
            <p className="text-xs text-muted-foreground">
              Run analytics first — upload exam + answers in Student Analytics.
            </p>
          )}
          {recStatus === "error" && (
            <p className="text-xs text-red-500">{recError}</p>
          )}
          {recStatus === "loaded" && recs.length === 0 && (
            <p className="text-xs text-muted-foreground">
              No recommendations available for the latest run.
            </p>
          )}
          {recStatus === "loaded" && recs.length > 0 && (
            <div className="grid sm:grid-cols-2 gap-2">
              {recs.map((r, i) => (
                <div key={`rec-${i}`} className="rounded-lg border border-border p-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge variant="secondary" className="bg-accent text-primary border-0">{r.topic ?? "—"}</Badge>
                    <Badge variant="outline" className="border-border text-muted-foreground">{r.bloom_level ?? "—"}</Badge>
                    <Badge className="bg-primary text-primary-foreground border-0 ml-auto">
                      {r.priority_score != null ? r.priority_score.toFixed(2) : "—"}
                    </Badge>
                  </div>
                  <div className="text-xs text-muted-foreground mt-2">
                    {r.question_type ?? "problem_solving"} · {r.mark_range?.[0] ?? 1}–{r.mark_range?.[1] ?? 4} marks
                  </div>
                  {r.evidence && (
                    <div className="text-xs text-muted-foreground mt-1">
                      mastery {typeof r.evidence.mastery === "number" ? r.evidence.mastery.toFixed(2) : "—"} ·{" "}
                      {String(r.evidence.evidence_status ?? "")}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>

      {/* Filters */}
      <Card className="p-4 border-border">
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          <Select defaultValue="3">
            <SelectTrigger><SelectValue placeholder="Year/Level" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="1">1st Year</SelectItem>
              <SelectItem value="2">2nd Year</SelectItem>
              <SelectItem value="3">3rd Year</SelectItem>
              <SelectItem value="4">4th Year — Final</SelectItem>
            </SelectContent>
          </Select>
          <Select defaultValue="final">
            <SelectTrigger><SelectValue placeholder="Exam type" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="midterm">Mid-term</SelectItem>
              <SelectItem value="final">Final</SelectItem>
              <SelectItem value="quiz">Quiz</SelectItem>
            </SelectContent>
          </Select>
          <Select defaultValue="all">
            <SelectTrigger><SelectValue placeholder="Topic" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All topics</SelectItem>
              <SelectItem value="er">ER Modeling</SelectItem>
              <SelectItem value="norm">Normalization</SelectItem>
              <SelectItem value="sql">SQL</SelectItem>
            </SelectContent>
          </Select>
          <Select defaultValue="all">
            <SelectTrigger><SelectValue placeholder="Difficulty" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All</SelectItem>
              <SelectItem value="easy">Easy</SelectItem>
              <SelectItem value="med">Medium</SelectItem>
              <SelectItem value="hard">Hard</SelectItem>
            </SelectContent>
          </Select>
          <div className="relative">
            <Search className="size-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <Input className="pl-9" placeholder="Search question bank…" />
          </div>
        </div>
      </Card>

      <div className="grid lg:grid-cols-5 gap-6">
        {/* Question bank */}
        <Card className="lg:col-span-2 border-slate-200">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
            <div className="text-slate-900">Question bank</div>
            <Badge variant="secondary" className="bg-slate-100 border-0">{bank.length} items</Badge>
          </div>
          <div className="divide-y divide-slate-100 max-h-[640px] overflow-auto">
            {bank.map((q) => {
              const on = selected.includes(q.id);
              return (
                <div key={q.id} className="p-4 hover:bg-slate-50 flex gap-3 group">
                  <GripVertical className="size-4 text-slate-300 mt-1 cursor-grab" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs text-slate-400">{q.id}</span>
                      <Badge variant="secondary" className="bg-blue-50 text-blue-700 border-0">{q.topic}</Badge>
                      <Badge variant="secondary" className={diffColor[q.diff] + " border-0"}>{q.diff}</Badge>
                      <Badge variant="outline" className="border-slate-200 text-slate-600">{q.bloom}</Badge>
                      <span className="text-xs text-slate-500 ml-auto">{q.marks} mk</span>
                    </div>
                    <div className="text-sm text-slate-700 mt-2">{q.text}</div>
                  </div>
                  <Button size="icon" variant={on ? "default" : "outline"} onClick={() => toggle(q.id)}
                          className={"size-8 " + (on ? "bg-blue-600 hover:bg-blue-700" : "")}>
                    <Plus className={"size-4 " + (on ? "rotate-45" : "")} />
                  </Button>
                </div>
              );
            })}
          </div>
        </Card>

        {/* Builder + preview */}
        <div className="lg:col-span-3 space-y-4">
          <Card className="border-slate-200">
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <div className="text-slate-900">Database Systems — Final Exam</div>
                <div className="text-xs text-slate-500 mt-0.5">{exam.length} questions · {total} marks · 3 hours</div>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void loadRecommendations()}
                disabled={recStatus === "loading"}
              >
                <Sparkles className="size-4 mr-1.5 text-primary" />
                {recStatus === "loading" ? "Loading…" : "Auto-balance"}
              </Button>
            </div>
            <div className="p-5 space-y-3">
              {exam.map((q, i) => (
                <div key={q.id} className="flex gap-3 p-3 rounded-lg border border-slate-200 bg-white">
                  <div className="size-7 rounded-md bg-blue-50 text-blue-700 flex items-center justify-center text-sm shrink-0">
                    {i + 1}
                  </div>
                  <div className="flex-1">
                    <div className="text-sm text-slate-900">{q.text}</div>
                    <div className="flex gap-2 mt-1.5">
                      <Badge variant="secondary" className="bg-slate-100 border-0 text-xs">{q.topic}</Badge>
                      <Badge variant="outline" className="text-xs">{q.bloom}</Badge>
                      <span className="text-xs text-slate-500 ml-auto">{q.marks} marks</span>
                    </div>
                  </div>
                  <Button size="icon" variant="ghost" onClick={() => toggle(q.id)} className="size-8">
                    <Trash2 className="size-4 text-slate-400" />
                  </Button>
                </div>
              ))}
            </div>
          </Card>

          <div className="grid sm:grid-cols-2 gap-4">
            <Card className="p-5 border-slate-200">
              <div className="text-slate-900">Bloom's level distribution</div>
              <div className="h-40 mt-3">
                <ResponsiveContainer>
                  <BarChart data={bloomDist}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                    <XAxis dataKey="b" tick={{ fontSize: 10, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                    <YAxis hide />
                    <Tooltip contentStyle={{ borderRadius: 8, fontSize: 12 }} />
                    <Bar dataKey="v" radius={[4, 4, 0, 0]}>
                      {bloomDist.map((_, i) => (
                        <Cell key={i} fill={["#a78bfa", "#60a5fa", "#34d399", "#fbbf24", "#fb923c", "#f87171"][i]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>

            <Card className="p-5 border-slate-200">
              <div className="text-slate-900">Topic coverage</div>
              <div className="space-y-3 mt-3">
                {[
                  { t: "ER Modeling", v: 25 },
                  { t: "Normalization", v: 30 },
                  { t: "SQL", v: 20 },
                  { t: "Transactions", v: 25 },
                ].map((c) => (
                  <div key={c.t}>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-700">{c.t}</span>
                      <span className="text-slate-500">{c.v}%</span>
                    </div>
                    <Progress value={c.v} className="h-1.5 mt-1.5" />
                  </div>
                ))}
              </div>
            </Card>
          </div>

          <Card className="p-5 border-slate-200">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-slate-900">Template library</div>
                <div className="text-xs text-slate-500 mt-0.5">Reuse formats from past semesters</div>
              </div>
              <Button variant="ghost" size="sm" className="text-blue-600">Browse all</Button>
            </div>
            <div className="grid grid-cols-3 gap-3 mt-4">
              {["DB Final 2024", "OS Mid-term 2025", "DSA Final 2023"].map((t, i) => (
                <div key={t} className="rounded-lg border border-slate-200 p-3 hover:border-blue-300 cursor-pointer">
                  <div className="aspect-[4/3] rounded bg-gradient-to-br from-slate-100 to-slate-50 flex items-center justify-center">
                    <FileText className="size-7 text-slate-400" />
                  </div>
                  <div className="text-sm text-slate-900 mt-2">{t}</div>
                  <div className="text-xs text-slate-500">{[8, 10, 12][i]} questions · {[60, 75, 100][i]} mk</div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
