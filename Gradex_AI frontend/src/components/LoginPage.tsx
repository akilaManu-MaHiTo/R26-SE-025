"use client";

import { useState } from "react";
import { Sparkles, GraduationCap, BookUser, ArrowRight } from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { cn } from "./ui/utils";

export function LoginPage({ onLogin }: { onLogin: (role: "lecturer" | "student") => void }) {
  const [role, setRole] = useState<"lecturer" | "student">("lecturer");

  return (
    <div className="min-h-screen flex bg-slate-50">
      <div className="hidden lg:flex flex-1 bg-gradient-to-br from-blue-600 via-blue-700 to-indigo-800 relative overflow-hidden p-12 flex-col justify-between text-white">
        <div className="absolute -top-24 -right-24 size-96 rounded-full bg-blue-400/20 blur-3xl" />
        <div className="absolute -bottom-32 -left-32 size-96 rounded-full bg-indigo-400/20 blur-3xl" />

        <div className="relative flex items-center gap-3">
          <div className="size-11 rounded-xl bg-white/10 backdrop-blur flex items-center justify-center">
            <Sparkles className="size-6" />
          </div>
          <div className="tracking-tight">GradeX AI</div>
        </div>

        <div className="relative space-y-6 max-w-lg">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/10 backdrop-blur border border-white/20 text-sm">
            <span className="size-1.5 rounded-full bg-emerald-400" /> AI-powered assessment
          </div>
          <h1 className="text-4xl tracking-tight leading-tight">
            Smarter grading. Deeper insight. Better outcomes.
          </h1>
          <p className="text-blue-100 leading-relaxed">
            GradeX AI helps lecturers grade diagrams, handwritten exams, and viva
            voce sessions in minutes — and gives students a clear view of their
            mastery across every topic.
          </p>
          <div className="grid grid-cols-3 gap-3 pt-4">
            {[
              { k: "92%", v: "Time saved" },
              { k: "12k+", v: "Exams graded" },
              { k: "4.9★", v: "Lecturer rating" },
            ].map((s) => (
              <div key={s.k} className="rounded-xl bg-white/10 backdrop-blur border border-white/15 p-4">
                <div className="tracking-tight">{s.k}</div>
                <div className="text-xs text-blue-100 mt-1">{s.v}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="relative text-sm text-blue-200">© 2026 GradeX AI · University Edition</div>
      </div>

      <div className="flex-1 flex items-center justify-center p-6 lg:p-12">
        <div className="w-full max-w-md">
          <div className="lg:hidden flex items-center gap-2.5 mb-8">
            <div className="size-9 rounded-xl bg-gradient-to-br from-blue-600 to-blue-500 flex items-center justify-center">
              <Sparkles className="size-5 text-white" />
            </div>
            <div className="tracking-tight text-slate-900">GradeX AI</div>
          </div>

          <h2 className="tracking-tight text-slate-900">Welcome back</h2>
          <p className="text-slate-500 mt-2">Sign in to continue to your workspace.</p>

          <div className="grid grid-cols-2 gap-3 mt-8">
            {[
              { id: "lecturer", label: "Lecturer", icon: BookUser },
              { id: "student", label: "Student", icon: GraduationCap },
            ].map((r) => {
              const Icon = r.icon;
              const active = role === r.id;
              return (
                <button
                  key={r.id}
                  onClick={() => setRole(r.id as any)}
                  className={cn(
                    "rounded-xl border p-4 text-left transition-all",
                    active
                      ? "border-blue-500 bg-blue-50 ring-2 ring-blue-100"
                      : "border-slate-200 bg-white hover:border-slate-300",
                  )}
                >
                  <Icon className={cn("size-5 mb-2", active ? "text-blue-600" : "text-slate-500")} />
                  <div className="text-sm text-slate-900">{r.label}</div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    {r.id === "lecturer" ? "Grade & analyze" : "Track progress"}
                  </div>
                </button>
              );
            })}
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              onLogin(role);
            }}
            className="space-y-4 mt-6"
          >
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" defaultValue={role === "lecturer" ? "r.mendis@uni.edu" : "sahan@uni.edu"} />
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label htmlFor="password">Password</Label>
                <button type="button" className="text-xs text-blue-600 hover:underline">
                  Forgot password?
                </button>
              </div>
              <Input id="password" type="password" defaultValue="••••••••••" />
            </div>
            <Button type="submit" className="w-full bg-blue-600 hover:bg-blue-700">
              Sign in <ArrowRight className="size-4 ml-1" />
            </Button>
            <div className="text-center text-sm text-slate-500">
              New to GradeX?{" "}
              <button type="button" className="text-blue-600 hover:underline">
                Create an account
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
