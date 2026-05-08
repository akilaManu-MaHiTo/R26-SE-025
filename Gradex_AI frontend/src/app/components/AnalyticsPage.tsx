import React, { useState } from "react";
import { AlertTriangle, Users, BookOpen, Brain, ChevronDown, ArrowUpDown } from "lucide-react";
import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./ui/tabs";
import { Progress } from "./ui/progress";
import {
  BarChart, Bar, XAxis, YAxis, ResponsiveContainer, CartesianGrid, Tooltip,
  ScatterChart, Scatter, ZAxis, ReferenceLine, Cell,
} from "recharts";

const distribution = [
  { band: "0-39", c: 8, fill: "#ef4444" },
  { band: "40-54", c: 22, fill: "#f59e0b" },
  { band: "55-69", c: 96, fill: "#3b82f6" },
  { band: "70-84", c: 142, fill: "#10b981" },
  { band: "85-100", c: 74, fill: "#059669" },
];

const students = [
  { id: "CS-2024-018", avg: 92, band: "high", weak: ["Q4"], cog: "Evaluate" },
  { id: "CS-2024-022", avg: 78, band: "high", weak: ["Q2", "Q7"], cog: "Analyze" },
  { id: "CS-2024-045", avg: 64, band: "mid", weak: ["Q3", "Q4", "Q7"], cog: "Apply" },
  { id: "CS-2024-061", avg: 58, band: "mid", weak: ["Q2", "Q5", "Q7"], cog: "Apply" },
  { id: "CS-2024-088", avg: 41, band: "low", weak: ["Q1", "Q3", "Q5", "Q7"], cog: "Understand" },
  { id: "CS-2024-104", avg: 36, band: "low", weak: ["Q2", "Q3", "Q5", "Q6", "Q7"], cog: "Remember" },
];

const bandStyle: Record<string, string> = {
  high: "bg-emerald-50 text-emerald-700 border-emerald-200",
  mid: "bg-amber-50 text-amber-700 border-amber-200",
  low: "bg-red-50 text-red-700 border-red-200",
};

const heatStudents = ["CS-018", "CS-022", "CS-045", "CS-061", "CS-088", "CS-104", "CS-117", "CS-128"];
const heatQs = ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8"];
const heatData: number[][] = [
  [9, 8, 7, 9, 9, 9, 8, 10],
  [8, 6, 7, 6, 8, 7, 4, 8],
  [7, 6, 5, 6, 5, 7, 4, 6],
  [6, 5, 4, 7, 4, 6, 3, 6],
  [4, 3, 3, 6, 3, 5, 2, 4],
  [3, 2, 3, 4, 2, 5, 1, 3],
  [7, 6, 7, 8, 6, 7, 5, 7],
  [8, 7, 7, 8, 7, 8, 6, 8],
];

const heatColor = (v: number) => {
  if (v >= 8) return "bg-emerald-500";
  if (v >= 6) return "bg-emerald-300";
  if (v >= 4) return "bg-amber-300";
  if (v >= 2) return "bg-orange-400";
  return "bg-red-500";
};

const cognitiveScatter = [
  { expected: 3, actual: 4 }, { expected: 4, actual: 4 }, { expected: 5, actual: 6 },
  { expected: 5, actual: 3 }, { expected: 6, actual: 4 }, { expected: 4, actual: 5 },
  { expected: 6, actual: 6 }, { expected: 3, actual: 2 }, { expected: 5, actual: 5 },
  { expected: 4, actual: 3 }, { expected: 6, actual: 5 }, { expected: 2, actual: 3 },
];

const topics = ["ER Modeling", "Normalization", "SQL", "Indexing", "Transactions", "Concurrency"];
const topicMastery: number[][] = [
  [85, 78, 92, 70, 64, 58],
  [72, 68, 81, 60, 55, 50],
  [60, 55, 75, 48, 42, 38],
  [82, 75, 88, 65, 60, 55],
  [40, 35, 60, 30, 28, 22],
  [90, 85, 95, 80, 78, 72],
];

const topicColor = (v: number) => {
  if (v >= 80) return "bg-emerald-500 text-white";
  if (v >= 65) return "bg-emerald-200 text-emerald-900";
  if (v >= 50) return "bg-amber-200 text-amber-900";
  if (v >= 35) return "bg-orange-300 text-orange-900";
  return "bg-red-400 text-white";
};

export function AnalyticsPage() {
  const [expanded, setExpanded] = useState<string | null>("CS-2024-104");

  const summary = [
    { title: "Class Performance", value: "342 students", icon: Users, color: "blue", note: "Avg 74.2 / 100" },
    { title: "At-Risk Students", value: "8", icon: AlertTriangle, color: "red", note: "Below 40% threshold" },
    { title: "Problem Questions", value: "3", icon: BookOpen, color: "amber", note: "Q3, Q5, Q7 underperforming" },
    { title: "Cognitive Gaps", value: "12", icon: Brain, color: "orange", note: "Below required Bloom level" },
  ];

  const colorMap: Record<string, string> = {
    blue: "from-blue-500 to-blue-600 text-blue-600 bg-blue-50",
    red: "from-red-500 to-red-600 text-red-600 bg-red-50",
    amber: "from-amber-500 to-amber-600 text-amber-600 bg-amber-50",
    orange: "from-orange-500 to-orange-600 text-orange-600 bg-orange-50",
  };

  return (
    <div className="p-8 space-y-6">
      <div>
        <h2 className="tracking-tight text-slate-900">Student Analytics</h2>
        <p className="text-sm text-slate-500 mt-1">Database Systems · Final Exam · Spring 2026</p>
      </div>

      {/* Section 1 — Executive summary */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {summary.map((s, i) => {
          const Icon = s.icon;
          const tone = colorMap[s.color];
          const [grad, text, bg] = tone.split(" ");
          return (
            <Card key={s.title} className="p-5 border-slate-200 relative overflow-hidden">
              {i === 0 && (
                <div className="absolute right-2 bottom-2 h-12 w-28 opacity-90">
                  <ResponsiveContainer>
                    <BarChart data={distribution}>
                      <Bar dataKey="c" radius={[3, 3, 0, 0]}>
                        {distribution.map((d, idx) => <Cell key={`dist-cell-${idx}`} fill={d.fill} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
              <div className={`size-10 rounded-lg ${bg} flex items-center justify-center ${text}`}>
                <Icon className="size-5" />
              </div>
              <div className="mt-4 text-sm text-slate-500">{s.title}</div>
              <div className="tracking-tight text-slate-900 mt-1">{s.value}</div>
              <div className="text-xs text-slate-500 mt-1">{s.note}</div>
            </Card>
          );
        })}
      </div>

      <Tabs defaultValue="students" className="space-y-4">
        <TabsList className="bg-slate-100">
          <TabsTrigger value="students">Student performance</TabsTrigger>
          <TabsTrigger value="questions">Question analysis</TabsTrigger>
          <TabsTrigger value="cognitive">Cognitive gaps</TabsTrigger>
          <TabsTrigger value="topics">Topic mastery</TabsTrigger>
        </TabsList>

        {/* Section 2 — Leaderboard */}
        <TabsContent value="students" className="m-0">
          <Card className="border-slate-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
              <div className="text-slate-900">Leaderboard</div>
              <div className="text-xs text-slate-500">Click a row to drill down</div>
            </div>
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
                <tr>
                  {["Student ID", "Avg score", "Band", "Weak questions", "Cognitive level", ""].map((h, i) => (
                    <th key={`th-${i}`} className="text-left px-5 py-3">
                      <button className="inline-flex items-center gap-1 hover:text-slate-900">
                        {h}{h && <ArrowUpDown className="size-3" />}
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {students.map((s) => {
                  const open = expanded === s.id;
                  return (
                    <React.Fragment key={s.id}>
                      <tr onClick={() => setExpanded(open ? null : s.id)}
                          className="border-t border-slate-100 hover:bg-slate-50 cursor-pointer">
                        <td className="px-5 py-3 text-slate-900">{s.id}</td>
                        <td className="px-5 py-3">
                          <div className="flex items-center gap-2">
                            <span className="text-slate-900">{s.avg}</span>
                            <Progress value={s.avg} className="w-24 h-1.5" />
                          </div>
                        </td>
                        <td className="px-5 py-3">
                          <Badge variant="outline" className={bandStyle[s.band]}>
                            {s.band === "high" ? "High" : s.band === "mid" ? "Medium" : "Low"}
                          </Badge>
                        </td>
                        <td className="px-5 py-3">
                          <div className="flex flex-wrap gap-1">
                            {s.weak.map((w) => (
                              <span key={w} className="px-1.5 py-0.5 rounded bg-red-50 text-red-700 text-xs">{w}</span>
                            ))}
                          </div>
                        </td>
                        <td className="px-5 py-3 text-slate-700">{s.cog}</td>
                        <td className="px-5 py-3 text-right">
                          <ChevronDown className={"size-4 text-slate-400 transition-transform " + (open ? "rotate-180" : "")} />
                        </td>
                      </tr>
                      {open && (
                        <tr className="bg-slate-50/60 border-t border-slate-100">
                          <td colSpan={6} className="p-5">
                            <div className="grid md:grid-cols-3 gap-4">
                              <Card className="p-4 border-slate-200 bg-white">
                                <div className="text-xs text-slate-500 uppercase tracking-wide">Weak topics</div>
                                <div className="mt-2 space-y-2">
                                  {["Normalization", "Indexing", "Transactions"].map((t, i) => (
                                    <div key={t}>
                                      <div className="flex items-center justify-between text-sm">
                                        <span className="text-slate-700">{t}</span>
                                        <span className="text-slate-500">{[42, 38, 28][i]}%</span>
                                      </div>
                                      <Progress value={[42, 38, 28][i]} className="h-1.5 mt-1" />
                                    </div>
                                  ))}
                                </div>
                              </Card>
                              <Card className="p-4 border-slate-200 bg-white">
                                <div className="text-xs text-slate-500 uppercase tracking-wide">Score distribution</div>
                                <div className="h-28 mt-2">
                                  <ResponsiveContainer>
                                    <BarChart data={[
                                      { k: "Performance", v: 36 },
                                      { k: "Concept", v: 42 },
                                      { k: "Cognitive", v: 28 },
                                    ]}>
                                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                                      <XAxis dataKey="k" tick={{ fontSize: 10, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                                      <YAxis hide />
                                      <Bar dataKey="v" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                                    </BarChart>
                                  </ResponsiveContainer>
                                </div>
                              </Card>
                              <Card className="p-4 border-slate-200 bg-white">
                                <div className="text-xs text-slate-500 uppercase tracking-wide">Per-question grid</div>
                                <div className="grid grid-cols-4 gap-1.5 mt-2">
                                  {[3, 2, 3, 4, 2, 5, 1, 3].map((v, i) => (
                                    <div key={i} className={`aspect-square rounded text-[10px] flex items-center justify-center ${heatColor(v)} text-white`}>
                                      Q{i+1}
                                    </div>
                                  ))}
                                </div>
                              </Card>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </Card>
        </TabsContent>

        {/* Section 3 — Heatmap & problem questions */}
        <TabsContent value="questions" className="m-0 space-y-4">
          <Card className="p-5 border-slate-200">
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="text-slate-900">Performance heatmap</div>
                <div className="text-xs text-slate-500 mt-0.5">Students × Questions · score out of 10</div>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <span>Low</span>
                <div className="flex">
                  {["bg-red-500", "bg-orange-400", "bg-amber-300", "bg-emerald-300", "bg-emerald-500"].map((c, i) => (
                    <div key={i} className={`w-6 h-3 ${c}`} />
                  ))}
                </div>
                <span>High</span>
              </div>
            </div>
            <div className="overflow-auto">
              <div className="inline-grid gap-1.5" style={{ gridTemplateColumns: `auto repeat(${heatQs.length}, minmax(40px, 1fr))` }}>
                <div />
                {heatQs.map((q) => <div key={q} className="text-xs text-slate-500 text-center">{q}</div>)}
                {heatStudents.map((s, r) => (
                  <React.Fragment key={s}>
                    <div className="text-xs text-slate-500 pr-2 flex items-center">{s}</div>
                    {heatData[r].map((v, c) => (
                      <div key={`${s}-col-${c}`} className={`aspect-square rounded ${heatColor(v)} text-white text-[10px] flex items-center justify-center`}>
                        {v}
                      </div>
                    ))}
                  </React.Fragment>
                ))}
              </div>
            </div>
          </Card>

          <Card className="border-slate-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 text-slate-900">Problem questions</div>
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
                <tr>
                  <th className="text-left px-5 py-3">Question</th>
                  <th className="text-left px-5 py-3">Below threshold</th>
                  <th className="text-left px-5 py-3">Avg score</th>
                  <th className="text-left px-5 py-3">Required vs actual Bloom</th>
                  <th className="text-right px-5 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {[
                  { q: "Q7 — Concurrency control protocols", below: "62%", avg: 3.8, req: "Analyze", act: "Apply" },
                  { q: "Q3 — Normalization to BCNF", below: "48%", avg: 4.6, req: "Apply", act: "Understand" },
                  { q: "Q5 — Index selection trade-offs", below: "44%", avg: 5.1, req: "Evaluate", act: "Apply" },
                ].map((p) => (
                  <tr key={p.q} className="border-t border-slate-100">
                    <td className="px-5 py-3 text-slate-900">{p.q}</td>
                    <td className="px-5 py-3"><Badge className="bg-red-50 text-red-700 border-0 hover:bg-red-50">{p.below}</Badge></td>
                    <td className="px-5 py-3 text-slate-700">{p.avg} / 10</td>
                    <td className="px-5 py-3 text-slate-700">
                      <span className="text-slate-500 line-through mr-2">{p.req}</span>
                      <span className="text-red-600">{p.act}</span>
                    </td>
                    <td className="px-5 py-3 text-right"><Button variant="outline" size="sm">View answer</Button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </TabsContent>

        {/* Section 4 — Cognitive gaps */}
        <TabsContent value="cognitive" className="m-0 space-y-4">
          <div className="grid lg:grid-cols-2 gap-4">
            <Card className="p-5 border-slate-200">
              <div className="text-slate-900">Bloom's Taxonomy ladder</div>
              <div className="text-xs text-slate-500 mt-0.5">Class average per cognitive level</div>
              <div className="mt-4 space-y-2">
                {[
                  { l: "Create", v: 32, c: "bg-violet-500" },
                  { l: "Evaluate", v: 48, c: "bg-indigo-500" },
                  { l: "Analyze", v: 61, c: "bg-blue-500" },
                  { l: "Apply", v: 74, c: "bg-emerald-500" },
                  { l: "Understand", v: 86, c: "bg-emerald-400" },
                  { l: "Remember", v: 92, c: "bg-emerald-300" },
                ].map((b) => (
                  <div key={b.l} className="flex items-center gap-3">
                    <div className="w-24 text-sm text-slate-600">{b.l}</div>
                    <div className="flex-1 h-7 rounded-md bg-slate-100 overflow-hidden">
                      <div className={`${b.c} h-full flex items-center justify-end pr-2 text-xs text-white`} style={{ width: `${b.v}%` }}>
                        {b.v}%
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>

            <Card className="p-5 border-slate-200">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-slate-900">Expected vs Actual</div>
                  <div className="text-xs text-slate-500 mt-0.5">Points below the diagonal indicate cognitive gaps</div>
                </div>
                <div className="flex gap-2 text-xs">
                  <Badge className="bg-emerald-50 text-emerald-700 border-0">Low</Badge>
                  <Badge className="bg-amber-50 text-amber-700 border-0">Medium</Badge>
                  <Badge className="bg-red-50 text-red-700 border-0">High</Badge>
                </div>
              </div>
              <div className="h-72 mt-4">
                <ResponsiveContainer>
                  <ScatterChart margin={{ top: 10, right: 10, bottom: 10, left: 0 }}>
                    <CartesianGrid stroke="#f1f5f9" />
                    <XAxis type="number" dataKey="expected" domain={[0, 7]} tickCount={7} tick={{ fontSize: 11, fill: "#94a3b8" }} label={{ value: "Expected level", position: "insideBottom", offset: -5, fill: "#64748b", fontSize: 12 }} />
                    <YAxis type="number" dataKey="actual" domain={[0, 7]} tickCount={7} tick={{ fontSize: 11, fill: "#94a3b8" }} label={{ value: "Actual", angle: -90, position: "insideLeft", fill: "#64748b", fontSize: 12 }} />
                    <ZAxis range={[80, 81]} />
                    <Tooltip cursor={{ strokeDasharray: "3 3" }} contentStyle={{ borderRadius: 8, fontSize: 12 }} />
                    <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 7, y: 7 }]} stroke="#94a3b8" strokeDasharray="4 4" />
                    <Scatter data={cognitiveScatter}>
                      {cognitiveScatter.map((p, i) => (
                        <Cell key={`scatter-cell-${i}`} fill={p.actual >= p.expected ? "#10b981" : p.expected - p.actual >= 2 ? "#ef4444" : "#f59e0b"} />
                      ))}
                    </Scatter>
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>
        </TabsContent>

        {/* Section 5 — Topic mastery */}
        <TabsContent value="topics" className="m-0">
          <Card className="p-5 border-slate-200">
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="text-slate-900">Topic mastery matrix</div>
                <div className="text-xs text-slate-500 mt-0.5">Highlighted columns indicate ≥40% failure rate</div>
              </div>
            </div>
            <div className="overflow-auto">
              <table className="text-sm border-separate border-spacing-1">
                <thead>
                  <tr>
                    <th className="text-left text-xs text-slate-500 px-2">Student</th>
                    {topics.map((t) => {
                      const fail = ["Transactions"].includes(t);
                      return (
                        <th key={t} className={`text-xs px-2 py-1 rounded ${fail ? "bg-red-50 text-red-700" : "text-slate-500"}`}>
                          {t}
                        </th>
                      );
                    })}
                    <th className="text-xs text-slate-500 px-2">Avg</th>
                  </tr>
                </thead>
                <tbody>
                  {heatStudents.slice(0, 6).map((s, r) => {
                    const avg = Math.round(topicMastery[r].reduce((a, b) => a + b, 0) / topics.length);
                    return (
                      <tr key={s}>
                        <td className="text-slate-700 px-2 py-1 whitespace-nowrap">{s}</td>
                        {topicMastery[r].map((v, c) => (
                          <td key={`mastery-${r}-${c}`} className={`text-center px-3 py-2 rounded ${topicColor(v)}`}>{v}</td>
                        ))}
                        <td className="text-slate-900 px-2">{avg}</td>
                      </tr>
                    );
                  })}
                  <tr>
                    <td className="text-slate-500 px-2 pt-3 text-xs uppercase tracking-wide">Topic avg</td>
                    {topics.map((t, c) => {
                      const avg = Math.round(topicMastery.slice(0, 6).reduce((a, b) => a + b[c], 0) / 6);
                      return <td key={`avg-${c}`} className="text-center text-slate-700 pt-3">{avg}</td>;
                    })}
                    <td />
                  </tr>
                </tbody>
              </table>
            </div>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}