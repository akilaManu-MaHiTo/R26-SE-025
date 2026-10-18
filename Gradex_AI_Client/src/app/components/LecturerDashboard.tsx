import React, { useEffect, useState } from "react";
import { Workflow, FileText, BarChart3, Video, ArrowRight, TrendingUp, Clock, CheckCircle2 } from "lucide-react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { useNavigate } from "react-router";
import { fetchExams, type ExamListItem } from "../api/lecturerApi";

export function LecturerDashboard() {
  const navigate = useNavigate();
  const [exams, setExams] = useState<ExamListItem[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let ignore = false;
    fetchExams().then((rows) => {
      if (!ignore) setExams(rows);
    }).catch(() => {
      if (!ignore) setError(true);
    });
    return () => { ignore = true; };
  }, []);

  const cards = [
    {
      path: "/diagram-evaluation/diagram-grading",
      title: "Grade diagram exams",
      desc: "Auto-extract shapes, labels and structure to grade ER diagrams, flowcharts and UML.",
      icon: Workflow,
    },
    {
      path: "/grading/handwritten-grading",
      title: "Grade handwritten exams",
      desc: "OCR + rubric matching for scanned answer sheets with AI confidence scoring.",
      icon: FileText,
    },
    {
      path: "/question-exam/analytics",
      title: "Student analytics",
      desc: "Review observed performance by exam, student, topic and Bloom level.",
      icon: BarChart3,
    },
    {
      path: "/viva-evaluation/vivas",
      title: "Viva assessment",
      desc: "Create a viva per subject, then upload recordings — get transcripts, key moments and rubric scoring.",
      icon: Video,
    },
  ];

  const stats = [
    { label: "Exams listed", value: error ? "Unavailable" : exams === null ? "Loading…" : exams.length, icon: FileText },
    { label: "Analytics available", value: error ? "Unavailable" : exams === null ? "Loading…" : exams.filter(exam => exam.analyzed).length, icon: CheckCircle2 },
    { label: "Avg. grading time", value: "No data available", icon: Clock },
    { label: "Class average", value: "Select an exam", icon: TrendingUp },
  ];

  return (
    <div className="p-8 space-y-8">
      {/* Greeting */}
      <div className="rounded-2xl border border-border bg-card p-8 relative overflow-hidden">
        <div className="absolute -right-16 -top-24 size-64 rounded-full bg-primary/[0.04] blur-2xl" />
        <div className="relative flex items-start justify-between gap-6 flex-wrap">
          <div>
            <Badge variant="outline" className="border-border text-muted-foreground">{new Date().toLocaleDateString(undefined, { weekday: "long", year: "numeric", month: "long", day: "numeric" })}</Badge>
            <h2 className="mt-4 text-2xl tracking-tight">Welcome back</h2>
            <p className="text-muted-foreground mt-2 max-w-xl">
              Choose an assessment tool or review student performance for an exam.
            </p>
          </div>
          <Button onClick={() => navigate("/grading/handwritten-grading")}>
            Open grading <ArrowRight className="size-4 ml-1" />
          </Button>
        </div>
      </div>

      {error && <p role="alert" className="text-sm text-destructive">Could not load exam summaries. Open Student analytics to retry.</p>}
      {exams?.length === 0 && <p className="text-sm text-muted-foreground">No exams available.</p>}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((s) => {
          const Icon = s.icon;
          return (
            <Card key={s.label} className="p-5">
              <div className="flex items-start justify-between">
                <div className="size-10 rounded-lg bg-muted flex items-center justify-center text-muted-foreground">
                  <Icon className="size-5" />
                </div>
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
            <div className="font-medium">Grading throughput</div>
            <p className="mt-3 text-sm text-muted-foreground">No data available. Grading throughput is not currently measured.</p>
          </Card>

          <Card className="p-5">
            <div className="font-medium mb-3">Recent activity</div>
            <p className="text-sm text-muted-foreground">No data available. An activity feed is not currently available.</p>
          </Card>
        </div>
      </div>
    </div>
  );
}
