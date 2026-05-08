
"use client";

import { Upload, Play, CheckCircle2, Mic, FileDown, Sparkles, Pause } from "lucide-react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Progress } from "./ui/progress";
import { Input } from "./ui/input";
import { Checkbox } from "./ui/checkbox";

const criteria = [
  { name: "Communication Skills", score: 8, max: 10 },
  { name: "Technical Knowledge", score: 7, max: 10 },
  { name: "Problem-Solving", score: 9, max: 10 },
  { name: "Presentation Quality", score: 7, max: 10 },
];

const moments = [
  { t: "00:42", label: "Introduction & background", tone: "neutral" },
  { t: "02:15", label: "Strong explanation of B+ trees", tone: "good" },
  { t: "05:08", label: "Hesitation on isolation levels", tone: "warn" },
  { t: "08:27", label: "Excellent example with real-world case", tone: "good" },
  { t: "11:54", label: "Closing summary", tone: "neutral" },
];

const toneColor: Record<string, string> = {
  good: "bg-emerald-500",
  warn: "bg-amber-500",
  neutral: "bg-blue-500",
};

export function VivaPage() {
  const total = criteria.reduce((a, b) => a + b.score, 0);
  const max = criteria.reduce((a, b) => a + b.max, 0);

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className="tracking-tight text-slate-900">Viva Assessment</h2>
          <p className="text-sm text-slate-500 mt-1">Upload, transcribe and score viva voce sessions with AI assistance.</p>
        </div>
        <Button className="bg-blue-600 hover:bg-blue-700"><FileDown className="size-4 mr-2" />Export report</Button>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Upload */}
          <Card className="p-6 border-slate-200">
            <div className="flex items-center justify-between">
              <div className="text-slate-900">Recording</div>
              <Badge className="bg-emerald-50 text-emerald-700 border-0 hover:bg-emerald-50">
                <CheckCircle2 className="size-3 mr-1" /> Uploaded
              </Badge>
            </div>

            <div className="mt-4 rounded-xl border-2 border-dashed border-slate-200 bg-slate-50/40 p-6 hover:border-blue-300 hover:bg-blue-50/40 transition-colors cursor-pointer text-center">
              <div className="size-12 rounded-full bg-blue-100 mx-auto flex items-center justify-center text-blue-600">
                <Upload className="size-6" />
              </div>
              <div className="text-sm text-slate-900 mt-3">Drag & drop a viva recording</div>
              <div className="text-xs text-slate-500 mt-1">Supports MP4, AVI, MOV · up to 1 GB</div>
            </div>

            {/* Mock player */}
            <div className="mt-5 rounded-xl bg-slate-900 aspect-video relative overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-br from-slate-800 via-slate-900 to-black flex items-center justify-center">
                <div className="size-16 rounded-full bg-white/10 backdrop-blur flex items-center justify-center cursor-pointer hover:bg-white/20">
                  <Play className="size-7 text-white ml-0.5" fill="white" />
                </div>
              </div>
              <div className="absolute top-3 left-3 flex items-center gap-2">
                <span className="size-2 rounded-full bg-red-500 animate-pulse" />
                <span className="text-white/80 text-xs">viva_session_24.mp4</span>
              </div>
              <div className="absolute bottom-0 inset-x-0 p-4 bg-gradient-to-t from-black/80 to-transparent">
                <div className="flex items-center gap-3 text-white">
                  <Pause className="size-4" />
                  <span className="text-xs">04:32 / 12:48</span>
                  <div className="flex-1 h-1 rounded-full bg-white/20">
                    <div className="h-full w-1/3 rounded-full bg-blue-400" />
                  </div>
                  <Mic className="size-4" />
                </div>
              </div>
            </div>

            {/* Timeline of moments */}
            <div className="mt-5">
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm text-slate-900">Key moments</div>
                <div className="text-xs text-slate-500">AI-detected</div>
              </div>
              <div className="space-y-1.5">
                {moments.map((m) => (
                  <div key={m.t} className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-slate-50 cursor-pointer">
                    <span className={`size-2 rounded-full ${toneColor[m.tone]}`} />
                    <span className="text-xs font-mono text-slate-500 w-12">{m.t}</span>
                    <span className="text-sm text-slate-700 flex-1">{m.label}</span>
                    <Play className="size-3.5 text-slate-400" />
                  </div>
                ))}
              </div>
            </div>
          </Card>

          {/* Transcript */}
          <Card className="p-6 border-slate-200">
            <div className="flex items-center justify-between">
              <div className="text-slate-900">Transcript</div>
              <Badge variant="secondary" className="bg-blue-50 text-blue-700 border-0">
                <Sparkles className="size-3 mr-1" /> AI generated
              </Badge>
            </div>
            <div className="mt-4 space-y-4 max-h-72 overflow-y-auto pr-2">
              {[
                { who: "Examiner", t: "00:12", text: "Could you walk us through the architecture of your database project?" },
                { who: "Student", t: "00:24", text: "Sure. The system uses a normalized schema with five core entities. The user table stores authentication data, while the activities table…" },
                { who: "Examiner", t: "02:08", text: "How did you decide between B+ trees and hash indexing?" },
                { who: "Student", t: "02:15", text: "I chose B+ trees for the user_id column because we run a lot of range queries on creation date, and B+ trees keep keys sorted on disk pages…", highlight: true },
                { who: "Examiner", t: "05:00", text: "What about your isolation level — are you comfortable with the trade-offs?" },
                { who: "Student", t: "05:08", text: "I think... I used the default level. I'm not entirely sure what each level guarantees…", flag: true },
              ].map((m, i) => (
                <div key={i} className="flex gap-3">
                  <div className="text-xs font-mono text-slate-400 w-12 shrink-0 mt-0.5">{m.t}</div>
                  <div className="flex-1">
                    <div className="text-xs text-slate-500">{m.who}</div>
                    <div className={
                      "text-sm mt-0.5 " +
                      (m.highlight ? "text-emerald-800 bg-emerald-50 px-2 py-1 rounded" :
                       m.flag ? "text-amber-800 bg-amber-50 px-2 py-1 rounded" :
                       "text-slate-700")
                    }>
                      {m.text}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        <div className="space-y-6">
          {/* Guidelines */}
          <Card className="p-5 border-slate-200">
            <div className="text-slate-900">Recording checklist</div>
            <div className="mt-3 space-y-2.5">
              {[
                "Audio is clear & free of noise",
                "Both examiner and student visible",
                "Session ≥ 10 minutes",
                "Slides/notes shared on screen",
                "Consent acknowledged",
              ].map((g, i) => (
                <label key={g} className="flex items-center gap-2.5 text-sm text-slate-700">
                  <Checkbox defaultChecked={i < 4} /> {g}
                </label>
              ))}
            </div>
          </Card>

          {/* Criteria */}
          <Card className="p-5 border-slate-200">
            <div className="flex items-center justify-between">
              <div className="text-slate-900">Evaluation rubric</div>
              <Badge className="bg-blue-50 text-blue-700 border-0 hover:bg-blue-50">AI scored</Badge>
            </div>
            <div className="mt-4 space-y-4">
              {criteria.map((c) => (
                <div key={c.name}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-700">{c.name}</span>
                    <span className="text-slate-900">{c.score}/{c.max}</span>
                  </div>
                  <Progress value={(c.score / c.max) * 100} className="h-1.5 mt-1.5" />
                </div>
              ))}
            </div>

            <div className="mt-5 pt-4 border-t border-slate-100">
              <div className="flex items-end justify-between">
                <div>
                  <div className="text-xs text-slate-500 uppercase tracking-wide">Total</div>
                  <div className="tracking-tight text-slate-900 mt-0.5">
                    <span className="text-3xl">{total}</span><span className="text-slate-400">/{max}</span>
                  </div>
                </div>
                <Badge className="bg-emerald-50 text-emerald-700 border-0 hover:bg-emerald-50">Distinction</Badge>
              </div>
            </div>

            <div className="mt-4 p-3 rounded-lg bg-blue-50 border border-blue-100 text-xs text-blue-900">
              <span className="text-blue-700">AI recommendation:</span> Strong technical clarity. Consider deeper questions on isolation levels in next viva.
            </div>

            <div className="mt-4">
              <label className="text-sm text-slate-700">Final grade (override)</label>
              <Input className="mt-1.5" defaultValue="A" />
            </div>
            <Button className="w-full mt-4 bg-blue-600 hover:bg-blue-700">Save & publish</Button>
          </Card>
        </div>
      </div>
    </div>
  );
}
