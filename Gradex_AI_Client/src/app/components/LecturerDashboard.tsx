import { Workflow, FileText, BarChart3, Video, ArrowRight, TrendingUp, Clock, Users, CheckCircle2, Sparkles } from "lucide-react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { useNavigate } from "react-router";
import { LineChart, Line, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";

const trend = [
  { d: "Mon", v: 32 }, { d: "Tue", v: 48 }, { d: "Wed", v: 41 },
  { d: "Thu", v: 64 }, { d: "Fri", v: 58 }, { d: "Sat", v: 72 }, { d: "Sun", v: 81 },
];

export function LecturerDashboard() {
  const navigate = useNavigate();
  const cards = [
    {
      path: "/diagram-evaluation/diagram-grading",
      title: "Grade diagram exams",
      desc: "Auto-extract shapes, labels and structure to grade ER diagrams, flowcharts and UML.",
      icon: Workflow,
      stat: "12 pending",
    },
    {
      path: "/grading/handwritten-grading",
      title: "Grade handwritten exams",
      desc: "OCR + rubric matching for scanned answer sheets with AI confidence scoring.",
      icon: FileText,
      stat: "28 pending",
    },
    {
      path: "/question-exam/analytics",
      title: "Student analytics",
      desc: "Performance bands, cognitive gaps, topic mastery and at-risk early warnings.",
      icon: BarChart3,
      stat: "4 alerts",
    },
    {
      path: "/viva-evaluation/viva-assessment",
      title: "Viva assessment",
      desc: "Upload viva recordings — get transcripts, key moments and rubric scoring.",
      icon: Video,
      stat: "6 to review",
    },
  ];

  const stats = [
    { label: "Exams graded", value: "1,284", delta: "+12%", icon: CheckCircle2 },
    { label: "Avg. grade time", value: "2m 14s", delta: "−38%", icon: Clock },
    { label: "Active students", value: "342", delta: "+5%", icon: Users },
    { label: "Class average", value: "74.2", delta: "+1.8", icon: TrendingUp },
  ];

  const activity = [
    { who: "CS-2024-018", what: "Submitted DB Final exam", time: "2 min ago", tag: "new" },
    { who: "Auto-grader", what: "Completed grading for Quiz 03 (47 papers)", time: "18 min ago", tag: "done" },
    { who: "CS-2024-104", what: "Flagged for low cognitive level on Q7", time: "1 hr ago", tag: "alert" },
    { who: "You", what: "Published rubric for Operating Systems Mid-term", time: "3 hr ago", tag: "rubric" },
  ];

  const tagColor: Record<string, string> = {
    new: "bg-accent text-accent-foreground",
    done: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
    alert: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
    rubric: "bg-muted text-muted-foreground",
  };

  return (
    <div className="p-8 space-y-8">
      {/* Greeting */}
      <div className="rounded-2xl border border-border bg-card p-8 relative overflow-hidden">
        <div className="absolute -right-16 -top-24 size-64 rounded-full bg-primary/[0.04] blur-2xl" />
        <div className="relative flex items-start justify-between gap-6 flex-wrap">
          <div>
            <Badge variant="outline" className="border-border text-muted-foreground">Friday, 8 May 2026</Badge>
            <h2 className="mt-4 text-2xl tracking-tight">Good morning, Dr. Mendis</h2>
            <p className="text-muted-foreground mt-2 max-w-xl">
              You have <span className="text-foreground font-medium">46 papers</span> waiting and{" "}
              <span className="text-foreground font-medium">4 students</span> flagged as at-risk this week.
            </p>
          </div>
          <Button onClick={() => navigate("/grading/handwritten-grading")}>
            Resume grading <ArrowRight className="size-4 ml-1" />
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((s) => {
          const Icon = s.icon;
          return (
            <Card key={s.label} className="p-5">
              <div className="flex items-start justify-between">
                <div className="size-10 rounded-lg bg-muted flex items-center justify-center text-muted-foreground">
                  <Icon className="size-5" />
                </div>
                <span className="text-xs text-emerald-700 dark:text-emerald-400">{s.delta}</span>
              </div>
              <div className="mt-4 text-2xl tracking-tight tabular-nums">{s.value}</div>
              <div className="text-sm text-muted-foreground mt-0.5">{s.label}</div>
            </Card>
          );
        })}
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 grid sm:grid-cols-2 gap-4">
          {cards.map((c) => {
            const Icon = c.icon;
            return (
              <Card key={c.path} className="group p-6 hover:border-primary/40 transition-colors duration-200 cursor-pointer" onClick={() => navigate(c.path)}>
                <div className="flex items-start justify-between">
                  <div className="size-12 rounded-xl bg-primary text-primary-foreground flex items-center justify-center">
                    <Icon className="size-6" />
                  </div>
                  <Badge variant="secondary" className="bg-muted text-muted-foreground">{c.stat}</Badge>
                </div>
                <div className="mt-5 text-lg tracking-tight">{c.title}</div>
                <p className="text-sm text-muted-foreground mt-1.5 leading-relaxed">{c.desc}</p>
                <Button variant="ghost" className="mt-3 px-0 text-primary group-hover:translate-x-1 transition-transform">
                  Access <ArrowRight className="size-4 ml-1" />
                </Button>
              </Card>
            );
          })}
        </div>

        <div className="space-y-6">
          <Card className="p-5">
            <div className="flex items-center justify-between">
              <div className="font-medium">Grading throughput</div>
              <Badge variant="secondary" className="bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300">+24% wk</Badge>
            </div>
            <div className="h-32 mt-3 -mx-2">
              <ResponsiveContainer>
                <LineChart data={trend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="d" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
                  <YAxis hide />
                  <Tooltip contentStyle={{ borderRadius: 8, fontSize: 12, border: "1px solid var(--border)", background: "var(--card)" }} />
                  <Line type="monotone" dataKey="v" stroke="var(--ring)" strokeWidth={2.5} dot={{ r: 3, fill: "var(--ring)" }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card className="p-5">
            <div className="font-medium mb-3">Recent activity</div>
            <div className="space-y-3">
              {activity.map((a, i) => (
                <div key={i} className="flex gap-3">
                  <div className={`shrink-0 px-2 py-0.5 h-fit rounded text-[10px] uppercase tracking-wide ${tagColor[a.tag]}`}>
                    {a.tag}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm truncate">{a.who}</div>
                    <div className="text-xs text-muted-foreground truncate">{a.what}</div>
                    <div className="text-[11px] text-muted-foreground/70 mt-0.5">{a.time}</div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
