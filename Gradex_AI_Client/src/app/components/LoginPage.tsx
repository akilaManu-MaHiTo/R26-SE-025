import { useState } from "react";
import { GraduationCap, BookUser, ArrowRight, Sparkles } from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { cn } from "./ui/utils";

export function LoginPage({ onLogin }: { onLogin: (role: "lecturer" | "student") => void }) {
  const [role, setRole] = useState<"lecturer" | "student">("lecturer");

  return (
    <div className="min-h-screen flex bg-background">
      {/* Editorial panel */}
      <div className="hidden lg:flex flex-1 relative overflow-hidden p-14 flex-col justify-between border-r border-border">
        <div className="absolute inset-0 -z-10 bg-gradient-to-br from-accent/70 via-background to-transparent" />
        <div className="absolute -top-40 -right-40 size-[480px] rounded-full bg-primary/5 blur-3xl" />

        <div className="relative flex items-center gap-3">
          <div className="size-10 rounded-lg bg-primary text-primary-foreground flex items-center justify-center">
            <Sparkles className="size-5" />
          </div>
          <div className="tracking-tight text-lg font-medium">GradeX AI</div>
        </div>

        <div className="relative space-y-8 max-w-lg">
          <div className="inline-flex items-center gap-2 text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
            <span className="size-1.5 rounded-full bg-primary" /> AI-powered assessment
          </div>
          <h1 className="text-[2.75rem] leading-[1.1] tracking-tight">
            Smarter grading.
            <br />
            Deeper insight.
            <br />
            Better outcomes.
          </h1>
          <p className="text-muted-foreground leading-relaxed max-w-md">
            GradeX AI helps lecturers grade diagrams, handwritten exams, and viva
            voce sessions in minutes — and gives students a clear view of their
            mastery across every topic.
          </p>
          <div className="grid grid-cols-3 gap-4 pt-2 max-w-lg">
            {[
              { k: "92%", v: "Time saved" },
              { k: "12k+", v: "Exams graded" },
              { k: "4.9", v: "Lecturer rating" },
            ].map((s) => (
              <div key={s.k} className="rounded-xl border border-border bg-card/60 p-5">
                <div className="text-2xl tracking-tight tabular-nums">{s.k}</div>
                <div className="text-xs text-muted-foreground mt-1.5">{s.v}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="relative text-sm text-muted-foreground">© 2026 GradeX AI · University Edition</div>
      </div>

      {/* Form panel */}
      <div className="flex-1 flex items-center justify-center p-6 lg:p-12">
        <div className="w-full max-w-md">
          <div className="lg:hidden flex items-center gap-2.5 mb-8">
            <div className="size-9 rounded-lg bg-primary text-primary-foreground flex items-center justify-center">
              <Sparkles className="size-5" />
            </div>
            <div className="tracking-tight text-lg font-medium text-foreground">GradeX AI</div>
          </div>

          <h2 className="tracking-tight text-2xl text-foreground">Welcome back</h2>
          <p className="text-muted-foreground mt-2">Sign in to continue to your workspace.</p>

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
                    "rounded-xl border p-4 text-left transition-all duration-200",
                    active
                      ? "border-primary bg-primary text-primary-foreground shadow-sm"
                      : "border-border bg-card hover:border-primary/50",
                  )}
                >
                  <Icon className={cn("size-5 mb-2", active ? "text-primary-foreground" : "text-muted-foreground")} />
                  <div className={cn("text-sm", active ? "text-primary-foreground" : "text-foreground")}>{r.label}</div>
                  <div className={cn("text-xs mt-0.5", active ? "text-primary-foreground/70" : "text-muted-foreground")}>
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
                <button type="button" className="text-xs text-muted-foreground hover:text-foreground hover:underline">
                  Forgot password?
                </button>
              </div>
              <Input id="password" type="password" defaultValue="••••••••••" />
            </div>
            <Button type="submit" className="w-full">
              Sign in <ArrowRight className="size-4 ml-1" />
            </Button>
            <div className="text-center text-sm text-muted-foreground">
              New to GradeX?{" "}
              <button type="button" className="text-foreground hover:underline">
                Create an account
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
