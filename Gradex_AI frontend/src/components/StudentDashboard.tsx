
"use client";

import { Calendar, BookOpen, TrendingUp, Bell, Award, ChevronRight } from "lucide-react";
import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { LineChart, Line, ResponsiveContainer, XAxis, YAxis, CartesianGrid, Tooltip, Area, AreaChart } from "recharts";

const trend = [
  { m: "Sep", v: 62 }, { m: "Oct", v: 68 }, { m: "Nov", v: 64 },
  { m: "Dec", v: 72 }, { m: "Jan", v: 78 }, { m: "Feb", v: 81 }, { m: "Mar", v: 85 },
];

const grades = [
  { course: "Database Systems", item: "Mid-term", score: 86, band: "A", color: "bg-emerald-50 text-emerald-700" },
  { course: "Operating Systems", item: "Quiz 03", score: 72, band: "B+", color: "bg-blue-50 text-blue-700" },
  { course: "Algorithms", item: "Assignment 4", score: 64, band: "C+", color: "bg-amber-50 text-amber-700" },
  { course: "Software Engineering", item: "Project Phase 1", score: 91, band: "A+", color: "bg-emerald-50 text-emerald-700" },
];

const upcoming = [
  { d: "12", m: "May", title: "Database Systems · Final", time: "09:00 AM · Hall A", tone: "blue" },
  { d: "16", m: "May", title: "Operating Systems · Final", time: "01:00 PM · Hall B", tone: "amber" },
  { d: "22", m: "May", title: "Algorithms · Viva", time: "10:30 AM · Room 204", tone: "emerald" },
];

const toneStyle: Record<string, string> = {
  blue: "bg-blue-50 text-blue-700",
  amber: "bg-amber-50 text-amber-700",
  emerald: "bg-emerald-50 text-emerald-700",
};

export function StudentDashboard() {
  return (
    <div className="p-8 space-y-6">
      {/* Welcome */}
      <Card className="p-6 border-slate-200 bg-gradient-to-br from-blue-600 to-indigo-600 text-white relative overflow-hidden">
        <div className="absolute -right-12 -top-12 size-56 rounded-full bg-white/10 blur-2xl" />
        <div className="relative flex items-center gap-5 flex-wrap">
          <div className="size-16 rounded-2xl bg-white/15 backdrop-blur flex items-center justify-center text-2xl tracking-tight">
            SP
          </div>
          <div className="flex-1 min-w-[240px]">
            <div className="text-blue-100 text-sm">Welcome back,</div>
            <h2 className="tracking-tight">Sahan Perera</h2>
            <div className="text-sm text-blue-100 mt-0.5">3rd Year · Computer Science · CS-2024-018</div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {[
              { k: "GPA", v: "3.72" },
              { k: "Rank", v: "#14" },
              { k: "Streak", v: "12d" },
            ].map((s) => (
              <div key={s.k} className="px-4 py-3 rounded-lg bg-white/10 backdrop-blur border border-white/15 min-w-[80px] text-center">
                <div className="tracking-tight">{s.v}</div>
                <div className="text-xs text-blue-100 mt-0.5">{s.k}</div>
              </div>
            ))}
          </div>
        </div>
      </Card>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Performance trend */}
          <Card className="p-5 border-slate-200">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-slate-900">Performance trend</div>
                <div className="text-xs text-slate-500 mt-0.5">Average score across all subjects</div>
              </div>
              <Badge className="bg-emerald-50 text-emerald-700 border-0 hover:bg-emerald-50">
                <TrendingUp className="size-3 mr-1" /> +23% YoY
              </Badge>
            </div>
            <div className="h-56 mt-4 -mx-2">
              <ResponsiveContainer>
                <AreaChart data={trend}>
                  <defs>
                    <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#2563eb" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#2563eb" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                  <XAxis dataKey="m" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} domain={[40, 100]} />
                  <Tooltip contentStyle={{ borderRadius: 8, fontSize: 12, border: "1px solid #e2e8f0" }} />
                  <Area type="monotone" dataKey="v" stroke="#2563eb" strokeWidth={2.5} fill="url(#grad)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {/* Recent grades */}
          <Card className="border-slate-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
              <div className="text-slate-900">Recent grades</div>
              <Button variant="ghost" size="sm" className="text-blue-600">View all <ChevronRight className="size-4 ml-1" /></Button>
            </div>
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
                <tr>
                  <th className="text-left px-5 py-3">Course</th>
                  <th className="text-left px-5 py-3">Assessment</th>
                  <th className="text-left px-5 py-3">Score</th>
                  <th className="text-left px-5 py-3">Grade</th>
                </tr>
              </thead>
              <tbody>
                {grades.map((g) => (
                  <tr key={g.course} className="border-t border-slate-100 hover:bg-slate-50">
                    <td className="px-5 py-3 text-slate-900">{g.course}</td>
                    <td className="px-5 py-3 text-slate-600">{g.item}</td>
                    <td className="px-5 py-3 text-slate-700">{g.score}/100</td>
                    <td className="px-5 py-3"><Badge className={`${g.color} border-0 hover:${g.color}`}>{g.band}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </div>

        <div className="space-y-6">
          {/* Upcoming exams */}
          <Card className="p-5 border-slate-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-slate-900">
                <Calendar className="size-4 text-blue-600" /> Upcoming exams
              </div>
              <Badge variant="secondary" className="bg-slate-100 border-0">3</Badge>
            </div>
            <div className="mt-4 space-y-3">
              {upcoming.map((u) => (
                <div key={u.title} className="flex items-center gap-3 p-3 rounded-lg border border-slate-100 hover:border-blue-200 hover:bg-blue-50/30 cursor-pointer">
                  <div className={`size-12 rounded-lg ${toneStyle[u.tone]} flex flex-col items-center justify-center leading-tight`}>
                    <span className="text-sm">{u.d}</span>
                    <span className="text-[10px] uppercase">{u.m}</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-slate-900 truncate">{u.title}</div>
                    <div className="text-xs text-slate-500">{u.time}</div>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Announcements */}
          <Card className="p-5 border-slate-200">
            <div className="flex items-center gap-2 text-slate-900">
              <Bell className="size-4 text-amber-500" /> Announcements
            </div>
            <div className="mt-3 space-y-3">
              {[
                { t: "Final exam timetable released", d: "2 hr ago", icon: Calendar, c: "text-blue-600 bg-blue-50" },
                { t: "Resources uploaded for OS revision", d: "Yesterday", icon: BookOpen, c: "text-emerald-600 bg-emerald-50" },
                { t: "Dean's list — congratulations!", d: "3 days ago", icon: Award, c: "text-amber-600 bg-amber-50" },
              ].map((a) => {
                const Icon = a.icon;
                return (
                  <div key={a.t} className="flex gap-3">
                    <div className={`size-8 rounded-lg ${a.c} flex items-center justify-center shrink-0`}>
                      <Icon className="size-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-slate-900">{a.t}</div>
                      <div className="text-xs text-slate-500">{a.d}</div>
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
