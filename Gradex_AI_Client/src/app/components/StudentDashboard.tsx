import { Calendar, BookOpen, TrendingUp, Bell, Award, ChevronRight, Sparkles } from "lucide-react";
import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { AreaChart, Area, LineChart, Line, ResponsiveContainer, XAxis, YAxis, CartesianGrid, Tooltip } from "recharts";

const trend = [
  { m: "Sep", v: 62 }, { m: "Oct", v: 68 }, { m: "Nov", v: 64 },
  { m: "Dec", v: 72 }, { m: "Jan", v: 78 }, { m: "Feb", v: 81 }, { m: "Mar", v: 85 },
];

const grades = [
  { course: "Database Systems", item: "Mid-term", score: 86, band: "A", tone: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300" },
  { course: "Operating Systems", item: "Quiz 03", score: 72, band: "B+", tone: "bg-accent text-accent-foreground" },
  { course: "Algorithms", item: "Assignment 4", score: 64, band: "C+", tone: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300" },
  { course: "Software Engineering", item: "Project Phase 1", score: 91, band: "A+", tone: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300" },
];

const upcoming = [
  { d: "12", m: "May", title: "Database Systems · Final", time: "09:00 AM · Hall A" },
  { d: "16", m: "May", title: "Operating Systems · Final", time: "01:00 PM · Hall B" },
  { d: "22", m: "May", title: "Algorithms · Viva", time: "10:30 AM · Room 204" },
];

export function StudentDashboard() {
  return (
    <div className="p-8 space-y-6">
      {/* Welcome */}
      <Card className="p-8 border-border relative overflow-hidden">
        <div className="absolute -right-12 -top-12 size-56 rounded-full bg-primary/[0.04] blur-2xl" />
        <div className="relative flex items-center gap-6 flex-wrap">
          <div className="size-16 rounded-2xl bg-primary text-primary-foreground flex items-center justify-center text-2xl tracking-tight font-medium">
            SP
          </div>
          <div className="flex-1 min-w-[240px]">
            <div className="text-muted-foreground text-sm">Welcome back,</div>
            <h2 className="text-2xl tracking-tight mt-0.5">Sahan Perera</h2>
            <div className="text-sm text-muted-foreground mt-1">3rd Year · Computer Science · CS-2024-018</div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {[
              { k: "GPA", v: "3.72" },
              { k: "Rank", v: "#14" },
              { k: "Streak", v: "12d" },
            ].map((s) => (
              <div key={s.k} className="px-4 py-3 rounded-lg border border-border bg-card/60 min-w-[80px] text-center">
                <div className="text-lg tracking-tight tabular-nums">{s.v}</div>
                <div className="text-xs text-muted-foreground mt-0.5">{s.k}</div>
              </div>
            ))}
          </div>
        </div>
      </Card>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Performance trend */}
          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium">Performance trend</div>
                <div className="text-xs text-muted-foreground mt-0.5">Average score across all subjects</div>
              </div>
              <Badge className="bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300">
                <TrendingUp className="size-3 mr-1" /> +23% YoY
              </Badge>
            </div>
            <div className="h-56 mt-4 -mx-2">
              <ResponsiveContainer>
                <AreaChart data={trend}>
                  <defs>
                    <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--ring)" stopOpacity={0.25} />
                      <stop offset="100%" stopColor="var(--ring)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="m" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} domain={[40, 100]} />
                  <Tooltip contentStyle={{ borderRadius: 8, fontSize: 12, border: "1px solid var(--border)", background: "var(--card)" }} />
                  <Area type="monotone" dataKey="v" stroke="var(--ring)" strokeWidth={2.5} fill="url(#grad)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {/* Recent grades */}
          <Card className="overflow-hidden">
            <div className="px-6 py-4 border-b border-border flex items-center justify-between">
              <div className="font-medium">Recent grades</div>
              <Button variant="ghost" size="sm" className="text-primary">View all <ChevronRight className="size-4 ml-1" /></Button>
            </div>
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-muted-foreground text-xs uppercase tracking-wide">
                <tr>
                  <th className="text-left px-6 py-3 font-medium">Course</th>
                  <th className="text-left px-6 py-3 font-medium">Assessment</th>
                  <th className="text-left px-6 py-3 font-medium">Score</th>
                  <th className="text-left px-6 py-3 font-medium">Grade</th>
                </tr>
              </thead>
              <tbody>
                {grades.map((g) => (
                  <tr key={g.course} className="border-t border-border hover:bg-muted/40">
                    <td className="px-6 py-3">{g.course}</td>
                    <td className="px-6 py-3 text-muted-foreground">{g.item}</td>
                    <td className="px-6 py-3 tabular-nums">{g.score}/100</td>
                    <td className="px-6 py-3"><Badge className={`${g.tone} border-0`}>{g.band}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </div>

        <div className="space-y-6">
          {/* Upcoming exams */}
          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 font-medium">
                <Calendar className="size-4 text-primary" /> Upcoming exams
              </div>
              <Badge variant="secondary" className="bg-muted text-muted-foreground">3</Badge>
            </div>
            <div className="mt-4 space-y-3">
              {upcoming.map((u) => (
                <div key={u.title} className="flex items-center gap-3 p-3 rounded-lg border border-border hover:border-primary/40 transition-colors cursor-pointer">
                  <div className="size-12 rounded-lg bg-muted flex flex-col items-center justify-center leading-tight">
                    <span className="text-sm font-medium tabular-nums">{u.d}</span>
                    <span className="text-[10px] uppercase text-muted-foreground">{u.m}</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm truncate">{u.title}</div>
                    <div className="text-xs text-muted-foreground">{u.time}</div>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Announcements */}
          <Card className="p-6">
            <div className="flex items-center gap-2 font-medium">
              <Bell className="size-4 text-primary" /> Announcements
            </div>
            <div className="mt-3 space-y-3">
              {[
                { t: "Final exam timetable released", d: "2 hr ago", icon: Calendar },
                { t: "Resources uploaded for OS revision", d: "Yesterday", icon: BookOpen },
                { t: "Dean's list — congratulations", d: "3 days ago", icon: Award },
              ].map((a) => {
                const Icon = a.icon;
                return (
                  <div key={a.t} className="flex gap-3">
                    <div className="size-8 rounded-lg bg-muted flex items-center justify-center shrink-0 text-muted-foreground">
                      <Icon className="size-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm">{a.t}</div>
                      <div className="text-xs text-muted-foreground">{a.d}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
