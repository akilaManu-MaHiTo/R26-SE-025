import { Workflow, FileText, BarChart3, Video, ArrowRight, TrendingUp, Clock, Users, CheckCircle2 } from "lucide-react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import type { Page } from "./Sidebar";
import { LineChart, Line, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";

const trend = [
  { d: "Mon", v: 32 }, { d: "Tue", v: 48 }, { d: "Wed", v: 41 },
  { d: "Thu", v: 64 }, { d: "Fri", v: 58 }, { d: "Sat", v: 72 }, { d: "Sun", v: 81 },
];

export function LecturerDashboard({ onNavigate }: { onNavigate: (p: Page) => void }) {
  const cards = [
    {
      id: "grading-diagram" as Page,
      title: "Grade Diagram Exams",
      desc: "Auto-extract shapes, labels and structure to grade ER diagrams, flowcharts and UML.",
      icon: Workflow,
      color: "from-blue-500 to-blue-700",
      tint: "bg-blue-50 text-blue-600",
      stat: "12 pending",
    },
    {
      id: "grading-handwritten" as Page,
      title: "Grade Handwritten Exams",
      desc: "OCR + rubric matching for scanned answer sheets with AI confidence scoring.",
      icon: FileText,
      color: "from-emerald-500 to-emerald-700",
      tint: "bg-emerald-50 text-emerald-600",
      stat: "28 pending",
    },
    {
      id: "analytics" as Page,
      title: "Student Analytics",
      desc: "Performance bands, cognitive gaps, topic mastery and at-risk early warnings.",
      icon: BarChart3,
      color: "from-violet-500 to-violet-700",
      tint: "bg-violet-50 text-violet-600",
      stat: "4 alerts",
    },
    {
      id: "viva" as Page,
      title: "Viva Assessment",
      desc: "Upload viva recordings — get transcripts, key moments and rubric scoring.",
      icon: Video,
      color: "from-amber-500 to-amber-600",
      tint: "bg-amber-50 text-amber-600",
      stat: "6 to review",
    },
  ];

  const stats = [
    { label: "Exams graded", value: "1,284", delta: "+12%", icon: CheckCircle2, color: "text-emerald-600" },
    { label: "Avg. grade time", value: "2m 14s", delta: "−38%", icon: Clock, color: "text-blue-600" },
    { label: "Active students", value: "342", delta: "+5%", icon: Users, color: "text-violet-600" },
    { label: "Class average", value: "74.2", delta: "+1.8", icon: TrendingUp, color: "text-amber-600" },
  ];

  const activity = [
    { who: "CS-2024-018", what: "Submitted DB Final exam", time: "2 min ago", tag: "new", color: "bg-blue-100 text-blue-700" },
    { who: "Auto-grader", what: "Completed grading for Quiz 03 (47 papers)", time: "18 min ago", tag: "done", color: "bg-emerald-100 text-emerald-700" },
    { who: "CS-2024-104", what: "Flagged for low cognitive level on Q7", time: "1 hr ago", tag: "alert", color: "bg-red-100 text-red-700" },
    { who: "You", what: "Published rubric for Operating Systems Mid-term", time: "3 hr ago", tag: "rubric", color: "bg-slate-100 text-slate-700" },
  ];

  return (
    <div className="p-8 space-y-8">
      <div className="rounded-2xl p-6 bg-gradient-to-r from-blue-600 to-indigo-600 text-white relative overflow-hidden">
        <div className="absolute -right-16 -top-16 size-64 rounded-full bg-white/10 blur-2xl" />
        <div className="relative flex items-start justify-between gap-6 flex-wrap">
          <div>
            <Badge className="bg-white/15 hover:bg-white/15 text-white border-0">Friday, 8 May 2026</Badge>
            <h2 className="mt-3 tracking-tight">Good morning, Dr. Mendis 👋</h2>
            <p className="text-blue-100 mt-1.5 max-w-xl">
              You have <span className="text-white">46 papers</span> waiting and <span className="text-white">4 students</span> flagged as at-risk this week.
            </p>
          </div>
          <Button className="bg-white text-blue-700 hover:bg-blue-50" onClick={() => onNavigate("grading-handwritten")}>
            Resume grading <ArrowRight className="size-4 ml-1" />
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((s) => {
          const Icon = s.icon;
          return (
            <Card key={s.label} className="p-5 border-slate-200">
              <div className="flex items-start justify-between">
                <div className={`size-10 rounded-lg bg-slate-50 flex items-center justify-center ${s.color}`}>
                  <Icon className="size-5" />
                </div>
                <span className="text-xs text-emerald-600">{s.delta}</span>
              </div>
              <div className="mt-4 tracking-tight text-slate-900">{s.value}</div>
              <div className="text-sm text-slate-500 mt-0.5">{s.label}</div>
            </Card>
          );
        })}
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 grid sm:grid-cols-2 gap-4">
          {cards.map((c) => {
            const Icon = c.icon;
            return (
              <Card key={c.id} className="group p-6 border-slate-200 hover:border-blue-200 hover:shadow-lg hover:shadow-blue-50 transition-all cursor-pointer" onClick={() => onNavigate(c.id)}>
                <div className="flex items-start justify-between">
                  <div className={`size-12 rounded-xl bg-gradient-to-br ${c.color} flex items-center justify-center shadow-md shadow-slate-200`}>
                    <Icon className="size-6 text-white" />
                  </div>
                  <Badge variant="secondary" className={c.tint + " border-0"}>{c.stat}</Badge>
                </div>
                <div className="mt-5 tracking-tight text-slate-900">{c.title}</div>
                <p className="text-sm text-slate-500 mt-1.5 leading-relaxed">{c.desc}</p>
                <Button variant="ghost" className="mt-3 px-0 text-blue-600 hover:text-blue-700 hover:bg-transparent group-hover:translate-x-1 transition-transform">
                  Access <ArrowRight className="size-4 ml-1" />
                </Button>
              </Card>
            );
          })}
        </div>

        <div className="space-y-6">
          <Card className="p-5 border-slate-200">
            <div className="flex items-center justify-between">
              <div className="text-slate-900">Grading throughput</div>
              <Badge variant="secondary" className="bg-emerald-50 text-emerald-700 border-0">+24% wk</Badge>
            </div>
            <div className="h-32 mt-3 -mx-2">
              <ResponsiveContainer>
                <LineChart data={trend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                  <XAxis dataKey="d" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                  <YAxis hide />
                  <Tooltip contentStyle={{ borderRadius: 8, fontSize: 12, border: "1px solid #e2e8f0" }} />
                  <Line type="monotone" dataKey="v" stroke="#2563eb" strokeWidth={2.5} dot={{ r: 3, fill: "#2563eb" }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card className="p-5 border-slate-200">
            <div className="text-slate-900 mb-3">Recent activity</div>
            <div className="space-y-3">
              {activity.map((a, i) => (
                <div key={i} className="flex gap-3">
                  <div className={`shrink-0 px-2 py-0.5 h-fit rounded text-[10px] uppercase tracking-wide ${a.color}`}>
                    {a.tag}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-slate-900 truncate">{a.who}</div>
                    <div className="text-xs text-slate-500 truncate">{a.what}</div>
                    <div className="text-[11px] text-slate-400 mt-0.5">{a.time}</div>
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
